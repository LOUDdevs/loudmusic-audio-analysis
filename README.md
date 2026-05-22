# LOUDmusic Audio Analysis MVP

Standalone web app version of the WordPress Audio Tagging prototype.

## Features

- Audio upload analysis flow for MP3/WAV/FLAC
- Spotify track URL analysis flow
- Polished LOUDmusic dashboard UI
- Demo-mode analysis responses when no backend API is configured
- API routes ready to connect to the real tagging backend and enrichment services

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

## Production build

```bash
npm run test
npm run typecheck
npm run build
npm start
```

## API routes

- `POST /api/analyze/audio` — accepts `multipart/form-data` with a `file` field
- `POST /api/analyze/spotify` — accepts JSON `{ "spotifyUrl": "https://open.spotify.com/track/..." }`

If `AUDIO_TAGGING_API_URL` is unset, routes return demo MVP data so the product can be reviewed live without the Python tagging service.
