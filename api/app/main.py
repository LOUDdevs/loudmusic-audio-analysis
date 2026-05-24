from __future__ import annotations

import base64
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SPOTIFY_TRACK_RE = re.compile(r"spotify:track:([A-Za-z0-9]{22})|open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")
SPOTIFY_ARTIST_RE = re.compile(r"spotify:artist:([A-Za-z0-9]{22})|open\.spotify\.com/(?:intl-[a-z]{2}/)?artist/([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


class SpotifyRef(BaseModel):
    spotify_url: str | None = None
    spotify_id: str | None = None


class Health(BaseModel):
    status: str
    service: str
    audio_tagging_api_url: str | None
    spotify_configured: bool
    chartmetric_configured: bool


class SpotifyTokenCache:
    token: str | None = None
    expires_at: float = 0


app = FastAPI(title="LOUDmusic Analysis API", version="0.1.0")

allowed_origins_env = env("ALLOWED_ORIGINS", "https://louddevs.github.io,http://localhost:3000") or ""
allowed_origins = [x.strip() for x in allowed_origins_env.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=Health)
async def health() -> Health:
    return Health(
        status="ok",
        service="loudmusic-analysis-api",
        audio_tagging_api_url=env("AUDIO_TAGGING_API_URL"),
        spotify_configured=bool(env("SPOTIFY_CLIENT_ID") and env("SPOTIFY_CLIENT_SECRET")),
        chartmetric_configured=bool(env("CHARTMETRIC_REFRESH_TOKEN")),
    )


def extract_id(value: str | None, kind: str) -> str | None:
    if not value:
        return None
    pattern = SPOTIFY_TRACK_RE if kind == "track" else SPOTIFY_ARTIST_RE
    match = pattern.search(value.strip())
    if not match:
        return None
    return next((group for group in match.groups() if group), None)


async def spotify_token() -> str:
    if SpotifyTokenCache.token and time.time() < SpotifyTokenCache.expires_at - 60:
        return SpotifyTokenCache.token

    client_id = env("SPOTIFY_CLIENT_ID")
    client_secret = env("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Spotify credentials are not configured")

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Spotify authentication failed")
    payload = response.json()
    SpotifyTokenCache.token = payload["access_token"]
    SpotifyTokenCache.expires_at = time.time() + int(payload.get("expires_in", 3600))
    return str(SpotifyTokenCache.token)


async def spotify_get(path: str) -> dict[str, Any]:
    token = await spotify_token()
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(f"https://api.spotify.com/v1{path}", headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Spotify item not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Spotify API error: {response.status_code}")
    return response.json()


def image_url(images: list[dict[str, Any]] | None) -> str | None:
    if not images:
        return None
    return images[0].get("url")


def track_analysis(track: dict[str, Any], artist: dict[str, Any] | None = None) -> dict[str, Any]:
    artist_names = ", ".join(a.get("name", "Unknown Artist") for a in track.get("artists", [])) or "Unknown Artist"
    popularity = int(track.get("popularity") or 0)
    genres = (artist or {}).get("genres") or []
    tags = ["spotify-live", "metadata-enriched", "campaign-ready"] + genres[:4]
    return {
        "source": "spotify",
        "track": {
            "title": track.get("name") or "Spotify Track",
            "artist": artist_names,
            "externalId": track.get("id"),
            "spotifyUrl": track.get("external_urls", {}).get("spotify"),
            "album": track.get("album", {}).get("name"),
            "releaseDate": track.get("album", {}).get("release_date"),
            "imageUrl": image_url(track.get("album", {}).get("images")),
            "popularity": popularity,
        },
        "summary": f"Live Spotify metadata found for {track.get('name') or 'this track'} by {artist_names}. Popularity is {popularity}/100; use this as the baseline before adding Chartmetric audience and social momentum.",
        "tags": tags,
        "scores": {
            "energy": min(100, max(35, popularity + 10)),
            "danceability": min(100, max(35, popularity + 5)),
            "mood": min(100, max(35, popularity)),
            "commercialFit": min(100, max(35, popularity + 12)),
        },
        "recommendations": [
            "Use the Spotify metadata as the source-of-truth record for campaign setup and reporting.",
            "Compare this track against recent catalog and playlist momentum before selecting campaign tiers.",
            "Add Chartmetric enrichment next for audience geography, social velocity, and playlist intelligence.",
        ],
        "enrichment": {"spotify": True, "chartmetric": False},
        "raw": {"spotifyTrack": track, "spotifyArtist": artist},
    }


def artist_result(artist: dict[str, Any], top_tracks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    followers = artist.get("followers", {}).get("total") or 0
    popularity = int(artist.get("popularity") or 0)
    genres = artist.get("genres") or []
    tracks = [t.get("name") for t in (top_tracks or []) if t.get("name")][:6]
    return {
        "name": artist.get("name") or "Spotify Artist",
        "artistId": artist.get("id"),
        "genres": genres,
        "monthlyListeners": f"{followers:,} Spotify followers",
        "topTracks": tracks,
        "summary": f"Live Spotify artist profile for {artist.get('name') or 'this artist'} with {followers:,} followers and popularity {popularity}/100. Chartmetric enrichment can add audience/social momentum once mapped.",
        "mood": genres[0].title() if genres else "Live Spotify Profile",
        "energy": popularity,
        "spotifyUrl": artist.get("external_urls", {}).get("spotify"),
        "imageUrl": image_url(artist.get("images")),
        "enrichment": {"spotify": True, "chartmetric": False},
        "raw": {"spotifyArtist": artist, "topTracks": top_tracks or []},
    }


@app.post("/api/spotify/track")
async def analyze_spotify_track(ref: SpotifyRef) -> dict[str, Any]:
    track_id = extract_id(ref.spotify_id or ref.spotify_url, "track")
    if not track_id:
        raise HTTPException(status_code=400, detail="Provide a valid Spotify track URL or ID")
    track = await spotify_get(f"/tracks/{track_id}")
    artist = None
    if track.get("artists"):
        artist = await spotify_get(f"/artists/{track['artists'][0]['id']}")
    return track_analysis(track, artist)


@app.post("/api/spotify/artist")
async def analyze_spotify_artist(ref: SpotifyRef) -> dict[str, Any]:
    artist_id = extract_id(ref.spotify_id or ref.spotify_url, "artist")
    if not artist_id:
        raise HTTPException(status_code=400, detail="Provide a valid Spotify artist URL or ID")
    artist = await spotify_get(f"/artists/{artist_id}")
    top_tracks_payload = await spotify_get(f"/artists/{artist_id}/top-tracks?market=US")
    return artist_result(artist, top_tracks_payload.get("tracks", []))


@app.post("/api/audio/analyze")
async def analyze_audio(file: UploadFile = File(...)) -> dict[str, Any]:
    base_url = (env("AUDIO_TAGGING_API_URL") or "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=500, detail="Audio tagging API URL is not configured")

    data = await file.read()
    async with httpx.AsyncClient(timeout=240) as client:
        upload_response = await client.post(
            f"{base_url}/audio/upload",
            files={"file": (file.filename or "audio.wav", data, file.content_type or "application/octet-stream")},
        )
        if upload_response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Audio upload failed: {upload_response.status_code}")
        upload_payload = upload_response.json()
        audio_id = upload_payload.get("audio_id")
        if not audio_id:
            raise HTTPException(status_code=502, detail="Audio backend did not return audio_id")
        analysis_response = await client.post(f"{base_url}/analyze/{audio_id}")
        if analysis_response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Audio analysis failed: {analysis_response.status_code}")
        analysis = analysis_response.json()

    tags = (analysis.get("semantic_tags") or analysis.get("tags") or [])[:8]
    return {
        "source": "audio",
        "track": {"title": file.filename or "Uploaded audio", "artist": "Uploaded Track", "externalId": audio_id},
        "file": {"mimeType": file.content_type or "audio/*", "sizeMb": f"{len(data) / 1024 / 1024:.2f} MB"},
        "summary": "Live audio analysis completed through the existing LOUDmusic tagging engine.",
        "tags": tags or ["audio-analyzed", "tagging-engine"],
        "scores": {"energy": 75, "danceability": 70, "mood": 68, "commercialFit": 72},
        "recommendations": [
            "Review the semantic tags to position the track for playlist and short-form content strategy.",
            "Pair this audio profile with Spotify and Chartmetric artist data for stronger campaign targeting.",
            "Use repeated analysis across releases to build an internal LOUDmusic benchmark dataset.",
        ],
        "enrichment": {"spotify": False, "chartmetric": False},
        "raw": {"upload": upload_payload, "analysis": analysis},
    }


@app.post("/api/analyze/full")
async def analyze_full(
    spotify_url: str | None = Form(default=None),
    spotify_id: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    response: dict[str, Any] = {"spotify": None, "audio": None}
    if spotify_url or spotify_id:
        response["spotify"] = await analyze_spotify_track(SpotifyRef(spotify_url=spotify_url, spotify_id=spotify_id))
    if file is not None:
        response["audio"] = await analyze_audio(file)
    if not response["spotify"] and not response["audio"]:
        raise HTTPException(status_code=400, detail="Provide spotify_url/spotify_id and/or an audio file")
    return response
