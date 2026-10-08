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
from app.services.csv_parser import csv_parser
from app.services.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playlist", tags=["Playlist"])


@router.post(
    "/submit-url",
    response_model=PlaylistSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Spotify public URL (Supports skip_existing and compression bitrate)",
)
async def submit_playlist_url(
    payload: PlaylistUrlRequest,
    background_tasks: BackgroundTasks,
):
    """
    1. Scrapes Spotify track metadata directly from public web pages / anonymous web tokens.
    2. Spawns a background task with optional duplicate prevention and compression bitrate ('320k', '192k', '128k').
    3. Returns job_id for progress polling.
    """
    try:
        playlist_metadata = spotify_scraper.extract_from_url(payload.url)
        playlist_metadata.skip_existing = payload.skip_existing
        playlist_metadata.bitrate = payload.bitrate or "320k"
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error scraping Spotify playlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metadata from Spotify: {e}",
        )

    if not playlist_metadata.tracks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No downloadable tracks found in the provided Spotify URL.",
        )

    job_id = job_manager.create_job(playlist_metadata)
    background_tasks.add_task(job_manager.process_playlist, job_id, playlist_metadata)

    return PlaylistSubmitResponse(
        job_id=job_id,
        playlist_title=playlist_metadata.playlist_title,
        total_tracks=playlist_metadata.total_tracks,
        source="spotify",
        skip_existing=payload.skip_existing,
        bitrate=payload.bitrate,
        message="Spotify playlist metadata scraped and background download job started.",
    )


@router.post(
    "/submit-csv",
    response_model=PlaylistSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload playlist CSV export (TuneMyMusic / Exportify / CSVMusic)",
)
async def submit_playlist_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file containing playlist tracks"),
    playlist_name: str = Form(default="Imported CSV Playlist", description="Custom playlist title"),
    skip_existing: bool = Form(default=True, description="Skip downloading tracks that already exist"),
    bitrate: str = Form(default="320k", description="Audio compression bitrate: 320k, 192k, or 128k"),
):
    """
    Accepts CSV exports from TuneMyMusic, Exportify, Soundiiz, or CSVMusic with compression bitrate.
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
    background_tasks.add_task(job_manager.process_playlist, job_id, playlist_metadata)

    return PlaylistSubmitResponse(
        job_id=job_id,
        playlist_title=playlist_metadata.playlist_title,
        total_tracks=playlist_metadata.total_tracks,
        source="csv",
        skip_existing=skip_existing,
        bitrate=bitrate,
        message="CSV playlist parsed and background download job started.",
    )


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
