import re
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
        """Removes illegal filesystem characters."""
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()

    def download_audio(
        self,
        target_url: str,
        track: TrackMetadata,
        output_dir: Optional[Path] = None,
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Downloads the best audio stream for the given matched URL/ID using yt-dlp.
        Returns the downloaded audio file path and extractor info.
        """
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
            "ignoreerrors": False,
            "socket_timeout": 30,
            "retries": 3,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                if not info:
                    raise RuntimeError("yt-dlp returned empty info dictionary.")

                if "entries" in info:
                    entries = info.get("entries")
                    if not entries:
                        raise RuntimeError("No matching video entries found.")
                    info = entries[0]

                downloaded_file = Path(ydl.prepare_filename(info))

                if not downloaded_file.exists():
                    # Check for file matching stem in target_dir
                    matching = list(target_dir.glob(f"{safe_artist} - {safe_title}.*"))
                    if matching:
                        downloaded_file = matching[0]
                    else:
                        raise FileNotFoundError(f"Downloaded audio file for '{track.title}' could not be located.")

                return downloaded_file, info

        except Exception as e:
            logger.error(f"Download error for '{track.artist} - {track.title}' from {target_url}: {e}")
            raise RuntimeError(f"Download failed: {e}") from e


youtube_downloader = YouTubeDownloader()
