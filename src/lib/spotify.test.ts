import { describe, expect, it } from 'vitest';
import { parseSpotifyTrackId } from './spotify';

describe('parseSpotifyTrackId', () => {
  it('extracts a track id from a standard Spotify URL', () => {
    expect(parseSpotifyTrackId('https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC')).toBe('4uLU6hMCjMI75M1A2tKUQC');
  });

  it('extracts a track id when query params are present', () => {
    expect(parseSpotifyTrackId('https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=abc')).toBe('4uLU6hMCjMI75M1A2tKUQC');
  });

  it('rejects unsupported Spotify URLs', () => {
    expect(parseSpotifyTrackId('https://open.spotify.com/playlist/abc')).toBeNull();
  });
});
