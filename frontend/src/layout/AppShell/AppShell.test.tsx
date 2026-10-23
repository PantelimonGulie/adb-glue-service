import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderPage, silenceRenderErrors, users } from '../../test/render';
import { AppShell } from './AppShell';

const working = { ok: true, state: 'ok', latency_ms: 3 };
const overview = {
  counters: { received: 0, duplicates: 0, reserved: 0, retries: 0, failed: 0 },
  previous: null,
  systems: { shop: working, emag: working, warehouse: working },
  open_reviews: 2,
  review_groups: [],
  latest: [],
};

function Broken(): never {
  throw new Error('render failed');
}

beforeEach(silenceRenderErrors);

beforeEach(() => {
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(overview)))),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it('keeps the header and the menu when a page crashes', async () => {
  renderPage(
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Broken />} />
      </Route>
    </Routes>,
    { user: users.admin },
  );

  expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong on this page');
  expect(screen.getByRole('button', { name: 'admin · admin' })).toBeInTheDocument();
  expect(await screen.findByRole('link', { name: /Review queue\s*2/ })).toBeInTheDocument();
});
