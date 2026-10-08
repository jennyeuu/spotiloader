import re
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import yt_dlp

from app.config import settings
from app.schemas.playlist import TrackMetadata

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    def __init__(self, download_dir: Path = settings.DOWNLOAD_DIR):
        self.download_dir = download_dir

    def _sanitize_filename(self, name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()

    def download_audio(
        self,
        target_url: str,
        track: TrackMetadata,
        output_dir: Optional[Path] = None,
        max_attempts: int = 3,
    ) -> Tuple[Path, Dict[str, Any]]:
        target_dir = output_dir or self.download_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_artist = self._sanitize_filename(track.artist)
        safe_title = self._sanitize_filename(track.title)
        out_template = str(target_dir / f"{safe_artist} - {safe_title}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "ffmpeg_location": settings.FFMPEG_PATH,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "ignoreerrors": False,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web", "ios", "mweb"],
                }
            },
        }

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target_url, download=True)
                    if not info:
                        raise RuntimeError("yt-dlp returned empty info dictionary.")

                    if "entries" in info:
                        entries = info.get("entries")
                        if not entries:
                            raise RuntimeError("no matching video entries found.")
                        info = entries[0]

                    downloaded_file = Path(ydl.prepare_filename(info))

                    if not downloaded_file.exists():
                        # check if file got saved under alternate extension
                        matching = [
                            f for f in target_dir.glob(f"{safe_artist} - {safe_title}.*")
                            if not f.name.endswith(".mp3") and not f.name.endswith(".part")
                        ]
                        if matching:
                            downloaded_file = matching[0]
                        else:
                            raise FileNotFoundError(f"downloaded audio file for '{track.title}' could not be located.")

                    return downloaded_file, info

            except Exception as e:
                last_error = e
                logger.warning(
                    f"attempt {attempt}/{max_attempts} failed for '{track.artist} - {track.title}' from {target_url}: {e}"
                )
                # clean up any partial files
                for part_file in target_dir.glob(f"{safe_artist} - {safe_title}.*.part"):
                    try:
                        part_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                if attempt < max_attempts:
                    time.sleep(1.0 * attempt)

        logger.error(f"all {max_attempts} download attempts failed for '{track.artist} - {track.title}' from {target_url}: {last_error}")
        raise RuntimeError(f"download failed after {max_attempts} attempts: {last_error}") from last_error


youtube_downloader = YouTubeDownloader()

