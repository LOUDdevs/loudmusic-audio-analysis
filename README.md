# LOUDmusic Audio Analysis MVP

Standalone web app version of the WordPress Audio Tagging prototype.

## Features

- Audio upload analysis flow for MP3/WAV/FLAC
- Spotify track URL analysis flow
- Polished LOUDmusic dashboard UI
- Demo-mode analysis responses while the production backend is offline
- Backend-ready integration plan for Spotify + Chartmetric artist intelligence

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

Copy `.env.example` to `.env.local` and fill in production credentials. Never commit real keys.

```bash
cp .env.example .env.local
```

Required server-side secrets for the real integration:

```env
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
CHARTMETRIC_REFRESH_TOKEN=
```

Do **not** prefix these with `NEXT_PUBLIC_`. They must stay on a backend/API service, not in the static browser bundle.

## Production build

```bash
npm run test
npm run typecheck
npm run build
```

## Deployment

The current MVP deploys as a static export to GitHub Pages:

https://louddevs.github.io/loudmusic-audio-analysis/

Because GitHub Pages is static, the live site currently uses demo-mode responses. The next production step is a server-side API endpoint such as:

```text
POST /api/analyze-spotify
```

That backend should:

1. Parse the Spotify track URL.
2. Use Spotify credentials to fetch track and artist metadata.
3. Resolve Chartmetric artist/track IDs.
4. Fetch Chartmetric artist URLs, audience stats, Instagram/TikTok/YouTube audience data, and top content.
5. Return a safe LOUDmusic campaign analysis to the frontend.

## Chartmetric-first data strategy

For the first real version, use Chartmetric as the primary intelligence layer. Do not add SocialScraper, direct Instagram/Meta, Bandsintown, or Soundcharts credentials unless the product hits a specific Chartmetric limitation.
