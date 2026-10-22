import { useEffect, useRef, useState } from 'react';

// Scales a drawing of the given width to fill its frame, never below `min`; under that the
// frame scrolls instead.
export function useFitScale(width: number, min: number) {
  const frame = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      setScale(Math.max(min, entry.contentRect.width / width));
    });
    observer.observe(frame.current!);
    return () => observer.disconnect();
  }, [width, min]);
  return [frame, scale] as const;
}
