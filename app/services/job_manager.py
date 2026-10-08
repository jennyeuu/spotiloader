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
        # strip characters that break file systems
        cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
        cleaned = re.sub(r'\s+', " ", cleaned).strip()
        cleaned = cleaned.strip(".")
        return cleaned

    def find_existing_file(self, track: TrackMetadata, playlist_dir: Path) -> Optional[Tuple[Path, str]]:
        safe_artist = self._sanitize_filename(track.artist)
        safe_title = self._sanitize_filename(track.title)
        expected_name = f"{safe_artist} - {safe_title}.mp3"

        # check local playlist folder first
        local_file = playlist_dir / expected_name
        if local_file.exists() and local_file.stat().st_size > 50000:
            return local_file, "Existing track in playlist"

        # look through all other playlist folders
        src_clean_title = music_matcher.clean_text(track.title)
        src_clean_artist = music_matcher.clean_text(track.artist)

        try:
            for candidate in settings.DOWNLOAD_DIR.rglob("*.mp3"):
                if not candidate.is_file() or candidate.stat().st_size <= 50000:
                    continue
                # skip zips and current folder
                if "zips" in candidate.parts or candidate.parent.resolve() == playlist_dir.resolve():
                    continue

                origin_folder = candidate.parent.name
                cand_stem = candidate.stem

                # try matching by filename
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

                # fallback to checking id3 tags
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
        playlist_safe_name = self._sanitize_filename(playlist.playlist_title) or f"Playlist_{playlist.playlist_id}"
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        tracks_detail = []
        completed_count = 0

        for track in playlist.tracks:
            existing = None
            if playlist.skip_existing:
                existing = self.find_existing_file(track, playlist_dir)

            if existing:
                existing_file, origin_desc = existing
                completed_count += 1
                tracks_detail.append({
                    "track_id": track.id,
                    "title": track.title,
                    "artist": track.artist,
                    "status": "completed",
                    "matched_title": origin_desc,
                    "match_score": 100.0,
                    "file_path": str(existing_file.resolve()),
                    "cached": True,
                    "error": None,
                })
            else:
                tracks_detail.append({
                    "track_id": track.id,
                    "title": track.title,
                    "artist": track.artist,
                    "status": "ready",
                    "matched_title": None,
                    "match_score": None,
                    "file_path": None,
                    "cached": False,
                    "error": None,
                })

        total = playlist.total_tracks
        initial_status = "SUCCESS" if (completed_count == total and total > 0) else "READY"
        progress_pct = round((completed_count / total) * 100, 2) if total > 0 else 0.0

        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": initial_status,
                "playlist_id": playlist.playlist_id,
                "playlist_title": playlist.playlist_title,
                "source": playlist.source,
                "skip_existing": playlist.skip_existing,
                "bitrate": playlist.bitrate or settings.AUDIO_BITRATE,
                "total_tracks": total,
                "completed_tracks": completed_count,
                "failed_tracks": 0,
                "progress_percentage": progress_pct,
                "current_track": "Playlist loaded and ready for download.",
                "tracks_detail": tracks_detail,
                "playlist_dir": str(playlist_dir.resolve()),
                "playlist_metadata": playlist,
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

    def download_single_job_track(self, job_id: str, track_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

        playlist = job.get("playlist_metadata")
        if not playlist:
            return

        tracks_status = job.get("tracks_detail", [])
        # match track
        matched_idx = None
        matched_track_obj = None
        for i, st in enumerate(tracks_status):
            if st.get("track_id") == track_id or (not track_id and i == 0):
                matched_idx = i
                break

        if matched_idx is None:
            return

        for t in playlist.tracks:
            if t.id == track_id or (not track_id and playlist.tracks):
                matched_track_obj = t
                break

        if not matched_track_obj and matched_idx < len(playlist.tracks):
            matched_track_obj = playlist.tracks[matched_idx]

        if not matched_track_obj:
            return

        selected_bitrate = job.get("bitrate") or playlist.bitrate or settings.AUDIO_BITRATE
        playlist_safe_name = self._sanitize_filename(playlist.playlist_title) or f"Playlist_{playlist.playlist_id}"
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        track_display = f"{matched_track_obj.artist} - {matched_track_obj.title}"
        tracks_status[matched_idx]["status"] = "in_progress"
        tracks_status[matched_idx]["error"] = None

        self._update_job(
            job_id,
            current_track=f"Downloading: {track_display}...",
            tracks_detail=tracks_status,
        )

        try:
            track_result = self._process_single_track(
                track=matched_track_obj,
                playlist_dir=playlist_dir,
                selected_bitrate=selected_bitrate,
                skip_existing=False,
            )
            tracks_status[matched_idx].update(track_result)
            logger.info(f"Downloaded individual track: {track_display} -> {playlist_safe_name}")
        except Exception as e:
            tracks_status[matched_idx]["status"] = "failed"
            tracks_status[matched_idx]["error"] = str(e)
            logger.error(f"Failed individual track download {track_display}: {e}")

        completed_tracks = len([t for t in tracks_status if t.get("status") == "completed"])
        failed_tracks = len([t for t in tracks_status if t.get("status") == "failed"])
        total_tracks = job.get("total_tracks", len(tracks_status))
        progress_pct = round((completed_tracks / total_tracks) * 100, 2) if total_tracks > 0 else 0.0

        final_status = "SUCCESS" if (completed_tracks == total_tracks and total_tracks > 0) else "READY"

        self._update_job(
            job_id,
            status=final_status,
            completed_tracks=completed_tracks,
            failed_tracks=failed_tracks,
            progress_percentage=progress_pct,
            current_track=f"Saved: {track_display}",
            tracks_detail=tracks_status,
        )

    def start_all_downloads(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

        playlist = job.get("playlist_metadata")
        if not playlist:
            return

        selected_bitrate = job.get("bitrate") or playlist.bitrate or settings.AUDIO_BITRATE
        playlist_safe_name = self._sanitize_filename(playlist.playlist_title) or f"Playlist_{playlist.playlist_id}"
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        tracks_status = job.get("tracks_detail", [])
        total_tracks = playlist.total_tracks
        tracks_map = {t.id: t for t in playlist.tracks}

        self._update_job(
            job_id,
            status="PROGRESS",
            current_track="Starting batch download...",
        )

        for index, track in enumerate(playlist.tracks, start=1):
            st_idx = None
            for i, s in enumerate(tracks_status):
                if s.get("track_id") == track.id:
                    st_idx = i
                    break

            if st_idx is None:
                st_idx = index - 1

            # if already completed, skip
            if st_idx < len(tracks_status) and tracks_status[st_idx].get("status") == "completed":
                continue

            track_display = f"{track.artist} - {track.title}"
            if st_idx < len(tracks_status):
                tracks_status[st_idx]["status"] = "in_progress"
                tracks_status[st_idx]["error"] = None

            completed_now = len([t for t in tracks_status if t.get("status") == "completed"])
            failed_now = len([t for t in tracks_status if t.get("status") == "failed"])

            self._update_job(
                job_id,
                status="PROGRESS",
                completed_tracks=completed_now,
                failed_tracks=failed_now,
                progress_percentage=round(((index - 1) / total_tracks) * 100, 2),
                current_track=f"({index}/{total_tracks}) Downloading: {track_display}",
                tracks_detail=tracks_status,
            )

            try:
                track_result = self._process_single_track(
                    track=track,
                    playlist_dir=playlist_dir,
                    selected_bitrate=selected_bitrate,
                    skip_existing=playlist.skip_existing,
                )
                if st_idx < len(tracks_status):
                    tracks_status[st_idx].update(track_result)
            except Exception as e:
                if st_idx < len(tracks_status):
                    tracks_status[st_idx]["status"] = "failed"
                    tracks_status[st_idx]["error"] = str(e)
                logger.error(f"[{index}/{total_tracks}] Failed downloading {track_display}: {e}")

            completed_now = len([t for t in tracks_status if t.get("status") == "completed"])
            failed_now = len([t for t in tracks_status if t.get("status") == "failed"])

            self._update_job(
                job_id,
                completed_tracks=completed_now,
                failed_tracks=failed_now,
                progress_percentage=round((index / total_tracks) * 100, 2),
                current_track=f"Processed: {track_display}",
                tracks_detail=tracks_status,
            )

        # auto-retry any failed tracks
        failed_indices = [i for i, st in enumerate(tracks_status) if st.get("status") == "failed"]
        if failed_indices:
            for retry_round in range(1, 4):
                remaining_failed = [i for i, st in enumerate(tracks_status) if st.get("status") == "failed"]
                if not remaining_failed:
                    break

                self._update_job(
                    job_id,
                    current_track=f"Auto-retrying {len(remaining_failed)} failed track(s) (Round {retry_round}/3)...",
                )

                for idx in remaining_failed:
                    st = tracks_status[idx]
                    track_obj = tracks_map.get(st.get("track_id"))
                    if not track_obj:
                        continue

                    track_display = f"{track_obj.artist} - {track_obj.title}"
                    try:
                        track_result = self._process_single_track(
                            track=track_obj,
                            playlist_dir=playlist_dir,
                            selected_bitrate=selected_bitrate,
                            skip_existing=False,
                        )
                        tracks_status[idx].update(track_result)
                        self._update_job(
                            job_id,
                            completed_tracks=len([t for t in tracks_status if t.get("status") == "completed"]),
                            failed_tracks=len([t for t in tracks_status if t.get("status") == "failed"]),
                            tracks_detail=tracks_status,
                            current_track=f"Recovered: {track_display}",
                        )
                    except Exception as err:
                        tracks_status[idx]["error"] = str(err)

        final_completed = len([t for t in tracks_status if t.get("status") == "completed"])
        final_failed = len([t for t in tracks_status if t.get("status") == "failed"])
        final_status = "SUCCESS" if final_failed == 0 else ("PARTIAL_SUCCESS" if final_completed > 0 else "FAILURE")

        self._update_job(
            job_id,
            status=final_status,
            completed_tracks=final_completed,
            failed_tracks=final_failed,
            progress_percentage=100.0,
            current_track="Finished playlist processing.",
            playlist_dir=str(playlist_dir.resolve()),
            tracks_detail=tracks_status,
        )

    def _process_single_track(
        self,
        track: TrackMetadata,
        playlist_dir: Path,
        selected_bitrate: str,
        skip_existing: bool,
    ) -> Dict[str, Any]:
        track_display = f"{track.artist} - {track.title}"

        # check for cached file across playlists
        if skip_existing:
            existing_match = self.find_existing_file(track, playlist_dir)
            if existing_match:
                existing_file, origin_desc = existing_match
                logger.info(f"Skipping download (already exists): {track_display} ({origin_desc})")
                return {
                    "track_id": track.id,
                    "title": track.title,
                    "artist": track.artist,
                    "status": "completed",
                    "matched_title": origin_desc,
                    "match_score": 100.0,
                    "file_path": str(existing_file.resolve()),
                    "cached": True,
                    "error": None,
                }

        candidates = music_matcher.find_candidates(track)
        last_error = None

        # try each candidate in priority order until one succeeds
        for attempt_idx, (target_url, match_info) in enumerate(candidates, start=1):
            try:
                raw_audio_path, yt_info = youtube_downloader.download_audio(
                    target_url=target_url,
                    track=track,
                    output_dir=playlist_dir,
                    max_attempts=2,
                )

                mp3_path = playlist_dir / f"{raw_audio_path.stem}.mp3"
                final_mp3 = audio_processor.convert_to_mp3(
                    input_file=raw_audio_path,
                    output_file=mp3_path,
                    bitrate=selected_bitrate,
                )

                if not track.cover_art_url and match_info.get("thumbnails"):
                    thumbs = match_info["thumbnails"]
                    if thumbs:
                        track.cover_art_url = thumbs[-1].get("url")

                audio_processor.inject_metadata(
                    mp3_path=final_mp3,
                    metadata=track,
                )

                logger.info(
                    f"Successfully downloaded and processed: {track_display} "
                    f"using candidate #{attempt_idx} ({match_info.get('title')})"
                )

                return {
                    "track_id": track.id,
                    "title": track.title,
                    "artist": track.artist,
                    "status": "completed",
                    "matched_title": match_info.get("title") or track_display,
                    "match_score": match_info.get("score") or 80.0,
                    "file_path": str(final_mp3.resolve()),
                    "cached": False,
                    "error": None,
                }

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Candidate #{attempt_idx} ({target_url}) failed for '{track_display}': {e}. Trying next candidate..."
                )

        raise RuntimeError(f"All candidate sources failed. Last error: {last_error}")

    def process_playlist(self, job_id: str, playlist: PlaylistMetadata):
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

        # dedicated folder per playlist
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        completed_tracks = 0
        failed_tracks = 0
        tracks_status = []

        # pass 1: process all tracks
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
                track_result = self._process_single_track(
                    track=track,
                    playlist_dir=playlist_dir,
                    selected_bitrate=selected_bitrate,
                    skip_existing=playlist.skip_existing,
                )
                completed_tracks += 1
                current_status.update(track_result)
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

        # auto-retry failed songs in multiple passes until resolved
        if failed_tracks > 0:
            tracks_map = {t.id: t for t in playlist.tracks}
            for retry_round in range(1, 4):
                failed_indices = [i for i, st in enumerate(tracks_status) if st.get("status") == "failed"]
                if not failed_indices:
                    break

                self._update_job(
                    job_id,
                    current_track=f"Auto-retrying {len(failed_indices)} failed track(s) (Round {retry_round}/3)...",
                )

                for idx in failed_indices:
                    st = tracks_status[idx]
                    track_obj = tracks_map.get(st.get("track_id"))
                    if not track_obj:
                        continue

                    track_display = f"{track_obj.artist} - {track_obj.title}"
                    try:
                        logger.info(f"[Retry Round {retry_round}] Retrying failed track: {track_display}")
                        track_result = self._process_single_track(
                            track=track_obj,
                            playlist_dir=playlist_dir,
                            selected_bitrate=selected_bitrate,
                            skip_existing=False,
                        )
                        tracks_status[idx].update(track_result)
                        completed_tracks += 1
                        failed_tracks -= 1
                        self._update_job(
                            job_id,
                            completed_tracks=completed_tracks,
                            failed_tracks=failed_tracks,
                            tracks_detail=tracks_status,
                            current_track=f"Successfully recovered: {track_display}",
                        )
                    except Exception as err:
                        logger.warning(f"[Retry Round {retry_round}] Track still failing: {track_display} ({err})")
                        tracks_status[idx]["error"] = str(err)

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

    def retry_failed_tracks(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

        playlist = job.get("playlist_metadata")
        if not playlist:
            return

        tracks_status = job.get("tracks_detail", [])
        failed_indices = [i for i, st in enumerate(tracks_status) if st.get("status") == "failed"]
        if not failed_indices:
            return

        selected_bitrate = job.get("bitrate") or playlist.bitrate or settings.AUDIO_BITRATE
        playlist_safe_name = self._sanitize_filename(playlist.playlist_title) or f"Playlist_{playlist.playlist_id}"
        playlist_dir = settings.DOWNLOAD_DIR / playlist_safe_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        completed_tracks = job.get("completed_tracks", 0)
        failed_tracks = job.get("failed_tracks", len(failed_indices))
        tracks_map = {t.id: t for t in playlist.tracks}

        self._update_job(
            job_id,
            status="PROGRESS",
            current_track=f"Retrying {len(failed_indices)} failed track(s)...",
        )

        for retry_round in range(1, 4):
            remaining_failed = [i for i, st in enumerate(tracks_status) if st.get("status") == "failed"]
            if not remaining_failed:
                break

            for idx in remaining_failed:
                st = tracks_status[idx]
                track_obj = tracks_map.get(st.get("track_id"))
                if not track_obj:
                    continue

                track_display = f"{track_obj.artist} - {track_obj.title}"
                self._update_job(job_id, current_track=f"Retrying: {track_display}...")

                try:
                    track_result = self._process_single_track(
                        track=track_obj,
                        playlist_dir=playlist_dir,
                        selected_bitrate=selected_bitrate,
                        skip_existing=False,
                    )
                    tracks_status[idx].update(track_result)
                    completed_tracks += 1
                    failed_tracks -= 1
                    self._update_job(
                        job_id,
                        completed_tracks=completed_tracks,
                        failed_tracks=failed_tracks,
                        tracks_detail=tracks_status,
                        current_track=f"Successfully recovered: {track_display}",
                    )
                except Exception as err:
                    logger.warning(f"Manual retry round {retry_round} failed for {track_display}: {err}")
                    tracks_status[idx]["error"] = str(err)

        final_status = "SUCCESS" if failed_tracks == 0 else ("PARTIAL_SUCCESS" if completed_tracks > 0 else "FAILURE")
        self._update_job(
            job_id,
            status=final_status,
            completed_tracks=completed_tracks,
            failed_tracks=failed_tracks,
            current_track="Finished retry processing.",
            tracks_detail=tracks_status,
        )


job_manager = JobManager()

