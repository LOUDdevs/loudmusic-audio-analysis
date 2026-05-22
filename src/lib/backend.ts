export const runtime = 'nodejs';

export async function proxyToTaggingBackend(path: string, init: RequestInit): Promise<Response | null> {
  const baseUrl = process.env.AUDIO_TAGGING_API_URL?.replace(/\/$/, '');
  if (!baseUrl) return null;

  const target = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
  return fetch(target, init);
}
