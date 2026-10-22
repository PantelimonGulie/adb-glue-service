import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { User } from '../api/types';

export const meKey = ['/api/me'];

export const useMe = () =>
  useQuery({ queryKey: meKey, queryFn: () => api<User>('/api/me'), staleTime: Infinity });

export function useSignIn() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      api<User>('/api/session', { method: 'POST', body: credentials }),
    onSuccess: (user) => {
      client.clear();
      client.setQueryData(meKey, user);
    },
  });
}

export const useSignOut = () =>
  useMutation({
    mutationFn: () => api<undefined>('/api/session', { method: 'DELETE' }),
    // A full page load forgets everything the previous user had loaded.
    onSuccess: () => window.location.assign('/sign-in'),
  });
