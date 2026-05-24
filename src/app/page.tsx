'use client';

import { FormEvent, useState } from 'react';
import { type AnalysisResult } from '@/lib/analysis';
import { parseSpotifyTrackId, parseSpotifyArtistId } from '@/lib/spotify';

type View = 'tracks' | 'artists';
type TrackMode = 'audio' | 'spotify';

const demoSpotifyUrl = 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC';
const demoArtistUrl = 'https://open.spotify.com/artist/2nWo31Kvu9rMSVfhuUVUw3';
const apiBaseUrl = process.env.NEXT_PUBLIC_LOUDMUSIC_API_URL?.replace(/\/$/, '') ?? '';

async function parseApiResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.detail || payload?.error || `API request failed with ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

function requireApiBaseUrl(): string {
  if (!apiBaseUrl) {
    throw new Error('Live API is not configured yet. Set NEXT_PUBLIC_LOUDMUSIC_API_URL for this deployment.');
  }
  return apiBaseUrl;
}

interface ArtistTrack {
  id?: string;
  name: string;
  artists?: string;
  album?: string;
  releaseDate?: string;
  url?: string;
  imageUrl?: string;
  popularity?: number;
  tempoBpm?: number;
  energy?: number;
  danceability?: number;
  valence?: number;
  acousticness?: number;
}

interface ArtistAlbum {
  id?: string;
  name?: string;
  releaseDate?: string;
  url?: string;
  imageUrl?: string;
  type?: string;
  totalTracks?: number;
}

interface ArtistResult {
  name: string;
  artistId: string;
  imageUrl?: string;
  spotifyUrl?: string;
  genres: string[];
  monthlyListeners: string;
  spotifyFollowers?: number;
  spotifyPopularity?: number;
  topTracks: string[];
  topTracksDetailed?: ArtistTrack[];
  albums?: ArtistAlbum[];
  chartmetricAlbums?: ArtistAlbum[];
  releaseYears?: string[];
  summary: string;
  mood: string;
  energy: number;
  audioProfile?: {
    coverage?: number;
    tempoBpm?: number | null;
    energy?: number | null;
    danceability?: number | null;
    valence?: number | null;
    acousticness?: number | null;
    energyProfile?: string | null;
    vibeDescription?: string | null;
  };
  enrichment?: {
    spotify: boolean;
    chartmetric: boolean;
  };
  chartmetricId?: string;
  country?: string;
  city?: string;
  careerStage?: string;
  careerTrend?: string;
  growthLevel?: string;
  biography?: string;
  recordLabel?: string;
  team?: Record<string, string | null | undefined>;
  socialUrls?: Record<string, string>;
  chartmetricScores?: Record<string, number | string | string[] | null | undefined>;
  platformStats?: Record<string, number | string | null | undefined>;
  moods?: string[];
  activities?: string[];
  socialContent?: {
    topPosts?: Array<Record<string, string | number | null | undefined>>;
    topReels?: Array<Record<string, string | number | null | undefined>>;
  };
}

function formatCompact(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const numberValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isFinite(numberValue)) {
    return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(numberValue as number);
  }
  return String(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${Math.round(value <= 1 ? value * 100 : value)}%`;
}

function titleCase(value: string): string {
  return value.replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ').replace(/^./, (char) => char.toUpperCase());
}

