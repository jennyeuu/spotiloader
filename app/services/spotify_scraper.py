import re
import json
import logging
from typing import Optional, List, Tuple
import httpx
from bs4 import BeautifulSoup

from app.schemas.playlist import PlaylistMetadata, TrackMetadata

logger = logging.getLogger(__name__)


class SpotifyScraperService:
    """
    Extracts Spotify playlist, album, and single track metadata directly from public web pages,
    embeds, and anonymous web player tokens without needing Spotify developer credentials.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def parse_spotify_url(url: str) -> Tuple[str, str]:
        """
        Parses URL into (entity_type, entity_id).
        Supports: playlist, album, track.
        Handles shortlinks (spotify.link / spoti.fi) and language subpaths.
        """
        clean_url = url.strip()

        # resolve shortened URLs if needed
        if "spotify.link" in clean_url or "spoti.fi" in clean_url:
            try:
                with httpx.Client(follow_redirects=True, timeout=10.0, headers=SpotifyScraperService.HEADERS) as client:
                    resp = client.head(clean_url)
                    clean_url = str(resp.url)
            except Exception as e:
                logger.warning(f"failed to expand shortened spotify link: {e}")

        # standard web URL with any country code prefix
        match = re.search(r"spotify\.com/(?:intl-[^/]+/)?(playlist|album|track)/([a-zA-Z0-9]{22})", clean_url)
        if match:
            return match.group(1), match.group(2)

        # URI format (e.g. spotify:track:0VjIjW4GlUZAMYd2vXMi3b)
        uri_match = re.search(r"spotify:(playlist|album|track):([a-zA-Z0-9]{22})", clean_url)
        if uri_match:
            return uri_match.group(1), uri_match.group(2)

        raise ValueError(f"Invalid Spotify URL or Track Link format: '{url}'")

    def get_anonymous_token(self) -> Optional[str]:
        """
        Fetches public web-player bearer token directly from Spotify.
        """
        try:
            url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
            with httpx.Client(headers=self.HEADERS, timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("accessToken")
        except Exception as e:
            logger.warning(f"failed to fetch anonymous spotify web token: {e}")
        return None

    def fetch_via_web_api(self, entity_type: str, entity_id: str, token: str) -> Optional[PlaylistMetadata]:
        """
        Uses Spotify Web API with the public anonymous token to retrieve track details.
        """
        headers = {**self.HEADERS, "Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(headers=headers, timeout=15.0) as client:
                if entity_type == "track":
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
                    track_title = data.get("name", "Unknown Title")

                    track_obj = TrackMetadata(
                        id=data.get("id", entity_id),
                        title=track_title,
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
                        playlist_title=f"{artist_name} - {track_title}",
                        owner=artist_name,
                        source="spotify",
                        total_tracks=1,
                        tracks=[track_obj],
                    )

                elif entity_type == "playlist":
                    res = client.get(f"https://api.spotify.com/v1/playlists/{entity_id}")
                    if res.status_code != 200:
                        return None
                    data = res.json()
                    title = data.get("name", "Spotify Playlist")
                    owner = data.get("owner", {}).get("display_name", "Spotify User")
                    tracks_data = data.get("tracks", {})
                    items = tracks_data.get("items", [])

                    # handle pagination
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

        except Exception as e:
            logger.warning(f"error fetching metadata via web api token: {e}")
        return None

    def fetch_via_embed_scraper(self, entity_type: str, entity_id: str) -> PlaylistMetadata:
        """
        Fallback scraper using Spotify embed HTML pages.
        Extracts embedded __NEXT_DATA__ or entity payload directly from HTML.
        Supports single tracks, albums, and playlists.
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

                if entity_type == "track":
                    track_title = state.get("title") or state.get("name") or "Unknown Track"
                    artists_data = state.get("artists", [])
                    if artists_data:
                        artists = [a.get("name", "") if isinstance(a, dict) else str(a) for a in artists_data if a]
                        artist_name = ", ".join(artists) if artists else "Unknown Artist"
                    elif state.get("subtitle"):
                        artist_name = state.get("subtitle")
                    else:
                        artist_name = "Unknown Artist"

                    cover_url = None
                    visual_images = state.get("visualIdentity", {}).get("image", [])
                    cover_sources = state.get("coverArt", {}).get("sources", [])
                    if visual_images:
                        cover_url = visual_images[0].get("url")
                    elif cover_sources:
                        cover_url = cover_sources[0].get("url")

                    duration_ms = state.get("duration", 0)
                    release_date = state.get("releaseDate", {}).get("isoString") if isinstance(state.get("releaseDate"), dict) else state.get("releaseDate")

                    track_obj = TrackMetadata(
                        id=state.get("id") or entity_id,
                        title=track_title,
                        artist=artist_name,
                        cover_art_url=cover_url,
                        duration_seconds=round(duration_ms / 1000) if duration_ms else None,
                        release_date=release_date[:10] if release_date else None,
                        track_number=1,
                        total_tracks=1,
                        isrc=state.get("isrc"),
                    )

                    return PlaylistMetadata(
                        playlist_id=entity_id,
                        playlist_title=f"{artist_name} - {track_title}",
                        owner=artist_name,
                        source="spotify",
                        total_tracks=1,
                        tracks=[track_obj],
                    )

                # playlist or album handling
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

                if tracks:
                    return PlaylistMetadata(
                        playlist_id=entity_id,
                        playlist_title=title,
                        owner=owner,
                        source="spotify",
                        total_tracks=len(tracks),
                        tracks=tracks,
                    )

        # fallback to opengraph metadata scraping if embed next_data was insufficient
        return self.fetch_via_opengraph_scraper(entity_type, entity_id)

    def fetch_via_opengraph_scraper(self, entity_type: str, entity_id: str) -> PlaylistMetadata:
        """
        Direct OpenGraph HTML meta tag parser for single Spotify tracks/albums.
        """
        target_url = f"https://open.spotify.com/{entity_type}/{entity_id}"
        with httpx.Client(headers=self.HEADERS, timeout=15.0, follow_redirects=True) as client:
            res = client.get(target_url)
            if res.status_code != 200:
                raise ValueError(f"could not access Spotify page (status {res.status_code})")

            soup = BeautifulSoup(res.text, "html.parser")
            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")

            title = og_title.get("content", "").strip() if og_title else "Spotify Track"
            description = og_desc.get("content", "").strip() if og_desc else ""
            cover_url = og_image.get("content", "").strip() if og_image else None

            # OpenGraph description format usually is "Artist · Song · Year" or "Artist · Album · Year"
            artist_name = "Spotify Artist"
            if "·" in description:
                artist_name = description.split("·")[0].strip()
            elif description:
                artist_name = description

            track_obj = TrackMetadata(
                id=entity_id,
                title=title,
                artist=artist_name,
                cover_art_url=cover_url,
                track_number=1,
                total_tracks=1,
            )

            return PlaylistMetadata(
                playlist_id=entity_id,
                playlist_title=f"{artist_name} - {title}",
                owner=artist_name,
                source="spotify",
                total_tracks=1,
                tracks=[track_obj],
            )

    def extract_from_url(self, url: str) -> PlaylistMetadata:
        entity_type, entity_id = self.parse_spotify_url(url)

        # grab web player token first for full metadata
        token = self.get_anonymous_token()
        if token:
            meta = self.fetch_via_web_api(entity_type, entity_id, token)
            if meta and meta.tracks:
                logger.info(f"successfully scraped {len(meta.tracks)} tracks via Spotify Web API ({entity_type})")
                return meta

        # fallback to embed scraping
        logger.info(f"falling back to Spotify embed scraper for {entity_type}/{entity_id}")
        return self.fetch_via_embed_scraper(entity_type, entity_id)


spotify_scraper = SpotifyScraperService()

