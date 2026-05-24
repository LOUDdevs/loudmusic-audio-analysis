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


def format_key_name(value: int | None, mode: int | None) -> str | None:
    if value is None or mode is None:
        return None
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    if value < 0 or value >= len(keys):
        return None
    return f"{keys[value]} {'Major' if mode == 1 else 'Minor'}"


def normalize_confidence_tags(tags: Any) -> list[dict[str, Any]]:
    if isinstance(tags, dict):
        items = list(tags.items())
    elif isinstance(tags, list):
        items = []
        for tag in tags:
            if isinstance(tag, str):
                items.append((tag, None))
            elif isinstance(tag, dict):
                name = tag.get("name") or tag.get("label") or tag.get("tag")
                if isinstance(name, str) and name.strip():
                    items.append((name.strip(), first_number(tag.get("confidence"), tag.get("score"), tag.get("value"))))
    else:
        items = []
    normalized: list[dict[str, Any]] = []
    for name, confidence in items:
        if not isinstance(name, str) or not name.strip():
            continue
        normalized.append({"name": name.strip(), "confidence": float(confidence) if isinstance(confidence, (int, float)) else None})
    normalized.sort(key=lambda item: item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else -1, reverse=True)
    return normalized


def normalize_audience_series(data: Any) -> dict[str, Any]:
    items = data.get("items") if isinstance(data, dict) else data if isinstance(data, list) else []
    normalized_items: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            value = first_number(item.get("value"), item.get("count"), item.get("listeners"), item.get("streams"))
            if value is None:
                continue
            normalized_items.append({
                "date": item.get("date") or item.get("timestp") or item.get("startDate") or item.get("endDate"),
                "label": item.get("label") or item.get("platform") or item.get("name"),
                "value": value,
            })
    return {"items": normalized_items}


