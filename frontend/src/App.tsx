import { Route, Routes } from 'react-router-dom';
import { SignIn } from './auth/SignIn/SignIn';
import { EmptyState } from './components/EmptyState/EmptyState';
import { AppShell } from './layout/AppShell/AppShell';
import { Placeholder } from './pages/Placeholder/Placeholder';

export function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route element={<AppShell />}>
        <Route index element={<Placeholder title="Overview" />} />
        <Route path="flow" element={<Placeholder title="Flow" />} />
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
