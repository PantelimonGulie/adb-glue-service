import { useCallback, useState } from 'react';
import { useEvents } from '../../api/hooks';
import { dotsForRows, type LiveDots } from './dots';

// Each poll adds its dots; a dot removes itself when its animation ends.
export function useLiveDots() {
  const { data } = useEvents();
  const [poll, setPoll] = useState(data);
  const [live, setLive] = useState<LiveDots>({ dots: [], summary: null });
  if (data !== poll) {
    setPoll(data);
    const next = dotsForRows(data?.rows ?? []);
    setLive((current) => ({ dots: [...current.dots, ...next.dots], summary: next.summary }));
  }
  const finish = useCallback((id: number) => {
    setLive((current) => ({ ...current, dots: current.dots.filter((dot) => dot.id !== id) }));
  }, []);
  return { ...live, finish };
}
