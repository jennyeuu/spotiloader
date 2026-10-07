import csv
import io
import uuid
import logging
from typing import List
from app.schemas.playlist import PlaylistMetadata, TrackMetadata

logger = logging.getLogger(__name__)


class CSVPlaylistParser:
    """
    Parses playlist CSV exports from TuneMyMusic, Exportify, Soundiiz, Spotlistr, and CSVMusic formats.
    """

    @staticmethod
    def parse_csv(csv_content: str, playlist_name: str = "Imported CSV Playlist") -> PlaylistMetadata:
        reader = csv.DictReader(io.StringIO(csv_content))
        tracks: List[TrackMetadata] = []

        # Normalize column header lookup (lowercase, stripped)
        fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

        def get_val(row: dict, keys: list[str]) -> str:
            for k in keys:
                for row_key, row_val in row.items():
                    if row_key and row_key.strip().lower() == k:
                        return (row_val or "").strip()
            return ""

        for idx, row in enumerate(reader, start=1):
            title = get_val(row, ["track name", "track", "title", "song", "name"])
            artist = get_val(row, ["artist name", "artist", "artists", "channel"])
            album = get_val(row, ["album name", "album"])
            isrc = get_val(row, ["isrc", "isrc code"])
            duration_str = get_val(row, ["duration (ms)", "duration", "duration ms", "length"])

            if not title or not artist:
                continue

            duration_seconds = None
            if duration_str:
                try:
                    if ":" in duration_str:
                        parts = duration_str.split(":")
                        if len(parts) == 2:
                            duration_seconds = int(parts[0]) * 60 + int(parts[1])
                    else:
                        d_val = float(duration_str)
                        # If value is large, assume ms
                        duration_seconds = int(d_val / 1000) if d_val > 1000 else int(d_val)
                except ValueError:
                    pass

            tracks.append(
                TrackMetadata(
                    id=f"csv_track_{idx}",
                    title=title,
                    artist=artist,
                    album=album or None,
                    track_number=idx,
                    total_tracks=1,
                    duration_seconds=duration_seconds,
                    isrc=isrc or None,
                )
            )

        if not tracks:
            raise ValueError("No valid tracks found in CSV file. Ensure columns contain 'Track Name' and 'Artist Name'.")

        for t in tracks:
            t.total_tracks = len(tracks)

        return PlaylistMetadata(
            playlist_id=f"csv_{uuid.uuid4().hex[:8]}",
            playlist_title=playlist_name,
            owner="CSV Import",
            source="csv",
            total_tracks=len(tracks),
            tracks=tracks,
        )


csv_parser = CSVPlaylistParser()
