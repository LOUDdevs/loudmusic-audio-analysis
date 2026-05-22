const SPOTIFY_TRACK_ID_PATTERN = /^[A-Za-z0-9]{22}$/;
const SPOTIFY_URI_PATTERN = /spotify:track:([A-Za-z0-9]{22})/;
const SPOTIFY_URL_PATTERN = /(?:https?:\/\/)?(?:www\.)?open\.spotify\.com\/[^\s<>"']+/i;

export function parseSpotifyTrackId(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const uriMatch = trimmed.match(SPOTIFY_URI_PATTERN);
  if (uriMatch?.[1]) return uriMatch[1];

  const urlText = trimmed.match(SPOTIFY_URL_PATTERN)?.[0] ?? trimmed;
  const normalizedUrl = /^https?:\/\//i.test(urlText) ? urlText : `https://${urlText}`;

  try {
    const url = new URL(normalizedUrl);
    const hostname = url.hostname.replace(/^www\./, '');
    if (hostname !== 'open.spotify.com') return null;

    const parts = url.pathname.split('/').filter(Boolean);
    const trackIndex = parts.indexOf('track');
    const trackId = trackIndex >= 0 ? parts[trackIndex + 1] : null;

    return trackId && SPOTIFY_TRACK_ID_PATTERN.test(trackId) ? trackId : null;
  } catch {
    return null;
  }
}
