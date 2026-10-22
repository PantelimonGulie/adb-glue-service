import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { SignIn } from './auth/SignIn/SignIn';
import { EmptyState } from './components/EmptyState/EmptyState';
import { AppShell } from './layout/AppShell/AppShell';
import { Activity } from './pages/Activity/Activity';
import { Assistant } from './pages/Assistant/Assistant';
import { Demo } from './pages/Demo/Demo';
import { OrderDetail } from './pages/OrderDetail/OrderDetail';
import { Orders } from './pages/Orders/Orders';
import { Overview } from './pages/Overview/Overview';
import { Review } from './pages/Review/Review';
import { Rules } from './pages/Rules/Rules';
import { Settings } from './pages/Settings/Settings';
import { Stock } from './pages/Stock/Stock';
import { Users } from './pages/Users/Users';

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
        <Route path="orders" element={<Orders />} />
        <Route path="orders/:id" element={<OrderDetail />} />
        <Route path="stock" element={<Stock />} />
        <Route path="review" element={<Review />} />
        <Route path="activity" element={<Activity />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="demo" element={<Demo />} />
        <Route path="rules" element={<Rules />} />
        <Route path="settings" element={<Settings />} />
        <Route path="users" element={<Users />} />
        <Route path="*" element={<EmptyState title="This page does not exist" />} />
      </Route>
    </Routes>
  );
}
