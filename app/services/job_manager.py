import re
import uuid
import shutil
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from rapidfuzz import fuzz
from mutagen.mp3 import MP3

from app.config import settings
from app.schemas.playlist import PlaylistMetadata, JobStatusResponse, TrackMetadata
from app.services.matcher import music_matcher
from app.services.youtube_downloader import youtube_downloader
from app.services.audio_processor import audio_processor

logger = logging.getLogger(__name__)


class JobManager:
    """
    Thread-safe in-memory background job manager for FastAPI.
    Supports smart caching & audio compression bitrate selection.
    """

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _sanitize_filename(self, name: str) -> str:
        if not name:
            return ""
        # Remove characters that are illegal on Windows/Linux filesystems
        cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
        # Collapse multiple whitespace characters
        cleaned = re.sub(r'\s+', " ", cleaned).strip()
        # Remove leading/trailing dots
        cleaned = cleaned.strip(".")
        return cleaned

    def find_existing_file(self, track: TrackMetadata, playlist_dir: Path) -> Optional[Tuple[Path, str]]:
        """
        Intelligently checks if a valid MP3 file for this track already exists:
        1. In the current playlist directory.
        2. Across ANY previously downloaded playlist directory (using fuzzy title/artist matching and ID3 tags).
        Returns (file_path, origin_description) if found, otherwise None.
        """
        safe_artist = self._sanitize_filename(track.artist)
        safe_title = self._sanitize_filename(track.title)
        expected_name = f"{safe_artist} - {safe_title}.mp3"

        # 1. Check current playlist directory
        local_file = playlist_dir / expected_name
        if local_file.exists() and local_file.stat().st_size > 50000:
            return local_file, "Existing track in playlist"

        # 2. Check all subdirectories in DOWNLOAD_DIR
        src_clean_title = music_matcher.clean_text(track.title)
        src_clean_artist = music_matcher.clean_text(track.artist)

        try:
            for candidate in settings.DOWNLOAD_DIR.rglob("*.mp3"):
                if not candidate.is_file() or candidate.stat().st_size <= 50000:
                    continue
                # Skip zips folder or files in current playlist_dir
                if "zips" in candidate.parts or candidate.parent.resolve() == playlist_dir.resolve():
                    continue

                origin_folder = candidate.parent.name
                cand_stem = candidate.stem

                # A. Match via filename (e.g. "Artist - Title.mp3")
                if " - " in cand_stem:
                    c_art, c_tit = cand_stem.split(" - ", 1)
                    c_clean_art = music_matcher.clean_text(c_art)
                    c_clean_tit = music_matcher.clean_text(c_tit)

                    title_sim = fuzz.token_set_ratio(src_clean_title, c_clean_tit)
                    artist_sim = fuzz.token_set_ratio(src_clean_artist, c_clean_art)

                    if title_sim >= 88 and artist_sim >= 75:
                        dest_file = playlist_dir / expected_name
                        if not dest_file.exists():
                            shutil.copy2(candidate, dest_file)
                        logger.info(
                            f"Duplicate detected across playlists: '{track.artist} - {track.title}' "
                            f"reused from '{origin_folder}' (matched file: '{candidate.name}')"
                        )
                        return dest_file, f"Reused from playlist '{origin_folder}'"

                # B. Match via ID3 metadata tags
                try:
                    audio = MP3(candidate)
                    if audio.tags:
                        tit_tag = str(audio.tags.get("TIT2", "")).strip()
                        art_tag = str(audio.tags.get("TPE1", "")).strip()
                        isrc_tag = str(audio.tags.get("TSRC", "")).strip()

                        if track.isrc and isrc_tag and track.isrc.strip().lower() == isrc_tag.lower():
                            dest_file = playlist_dir / expected_name
                            if not dest_file.exists():
                                shutil.copy2(candidate, dest_file)
                            logger.info(f"Duplicate detected via ISRC match: '{track.artist} - {track.title}' reused from '{origin_folder}'")
                            return dest_file, f"Reused from playlist '{origin_folder}' (ISRC Match)"

                        if tit_tag and art_tag:
                            c_clean_tit = music_matcher.clean_text(tit_tag)
                            c_clean_art = music_matcher.clean_text(art_tag)
                            title_sim = fuzz.token_set_ratio(src_clean_title, c_clean_tit)
                            artist_sim = fuzz.token_set_ratio(src_clean_artist, c_clean_art)

                            if title_sim >= 88 and artist_sim >= 75:
                                dest_file = playlist_dir / expected_name
                                if not dest_file.exists():
                                    shutil.copy2(candidate, dest_file)
                                logger.info(
                                    f"Duplicate detected via ID3 tags: '{track.artist} - {track.title}' "
                                    f"reused from '{origin_folder}'"
                                )
                                return dest_file, f"Reused from playlist '{origin_folder}'"
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"Error scanning existing files for cross-playlist deduplication: {e}")

        return None

    def create_job(self, playlist: PlaylistMetadata) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "PENDING",
                "playlist_id": playlist.playlist_id,
                "playlist_title": playlist.playlist_title,
                "source": playlist.source,
                "skip_existing": playlist.skip_existing,
                "bitrate": playlist.bitrate or settings.AUDIO_BITRATE,
                "total_tracks": playlist.total_tracks,
                "completed_tracks": 0,
                "failed_tracks": 0,
                "progress_percentage": 0.0,
                "current_track": "Queued for processing...",
                "tracks_detail": [],
                "playlist_dir": None,
                "created_at": datetime.utcnow().isoformat(),
                "error": None,
            }
        return job_id

    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return JobStatusResponse(
                job_id=job["job_id"],
                status=job["status"],
                total_tracks=job["total_tracks"],
                completed_tracks=job["completed_tracks"],
                failed_tracks=job["failed_tracks"],
                progress_percentage=job["progress_percentage"],
                bitrate=job.get("bitrate", "320k"),
                current_track=job["current_track"],
                tracks_detail=job["tracks_detail"],
                error=job["error"],
            )

    def _update_job(self, job_id: str, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def process_playlist(self, job_id: str, playlist: PlaylistMetadata):
        """
        Background worker processing all tracks in playlist.
        Reuses cached audio when skip_existing is enabled and applies selected bitrate.
        """
        selected_bitrate = playlist.bitrate or settings.AUDIO_BITRATE

        self._update_job(
            job_id,
            status="PROGRESS",
            current_track=f"Starting processing (Bitrate: {selected_bitrate})...",
        )

        total_tracks = playlist.total_tracks
        playlist_safe_name = self._sanitize_filename(playlist.playlist_title)
        if not playlist_safe_name:
            playlist_safe_name = f"Playlist_{playlist.playlist_id}"
        
        # Dedicated folder per playlist
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        completed_tracks = 0
        failed_tracks = 0
        tracks_status = []

        for index, track in enumerate(playlist.tracks, start=1):
            track_display = f"{track.artist} - {track.title}"
            current_status = {
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "status": "in_progress",
                "matched_title": None,
                "match_score": None,
                "file_path": None,
                "cached": False,
                "error": None,
            }

            self._update_job(
                job_id,
                status="PROGRESS",
                completed_tracks=completed_tracks,
                failed_tracks=failed_tracks,
                progress_percentage=round(((index - 1) / total_tracks) * 100, 2),
                current_track=f"({index}/{total_tracks}) Processing: {track_display}",
                tracks_detail=tracks_status,
            )

            try:
                # Check for existing downloaded file if skip_existing is enabled
                existing_match = None
                if playlist.skip_existing:
                    existing_match = self.find_existing_file(track, playlist_dir)

                if existing_match:
                    existing_file, origin_desc = existing_match
                    logger.info(f"Skipping download (already exists): {track_display} ({origin_desc})")
                    completed_tracks += 1
                    current_status["status"] = "completed"
                    current_status["matched_title"] = origin_desc
                    current_status["match_score"] = 100.0
                    current_status["cached"] = True
                    current_status["file_path"] = str(existing_file.resolve())
                else:
                    # 1. Match track to best YouTube Music candidate using scoring algorithm
                    target_url, match_info = music_matcher.find_best_match(track)
                    current_status["matched_title"] = match_info.get("title")
                    current_status["match_score"] = match_info.get("score")

                    # 2. Download audio stream via yt-dlp
                    raw_audio_path, yt_info = youtube_downloader.download_audio(
                        target_url=target_url,
                        track=track,
                        output_dir=playlist_dir,
                    )

                    # 3. Transcode to MP3 with requested compression bitrate via FFmpeg
                    mp3_path = playlist_dir / f"{raw_audio_path.stem}.mp3"
                    final_mp3 = audio_processor.convert_to_mp3(
                        input_file=raw_audio_path,
                        output_file=mp3_path,
                        bitrate=selected_bitrate,
                    )

                    # 4. Inject ID3 tags and cover art
                    if not track.cover_art_url and match_info.get("thumbnails"):
                        thumbs = match_info["thumbnails"]
                        if thumbs:
                            track.cover_art_url = thumbs[-1].get("url")

                    audio_processor.inject_metadata(
                        mp3_path=final_mp3,
                        metadata=track,
                    )

                    completed_tracks += 1
                    current_status["status"] = "completed"
                    current_status["file_path"] = str(final_mp3.resolve())
                    logger.info(f"[{index}/{total_tracks}] Successfully processed: {track_display} ({selected_bitrate})")

            except Exception as e:
                failed_tracks += 1
                current_status["status"] = "failed"
                current_status["error"] = str(e)
                logger.error(f"[{index}/{total_tracks}] Failed processing {track_display}: {e}")

            tracks_status.append(current_status)

            self._update_job(
                job_id,
                completed_tracks=completed_tracks,
                failed_tracks=failed_tracks,
                progress_percentage=round((index / total_tracks) * 100, 2),
                current_track=f"Processed: {track_display}",
                tracks_detail=tracks_status,
            )

        final_status = "SUCCESS" if failed_tracks == 0 else ("PARTIAL_SUCCESS" if completed_tracks > 0 else "FAILURE")

        self._update_job(
            job_id,
            status=final_status,
            completed_tracks=completed_tracks,
            failed_tracks=failed_tracks,
            progress_percentage=100.0,
            current_track="Finished playlist processing.",
            playlist_dir=str(playlist_dir.resolve()),
            tracks_detail=tracks_status,
        )


job_manager = JobManager()
