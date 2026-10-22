import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

const REFRESH_MS = 2000;

const AutoRefresh = createContext<{ on: boolean; setOn: (on: boolean) => void }>({
  on: true,
  setOn: () => {},
});

export function AutoRefreshProvider({ children }: { children: ReactNode }) {
  const [on, setOn] = useState(true);
  const value = useMemo(() => ({ on, setOn }), [on]);
  return <AutoRefresh.Provider value={value}>{children}</AutoRefresh.Provider>;
}

export const useAutoRefresh = () => useContext(AutoRefresh);

export const useRefreshInterval = () => (useAutoRefresh().on ? REFRESH_MS : false);
