import { useSyncExternalStore } from 'react';

const NARROW = '(max-width: 899px)';

function subscribe(notify: () => void) {
  const query = window.matchMedia(NARROW);
  query.addEventListener('change', notify);
  return () => query.removeEventListener('change', notify);
}

export const useNarrow = () =>
  useSyncExternalStore(subscribe, () => window.matchMedia(NARROW).matches);
