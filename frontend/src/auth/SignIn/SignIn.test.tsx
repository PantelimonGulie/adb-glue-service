import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderPage, users } from '../../test/render';
import { SignIn } from './SignIn';

function respond(status: number, body: unknown) {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

async function signIn(next: string, password = 'admin') {
  renderPage(
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/orders" element={<p>Orders page</p>} />
      <Route path="/" element={<p>Overview page</p>} />
    </Routes>,
    { route: `/sign-in?next=${encodeURIComponent(next)}` },
  );
  await userEvent.type(screen.getByLabelText('User name'), 'admin');
  await userEvent.type(screen.getByLabelText('Password'), password);
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

beforeEach(() => {
  vi.stubGlobal('location', { pathname: '/sign-in', search: '', assign: vi.fn() });
});

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

it('signs in and opens the page the user came from', async () => {
  const fetch = respond(200, users.admin);

  await signIn('/orders');

  expect(await screen.findByText('Orders page')).toBeInTheDocument();
  const [path, init] = fetch.mock.calls[0];
  expect([path, init.method, init.body]).toEqual([
    '/api/session',
    'POST',
    '{"username":"admin","password":"admin"}',
  ]);
});

it('shows why signing in failed', async () => {
  respond(401, { detail: 'Wrong user name or password.' });

  await signIn('/orders', 'wrong');

  expect(await screen.findByText('Wrong user name or password.')).toBeInTheDocument();
  expect(screen.queryByText('Orders page')).toBeNull();
});

it('never leaves the dashboard after signing in', async () => {
  respond(200, users.admin);

  await signIn('//elsewhere.example/steal');

  expect(await screen.findByText('Overview page')).toBeInTheDocument();
});

it('says the session ended when Glue signed the user out', () => {
  renderPage(<SignIn />, { route: '/sign-in?next=%2Forders&ended=1' });

  expect(screen.getByRole('status')).toHaveTextContent('Your session ended. Sign in again.');
});

it('says nothing about a session on a first visit', () => {
  renderPage(<SignIn />, { route: '/sign-in?next=%2Forders' });

  expect(screen.queryByText(/session ended/)).toBeNull();
});

it('signing in forgets the conversation a previous user left in this tab', async () => {
  respond(200, users.admin);
  sessionStorage.setItem('glue.conversation.operator', '[{"role":"user","content":"hi"}]');

  await signIn('/orders');

  expect(await screen.findByText('Orders page')).toBeInTheDocument();
  expect(sessionStorage.getItem('glue.conversation.operator')).toBeNull();
});
