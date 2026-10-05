from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PlaylistUrlRequest(BaseModel):
    url: str = Field(
        ...,
        description="Public Spotify playlist, album, or track URL",
        examples=["https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"]
    )
    skip_existing: bool = Field(
        default=True,
        description="Skip downloading tracks that already exist in the downloads library"
    )
    bitrate: str = Field(
        default="320k",
        description="Audio bitrate/compression quality: '320k' (HQ), '192k' (Balanced), '128k' (Compressed/Lightweight)"
    )


class TrackMetadata(BaseModel):
    id: Optional[str] = None
    title: str
    artist: str
    album: Optional[str] = None
    album_artist: Optional[str] = None
    release_date: Optional[str] = None
    track_number: Optional[int] = 1
    total_tracks: Optional[int] = 1
    disc_number: Optional[int] = 1
    cover_art_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    isrc: Optional[str] = None


class PlaylistMetadata(BaseModel):
    playlist_id: str
    playlist_title: str
    owner: Optional[str] = "Unknown"
    source: str = "spotify"  # "spotify", "csv", "custom"
    total_tracks: int
    tracks: List[TrackMetadata]
    skip_existing: bool = True
    bitrate: str = "320k"


class PlaylistSubmitResponse(BaseModel):
    job_id: str
    playlist_title: str
    total_tracks: int
    source: str
    skip_existing: bool = True
    bitrate: str = "320k"
    message: str = "Download job queued successfully"


class TrackProgress(BaseModel):
    track_id: Optional[str] = None
    title: str
    artist: str
    status: str  # "pending", "downloading", "processing", "completed", "failed", "cached"
    matched_video_id: Optional[str] = None
    matched_title: Optional[str] = None
    match_score: Optional[float] = None
    file_path: Optional[str] = None
    cached: bool = False
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "PENDING", "PROGRESS", "SUCCESS", "FAILURE", "PARTIAL_SUCCESS"
    total_tracks: int
    completed_tracks: int
    failed_tracks: int
    progress_percentage: float
    bitrate: str = "320k"
    current_track: Optional[str] = None
    tracks_detail: List[Dict[str, Any]] = []
    error: Optional[str] = None
