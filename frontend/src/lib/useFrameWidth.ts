import { useLayoutEffect, useRef, useState } from 'react';

// The same width ResizeObserver reports: inside the padding.
function contentWidth(element: HTMLElement): number {
  const { paddingLeft, paddingRight } = getComputedStyle(element);
  return element.clientWidth - parseFloat(paddingLeft) - parseFloat(paddingRight);
}

// The width an element can use. It is measured before the first paint, so a phone never draws
// at `initial`; that stays only where nothing can be measured (a hidden element, tests).
export function useFrameWidth(initial: number) {
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(initial);
  useLayoutEffect(() => {
    const update = (measured: number) => {
      if (measured > 0) setWidth(measured);
    };
    update(contentWidth(frame.current!));
    const observer = new ResizeObserver(([entry]) => {
      update(entry.contentRect.width);
    });
    observer.observe(frame.current!);
    return () => observer.disconnect();
  }, []);
  return [frame, width] as const;
}
