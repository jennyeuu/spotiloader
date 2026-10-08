import shutil
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


def get_default_ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return "ffmpeg"


class Settings(BaseSettings):
    APP_NAME: str = "Spotiloader API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DOWNLOAD_DIR: Path = Path("./downloads")
    AUDIO_BITRATE: str = "320k"
    AUDIO_FORMAT: str = "mp3"
    FFMPEG_PATH: str = Field(default_factory=get_default_ffmpeg_path)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# make sure download folder is ready
settings.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
