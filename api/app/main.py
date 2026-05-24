from __future__ import annotations

import base64
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SPOTIFY_TRACK_RE = re.compile(r"spotify:track:([A-Za-z0-9]{22})|open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")
SPOTIFY_ARTIST_RE = re.compile(r"spotify:artist:([A-Za-z0-9]{22})|open\.spotify\.com/(?:intl-[a-z]{2}/)?artist/([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


class SpotifyRef(BaseModel):
    spotify_url: str | None = None
    spotify_id: str | None = None


class ChartmetricArtistRef(BaseModel):
    spotify_url: str | None = None
    spotify_id: str | None = None
    chartmetric_id: str | int | None = None


class Health(BaseModel):
    status: str
    service: str
    audio_tagging_api_url: str | None
    spotify_configured: bool
    chartmetric_configured: bool


class SpotifyTokenCache:
    token: str | None = None
    expires_at: float = 0


class ChartmetricTokenCache:
    token: str | None = None
    expires_at: float = 0


app = FastAPI(title="LOUDmusic Analysis API", version="0.2.0")

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


async def spotify_get_optional(path: str) -> dict[str, Any] | None:
    try:
        return await spotify_get(path)
    except Exception:
        return None


async def chartmetric_token() -> str:
    if ChartmetricTokenCache.token and time.time() < ChartmetricTokenCache.expires_at - 60:
        return ChartmetricTokenCache.token

    refresh_token = env("CHARTMETRIC_REFRESH_TOKEN") or env("CHARTMETRIC_LIVE_API_KEY")
    if not refresh_token:
        raise HTTPException(status_code=500, detail="Chartmetric refresh token is not configured")

    base_url = (env("CHARTMETRIC_BASE_URL", "https://api.chartmetric.com") or "https://api.chartmetric.com").rstrip("/")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{base_url}/api/token",
            json={"refreshtoken": refresh_token},
            headers={"Content-Type": "application/json"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Chartmetric authentication failed: {response.status_code}")
    payload = response.json().get("obj") or response.json()
    token = payload.get("token") or payload.get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Chartmetric did not return an access token")
    ChartmetricTokenCache.token = token
    ChartmetricTokenCache.expires_at = time.time() + int(payload.get("expires_in", 3600))
    return str(token)


async def chartmetric_get(path: str, params: dict[str, Any] | None = None) -> Any:
    token = await chartmetric_token()
    base_url = (env("CHARTMETRIC_BASE_URL", "https://api.chartmetric.com") or "https://api.chartmetric.com").rstrip("/")
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(f"{base_url}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Chartmetric API error: {response.status_code}")
    payload = response.json()
    return payload.get("obj", payload)


async def chartmetric_get_optional(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        return await chartmetric_get(path, params=params)
    except Exception:
        return None


async def resolve_chartmetric_artist_id(spotify_id: str | None = None, chartmetric_id: str | int | None = None) -> str | None:
    if chartmetric_id:
        return str(chartmetric_id)
    if not spotify_id:
        return None
    data = await chartmetric_get(f"/api/artist/spotify/{spotify_id}/get-ids", params={"aggregate": "true"})
    first = data[0] if isinstance(data, list) and data else data
    if not isinstance(first, dict):
        return None
    cm_id = first.get("chartmetric_id") or first.get("cm_artist") or first.get("cmid") or first.get("id")
    if isinstance(cm_id, list):
        cm_id = cm_id[0] if cm_id else None
    return str(cm_id) if cm_id else None


def normalize_chartmetric_urls(data: Any) -> dict[str, str]:
    items = data if isinstance(data, list) else []
    social: dict[str, str] = {}
    aliases = {
        "instagram": "instagram",
        "twitter": "twitter",
        "x": "twitter",
        "tiktok": "tiktok",
        "facebook": "facebook",
        "youtube": "youtube",
        "website": "website",
        "homepage": "website",
        "spotify": "spotify",
        "soundcloud": "soundcloud",
        "bandsintown": "bandsintown",
        "wikipedia": "wikipedia",
        "itunes": "appleMusic",
        "apple": "appleMusic",
        "deezer": "deezer",
        "amazon": "amazonMusic",
        "songkick": "songkick",
        "genius": "genius",
        "shazam": "shazam",
        "lastfm": "lastfm",
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or item.get("name") or "").lower()
        url_value = item.get("url")
        url = url_value[0] if isinstance(url_value, list) and url_value else url_value
        if not isinstance(url, str) or not url:
            continue
        for needle, key in aliases.items():
            if needle in domain and key not in social:
                social[key] = url
                break
    return social


def first_number(*values: Any) -> float | int | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def normalize_chartmetric_scores(meta: dict[str, Any], stats: Any, career: Any) -> dict[str, Any]:
    cm_stats_raw = meta.get("cm_statistics")
    cm_stats: dict[str, Any] = cm_stats_raw if isinstance(cm_stats_raw, dict) else {}
    stats_obj = stats if isinstance(stats, dict) else {}
    career_item = career[0] if isinstance(career, list) and career and isinstance(career[0], dict) else {}
    score = first_number(meta.get("cm_artist_score"), meta.get("cm_artist_rank"), cm_stats.get("sp_followers"), stats_obj.get("cm_artist_score"), career_item.get("score"))
    fanbase = first_number(cm_stats.get("sp_followers"), stats_obj.get("sp_followers"), stats_obj.get("spotify_followers"))
    monthly = first_number(cm_stats.get("sp_monthly_listeners"), stats_obj.get("sp_monthly_listeners"), stats_obj.get("spotify_monthly_listeners"))
    return {
        "score": score,
        "rank": first_number(meta.get("cm_artist_rank"), stats_obj.get("rank")),
        "fanbaseScore": fanbase,
        "monthlyListeners": monthly,
        "followers": fanbase,
        "trendingScore": first_number(stats_obj.get("trending_score"), stats_obj.get("trendingScore"), career_item.get("trending_score")),
        "rawStatsKeys": sorted(stats_obj.keys())[:30],
    }


def normalize_label_list(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    labels: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("name") or item.get("label") or item.get("title") or item.get("value")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())
    return labels


def normalize_instagram_content(data: Any) -> dict[str, Any]:
    obj = data if isinstance(data, dict) else {}
    def item_summary(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        return {
            "url": item.get("url") or item.get("permalink") or item.get("post_url"),
            "caption": item.get("caption") or item.get("text") or item.get("description"),
            "likes": first_number(item.get("likes"), item.get("like_count"), item.get("likes_count")),
            "comments": first_number(item.get("comments"), item.get("comment_count"), item.get("comments_count")),
            "views": first_number(item.get("views"), item.get("view_count"), item.get("plays")),
            "date": item.get("date") or item.get("created_at") or item.get("timestamp"),
            "thumbnailUrl": item.get("thumbnail") or item.get("thumbnail_url") or item.get("image_url"),
        }
    return {
        "topPosts": [x for x in (item_summary(i) for i in obj.get("top_posts", [])[:6]) if x],
        "topReels": [x for x in (item_summary(i) for i in obj.get("top_reels", [])[:6]) if x],
    }


async def chartmetric_enrich_artist(spotify_id: str | None = None, chartmetric_id: str | int | None = None) -> dict[str, Any] | None:
    cm_id = await resolve_chartmetric_artist_id(spotify_id=spotify_id, chartmetric_id=chartmetric_id)
    if not cm_id:
        return None
    metadata = await chartmetric_get(f"/api/artist/{cm_id}")
    urls_payload = await chartmetric_get_optional(f"/api/artist/{cm_id}/urls")
    stats_payload = await chartmetric_get_optional(f"/api/artist/{cm_id}/cmStats")
    career_payload = await chartmetric_get_optional(f"/api/artist/{cm_id}/career", params={"limit": 1})
    albums_payload = await chartmetric_get_optional(f"/api/artist/{cm_id}/albums", params={"limit": 12})
    instagram_payload = await chartmetric_get_optional(f"/api/SNS/deepSocial/cm_artist/{cm_id}/instagram")
    meta = metadata if isinstance(metadata, dict) else {}
    social_urls = normalize_chartmetric_urls(urls_payload)
    raw_genres = meta.get("genres")
    genres = raw_genres if isinstance(raw_genres, list) else ([meta.get("genre")] if meta.get("genre") else [])
    career_status = meta.get("career_status") if isinstance(meta.get("career_status"), dict) else {}
    cm_stats = meta.get("cm_statistics") if isinstance(meta.get("cm_statistics"), dict) else {}
    normalized_albums = []
    album_items = albums_payload if isinstance(albums_payload, list) else []
    for album in album_items[:12]:
        if not isinstance(album, dict):
            continue
        normalized_albums.append({
            "name": album.get("name") or album.get("album_name"),
            "releaseDate": album.get("release_date") or album.get("releaseDate"),
            "imageUrl": album.get("image_url") or album.get("cover_url"),
            "url": album.get("url") or album.get("spotify_url"),
        })
    return {
        "chartmetricId": cm_id,
        "name": meta.get("name"),
        "imageUrl": meta.get("image_url") or meta.get("cover_url") or meta.get("image") or meta.get("picture"),
        "genres": genres,
        "moods": normalize_label_list(meta.get("moods")),
        "activities": normalize_label_list(meta.get("activities")),
        "country": meta.get("code2") or meta.get("country") or meta.get("country_code"),
        "city": meta.get("current_city") or meta.get("hometown_city"),
        "hometownCity": meta.get("hometown_city"),
        "currentCity": meta.get("current_city"),
        "careerStage": career_status.get("stage") or meta.get("career_stage"),
        "careerTrend": career_status.get("trend") or meta.get("career_trend"),
        "growthLevel": career_status.get("level") or meta.get("growth_level"),
        "biography": meta.get("description") or meta.get("bio") or meta.get("biography"),
        "recordLabel": meta.get("record_label"),
        "bookingAgent": meta.get("booking_agent"),
        "pressContact": meta.get("press_contact"),
        "generalManager": meta.get("general_manager"),
        "bandMembers": meta.get("band_members"),
        "socialUrls": social_urls,
        "scores": normalize_chartmetric_scores(meta, stats_payload, career_payload),
        "platformStats": cm_stats,
        "albums": normalized_albums,
        "instagram": normalize_instagram_content(instagram_payload),
        "enrichment": {"chartmetric": True},
        "raw": {"metadata": metadata, "urls": urls_payload, "stats": stats_payload, "career": career_payload, "albums": albums_payload, "instagram": instagram_payload},
    }


async def safe_chartmetric_enrich_artist(spotify_id: str | None = None, chartmetric_id: str | int | None = None) -> dict[str, Any] | None:
    try:
        return await chartmetric_enrich_artist(spotify_id=spotify_id, chartmetric_id=chartmetric_id)
    except HTTPException:
        return None
    except Exception:
        return None


def merge_chartmetric_into_track(result: dict[str, Any], chartmetric: dict[str, Any] | None) -> dict[str, Any]:
    if not chartmetric:
        return result
    result["enrichment"]["chartmetric"] = True
    result["chartmetric"] = {k: v for k, v in chartmetric.items() if k != "raw"}
    result["tags"] = list(dict.fromkeys(result["tags"] + ["chartmetric-enriched", "audience-intelligence"]))
    result["summary"] += f" Chartmetric matched artist ID {chartmetric['chartmetricId']}, enabling audience and social intelligence for campaign planning."
    result["recommendations"][2] = "Use Chartmetric social links, country, career stage, and audience data to sharpen platform-specific campaign targeting."
    result["raw"]["chartmetric"] = chartmetric.get("raw")
    return result


def merge_chartmetric_into_artist(result: dict[str, Any], chartmetric: dict[str, Any] | None) -> dict[str, Any]:
    if not chartmetric:
        return result
    result["enrichment"]["chartmetric"] = True
    result["chartmetricId"] = chartmetric["chartmetricId"]
    result["socialUrls"] = chartmetric.get("socialUrls") or {}
    result["country"] = chartmetric.get("country")
    result["city"] = chartmetric.get("city")
    result["careerStage"] = chartmetric.get("careerStage")
    result["careerTrend"] = chartmetric.get("careerTrend")
    result["growthLevel"] = chartmetric.get("growthLevel")
    result["biography"] = chartmetric.get("biography")
    result["recordLabel"] = chartmetric.get("recordLabel")
    result["team"] = {
        "bookingAgent": chartmetric.get("bookingAgent"),
        "pressContact": chartmetric.get("pressContact"),
        "generalManager": chartmetric.get("generalManager"),
        "bandMembers": chartmetric.get("bandMembers"),
    }
    result["chartmetricScores"] = chartmetric.get("scores") or {}
    result["platformStats"] = chartmetric.get("platformStats") or {}
    result["socialContent"] = chartmetric.get("instagram") or {"topPosts": [], "topReels": []}
    if chartmetric.get("albums"):
        result["chartmetricAlbums"] = chartmetric.get("albums")
    result["moods"] = chartmetric.get("moods") or result.get("moods") or []
    result["activities"] = chartmetric.get("activities") or []
    result["summary"] += f" Chartmetric matched ID {chartmetric['chartmetricId']} and added profile, social links, career, and platform intelligence."
    result["raw"]["chartmetric"] = chartmetric.get("raw")
    return result


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


def normalize_album(album: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": album.get("id"),
        "name": album.get("name"),
        "releaseDate": album.get("release_date"),
        "url": album.get("external_urls", {}).get("spotify"),
        "imageUrl": image_url(album.get("images")),
        "type": album.get("album_type"),
        "totalTracks": album.get("total_tracks"),
    }


def normalize_top_track(track: dict[str, Any], audio_features: dict[str, Any] | None = None) -> dict[str, Any]:
    features = audio_features or {}
    return {
        "id": track.get("id"),
        "name": track.get("name"),
        "artists": ", ".join(a.get("name", "") for a in track.get("artists", []) if a.get("name")),
        "album": track.get("album", {}).get("name"),
        "releaseDate": track.get("album", {}).get("release_date"),
        "url": track.get("external_urls", {}).get("spotify"),
        "imageUrl": image_url(track.get("album", {}).get("images")),
        "popularity": track.get("popularity"),
        "tempoBpm": features.get("tempo"),
        "energy": features.get("energy"),
        "danceability": features.get("danceability"),
        "valence": features.get("valence"),
        "acousticness": features.get("acousticness"),
    }


def summarize_audio_profile(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["tempoBpm", "energy", "danceability", "valence", "acousticness"]
    profile: dict[str, Any] = {"coverage": 0}
    usable = [t for t in tracks if any(t.get(field) is not None for field in fields)]
    profile["coverage"] = len(usable)
    for field in fields:
        values = [float(t[field]) for t in usable if t.get(field) is not None]
        profile[field] = sum(values) / len(values) if values else None
    energy = profile.get("energy")
    tempo = profile.get("tempoBpm")
    profile["energyProfile"] = "high" if isinstance(energy, (int, float)) and energy >= 0.6 else "moderate" if isinstance(energy, (int, float)) and energy >= 0.35 else "low" if energy is not None else None
    profile["vibeDescription"] = f"Around {round(tempo)} BPM with {profile['energyProfile']} energy." if isinstance(tempo, (int, float)) and profile.get("energyProfile") else None
    return profile


def artist_result(artist: dict[str, Any], top_tracks: list[dict[str, Any]] | None = None, albums: list[dict[str, Any]] | None = None, audio_features: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    followers = artist.get("followers", {}).get("total") or 0
    popularity = int(artist.get("popularity") or 0)
    genres = artist.get("genres") or []
    detailed_tracks = []
    for t in (top_tracks or []):
        if not t.get("name"):
            continue
        tid = t.get("id")
        detailed_tracks.append(normalize_top_track(t, (audio_features or {}).get(str(tid)) if tid else None))
    tracks = [t["name"] for t in detailed_tracks if t.get("name")][:6]
    normalized_albums = [normalize_album(a) for a in (albums or []) if isinstance(a, dict)][:12]
    audio_profile = summarize_audio_profile(detailed_tracks)
    release_years = sorted({str(a.get("releaseDate", ""))[:4] for a in normalized_albums if a.get("releaseDate")}, reverse=True)
    return {
        "name": artist.get("name") or "Spotify Artist",
        "artistId": artist.get("id"),
        "genres": genres,
        "monthlyListeners": f"{followers:,} Spotify followers",
        "spotifyFollowers": followers,
        "spotifyPopularity": popularity,
        "topTracks": tracks,
        "topTracksDetailed": detailed_tracks,
        "albums": normalized_albums,
        "releaseYears": release_years,
        "summary": f"Live Spotify artist profile for {artist.get('name') or 'this artist'} with {followers:,} followers and popularity {popularity}/100. Catalog and audio-profile fields are now included for campaign planning.",
        "mood": genres[0].title() if genres else "Live Spotify Profile",
        "energy": popularity,
        "audioProfile": audio_profile,
        "spotifyUrl": artist.get("external_urls", {}).get("spotify"),
        "imageUrl": image_url(artist.get("images")),
        "enrichment": {"spotify": True, "chartmetric": False},
        "raw": {"spotifyArtist": artist, "topTracks": top_tracks or [], "albums": albums or [], "audioFeatures": audio_features or {}},
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
    result = track_analysis(track, artist)
    chartmetric = None
    if track.get("artists"):
        chartmetric = await safe_chartmetric_enrich_artist(spotify_id=track["artists"][0]["id"])
    return merge_chartmetric_into_track(result, chartmetric)


@app.post("/api/spotify/artist")
async def analyze_spotify_artist(ref: SpotifyRef) -> dict[str, Any]:
    artist_id = extract_id(ref.spotify_id or ref.spotify_url, "artist")
    if not artist_id:
        raise HTTPException(status_code=400, detail="Provide a valid Spotify artist URL or ID")
    artist = await spotify_get(f"/artists/{artist_id}")
    top_tracks_payload = await spotify_get(f"/artists/{artist_id}/top-tracks?market=US")
    albums_payload = await spotify_get_optional(f"/artists/{artist_id}/albums?include_groups=album,single&market=US&limit=12") or {}
    tracks = top_tracks_payload.get("tracks", [])
    track_ids = [t.get("id") for t in tracks if t.get("id")]
    audio_features: dict[str, dict[str, Any]] = {}
    if track_ids:
        features_payload = await spotify_get_optional(f"/audio-features?ids={','.join(track_ids[:100])}")
        features = features_payload.get("audio_features", []) if isinstance(features_payload, dict) else []
        audio_features = {str(f.get("id")): f for f in features if isinstance(f, dict) and f.get("id")}
    result = artist_result(artist, tracks, albums_payload.get("items", []), audio_features)
    chartmetric = await safe_chartmetric_enrich_artist(spotify_id=artist_id)
    return merge_chartmetric_into_artist(result, chartmetric)


@app.post("/api/chartmetric/artist")
async def analyze_chartmetric_artist(ref: ChartmetricArtistRef) -> dict[str, Any]:
    spotify_id = extract_id(ref.spotify_id or ref.spotify_url, "artist") if (ref.spotify_id or ref.spotify_url) else None
    chartmetric = await chartmetric_enrich_artist(spotify_id=spotify_id, chartmetric_id=ref.chartmetric_id)
    if not chartmetric:
        raise HTTPException(status_code=404, detail="No Chartmetric artist match found")
    return chartmetric


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
