export const CHARTMETRIC_API_HOST = 'https://api.chartmetric.com';

export const REQUIRED_SERVER_SECRET_NAMES = [
  'SPOTIFY_CLIENT_ID',
  'SPOTIFY_CLIENT_SECRET',
  'CHARTMETRIC_REFRESH_TOKEN',
] as const;

export type RequiredServerSecretName = (typeof REQUIRED_SERVER_SECRET_NAMES)[number];

export interface ChartmetricArtistEndpoints {
  metadata: string;
  urls: string;
  fanMetrics: string;
  socialAudience: string;
  instagramAudience: string;
  tiktokAudience: string;
  youtubeAudience: string;
  instagramTopContent: string;
}

export function getRequiredServerSecretNames(): RequiredServerSecretName[] {
  return [...REQUIRED_SERVER_SECRET_NAMES];
}

export function buildChartmetricArtistEndpoints(chartmetricArtistId: number): ChartmetricArtistEndpoints {
  return {
    metadata: `/api/artist/${chartmetricArtistId}`,
    urls: `/api/artist/${chartmetricArtistId}/urls`,
    fanMetrics: `/api/artist/${chartmetricArtistId}/stat/:source`,
    socialAudience: `/api/artist/${chartmetricArtistId}/social-audience-stats`,
    instagramAudience: `/api/artist/${chartmetricArtistId}/instagram-audience-stats`,
    tiktokAudience: `/api/artist/${chartmetricArtistId}/tiktok-audience-stats`,
    youtubeAudience: `/api/artist/${chartmetricArtistId}/youtube-audience-stats`,
    instagramTopContent: `/api/SNS/deepSocial/cm_artist/${chartmetricArtistId}/instagram`,
  };
}
