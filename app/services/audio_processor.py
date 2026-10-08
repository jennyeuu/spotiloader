import logging
import subprocess
from pathlib import Path
from typing import Optional
import httpx
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TALB,
    TPE2,
    TRCK,
    TPOS,
    TDRC,
    TSRC,
    APIC,
    ID3NoHeaderError,
)

from app.config import settings
from app.schemas.playlist import TrackMetadata

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, ffmpeg_path: Optional[str] = None):
        self._ffmpeg_path = ffmpeg_path

    @property
    def ffmpeg_path(self) -> str:
        return self._ffmpeg_path or settings.FFMPEG_PATH

    def convert_to_mp3(self, input_file: Path, output_file: Path, bitrate: str = "320k") -> Path:
        """
        Converts any input audio file (opus, m4a, webm, etc.) to standard .mp3 using FFmpeg.
        """
        if not input_file.exists():
            raise FileNotFoundError(f"Input audio file not found: {input_file}")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(input_file),
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", bitrate,
            "-ar", "44100",
            str(output_file),
        ]

        logger.info(f"Converting {input_file.name} to MP3...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")

        # clean up raw source file
        if input_file.resolve() != output_file.resolve() and input_file.exists():
            try:
                input_file.unlink()
            except OSError as e:
                logger.warning(f"Could not remove source file {input_file}: {e}")

        return output_file

    def download_cover_art(self, url: Optional[str]) -> Optional[bytes]:
        if not url:
            return None
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.content
                logger.warning(f"Failed to fetch cover art from {url}: status {response.status_code}")
        except Exception as e:
            logger.warning(f"Error fetching cover art from {url}: {e}")
        return None

    def inject_metadata(
        self,
        mp3_path: Path,
        metadata: TrackMetadata,
        cover_image_bytes: Optional[bytes] = None
    ) -> None:
        if not mp3_path.exists():
            raise FileNotFoundError(f"MP3 file not found for tagging: {mp3_path}")

        try:
            audio = MP3(str(mp3_path), ID3=ID3)
        except ID3NoHeaderError:
            audio = MP3(str(mp3_path))
            audio.add_tags()

        if audio.tags is None:
            audio.add_tags()

        # write id3 tags
        if metadata.title:
            audio.tags.add(TIT2(encoding=3, text=metadata.title))

        if metadata.artist:
            audio.tags.add(TPE1(encoding=3, text=metadata.artist))

        if metadata.album:
            audio.tags.add(TALB(encoding=3, text=metadata.album))

        if metadata.album_artist:
            audio.tags.add(TPE2(encoding=3, text=metadata.album_artist))

        track_num_str = str(metadata.track_number) if metadata.track_number else "1"
        if metadata.total_tracks:
            track_num_str = f"{track_num_str}/{metadata.total_tracks}"
        audio.tags.add(TRCK(encoding=3, text=track_num_str))

        if metadata.disc_number:
            audio.tags.add(TPOS(encoding=3, text=str(metadata.disc_number)))

        if metadata.release_date:
            audio.tags.add(TDRC(encoding=3, text=metadata.release_date))

        if metadata.isrc:
            audio.tags.add(TSRC(encoding=3, text=metadata.isrc))

        if not cover_image_bytes and metadata.cover_art_url:
            cover_image_bytes = self.download_cover_art(metadata.cover_art_url)

        if cover_image_bytes:
            # embed cover art
            mime = "image/jpeg"
            if cover_image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                mime = "image/png"

            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=cover_image_bytes,
                )
            )

        audio.save(v2_version=3)
        logger.info(f"Successfully tagged MP3: {mp3_path.name}")


audio_processor = AudioProcessor()
