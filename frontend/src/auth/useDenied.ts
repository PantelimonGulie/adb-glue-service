import type { Permission } from '../api/types';
import { useMe } from './session';

// Why the signed-in user cannot do something, or undefined when they can.
export function useDenied(permission: Permission): string | undefined {
  const { data: me } = useMe();
  if (me?.permissions.includes(permission)) return undefined;
  return `Your role (${me?.role ?? 'unknown'}) cannot do this`;
}
