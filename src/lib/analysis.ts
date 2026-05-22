export type AnalysisSource = 'audio' | 'spotify';

export interface AnalysisResult {
  source: AnalysisSource;
  track: {
    title: string;
    artist: string;
    externalId?: string;
  };
  file?: {
    mimeType: string;
    sizeMb: string;
  };
  summary: string;
  tags: string[];
  scores: {
    energy: number;
    danceability: number;
    mood: number;
    commercialFit: number;
  };
  recommendations: string[];
  enrichment: {
    spotify: boolean;
    chartmetric: boolean;
    soundcharts: boolean;
    social: boolean;
  };
}

function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function buildDemoAudioAnalysis(filename: string, bytes: number, mimeType: string): AnalysisResult {
  const safeName = filename || 'Uploaded track';
  return {
    source: 'audio',
    track: {
      title: safeName,
      artist: 'Unsigned Artist',
    },
    file: {
      mimeType: mimeType || 'audio/*',
      sizeMb: formatBytes(bytes),
    },
    summary:
      'Demo-mode analysis generated from the upload flow. Wire AUDIO_TAGGING_API_URL to replace this with the real tagging engine response.',
    tags: ['radio-ready', 'melodic', 'high-energy', 'independent-release', 'playlist-pitch'],
    scores: {
      energy: 86,
      danceability: 78,
      mood: 72,
      commercialFit: 81,
    },
    recommendations: [
      'Prioritize short-form video hooks around the chorus or most memorable melodic phrase.',
      'Pitch to independent pop, energetic R&B, and discovery playlists once DSP metadata is finalized.',
      'Collect comparable artist references before campaign launch to improve audience targeting.',
    ],
    enrichment: {
      spotify: false,
      chartmetric: false,
      soundcharts: false,
      social: false,
    },
  };
}

export function buildDemoSpotifyAnalysis(trackId: string): AnalysisResult {
  return {
    source: 'spotify',
    track: {
      title: 'Spotify Track Analysis',
      artist: 'Spotify Artist',
      externalId: trackId,
    },
    summary:
      'Demo-mode Spotify analysis. Add Spotify/Chartmetric credentials to fetch real metadata, artist stats, and audience signals.',
    tags: ['spotify-linked', 'metadata-ready', 'artist-intelligence', 'campaign-research'],
    scores: {
      energy: 74,
      danceability: 82,
      mood: 69,
      commercialFit: 77,
    },
    recommendations: [
      'Use Spotify metadata as the base record, then enrich with Chartmetric and Soundcharts before campaign planning.',
      'Compare follower velocity, playlist adds, and social footprint before selecting campaign tiers.',
      'Create a one-page artist profile for outreach and paid campaign targeting.',
    ],
    enrichment: {
      spotify: true,
      chartmetric: false,
      soundcharts: false,
      social: false,
    },
  };
}
