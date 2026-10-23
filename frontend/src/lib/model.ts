import type { Assistant } from '../api/types';
import type { Tone } from './labels';

interface ModelState {
  label: string;
  tone: Tone;
  // Why the model cannot answer yet; undefined once it is ready.
  notice?: string;
}

export function modelState({ status, progress }: Assistant['model']): ModelState {
  const percent = `${Math.round(progress * 100)}%`;
  switch (status) {
    case 'ready':
      return { label: 'Ready', tone: 'green' };
    case 'downloading':
      return {
        label: `Downloading the local model · ${percent}`,
        tone: 'amber',
        notice: `Downloading the local model, about 2 GB, one time · ${percent}`,
      };
    case 'missing':
      return {
        label: 'Not downloaded yet',
        tone: 'amber',
        notice: 'The local model is not downloaded yet. Glue keeps trying in the background.',
      };
    case 'offline':
      return {
        label: 'Not answering',
        tone: 'red',
        notice: 'The local model server is not answering. Start Ollama, or its Docker container.',
      };
  }
}
