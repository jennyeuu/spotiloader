import shutil
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import FileResponse

from app.schemas.playlist import (
    PlaylistUrlRequest,
    PlaylistSubmitResponse,
    JobStatusResponse,
)
from app.services.spotify_scraper import spotify_scraper
from app.services.youtube_scraper import youtube_scraper
from app.services.csv_parser import csv_parser
from app.services.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playlist", tags=["Playlist"])


@router.post(
    "/submit-url",
    response_model=PlaylistSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Spotify or YouTube public URL (Loads tracks ready for download)",
)
async def submit_playlist_url(
    payload: PlaylistUrlRequest,
):
    """
    1. Detects Spotify vs YouTube URL.
    2. Scrapes metadata directly from Spotify public web pages / YouTube without API keys.
    3. Prepares tracks in 'ready' state so the user can download individually or all at once.
    4. Returns job_id for progress polling and interaction.
    """
    raw_url = payload.url.strip()
    try:
        if youtube_scraper.is_youtube_url(raw_url):
            playlist_metadata = youtube_scraper.extract_from_url(raw_url)
            source_type = "youtube"
        else:
            playlist_metadata = spotify_scraper.extract_from_url(raw_url)
            source_type = "spotify"

        playlist_metadata.skip_existing = payload.skip_existing
        playlist_metadata.bitrate = payload.bitrate or "320k"
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error scraping URL '{raw_url}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metadata from URL: {e}",
        )

    if not playlist_metadata.tracks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No downloadable tracks found in the provided URL.",
        )

    job_id = job_manager.create_job(playlist_metadata)

    return PlaylistSubmitResponse(
        job_id=job_id,
        playlist_title=playlist_metadata.playlist_title,
        total_tracks=playlist_metadata.total_tracks,
        source=source_type,
        skip_existing=payload.skip_existing,
        bitrate=payload.bitrate,
        message=f"{'YouTube' if source_type == 'youtube' else 'Spotify'} tracks loaded and ready for download.",
    )


@router.post(
    "/submit-csv",
    response_model=PlaylistSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload playlist CSV export (TuneMyMusic / Exportify / CSVMusic)",
)
async def submit_playlist_csv(
    file: UploadFile = File(..., description="CSV file containing playlist tracks"),
    playlist_name: str = Form(default="Imported CSV Playlist", description="Custom playlist title"),
    skip_existing: bool = Form(default=True, description="Skip downloading tracks that already exist"),
    bitrate: str = Form(default="320k", description="Audio compression bitrate: 320k, 192k, or 128k"),
):
    """
    Accepts CSV exports and loads tracks in ready state.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a .csv file.",
        )

    try:
        content_bytes = await file.read()
        csv_text = content_bytes.decode("utf-8-sig", errors="ignore")
        playlist_metadata = csv_parser.parse_csv(csv_text, playlist_name=playlist_name)
        playlist_metadata.skip_existing = skip_existing
        playlist_metadata.bitrate = bitrate or "320k"
    except Exception as e:
        logger.error(f"Failed to parse CSV file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {e}",
        )

    job_id = job_manager.create_job(playlist_metadata)

    return PlaylistSubmitResponse(
        job_id=job_id,
        playlist_title=playlist_metadata.playlist_title,
        total_tracks=playlist_metadata.total_tracks,
        source="csv",
        skip_existing=skip_existing,
        bitrate=bitrate,
        message="CSV playlist tracks loaded and ready for download.",
    )


@router.post(
    "/download-all/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start batch download of all tracks in playlist",
)
async def download_all_tracks(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    job = job_manager._jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' not found.",
        )

    background_tasks.add_task(job_manager.start_all_downloads, job_id)
    return job_manager.get_job_status(job_id)


@router.post(
    "/download-track/{job_id}/{track_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download a single track into the playlist folder",
)
async def download_single_playlist_track(
    job_id: str,
    track_id: str,
    background_tasks: BackgroundTasks,
):
    job = job_manager._jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' not found.",
        )

    background_tasks.add_task(job_manager.download_single_job_track, job_id, track_id)
    return job_manager.get_job_status(job_id)


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Get download job status and progress",
)
async def get_job_status(job_id: str):
    """
    Returns real-time download progress, matched tracks, and percentage completed.
    """
    job_status = job_manager.get_job_status(job_id)
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' not found.",
        )
    return job_status


@router.post(
    "/retry-failed/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed tracks for a playlist job",
)
async def retry_failed_tracks(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Spawns background retries specifically for tracks that failed in the given job.
    """
    job = job_manager._jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' not found.",
        )

    background_tasks.add_task(job_manager.retry_failed_tracks, job_id)
    return job_manager.get_job_status(job_id)


@router.get(
    "/download-zip/{job_id}",
    summary="Download all completed MP3 tracks as a ZIP file",
)
async def download_playlist_zip(job_id: str):
    """
    Creates and streams a .zip archive of the downloaded MP3 playlist tracks.
    """
    job = job_manager._jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.get("completed_tracks", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tracks have been downloaded yet. Please download at least one track before creating a ZIP.",
        )

    playlist_dir_str = job.get("playlist_dir")
    if not playlist_dir_str or not Path(playlist_dir_str).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playlist files are not ready or directory not found.",
        )

    playlist_dir = Path(playlist_dir_str)
    zip_output_dir = playlist_dir.parent / "zips"
    zip_output_dir.mkdir(parents=True, exist_ok=True)
    clean_title = job_manager._sanitize_filename(job.get("playlist_title") or playlist_dir.name) or "playlist"
    zip_base_name = str(zip_output_dir / f"{clean_title}_{job_id[:8]}")

    # zip up the whole playlist folder
    zip_file_path = shutil.make_archive(
        base_name=zip_base_name,
        format="zip",
        root_dir=playlist_dir.parent,
        base_dir=playlist_dir.name,
    )

    return FileResponse(
        path=zip_file_path,
        filename=f"{clean_title}.zip",
        media_type="application/zip",
    )


@router.get(
    "/download-track",
    summary="Download single MP3 track",
)
async def download_single_track(file_path: str):
    """
    Downloads an individual completed MP3 file.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".mp3":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")

    return FileResponse(
        path=path,
        filename=path.name,
        media_type="audio/mpeg",
    )
