import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { useMe } from '../../auth/session';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorBoundary } from '../../components/ErrorBoundary/ErrorBoundary';
import { setTimeZone } from '../../lib/format';
import { Header } from '../Header/Header';
import { SampleBanner } from '../SampleBanner/SampleBanner';
import { Sidebar } from '../Sidebar/Sidebar';
import styles from './AppShell.module.css';

export function AppShell() {
  const { data: me, error } = useMe();
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  if (!me) {
    // A 401 has already sent the browser to the sign-in page.
    const signingIn = error instanceof ApiError && error.status === 401;
    return error && !signingIn ? (
      <EmptyState title="The dashboard could not reach Glue">
        {error.message} Reload the page in a moment.
      </EmptyState>
    ) : null;
  }
  // Set while rendering, not in an effect: the pages below format times in this same render.
  setTimeZone(me.timezone);
  return (
    <div className={styles.shell}>
      <Header me={me} />
      <div className={styles.body}>
        <Sidebar />
        <main className={styles.main}>
          <SampleBanner />
          <ErrorBoundary resetKey={pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
