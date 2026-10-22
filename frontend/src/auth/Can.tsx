import type { ReactNode } from 'react';
import type { Permission } from '../api/types';
import { useMe } from './session';

interface Props {
  permission: Permission;
  children: ReactNode;
  fallback?: ReactNode;
}

export function Can({ permission, children, fallback = null }: Props) {
  const { data: me } = useMe();
  const allowed = me?.permissions.includes(permission) ?? false;
  return <>{allowed ? children : fallback}</>;
}