def normalize_platform_metrics(latest: dict[str, Any], mapping: list[tuple[str, str, str | None]], delta: dict[str, Any] | None = None, delta_percent: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for platform, key, context in mapping:
        value = first_number(latest.get(key))
        if value is None:
            continue
        rows.append({
            "platform": platform,
            "value": value,
            "delta": first_number((delta or {}).get(key)),
            "deltaPercent": first_number((delta_percent or {}).get(key)),
            "context": context,
        })
    rows.sort(key=lambda row: float(row.get("value", 0)), reverse=True)
    return rows


def normalize_chartmetric_platform_views(stats: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    stats_obj = stats if isinstance(stats, dict) else {}
    latest = stats_obj.get("latest") if isinstance(stats_obj.get("latest"), dict) else {}
    weekly = stats_obj.get("weekly_diff") if isinstance(stats_obj.get("weekly_diff"), dict) else {}
    weekly_pct = stats_obj.get("weekly_diff_percent") if isinstance(stats_obj.get("weekly_diff_percent"), dict) else {}
    history = []
    popularity = first_number(latest.get("sp_popularity"))
    if popularity is not None:
        history.append({"date": stats_obj.get("timestamp"), "label": "Spotify popularity", "value": popularity})
    followers = normalize_platform_metrics(latest, [
        ("Spotify", "sp_followers", "Followers"),
        ("Instagram", "ins_followers", "Followers"),
        ("YouTube", "ycs_subscribers", "Subscribers"),
        ("TikTok", "tiktok_followers", "Followers"),
        ("SoundCloud", "soundcloud_followers", "Followers"),
        ("Deezer", "deezer_fans", "Fans"),
    ], weekly, weekly_pct)
    listeners = normalize_platform_metrics(latest, [
        ("Spotify", "sp_monthly_listeners", "Monthly listeners"),
        ("YouTube", "ycs_views", "Views"),
        ("TikTok", "tiktok_top_video_views", "Top video views"),
        ("Pandora", "pandora_listeners_28_day", "28-day listeners"),
        ("Pandora", "pandora_lifetime_streams", "Lifetime streams"),
        ("TikTok", "tiktok_track_posts", "Track posts"),
    ], weekly, weekly_pct)
    return history, followers, listeners


def normalize_core_payload(data: Any) -> dict[str, Any]:
    obj = data if isinstance(data, dict) else {}
    key_value = obj.get("key")
    mode_value = obj.get("mode") if isinstance(obj.get("mode"), int) else obj.get("scale_mode")
    return {
        "tempoBpm": first_number(obj.get("tempo_bpm"), obj.get("tempo")),
        "key": format_key_name(int(key_value), int(mode_value)) if isinstance(key_value, int) and isinstance(mode_value, int) else obj.get("key_name") or obj.get("key"),
        "scale": obj.get("scale") or ("major" if mode_value == 1 else "minor" if mode_value == 0 else None),
        "keyStrength": first_number(obj.get("key_strength"), obj.get("keyConfidence"), obj.get("key_confidence")),
        "loudnessIntegrated": first_number(obj.get("loudness_integrated"), obj.get("loudness")),
        "dynamicRange": first_number(obj.get("dynamic_range"), obj.get("dynamicRange")),
        "energy": first_number(obj.get("energy")),
        "danceability": first_number(obj.get("danceability")),
    }


def normalize_perceptual_payload(data: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    obj = data if isinstance(data, dict) else {}
    fb = fallback if isinstance(fallback, dict) else {}
    return {
        "timbreBrightness": first_number(obj.get("timbre_brightness"), obj.get("brightness")),
        "timbreWarmth": first_number(obj.get("timbre_warmth"), obj.get("warmth")),
        "valence": first_number(obj.get("valence"), fb.get("valence")),
        "acousticness": first_number(obj.get("acousticness"), fb.get("acousticness")),
    }


def confidence_tags_from_genres(genres: list[Any], confidence: float = 0.6) -> list[dict[str, Any]]:
    return normalize_confidence_tags({str(genre): confidence for genre in genres if isinstance(genre, str) and genre.strip()})


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
    popularity_history, followers_platforms, listeners_platforms = normalize_chartmetric_platform_views((chartmetric.get("raw") or {}).get("stats"))
    result["enrichment"]["chartmetric"] = True
    result["chartmetric"] = {
        **{k: v for k, v in chartmetric.items() if k != "raw"},
        "popularityHistory": popularity_history,
        "followersPlatforms": followers_platforms,
        "listenersPlatforms": listeners_platforms,
    }
    result["tags"] = list(dict.fromkeys(result["tags"] + ["chartmetric-enriched", "audience-intelligence"]))
    result["summary"] += f" Chartmetric matched artist ID {chartmetric['chartmetricId']}, enabling audience and social intelligence for campaign planning."
    result["recommendations"][2] = "Use Chartmetric social links, country, career stage, and audience data to sharpen platform-specific campaign targeting."
    result["raw"]["chartmetric"] = chartmetric.get("raw")
    return result


def merge_chartmetric_into_artist(result: dict[str, Any], chartmetric: dict[str, Any] | None) -> dict[str, Any]:
    if not chartmetric:
        return result
    popularity_history, followers_platforms, listeners_platforms = normalize_chartmetric_platform_views((chartmetric.get("raw") or {}).get("stats"))
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
    result["popularityHistory"] = popularity_history
    result["followersPlatforms"] = followers_platforms
    result["listenersPlatforms"] = listeners_platforms
    monthly_listeners = next((row.get("value") for row in listeners_platforms if row.get("platform") == "Spotify" and row.get("context") == "Monthly listeners"), None)
    if monthly_listeners is not None:
        result["monthlyListeners"] = f"{int(monthly_listeners):,} monthly listeners"
    if chartmetric.get("albums"):
        result["chartmetricAlbums"] = chartmetric.get("albums")
    result["moods"] = chartmetric.get("moods") or result.get("moods") or []
    result["activities"] = chartmetric.get("activities") or []
    result["tempoStd"] = first_number((chartmetric.get("raw") or {}).get("metadata", {}).get("tempo_std"), result.get("tempoStd"))
    result["summary"] += f" Chartmetric matched ID {chartmetric['chartmetricId']} and added profile, social links, career, and platform intelligence."
    result["raw"]["chartmetric"] = chartmetric.get("raw")
    return result


def image_url(images: list[dict[str, Any]] | None) -> str | None:
    if not images:
        return None
    return images[0].get("url")


def track_analysis(track: dict[str, Any], artist: dict[str, Any] | None = None, audio_features: dict[str, Any] | None = None, song_audience: dict[str, Any] | None = None, playlist_audience: dict[str, Any] | None = None) -> dict[str, Any]:
    artist_names = ", ".join(a.get("name", "Unknown Artist") for a in track.get("artists", [])) or "Unknown Artist"
    popularity = int(track.get("popularity") or 0)
    genres = (artist or {}).get("genres") or []
    tag_rows = confidence_tags_from_genres(genres)
    top_genres = tag_rows[:5]
    tag_names = [row["name"] for row in tag_rows] or ["spotify-live", "metadata-enriched", "campaign-ready"]
    core = normalize_core_payload(audio_features)
    perceptual = normalize_perceptual_payload(audio_features)
    energy_for_score = first_number(core.get("energy"), popularity / 100)
    dance_for_score = first_number(core.get("danceability"), popularity / 100)
    mood_for_score = first_number(perceptual.get("valence"), popularity / 100)
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
        "summary": f"Live Spotify metadata found for {track.get('name') or 'this track'} by {artist_names}. Popularity is {popularity}/100; plugin-style audio profile, tag confidence, and audience trend containers are now included where the source data is available.",
        "tags": tag_names,
        "allTags": tag_rows,
        "topGenres": top_genres,
        "core": core,
        "perceptual": perceptual,
        "songAudience": normalize_audience_series(song_audience),
        "playlistAudience": normalize_audience_series(playlist_audience),
        "scores": {
            "energy": round(float(energy_for_score) * 100) if isinstance(energy_for_score, (int, float)) and energy_for_score <= 1 else min(100, max(35, popularity + 10)),
            "danceability": round(float(dance_for_score) * 100) if isinstance(dance_for_score, (int, float)) and dance_for_score <= 1 else min(100, max(35, popularity + 5)),
            "mood": round(float(mood_for_score) * 100) if isinstance(mood_for_score, (int, float)) and mood_for_score <= 1 else min(100, max(35, popularity)),
            "commercialFit": min(100, max(35, popularity + 12)),
        },
        "recommendations": [
            "Use the Spotify metadata as the source-of-truth record for campaign setup and reporting.",
            "Compare this track against recent catalog and playlist momentum before selecting campaign tiers.",
            "Use the detailed track profile, tag confidence, and audience trend sections to mirror the original plugin workflow while expanding campaign research depth.",
        ],
        "enrichment": {"spotify": True, "chartmetric": False},
        "raw": {"spotifyTrack": track, "spotifyArtist": artist, "audioFeatures": audio_features or {}, "songAudience": song_audience or {}, "playlistAudience": playlist_audience or {}},
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
    all_tags = confidence_tags_from_genres(genres)
    top_genres = all_tags[:5]
    return {
        "name": artist.get("name") or "Spotify Artist",
        "artistId": artist.get("id"),
        "genres": genres,
        "monthlyListeners": "—",
        "spotifyFollowers": followers,
        "spotifyPopularity": popularity,
        "topTracks": tracks,
        "topTracksDetailed": detailed_tracks,
        "albums": normalized_albums,
        "releaseYears": release_years,
        "summary": f"Live Spotify artist profile for {artist.get('name') or 'this artist'} with {followers:,} followers and popularity {popularity}/100. Catalog, release, and plugin-style audio profile fields are included for campaign planning.",
        "mood": genres[0].title() if genres else "Live Spotify Profile",
        "energy": popularity,
        "audioProfile": audio_profile,
        "spotifyUrl": artist.get("external_urls", {}).get("spotify"),
        "imageUrl": image_url(artist.get("images")),
        "allTags": all_tags,
        "topGenres": top_genres,
        "tempoStd": None,
        "curatorStrictness": audio_profile.get("energyProfile"),
        "releaseTimeline": [{"date": album.get("releaseDate"), "label": album.get("name"), "value": index + 1} for index, album in enumerate(normalized_albums) if album.get("releaseDate")],
        "similarArtists": [],
        "events": [],
        "radioSpins": [],
        "topRadioStations": [],
        "followersPlatforms": [],
        "listenersPlatforms": [],
        "popularityHistory": [],
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
    features_payload = await spotify_get_optional(f"/audio-features/{track_id}")
    song_audience = {"items": []}
    playlist_audience = {"items": []}
    if track.get("popularity") is not None:
        song_audience = {"items": [{"date": None, "label": "Spotify popularity", "value": int(track.get("popularity") or 0)}]}
    if artist and artist.get("followers", {}).get("total"):
        playlist_audience = {"items": [{"date": None, "label": "Artist followers", "value": int(artist.get("followers", {}).get("total") or 0)}]}
    result = track_analysis(track, artist, features_payload or {}, song_audience, playlist_audience)
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
