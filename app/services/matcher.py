import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from ytmusicapi import YTMusic
from rapidfuzz import fuzz

from app.schemas.playlist import TrackMetadata

logger = logging.getLogger(__name__)


class YouTubeMusicMatcher:
    """
    Candidate scoring and matching algorithm inspired by CSVMusic:
    - Normalizes titles (removes remaster, feat tags, audio markers)
    - Evaluates artist & title similarity
    - Applies strict duration-matching penalties (to eliminate video skits/intros)
    - Penalizes unwanted live/acoustic/karaoke/remix versions
    """

    def __init__(self):
        self.ytmusic = YTMusic()

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        # strip noisy tags like feat, remaster, official video
        text = re.sub(r"[\(\[](?:feat|ft|with)\.?\s+[^)\]]+[\)\]]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[\(\[](?:(?:\d{4}\s+)?Remaster(?:ed)?|Deluxe|Bonus\s+Track)[\)\]]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[\(\[](?:Official\s+(?:Audio|Video|Music\s+Video)|Lyrics?|Audio)[\)\]]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip().lower()

    def calculate_score(
        self,
        source_track: TrackMetadata,
        candidate_title: str,
        candidate_artist: str,
        candidate_duration_sec: Optional[int],
        is_official_song: bool = False,
    ) -> float:
        src_clean_title = self.clean_text(source_track.title)
        cand_clean_title = self.clean_text(candidate_title)

        src_clean_artist = self.clean_text(source_track.artist)
        cand_clean_artist = self.clean_text(candidate_artist)

        # fuzzy title & artist match
        title_sim = fuzz.token_set_ratio(src_clean_title, cand_clean_title)
        title_score = (title_sim / 100.0) * 45.0

        artist_sim = fuzz.token_set_ratio(src_clean_artist, cand_clean_artist)
        artist_score = (artist_sim / 100.0) * 35.0

        score = title_score + artist_score

        if is_official_song:
            score += 10.0

        # penalize big duration differences to avoid video skits
        if source_track.duration_seconds and candidate_duration_sec:
            duration_diff = abs(source_track.duration_seconds - candidate_duration_sec)
            if duration_diff <= 3:
                score += 10.0
            elif duration_diff <= 8:
                score += 5.0
            elif duration_diff > 25:
                score -= 35.0
            elif duration_diff > 12:
                score -= 15.0

        # penalize live, acoustic, or karaoke versions if not requested
        unwanted_keywords = ["live", "acoustic", "cover", "karaoke", "tribute", "instrumental", "remix"]
        src_lower = source_track.title.lower()
        cand_lower = candidate_title.lower()

        for kw in unwanted_keywords:
            if kw in cand_lower and kw not in src_lower:
                score -= 25.0

        return max(0.0, min(100.0, score))

    def find_best_match(self, track: TrackMetadata) -> Tuple[str, Dict[str, Any]]:
        search_query = f"{track.artist} - {track.title}"
        candidates: List[Dict[str, Any]] = []

        try:
            # search official yt music tracks first
            song_results = self.ytmusic.search(search_query, filter="songs", limit=5)
            for res in song_results:
                artists = [a.get("name", "") for a in res.get("artists", [])]
                artist_name = ", ".join(artists) if artists else ""
                
                dur_str = res.get("duration")
                dur_sec = None
                if dur_str and ":" in dur_str:
                    parts = dur_str.split(":")
                    if len(parts) == 2:
                        dur_sec = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                score = self.calculate_score(
                    source_track=track,
                    candidate_title=res.get("title", ""),
                    candidate_artist=artist_name,
                    candidate_duration_sec=dur_sec,
                    is_official_song=True,
                )
                candidates.append({
                    "video_id": res.get("videoId"),
                    "title": res.get("title"),
                    "artist": artist_name,
                    "duration_sec": dur_sec,
                    "score": score,
                    "type": "song",
                    "thumbnails": res.get("thumbnails", []),
                })
        except Exception as e:
            logger.warning(f"YTMusic song search failed for '{search_query}': {e}")

        # fallback to standard video search
        try:
            video_results = self.ytmusic.search(search_query, filter="videos", limit=5)
            for res in video_results:
                artists = [a.get("name", "") for a in res.get("artists", [])]
                artist_name = ", ".join(artists) if artists else ""
                
                dur_str = res.get("duration")
                dur_sec = None
                if dur_str and ":" in dur_str:
                    parts = dur_str.split(":")
                    if len(parts) == 2:
                        dur_sec = int(parts[0]) * 60 + int(parts[1])

                score = self.calculate_score(
                    source_track=track,
                    candidate_title=res.get("title", ""),
                    candidate_artist=artist_name,
                    candidate_duration_sec=dur_sec,
                    is_official_song=False,
                )
                candidates.append({
                    "video_id": res.get("videoId"),
                    "title": res.get("title"),
                    "artist": artist_name,
                    "duration_sec": dur_sec,
                    "score": score,
                    "type": "video",
                    "thumbnails": res.get("thumbnails", []),
                })
        except Exception as e:
            logger.warning(f"YTMusic video search failed: {e}")

        if not candidates:
            # fallback query
            return f"ytsearch1:{track.artist} - {track.title} audio", {
                "score": 50.0,
                "title": f"{track.artist} - {track.title}",
                "video_id": None
            }

        # pick highest score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        video_id = best.get("video_id")
        target_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else f"ytsearch1:{track.artist} - {track.title}"

        logger.info(
            f"Matched '{track.artist} - {track.title}' -> '{best.get('artist')} - {best.get('title')}' "
            f"(Score: {best.get('score'):.1f}, Type: {best.get('type')})"
        )
        return target_url, best


music_matcher = YouTubeMusicMatcher()
