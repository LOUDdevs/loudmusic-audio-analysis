import { buildDemoAudioAnalysis } from '@/lib/analysis';
import { proxyToTaggingBackend } from '@/lib/backend';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get('file');

  if (!(file instanceof File)) {
    return Response.json({ error: 'Upload an MP3, WAV, or FLAC file.' }, { status: 400 });
  }

  const allowed = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/flac', 'audio/x-flac'];
  if (file.type && !allowed.includes(file.type)) {
    return Response.json({ error: 'Unsupported file type. Use MP3, WAV, or FLAC.' }, { status: 400 });
  }

  const proxied = await proxyToTaggingBackend('/analyze/audio', {
    method: 'POST',
    body: formData,
  });

  if (proxied) {
    return proxied;
  }

  return Response.json(buildDemoAudioAnalysis(file.name, file.size, file.type));
}
