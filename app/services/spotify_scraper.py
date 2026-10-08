import re
import json
import logging
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup

from app.schemas.playlist import PlaylistMetadata, TrackMetadata

logger = logging.getLogger(__name__)


class SpotifyScraperService:
    """
    Extracts Spotify playlist, album, and track metadata directly from public web pages
    and anonymous web player tokens WITHOUT needing Spotify Developer credentials or Premium.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def parse_spotify_url(url: str) -> tuple[str, str]:
        """
        Parses URL into (entity_type, entity_id).
        Supports: playlist, album, track.
        """
        match = re.search(r"spotify\.com/(?:intl-[a-z]{2}/)?(playlist|album|track)/([a-zA-Z0-9]{22})", url)
        if match:
            return match.group(1), match.group(2)
        
        # URI format (e.g. spotify:playlist:37i9dQZF1DXcBWIGoYBM5M)
        uri_match = re.search(r"spotify:(playlist|album|track):([a-zA-Z0-9]{22})", url)
        if uri_match:
            return uri_match.group(1), uri_match.group(2)

        raise ValueError(f"Invalid Spotify URL format: {url}")

    def get_anonymous_token(self) -> Optional[str]:
        """
        Fetches public web-player bearer token directly from Spotify.
        No developer credentials required.
        """
        try:
            url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
            with httpx.Client(headers=self.HEADERS, timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("accessToken")
        except Exception as e:
            logger.warning(f"Failed to fetch anonymous Spotify web token: {e}")
        return None

    def fetch_via_web_api(self, entity_type: str, entity_id: str, token: str) -> Optional[PlaylistMetadata]:
        """
        Uses Spotify Web API with the public anonymous token to retrieve complete tracklists (including pagination).
        """
        headers = {**self.HEADERS, "Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(headers=headers, timeout=15.0) as client:
                if entity_type == "playlist":
                    res = client.get(f"https://api.spotify.com/v1/playlists/{entity_id}")
                    if res.status_code != 200:
                        return None
                    data = res.json()
                    title = data.get("name", "Spotify Playlist")
                    owner = data.get("owner", {}).get("display_name", "Spotify User")
                    tracks_data = data.get("tracks", {})
                    items = tracks_data.get("items", [])
                    
                    # Handle pagination
                    next_url = tracks_data.get("next")
                    while next_url:
                        next_res = client.get(next_url)
                        if next_res.status_code == 200:
                            next_data = next_res.json()
                            items.extend(next_data.get("items", []))
                            next_url = next_data.get("next")
                        else:
                            break

                    tracks: List[TrackMetadata] = []
                    for idx, item in enumerate(items, start=1):
                        track_item = item.get("track")
                        if not track_item or not track_item.get("id"):
                            continue
                        artists = [a.get("name", "") for a in track_item.get("artists", []) if a.get("name")]
                        artist_name = ", ".join(artists) if artists else "Unknown Artist"
                        album_data = track_item.get("album", {})
                        images = album_data.get("images", [])
                        cover_url = images[0].get("url") if images else None
                        duration_ms = track_item.get("duration_ms", 0)
                        
                        tracks.append(
                            TrackMetadata(
                                id=track_item.get("id"),
                                title=track_item.get("name", "Unknown Title"),
                                artist=artist_name,
                                album=album_data.get("name"),
                                album_artist=album_data.get("artists", [{}])[0].get("name", artist_name),
                                release_date=album_data.get("release_date"),
                                track_number=track_item.get("track_number", idx),
                                total_tracks=album_data.get("total_tracks", 1),
                                cover_art_url=cover_url,
                                duration_seconds=round(duration_ms / 1000) if duration_ms else None,
                                isrc=track_item.get("external_ids", {}).get("isrc"),
                            )
                        )

                    return PlaylistMetadata(
                        playlist_id=entity_id,
                        playlist_title=title,
                        owner=owner,
                        source="spotify",
                        total_tracks=len(tracks),
                        tracks=tracks,
                    )

                elif entity_type == "album":
                    res = client.get(f"https://api.spotify.com/v1/albums/{entity_id}")
                    if res.status_code != 200:
                        return None
                    data = res.json()
                    album_title = data.get("name", "Spotify Album")
                    artists = [a.get("name", "") for a in data.get("artists", []) if a.get("name")]
                    album_artist = ", ".join(artists) if artists else "Unknown Artist"
                    images = data.get("images", [])
                    cover_url = images[0].get("url") if images else None
                    release_date = data.get("release_date")
                    
                    tracks: List[TrackMetadata] = []
                    for idx, t in enumerate(data.get("tracks", {}).get("items", []), start=1):
                        t_artists = [a.get("name", "") for a in t.get("artists", []) if a.get("name")]
                        t_artist_name = ", ".join(t_artists) if t_artists else album_artist
                        duration_ms = t.get("duration_ms", 0)
                        tracks.append(
                            TrackMetadata(
                                id=t.get("id"),
                                title=t.get("name", "Unknown Title"),
                                artist=t_artist_name,
                                album=album_title,
                                album_artist=album_artist,
                                release_date=release_date,
                                track_number=t.get("track_number", idx),
                                total_tracks=data.get("total_tracks", 1),
                                cover_art_url=cover_url,
                                duration_seconds=round(duration_ms / 1000) if duration_ms else None,
                                isrc=t.get("external_ids", {}).get("isrc"),
                            )
                        )

                    return PlaylistMetadata(
                        playlist_id=entity_id,
                        playlist_title=album_title,
                        owner=album_artist,
                        source="spotify",
                        total_tracks=len(tracks),
                        tracks=tracks,
                    )

                elif entity_type == "track":
                    res = client.get(f"https://api.spotify.com/v1/tracks/{entity_id}")
                    if res.status_code != 200:
                        return None
                    data = res.json()
                    artists = [a.get("name", "") for a in data.get("artists", []) if a.get("name")]
                    artist_name = ", ".join(artists) if artists else "Unknown Artist"
                    album_data = data.get("album", {})
                    images = album_data.get("images", [])
                    cover_url = images[0].get("url") if images else None
                    duration_ms = data.get("duration_ms", 0)

                    track_obj = TrackMetadata(
                        id=data.get("id"),
                        title=data.get("name", "Unknown Title"),
                        artist=artist_name,
                        album=album_data.get("name"),
                        album_artist=album_data.get("artists", [{}])[0].get("name", artist_name),
                        release_date=album_data.get("release_date"),
                        track_number=data.get("track_number", 1),
                        total_tracks=1,
                        cover_art_url=cover_url,
                        duration_seconds=round(duration_ms / 1000) if duration_ms else None,
                        isrc=data.get("external_ids", {}).get("isrc"),
                    )

                    return PlaylistMetadata(
                        playlist_id=entity_id,
                        playlist_title=track_obj.title,
                        owner=artist_name,
                        source="spotify",
                        total_tracks=1,
                        tracks=[track_obj],
                    )

        except Exception as e:
            logger.warning(f"Error fetching metadata via Web API token: {e}")
        return None

    def fetch_via_embed_scraper(self, entity_type: str, entity_id: str) -> PlaylistMetadata:
        """
        Fallback scraper using Spotify embed HTML pages.
        Extracts embedded __NEXT_DATA__ or entity payload directly from HTML.
        """
        embed_url = f"https://open.spotify.com/embed/{entity_type}/{entity_id}"
        with httpx.Client(headers=self.HEADERS, timeout=15.0) as client:
            res = client.get(embed_url)
            if res.status_code != 200:
                raise ValueError(f"Spotify embed returned status {res.status_code}")
            
            soup = BeautifulSoup(res.text, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            
            if script_tag and script_tag.string:
                next_data = json.loads(script_tag.string)
                props = next_data.get("props", {}).get("pageProps", {})
                state = props.get("state", {}).get("data", {}).get("entity", {})
                
                title = state.get("title") or state.get("name") or "Spotify Playlist"
                owner = state.get("subtitle") or "Spotify"
                cover_url = state.get("coverArt", {}).get("sources", [{}])[0].get("url")
                
                raw_tracks = state.get("trackList", [])
                tracks: List[TrackMetadata] = []
                
                for idx, t in enumerate(raw_tracks, start=1):
                    tracks.append(
                        TrackMetadata(
                            id=t.get("id") or t.get("uri", "").split(":")[-1],
                            title=t.get("title", "Unknown Title"),
                            artist=t.get("subtitle") or t.get("artists", "Unknown Artist"),
                            album=title if entity_type == "album" else None,
                            cover_art_url=cover_url,
                            duration_seconds=round(t.get("duration", 0) / 1000) if t.get("duration") else None,
                            track_number=idx,
                            total_tracks=len(raw_tracks),
                            isrc=t.get("isrc"),
                        )
                    )
                
                return PlaylistMetadata(
                    playlist_id=entity_id,
                    playlist_title=title,
                    owner=owner,
                    source="spotify",
                    total_tracks=len(tracks),
                    tracks=tracks,
                )

        raise ValueError(f"Could not extract track metadata from Spotify for {entity_type}/{entity_id}")

    def extract_from_url(self, url: str) -> PlaylistMetadata:
        entity_type, entity_id = self.parse_spotify_url(url)

        # grab web player token first for full pagination
        token = self.get_anonymous_token()
        if token:
            meta = self.fetch_via_web_api(entity_type, entity_id, token)
            if meta and meta.tracks:
                logger.info(f"Successfully scraped {len(meta.tracks)} tracks via Spotify Web API")
                return meta

        # fallback to embed scraping
        logger.info(f"Falling back to Spotify embed scraper for {entity_type}/{entity_id}")
        return self.fetch_via_embed_scraper(entity_type, entity_id)


spotify_scraper = SpotifyScraperService()
