import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { ReviewItem } from '../../api/types';
import { assistant, order, overview, reviewItem, stock } from '../../test/fixtures';
import {
  Address,
  address,
  failure,
  lastQuery,
  renderPage,
  stubApi,
  users,
} from '../../test/render';
import { Review } from './Review';

const outage = (id: number): ReviewItem => ({
  ...reviewItem,
  id,
  kind: 'order_failed',
  cause: 'outage',
  order_id: `shop-${id}`,
  order: { ...order, order_id: `shop-${id}`, channel: 'shop' },
  reason: 'HTTP 503 after 5 attempts',
});
const review = {
  items: [1, 2, 3, 4].map(outage).concat(reviewItem),
  groups: [
    { cause: 'outage', count: 4 },
    { cause: 'soldout', count: 1 },
  ],
};
const api = {
  '/api/review': review,
  '/api/overview': { ...overview, open_reviews: 5 },
  '/api/assistant': assistant,
  '/api/stock': stock,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderReview(route = '/review', fetchApi: Record<string, unknown> = api) {
  const fetch = stubApi(fetchApi);
  renderPage(
    <>
      <Review />
      <Address />
    </>,
    { user: users.operator, route },
  );
  return fetch;
}

it('groups open orders by cause in plain words, a few of each', async () => {
  renderReview();

  const outages = await screen.findByRole('region', { name: 'Warehouse outage' });
  expect(within(outages).getByText(/4 orders · the warehouse did not answer/)).toBeInTheDocument();
  expect(within(outages).getAllByRole('article')).toHaveLength(3);
  expect(within(outages).getByText(/and 1 more with the same cause/)).toBeInTheDocument();
  const soldOut = screen.getByRole('region', { name: 'Sold out' });
  expect(within(soldOut).getAllByRole('article')).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: /^Retry all/ })).toHaveLength(1);
  expect(await screen.findByRole('button', { name: 'All open (5)' })).toBeInTheDocument();
});

it('shows every order of one cause', async () => {
  renderReview();

  await userEvent.click(await screen.findByRole('button', { name: 'Show all 4' }));

  expect(address().get('show')).toBe('outage');
  expect(screen.getAllByRole('article')).toHaveLength(4);
  expect(screen.queryByRole('region', { name: 'Sold out' })).toBeNull();
});

it('shows why the warehouse outage could not be retried', async () => {
  const down = failure(409, 'The warehouse is still not answering');
  renderReview('/review', { ...api, '/api/review/retry-all': down });

  await userEvent.click(await screen.findByRole('button', { name: 'Retry all 4' }));

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('The warehouse is still not answering');
});

it('cannot retry the outage while the warehouse is not answering', async () => {
  const down = { ok: false, state: 'Not responding', latency_ms: null };
  const systems = { ...overview.systems, warehouse: down };
  renderReview('/review', { ...api, '/api/overview': { ...overview, systems } });

  const retryAll = await screen.findByRole('button', { name: 'Retry all 4' });
  await waitFor(() => expect(retryAll).toBeDisabled());
  expect(retryAll).toHaveAttribute('title', 'Bucharest warehouse is not answering');
});

it('lists decided items, newest first as the API sends them', async () => {
  const decided = { ...reviewItem, status: 'decided', action: 'dismiss', decided_by: 'admin' };
  const decidedAt = '2026-10-22T10:45:00.000+00:00';
  const fetch = renderReview('/review?show=decided', {
    ...api,
    '/api/review': { items: [{ ...decided, decided_at: decidedAt, allowed: [] }], groups: [] },
  });

  expect(await screen.findByText('Closed without changes')).toBeInTheDocument();
  expect(lastQuery(fetch, '/api/review')?.get('status')).toBe('decided');
});

it('says when nothing is waiting', async () => {
  renderReview('/review', { ...api, '/api/review': { items: [], groups: [] } });

  expect(await screen.findByText('Nothing is waiting for a decision')).toBeInTheDocument();
});

it('shows why the review queue could not be loaded', async () => {
  renderReview('/review', { ...api, '/api/review': failure(500, 'The database is busy') });

  expect(await screen.findByText('The review queue could not be loaded')).toBeInTheDocument();
  expect(screen.getByText('The database is busy')).toBeInTheDocument();
});
