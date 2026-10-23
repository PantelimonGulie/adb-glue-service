import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { User } from '../api/types';

export const meKey = ['me'];
export const CONVERSATION = 'glue.conversation.';

// The assistant keeps each user's conversation for the browser tab. Signing in or out forgets
// all of them, so the next person at a shared browser cannot read the last one's.
function forgetConversations() {
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith(CONVERSATION)) sessionStorage.removeItem(key);
    }
  } catch {
    // Storage is blocked, so nothing was kept.
  }
}

export const useMe = () =>
  useQuery({ queryKey: meKey, queryFn: () => api<User>('/api/me'), staleTime: Infinity });

export function useSignIn() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      api<User>('/api/session', { method: 'POST', body: credentials }),
    onSuccess: (user) => {
      client.clear();
      forgetConversations();
      client.setQueryData(meKey, user);
    },
  });
}

export const useSignOut = () =>
  useMutation({
    mutationFn: () => api<undefined>('/api/session', { method: 'DELETE' }),
    // A full page load forgets everything the previous user had loaded.
    onSuccess: () => {
      forgetConversations();
      window.location.assign('/sign-in');
    },
  });
