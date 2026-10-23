import { useEffect, useState } from 'react';
import type { Turn } from '../../api/types';
import { useMe } from '../../auth/session';

export type Said = Turn & { meta?: string };

const isTurn = (value: unknown): value is Said =>
  typeof value === 'object' &&
  value !== null &&
  ['user', 'assistant'].includes((value as Said).role) &&
  typeof (value as Said).content === 'string';

// Storage can be missing or blocked (private windows); the conversation then starts empty.
function load(key: string): Said[] {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(key) ?? '[]');
    return Array.isArray(saved) ? saved.filter(isTurn) : [];
  } catch {
    return [];
  }
}

// Kept for this browser tab and user, so leaving the page does not lose the conversation.
export function useConversation() {
  const { data: me } = useMe();
  const key = `glue.conversation.${me?.name ?? ''}`;
  const [said, setSaid] = useState(() => load(key));
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(said));
    } catch {
      // Not kept, but the conversation on screen still works.
    }
  }, [key, said]);
  return [said, setSaid] as const;
}