export default function LoudmusicAnalyzer() {
  const [view, setView] = useState<View>('tracks');

  // Tracks state
  const [trackMode, setTrackMode] = useState<TrackMode>('spotify');
  const [file, setFile] = useState<File | null>(null);
  const [spotifyUrl, setSpotifyUrl] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Artists state
  const [artistUrl, setArtistUrl] = useState('');
  const [artistResult, setArtistResult] = useState<ArtistResult | null>(null);
  const [artistError, setArtistError] = useState('');
  const [artistLoading, setArtistLoading] = useState(false);

  async function submitAudio(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError('Choose an MP3, WAV, or FLAC file first.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${requireApiBaseUrl()}/api/audio/analyze`, {
        method: 'POST',
        body: formData,
      });
      setResult(await parseApiResponse<AnalysisResult>(response));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Audio analysis failed.');
    } finally {
      setLoading(false);
    }
  }

  async function submitSpotify(event: FormEvent) {
    event.preventDefault();
    const trackId = parseSpotifyTrackId(spotifyUrl);
    if (!trackId) {
      setError('Paste a valid Spotify track URL.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch(`${requireApiBaseUrl()}/api/spotify/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spotify_url: spotifyUrl, spotify_id: trackId }),
      });
      setResult(await parseApiResponse<AnalysisResult>(response));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Spotify analysis failed.');
    } finally {
      setLoading(false);
    }
  }

  async function submitArtist(event: FormEvent) {
    event.preventDefault();
    const artistId = parseSpotifyArtistId(artistUrl);
    if (!artistId) {
      setArtistError('Please paste a valid Spotify artist URL.');
      return;
    }

    setArtistLoading(true);
    setArtistError('');
    setArtistResult(null);

    try {
      const response = await fetch(`${requireApiBaseUrl()}/api/spotify/artist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spotify_url: artistUrl, spotify_id: artistId }),
      });
      setArtistResult(await parseApiResponse<ArtistResult>(response));
    } catch (err) {
      setArtistError(err instanceof Error ? err.message : 'Artist analysis failed.');
    } finally {
      setArtistLoading(false);
    }
  }

  return (
    <main className="shell">
      {/* Header */}
      <header className="site-header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">🎵</span>
            <span className="logo-text">LOUDmusic</span>
          </div>
          <nav className="main-nav">
            <button
              className={view === 'tracks' ? 'nav-link active' : 'nav-link'}
              onClick={() => setView('tracks')}
            >
              Tracks
            </button>
            <button
              className={view === 'artists' ? 'nav-link active' : 'nav-link'}
              onClick={() => setView('artists')}
            >
              Artists
            </button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <div className="eyebrow">LOUDmusic Intelligence MVP</div>
        <h1>{view === 'tracks' ? 'Track Analysis' : 'Artist Intelligence'}</h1>
        <p>
          {view === 'tracks'
            ? 'Upload audio or analyze a Spotify track. Turn metadata and audience signals into actionable campaign direction.'
            : 'Analyze any Spotify artist profile. Understand style, audience, momentum, and campaign fit.'}
        </p>
      </section>

      {/* Analyzer */}
      <section id="analyzer" className="panel analyzer">
        {view === 'tracks' ? (
          <>
            <div className="tabs" role="tablist">
              <button
                className={trackMode === 'audio' ? 'active' : ''}
                onClick={() => setTrackMode('audio')}
              >
                Upload audio
              </button>
              <button
                className={trackMode === 'spotify' ? 'active' : ''}
                onClick={() => setTrackMode('spotify')}
              >
                Spotify track
              </button>
            </div>

            {trackMode === 'audio' ? (
              <form onSubmit={submitAudio} className="flow">
                <label className="dropzone">
                  <span>Drop in an MP3, WAV, or FLAC</span>
                  <strong>{file ? file.name : 'Choose audio file'}</strong>
                  <input
                    accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/flac,audio/x-flac"
                    type="file"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </label>
                <button disabled={loading} className="submit" type="submit">
                  {loading ? 'Analyzing…' : 'Analyze audio'}
                </button>
              </form>
            ) : (
              <form onSubmit={submitSpotify} className="flow">
                <label className="field">
                  <span>Spotify track URL</span>
                  <input
                    value={spotifyUrl}
                    onChange={(e) => setSpotifyUrl(e.target.value)}
                    placeholder={demoSpotifyUrl}
                  />
                </label>
                <button disabled={loading} className="submit" type="submit">
                  {loading ? 'Analyzing…' : 'Analyze Spotify track'}
                </button>
              </form>
            )}

            {error && <p className="error">{error}</p>}
            {result ? <Results result={result} /> : <EmptyState />}
          </>
        ) : (
          /* Artists View */
          <div className="artist-view">
            <div className="artist-input-card">
              <div className="card-header">
                <div className="icon">🎤</div>
                <div>
                  <h3>Analyze Artist</h3>
                  <p>Paste a Spotify artist profile URL</p>
                </div>
              </div>

              <form onSubmit={submitArtist} className="artist-form">
                <input
                  type="text"
                  value={artistUrl}
                  onChange={(e) => setArtistUrl(e.target.value)}
                  placeholder={demoArtistUrl}
                  className="artist-input"
                />
                <button type="submit" disabled={artistLoading} className="submit">
                  {artistLoading ? 'Analyzing…' : 'Analyze Artist'}
                </button>
              </form>
            </div>

            {artistError && <p className="error">{artistError}</p>}

            {artistLoading && (
              <div className="loading-state">
                <div className="spinner" />
                <p>Fetching artist profile, top tracks, and audience data…</p>
              </div>
            )}

            {artistResult && <ArtistResults artistResult={artistResult} />}
          </div>
        )}
      </section>
    </main>
  );
}

// Shared components
function ArtistResults({ artistResult }: { artistResult: ArtistResult }) {
  const audio = artistResult.audioProfile;
  const catalog = artistResult.albums?.length ? artistResult.albums : artistResult.chartmetricAlbums || [];
  const socials = Object.entries(artistResult.socialUrls || {});
  const scoreRows = Object.entries(artistResult.chartmetricScores || {}).filter(([, value]) => value !== null && value !== undefined && !Array.isArray(value)).slice(0, 6);
  const platformRows = Object.entries(artistResult.platformStats || {}).filter(([, value]) => typeof value === 'number' || typeof value === 'string').slice(0, 8);
  const bioMeta = [
    ['Location', [artistResult.city, artistResult.country].filter(Boolean).join(', ')],
    ['Growth', artistResult.growthLevel],
    ['Career trend', artistResult.careerTrend],
    ['Record label', artistResult.recordLabel],
    ...Object.entries(artistResult.team || {}).map(([key, value]) => [titleCase(key), value]),
  ].filter(([, value]) => value);

  return (
    <div className="artist-result-panel">
      <div className="result-header">
        <div className="artist-identity">
          {artistResult.imageUrl ? (
            <img className="artist-avatar" src={artistResult.imageUrl} alt={`${artistResult.name} Spotify profile`} />
          ) : (
            <div className="artist-avatar placeholder" aria-hidden="true">🎤</div>
          )}
          <div>
            <span className="eyebrow">Artist Intelligence</span>
            <h2>{artistResult.name}</h2>
            <div className="meta">
              {artistResult.monthlyListeners} • Popularity {artistResult.spotifyPopularity ?? artistResult.energy}/100
              {artistResult.genres.length ? ` • ${artistResult.genres.join(' • ')}` : ''}
            </div>
          </div>
        </div>
        <div className="header-actions">
          {artistResult.spotifyUrl && <a className="profile-link" href={artistResult.spotifyUrl} target="_blank" rel="noopener">Open Spotify</a>}
          <div className="mood-pill">{artistResult.mood}</div>
        </div>
      </div>

      <p className="summary">{artistResult.summary}</p>

      <div className="tagList">
        <span>Spotify: {artistResult.enrichment?.spotify ? 'live' : 'not connected'}</span>
        <span>Chartmetric: {artistResult.enrichment?.chartmetric ? 'live' : 'pending'}</span>
        {artistResult.chartmetricId && <span>CM ID: {artistResult.chartmetricId}</span>}
        {artistResult.country && <span>Country: {artistResult.country}</span>}
        {artistResult.careerStage && <span>Stage: {artistResult.careerStage}</span>}
        {artistResult.releaseYears?.[0] && <span>Latest release year: {artistResult.releaseYears[0]}</span>}
        {artistResult.moods?.slice(0, 4).map((mood) => <span key={`mood-${mood}`}>{titleCase(mood)}</span>)}
        {artistResult.activities?.slice(0, 4).map((activity) => <span key={`activity-${activity}`}>{titleCase(activity)}</span>)}
      </div>

      <div className="stats-grid">
        <Metric label="Spotify followers" value={formatCompact(artistResult.spotifyFollowers)} />
        <Metric label="Popularity" value={`${artistResult.spotifyPopularity ?? artistResult.energy}/100`} />
        <Metric label="Top tracks" value={artistResult.topTracksDetailed?.length || artistResult.topTracks.length} />
        <Metric label="Catalog items" value={catalog.length} />
        <Metric label="Avg tempo" value={audio?.tempoBpm ? `${Math.round(audio.tempoBpm)} BPM` : '—'} />
        <Metric label="Danceability" value={formatPercent(audio?.danceability ?? null)} />
        <Metric label="Energy" value={formatPercent(audio?.energy ?? null)} />
        <Metric label="Mood" value={formatPercent(audio?.valence ?? null)} />
      </div>

      {audio?.vibeDescription && <p className="insight-note">{audio.vibeDescription} Audio profile coverage: {audio.coverage || 0} top tracks.</p>}

      {(artistResult.biography || bioMeta.length > 0) && (
        <section className="detail-section">
          <h3>About this artist</h3>
          {artistResult.biography && <p>{artistResult.biography}</p>}
          {bioMeta.length > 0 && (
            <div className="meta-grid">
              {bioMeta.map(([label, value]) => <Metric key={String(label)} label={String(label)} value={String(value)} />)}
            </div>
          )}
        </section>
      )}

      {socials.length > 0 && (
        <section className="detail-section">
          <h3>Social & streaming profiles</h3>
          <div className="link-grid">
            {socials.map(([platform, url]) => <a key={platform} href={url} target="_blank" rel="noopener">{titleCase(platform)}</a>)}
          </div>
        </section>
      )}

      {(scoreRows.length > 0 || platformRows.length > 0) && (
        <section className="detail-section">
          <h3>Chartmetric platform intelligence</h3>
          <div className="meta-grid">
            {scoreRows.map(([label, value]) => <Metric key={label} label={titleCase(label)} value={formatCompact(value as number | string)} />)}
            {platformRows.map(([label, value]) => <Metric key={label} label={titleCase(label)} value={formatCompact(value as number | string)} />)}
          </div>
        </section>
      )}

      {artistResult.topTracksDetailed && artistResult.topTracksDetailed.length > 0 && (
        <section className="detail-section">
          <h3>Top Songs</h3>
          <div className="track-list-rich">
            {artistResult.topTracksDetailed.slice(0, 10).map((track, index) => (
              <a className="track-row" key={track.id || track.name} href={track.url} target="_blank" rel="noopener">
                <span>{index + 1}</span>
                {track.imageUrl && <img src={track.imageUrl} alt="" />}
                <div>
                  <strong>{track.name}</strong>
                  <small>{track.album || track.artists || 'Spotify track'}{track.releaseDate ? ` • ${track.releaseDate}` : ''}</small>
                </div>
                <em>{track.popularity ?? '—'}/100</em>
              </a>
            ))}
          </div>
        </section>
      )}

      {catalog.length > 0 && (
        <section className="detail-section">
          <h3>Recent releases</h3>
          <div className="album-grid">
            {catalog.slice(0, 8).map((album, index) => (
              <a className="album-card-mini" key={album.id || `${album.name}-${index}`} href={album.url} target="_blank" rel="noopener">
                {album.imageUrl && <img src={album.imageUrl} alt="" />}
                <strong>{album.name}</strong>
                <small>{album.releaseDate || album.type || 'Release'}</small>
              </a>
            ))}
          </div>
        </section>
      )}

      {((artistResult.socialContent?.topPosts?.length || 0) > 0 || (artistResult.socialContent?.topReels?.length || 0) > 0) && (
        <section className="detail-section">
          <h3>Top Instagram content</h3>
          <div className="content-grid">
            {[...(artistResult.socialContent?.topPosts || []), ...(artistResult.socialContent?.topReels || [])].slice(0, 6).map((post, index) => (
              <a className="content-card" key={String(post.url || index)} href={String(post.url || '#')} target="_blank" rel="noopener">
                {post.thumbnailUrl && <img src={String(post.thumbnailUrl)} alt="" />}
                <strong>{post.views ? `${formatCompact(post.views as number)} views` : post.likes ? `${formatCompact(post.likes as number)} likes` : 'Instagram post'}</strong>
                <small>{String(post.caption || post.date || 'Chartmetric social signal').slice(0, 120)}</small>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value small">{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <section className="grid">
      <InfoCard title="Audio profile" body="Tags, scores, and creative positioning for the record." />
      <InfoCard title="Artist intelligence" body="Spotify metadata now, Chartmetric audience and social momentum next." />
      <InfoCard title="Campaign direction" body="Practical recommendations for release, playlisting, and content strategy." />
    </section>
  );
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <article className="card">
      <h3>{title}</h3>
      <p>{body}</p>
    </article>
  );
}

function Results({ result }: { result: AnalysisResult }) {
  return (
    <section className="panel results">
      <div className="resultHeader">
        <div className="track-identity">
          {result.track.imageUrl && <img className="track-artwork" src={result.track.imageUrl} alt={`${result.track.title} artwork`} />}
          <div>
            <span className="eyebrow">{result.source === 'audio' ? 'Uploaded audio' : 'Spotify analysis'}</span>
            <h2>{result.track.title}</h2>
            <p>{result.track.artist}</p>
            {(result.track.album || result.track.releaseDate || result.track.popularity !== undefined) && (
              <p className="meta">
                {[result.track.album, result.track.releaseDate, result.track.popularity !== undefined ? `Popularity ${result.track.popularity}/100` : null].filter(Boolean).join(' • ')}
              </p>
            )}
          </div>
        </div>
        {result.track.spotifyUrl && <a className="profile-link" href={result.track.spotifyUrl} target="_blank" rel="noopener">Open Spotify</a>}
        {result.file && (
          <div className="filePill">{result.file.mimeType || 'audio'} · {result.file.sizeMb}</div>
        )}
      </div>

      <p className="summary">{result.summary}</p>

      <div className="tagList">
        <span>Spotify: {result.enrichment.spotify ? 'live' : 'not connected'}</span>
        <span>Chartmetric: {result.enrichment.chartmetric ? 'live' : 'pending'}</span>
        {result.chartmetric?.chartmetricId && <span>CM ID: {result.chartmetric.chartmetricId}</span>}
        {result.chartmetric?.country && <span>Country: {result.chartmetric.country}</span>}
        {result.chartmetric?.careerStage && <span>Stage: {result.chartmetric.careerStage}</span>}
      </div>

      <div className="scoreGrid">
        {Object.entries(result.scores).map(([label, score]) => (
          <div className="score" key={label}>
            <span>{label.replace(/([A-Z])/g, ' $1')}</span>
            <strong>{score}</strong>
            <div><i style={{ width: `${score}%` }} /></div>
          </div>
        ))}
      </div>

      <div className="tagList">
        {result.tags.map((tag) => <span key={tag}>{tag}</span>)}
      </div>

      <div className="recommendations">
        <h3>Campaign recommendations</h3>
        <ol>
          {result.recommendations.map((item) => <li key={item}>{item}</li>)}
        </ol>
      </div>
    </section>
  );
}
