import { describe, expect, it } from 'vitest';
import { buildDemoAudioAnalysis, buildDemoSpotifyAnalysis } from './analysis';

describe('demo analysis builders', () => {
  it('creates an audio profile using the uploaded filename', () => {
    const result = buildDemoAudioAnalysis('single.wav', 12_345_678, 'audio/wav');

    expect(result.source).toBe('audio');
    expect(result.track.title).toBe('single.wav');
    expect(result.tags).toContain('radio-ready');
    expect(result.file?.sizeMb).toBe('11.77 MB');
  });

  it('creates a Spotify profile with the parsed track id and Chartmetric-only enrichment model', () => {
    const result = buildDemoSpotifyAnalysis('4uLU6hMCjMI75M1A2tKUQC');

    expect(result.source).toBe('spotify');
    expect(result.track.externalId).toBe('4uLU6hMCjMI75M1A2tKUQC');
    expect(result.enrichment).toEqual({ spotify: true, chartmetric: false });
    expect(result.recommendations.join(' ')).toContain('Chartmetric');
    expect(result.recommendations.join(' ')).not.toContain('Soundcharts');
  });
});
