import { useEffect, useRef, useState } from 'react';

// The width the map can use; it starts at the drawing's own width until measured.
export function useFrameWidth(initial: number) {
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      setWidth(entry.contentRect.width);
    });
    observer.observe(frame.current!);
    return () => observer.disconnect();
  }, []);
  return [frame, width] as const;
}
