import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { vi } from 'vitest';
import type { User } from '../api/types';
import { meKey } from '../auth/session';

const timezone = 'Europe/Bucharest';

export const users: Record<User['role'], User> = {
  viewer: { name: 'viewer', role: 'viewer', permissions: ['view'], timezone },
  operator: {
    name: 'operator',
    role: 'operator',
    permissions: ['ask', 'decide', 'view'],
    timezone,
  },
  admin: {
    name: 'admin',
    role: 'admin',
    permissions: ['ask', 'decide', 'demo', 'rules', 'settings', 'view'],
    timezone,
  },
};

export function testClient(user?: User) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (user) client.setQueryData(meKey, user);
  return client;
}

export function withClient(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

export function renderPage(
  ui: ReactElement,
  { user, route = '/' }: { user?: User; route?: string } = {},
) {
  const Wrapper = withClient(testClient(user));
  return render(
    <Wrapper>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </Wrapper>,
  );
}

// Answers by path, ignoring the query; any other path is a 404. A failure() answers with its error;
// any other function answers with the Response it makes from the request.
export function stubApi(answers: Record<string, unknown>) {
  const fetch = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>((path, init) => {
    const body = answers[new URL(path, 'http://glue').pathname];
    if (typeof body === 'function') return Promise.resolve(body(init) as Response);
    const response =
      body === undefined
        ? new Response('{"detail":"Not found"}', { status: 404 })
        : new Response(JSON.stringify(body));
    return Promise.resolve(response);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

export const failure = (status: number, detail: string) => () =>
  new Response(JSON.stringify({ detail }), { status });

// The JSON body of the newest request to `path` that sent one.
export function lastBody(fetch: ReturnType<typeof stubApi>, path: string) {
  const call = fetch.mock.calls.filter(([url, init]) => url === path && init?.body).at(-1);
  return call && JSON.parse(String(call[1]?.body));
}

// The query string of the newest request to `path`.
export function lastQuery(fetch: ReturnType<typeof stubApi>, path: string) {
  const urls = fetch.mock.calls.map(([url]) => new URL(url, 'http://glue'));
  return urls.filter((url) => url.pathname === path).at(-1)?.searchParams;
}

// Shows the page's address, so a test can read the filters a page keeps in it.
export function Address() {
  const { search } = useLocation();
  return <p aria-label="Address">{search}</p>;
}

export const address = () =>
  new URLSearchParams(screen.getByLabelText('Address').textContent ?? '');

// React reports a caught render error twice: on the console and as a window error event.
export function silenceRenderErrors() {
  const swallow = (event: ErrorEvent) => event.preventDefault();
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  window.addEventListener('error', swallow);
  return () => {
    window.removeEventListener('error', swallow);
    consoleError.mockRestore();
  };
}
