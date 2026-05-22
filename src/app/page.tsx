'use client';

import { FormEvent, useMemo, useState } from 'react';
import { buildDemoAudioAnalysis, buildDemoSpotifyAnalysis, type AnalysisResult } from '@/lib/analysis';
import { parseSpotifyTrackId } from '@/lib/spotify';

type Mode = 'audio' | 'spotify';

const demoSpotifyUrl = 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC';

export default function Home() {
  const [mode, setMode] = useState<Mode>('audio');
  const [file, setFile] = useState<File | null>(null);
  const [spotifyUrl, setSpotifyUrl] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const statusCopy = useMemo(() => {
    if (loading) return 'Analyzing signal, metadata, and campaign fit…';
    if (result) return 'Analysis complete. Use this profile to plan the next campaign move.';
    return 'Upload audio or paste a Spotify track to generate an artist-ready profile.';
  }, [loading, result]);

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

  return (
    <main className="shell">
      <section className="hero">
        <div className="eyebrow">LOUDmusic Intelligence MVP</div>
        <h1>Audio Analysis</h1>
        <p>Discover what makes a record move — upload audio or analyze a Spotify track, then turn the output into campaign direction.</p>
        <div className="heroActions">
          <a href="#analyzer" className="primaryLink">Start analysis</a>
          <span>{statusCopy}</span>
        </div>
      </section>

      <section id="analyzer" className="panel analyzer">
        <div className="tabs" role="tablist" aria-label="Analysis mode">
          <button className={mode === 'audio' ? 'active' : ''} onClick={() => setMode('audio')} type="button">Upload audio</button>
          <button className={mode === 'spotify' ? 'active' : ''} onClick={() => setMode('spotify')} type="button">Spotify track</button>
        </div>

        {mode === 'audio' ? (
          <form onSubmit={submitAudio} className="flow">
            <label className="dropzone">
              <span>Drop in an MP3, WAV, or FLAC</span>
              <strong>{file ? file.name : 'Choose audio file'}</strong>
              <input accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/flac,audio/x-flac" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            <button disabled={loading} className="submit" type="submit">{loading ? 'Analyzing…' : 'Analyze audio'}</button>
          </form>
        ) : (
          <form onSubmit={submitSpotify} className="flow">
            <label className="field">
              <span>Spotify track URL</span>
              <input value={spotifyUrl} onChange={(event) => setSpotifyUrl(event.target.value)} placeholder={demoSpotifyUrl} />
            </label>
            <button disabled={loading} className="submit" type="submit">{loading ? 'Analyzing…' : 'Analyze Spotify track'}</button>
          </form>
        )}

        {error ? <p className="error">{error}</p> : null}
      </section>

      {result ? <Results result={result} /> : <EmptyState />}
    </main>
  );
}

function EmptyState() {
  return (
    <section className="grid">
      <InfoCard title="Audio profile" body="Tags, scores, and creative positioning for the record." />
      <InfoCard title="Artist intelligence" body="Spotify metadata now, Chartmetric and social enrichment next." />
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
