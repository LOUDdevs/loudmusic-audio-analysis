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

interface ArtistResult {
  name: string;
  artistId: string;
  genres: string[];
  monthlyListeners: string;
  topTracks: string[];
  summary: string;
  mood: string;
  energy: number;
  enrichment?: {
    spotify: boolean;
    chartmetric: boolean;
  };
  chartmetricId?: string;
  country?: string;
  careerStage?: string;
  socialUrls?: Record<string, string>;
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

            {artistResult && (
              <div className="artist-result-panel">
                <div className="result-header">
                  <div>
                    <span className="eyebrow">Spotify Artist</span>
                    <h2>{artistResult.name}</h2>
                    <div className="meta">
                      {artistResult.monthlyListeners} monthly listeners • {artistResult.genres.join(' • ')}
                    </div>
                  </div>
                  <div className="mood-pill">{artistResult.mood}</div>
                </div>

                <p className="summary">{artistResult.summary}</p>

                <div className="tagList">
                  <span>Spotify: {artistResult.enrichment?.spotify ? 'live' : 'not connected'}</span>
                  <span>Chartmetric: {artistResult.enrichment?.chartmetric ? 'live' : 'pending'}</span>
                  {artistResult.chartmetricId && <span>CM ID: {artistResult.chartmetricId}</span>}
                  {artistResult.country && <span>Country: {artistResult.country}</span>}
                  {artistResult.careerStage && <span>Stage: {artistResult.careerStage}</span>}
                </div>

                <div className="stats-grid">
                  <div className="stat">
                    <div className="label">Energy</div>
                    <div className="value">{artistResult.energy}</div>
                  </div>
                  <div className="stat">
                    <div className="label">Top Tracks</div>
                    <div className="value small">{artistResult.topTracks.length}</div>
                  </div>
                  <div className="stat">
                    <div className="label">Genres</div>
                    <div className="value small">{artistResult.genres.length}</div>
                  </div>
                </div>

                <div className="top-tracks">
                  <h4>Top Tracks</h4>
                  <ul>
                    {artistResult.topTracks.map((track, index) => (
                      <li key={index}>{track}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

// Shared components
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
        <div>
          <span className="eyebrow">{result.source === 'audio' ? 'Uploaded audio' : 'Spotify analysis'}</span>
          <h2>{result.track.title}</h2>
          <p>{result.track.artist}</p>
        </div>
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
