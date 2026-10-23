import { useEffect, useState } from 'react';
import type { Turn } from '../../api/types';
import { CONVERSATION, useMe } from '../../auth/session';

export type Said = Turn & { meta?: string };

const isTurn = (value: unknown): value is Said =>
  typeof value === 'object' &&
  value !== null &&
  ['user', 'assistant'].includes((value as Said).role) &&
  typeof (value as Said).content === 'string';

// Storage can be missing or blocked (private windows); the conversation then starts empty.
function load(key: string | null): Said[] {
  if (key === null) return [];
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(key) ?? '[]');
    return Array.isArray(saved) ? saved.filter(isTurn) : [];
  } catch {
    return [];
  }
}

// Kept for this browser tab and user, so leaving the page does not lose the conversation.
// The turns carry the key they belong to: after a change of user they are read again for the
// new key before anything is saved, and nothing is saved before the user is known.
export function useConversation() {
  const { data: me } = useMe();
  const key = me ? `${CONVERSATION}${me.name}` : null;
  const [kept, setKept] = useState(() => ({ key, said: load(key) }));
  const said = kept.key === key ? kept.said : load(key);
  useEffect(() => {
    if (kept.key === null || kept.key !== key) return;
    try {
      sessionStorage.setItem(kept.key, JSON.stringify(kept.said));
    } catch {
      // Not kept, but the conversation on screen still works.
    }
  }, [kept, key]);

  function setSaid(update: (current: Said[]) => Said[]) {
    setKept((current) => ({ key, said: update(current.key === key ? current.said : load(key)) }));
  }
  return [said, setSaid] as const;
}
