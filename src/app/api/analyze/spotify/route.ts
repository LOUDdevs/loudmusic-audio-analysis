import { buildDemoSpotifyAnalysis } from '@/lib/analysis';
import { proxyToTaggingBackend } from '@/lib/backend';
import { parseSpotifyTrackId } from '@/lib/spotify';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { spotifyUrl?: string } | null;
  const trackId = parseSpotifyTrackId(body?.spotifyUrl ?? '');

  if (!trackId) {
    return Response.json({ error: 'Paste a valid Spotify track URL.' }, { status: 400 });
  }

  const proxied = await proxyToTaggingBackend('/analyze/spotify', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ spotifyUrl: body?.spotifyUrl, trackId }),
  });

  if (proxied) {
    return proxied;
  }

  return Response.json(buildDemoSpotifyAnalysis(trackId));
}
