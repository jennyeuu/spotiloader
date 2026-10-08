import re
import logging
from typing import Optional, List, Tuple
import yt_dlp

from app.schemas.playlist import PlaylistMetadata, TrackMetadata

logger = logging.getLogger(__name__)


class YouTubeScraperService:
    """
    Extracts YouTube playlists, albums, and single video/music metadata directly using yt-dlp
    without requiring API keys.
    """

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        if not url:
            return False
        clean_url = url.strip()
        patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?.*list=([a-zA-Z0-9_-]+)",
            r"(?:https?://)?(?:music\.)?youtube\.com/playlist\?.*list=([a-zA-Z0-9_-]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*list=([a-zA-Z0-9_-]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"(?:https?://)?(?:music\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)",
        ]
        return any(re.search(p, clean_url) for p in patterns)

    @staticmethod
    def clean_title_and_artist(raw_title: str, uploader: str = "") -> Tuple[str, str]:
        if not raw_title:
            return "YouTube Artist", "Unknown Track"

        clean = raw_title.strip()
        # strip noisy tags like [Official Music Video], (Official Audio), (4K Remaster), etc.
        clean_no_noise = re.sub(
            r"\s*[\(\[](?:Official\s+(?:Music\s+)?Video|Official\s+Audio|Lyrics?|Audio|4K\s+Remaster|Remastered|HD|Visualizer|Lyric\s+Video|HQ)[\)\]]\s*",
            "",
            clean,
            flags=re.IGNORECASE,
        ).strip()

        if " - " in clean_no_noise:
            parts = clean_no_noise.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        elif ":" in clean_no_noise and not clean_no_noise.startswith("http"):
            parts = clean_no_noise.split(":", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            clean_uploader = re.sub(r"\s*-\s*Topic$", "", uploader, flags=re.IGNORECASE).strip()
            artist = clean_uploader or "YouTube Artist"
            title = clean_no_noise or raw_title

        return artist, title

    def extract_from_url(self, url: str) -> PlaylistMetadata:
        clean_url = url.strip()

        ydl_opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "geo_bypass": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web", "ios", "mweb"],
                }
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp failed to extract info from {clean_url}: {e}")
            raise ValueError(f"Failed to load YouTube URL: {e}")

        if not info:
            raise ValueError("No metadata returned from YouTube for the provided link.")

        # check if it's a playlist or multiple entries
        is_playlist = info.get("_type") == "playlist" or "entries" in info

        if is_playlist:
            raw_entries = info.get("entries") or []
            entries = [e for e in raw_entries if e]
            if not entries:
                raise ValueError("YouTube playlist is empty or private.")

            playlist_id = info.get("id") or "yt_playlist"
            playlist_title = info.get("title") or f"YouTube Playlist {playlist_id}"
            owner = info.get("uploader") or info.get("channel") or info.get("uploader_id") or "YouTube"

            tracks: List[TrackMetadata] = []
            for i, entry in enumerate(entries, start=1):
                raw_title = entry.get("title") or f"Track {i}"
                uploader = entry.get("uploader") or entry.get("channel") or owner or ""
                explicit_artist = entry.get("artist")
                explicit_track = entry.get("track")

                if explicit_artist and explicit_track:
                    artist = explicit_artist
                    title = explicit_track
                else:
                    artist, title = self.clean_title_and_artist(raw_title, uploader)

                # thumbnail extraction
                thumb_url = None
                thumbs = entry.get("thumbnails")
                if thumbs and isinstance(thumbs, list):
                    thumb_url = thumbs[-1].get("url")
                elif entry.get("thumbnail"):
                    thumb_url = entry.get("thumbnail")

                video_id = entry.get("id")
                dur = entry.get("duration")
                dur_sec = int(dur) if dur and isinstance(dur, (int, float)) else None

                tracks.append(
                    TrackMetadata(
                        id=video_id or f"yt_{i}",
                        title=title,
                        artist=artist,
                        album=playlist_title,
                        album_artist=owner,
                        track_number=i,
                        total_tracks=len(entries),
                        disc_number=1,
                        cover_art_url=thumb_url,
                        duration_seconds=dur_sec,
                    )
                )

            return PlaylistMetadata(
                playlist_id=playlist_id,
                playlist_title=playlist_title,
                owner=owner,
                source="youtube",
                total_tracks=len(tracks),
                tracks=tracks,
                skip_existing=True,
                bitrate="320k",
            )
        else:
            # single youtube video
            video_id = info.get("id") or "yt_single"
            raw_title = info.get("title") or "YouTube Video"
            uploader = info.get("uploader") or info.get("channel") or "YouTube"
            explicit_artist = info.get("artist")
            explicit_track = info.get("track")

            if explicit_artist and explicit_track:
                artist = explicit_artist
                title = explicit_track
            else:
                artist, title = self.clean_title_and_artist(raw_title, uploader)

            thumb_url = None
            thumbs = info.get("thumbnails")
            if thumbs and isinstance(thumbs, list):
                thumb_url = thumbs[-1].get("url")
            elif info.get("thumbnail"):
                thumb_url = info.get("thumbnail")

            dur = info.get("duration")
            dur_sec = int(dur) if dur and isinstance(dur, (int, float)) else None

            single_track = TrackMetadata(
                id=video_id,
                title=title,
                artist=artist,
                album=info.get("album") or f"{title} - Single",
                album_artist=artist,
                release_date=info.get("upload_date"),
                track_number=1,
                total_tracks=1,
                disc_number=1,
                cover_art_url=thumb_url,
                duration_seconds=dur_sec,
            )

            return PlaylistMetadata(
                playlist_id=video_id,
                playlist_title=f"{artist} - {title}",
                owner=uploader,
                source="youtube",
                total_tracks=1,
                tracks=[single_track],
                skip_existing=True,
                bitrate="320k",
            )


youtube_scraper = YouTubeScraperService()
