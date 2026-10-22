import { useEffect, useRef, useState } from 'react';

// The width an element can use; it is `initial` until measured.
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
