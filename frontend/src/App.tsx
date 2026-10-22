import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { SignIn } from './auth/SignIn/SignIn';
import { EmptyState } from './components/EmptyState/EmptyState';
import { AppShell } from './layout/AppShell/AppShell';
import { Overview } from './pages/Overview/Overview';
import { Placeholder } from './pages/Placeholder/Placeholder';

// The charts library is large and only the Flow page uses it, so it loads with that page.
const Flow = lazy(() => import('./pages/Flow/Flow').then((page) => ({ default: page.Flow })));

export function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route
          path="flow"
          element={
            <Suspense fallback={null}>
              <Flow />
            </Suspense>
          }
        />
        <Route path="orders" element={<Placeholder title="Orders" />} />
        <Route path="orders/:id" element={<Placeholder title="Order" />} />
        <Route path="stock" element={<Placeholder title="Stock" />} />
        <Route path="review" element={<Placeholder title="Review queue" />} />
        <Route path="activity" element={<Placeholder title="Activity log" />} />
        <Route path="assistant" element={<Placeholder title="Assistant" />} />
        <Route path="demo" element={<Placeholder title="Demo controls" />} />
        <Route path="rules" element={<Placeholder title="Rules" />} />
        <Route path="settings" element={<Placeholder title="Settings" />} />
        <Route path="users" element={<Placeholder title="Users and roles" />} />
        <Route path="*" element={<EmptyState title="This page does not exist" />} />
      </Route>
    </Routes>
  );
}
