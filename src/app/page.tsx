'use client';

import { FormEvent, useState } from 'react';
import { buildDemoAudioAnalysis, buildDemoSpotifyAnalysis, type AnalysisResult } from '@/lib/analysis';
import { parseSpotifyTrackId } from '@/lib/spotify';

type View = 'tracks' | 'artists';
type TrackMode = 'audio' | 'spotify';

const demoSpotifyUrl = 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC';
const demoArtistUrl = 'https://open.spotify.com/artist/2nWo31Kvu9rMSVfhuUVUw3';

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
  const [artistResult, setArtistResult] = useState<any>(null);
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
    window.setTimeout(() => {
      setResult(buildDemoAudioAnalysis(file.name, file.size, file.type));
      setLoading(false);
    }, 650);
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
    window.setTimeout(() => {
      setResult(buildDemoSpotifyAnalysis(trackId));
      setLoading(false);
    }, 650);
  }

  async function submitArtist(event: FormEvent) {
    event.preventDefault();
    if (!artistUrl.trim()) {
      setArtistError('Please paste a Spotify artist URL.');
      return;
    }
    setArtistLoading(true);
    setArtistError('');
    setArtistResult(null);

    // Demo simulation for now
    window.setTimeout(() => {
      setArtistResult({
        name: 'The Weeknd',
        spotifyUrl: artistUrl,
        genres: ['R&B', 'Pop', 'Alternative'],
        monthlyListeners: '112.4M',
        topTracks: ['Blinding Lights', 'Save Your Tears', 'Starboy'],
        summary: 'The Weeknd continues to dominate global streaming with a signature blend of dark R&B, atmospheric production, and cinematic songwriting.',
      });
      setArtistLoading(false);
    }, 900);
  }

  return (
    <main className="shell">
      {/* Header with Navigation */}
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

      {/* Hero Section */}
      <section className="hero">
        <div className="eyebrow">LOUDmusic Intelligence MVP</div>
        <h1>{view === 'tracks' ? 'Track Analysis' : 'Artist Analysis'}</h1>
        <p>
          {view === 'tracks'
            ? 'Upload audio or analyze a Spotify track, then turn Spotify + Chartmetric intelligence into campaign direction.'
            : 'Paste any Spotify artist profile to generate deep audience, style, and campaign insights.'}
        </p>
      </section>

      {/* Main Analyzer Section */}
      <section id="analyzer" className="panel analyzer">
        {view === 'tracks' ? (
          <>
            <div className="tabs" role="tablist" aria-label="Track analysis mode">
              <button
                className={trackMode === 'audio' ? 'active' : ''}
                onClick={() => setTrackMode('audio')}
                type="button"
              >
                Upload audio
              </button>
              <button
                className={trackMode === 'spotify' ? 'active' : ''}
                onClick={() => setTrackMode('spotify')}
                type="button"
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
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
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
                    onChange={(event) => setSpotifyUrl(event.target.value)}
                    placeholder={demoSpotifyUrl}
                  />
                </label>
                <button disabled={loading} className="submit" type="submit">
                  {loading ? 'Analyzing…' : 'Analyze Spotify track'}
                </button>
              </form>
            )}

            {error ? <p className="error">{error}</p> : null}

            {result ? <Results result={result} /> : <EmptyState />}
          </>
        ) : (
          /* Artists View */
          <div className="artist-analysis">
            <div className="upload-card">
              <div className="upload-icon">🎤</div>
              <div className="upload-title">Paste artist Spotify URL</div>
              <div className="upload-description">
                Spotify artist profile • Enter URL and click Analyze
              </div>

              <form onSubmit={submitArtist} className="ata-artist-form">
                <input
                  type="text"
                  value={artistUrl}
                  onChange={(e) => setArtistUrl(e.target.value)}
                  placeholder={demoArtistUrl}
                  className="url-input"
                />
                <button type="submit" disabled={artistLoading} className="submit-button">
                  {artistLoading ? 'Analyzing…' : '✨ Analyze Artist'}
                </button>
              </form>
            </div>

            {artistError && <div className="ata-error">{artistError}</div>}

            {artistLoading && (
              <div className="loading-section">
                <div className="loading-title">Analyzing Artist Profile</div>
                <div className="loading-text">Fetching artist data from Spotify + Chartmetric…</div>
              </div>
            )}

            {artistResult && (
              <div className="artist-result">
                <h2>{artistResult.name}</h2>
                <p className="artist-meta">
                  {artistResult.monthlyListeners} monthly listeners • {artistResult.genres.join(', ')}
                </p>
                <p className="summary">{artistResult.summary}</p>

                <div className="top-tracks">
                  <h3>Top Tracks</h3>
                  <ul>
                    {artistResult.topTracks.map((track: string, i: number) => (
                      <li key={i}>{track}</li>
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

// Reusable components
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
        {result.file ? <div className="filePill">{result.file.mimeType || 'audio'} · {result.file.sizeMb}</div> : null}
      </div>

      <p className="summary">{result.summary}</p>

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
        {result.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>

      <div className="recommendations">
        <h3>Campaign recommendations</h3>
        <ol>
          {result.recommendations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </div>
    </section>
  );
}
