export function parseSpotifyTrackId(input: string): string | null {
  try {
    const url = new URL(input.trim());
    if (url.hostname !== 'open.spotify.com') return null;
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts[0] !== 'track' || !parts[1]) return null;
    return parts[1];
  } catch {
    const match = input.trim().match(/^spotify:track:([A-Za-z0-9]+)$/);
    return match?.[1] ?? null;
  }
}
