import { describe, expect, it } from 'vitest';
import { buildChartmetricArtistEndpoints, getRequiredServerSecretNames } from './chartmetric';

describe('Chartmetric-only integration plan', () => {
  it('requires only Spotify and Chartmetric server-side secrets', () => {
    expect(getRequiredServerSecretNames()).toEqual([
      'SPOTIFY_CLIENT_ID',
      'SPOTIFY_CLIENT_SECRET',
      'CHARTMETRIC_REFRESH_TOKEN',
    ]);
  });

  it('builds the Chartmetric endpoints needed for artist intelligence', () => {
    expect(buildChartmetricArtistEndpoints(2762)).toEqual({
      metadata: '/api/artist/2762',
      urls: '/api/artist/2762/urls',
      fanMetrics: '/api/artist/2762/stat/:source',
      socialAudience: '/api/artist/2762/social-audience-stats',
      instagramAudience: '/api/artist/2762/instagram-audience-stats',
      tiktokAudience: '/api/artist/2762/tiktok-audience-stats',
      youtubeAudience: '/api/artist/2762/youtube-audience-stats',
      instagramTopContent: '/api/SNS/deepSocial/cm_artist/2762/instagram',
    });
  });
});
