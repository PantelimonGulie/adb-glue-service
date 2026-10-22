import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { action } from '../../lib/labels';
import { row, stock } from '../../test/fixtures';
import { Address, address, lastQuery, renderPage, stubApi } from '../../test/render';
import { Activity } from './Activity';

const retry = { attempt: 1, delay_seconds: 0.5, problem: 'warehouse answered 503' };
const page = (rows: unknown[]) => ({ rows, total: rows.length, page: 1, per_page: 25 });
const api = {
  '/api/activity': page([row(1, 'retry_scheduled', retry)]),
  '/api/stock': stock,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderActivity(route = '/activity') {
  return renderPage(
    <>
      <Activity />
      <Address />
    </>,
    { route },
  );
}

it('each kind tab asks the log for that kind', async () => {
  const fetch = stubApi(api);
  renderActivity('/activity?page=2');
  const kinds = screen.getByRole('group', { name: 'What to show' });
  const tabs = {
    Orders: 'orders',
    Retries: 'retries',
    Problems: 'problems',
    Duplicates: 'duplicates',
    Stock: 'stock',
    Decisions: 'decisions',
    Everything: 'all',
  };

  for (const [name, kind] of Object.entries(tabs)) {
    await userEvent.click(within(kinds).getByRole('button', { name }));
    await waitFor(() => expect(lastQuery(fetch, '/api/activity')?.get('kind')).toBe(kind));
    expect(address().get('page')).toBeNull();
  }
});

it('explains each label on hover', async () => {
  stubApi(api);
  renderActivity();

  const tag = await screen.findByText(action('retry_scheduled').label);

  expect(tag).toHaveAttribute('title', action('retry_scheduled').explanation);
});

it('a chart bar link shows only its time window until the window is cleared', async () => {
  const fetch = stubApi(api);
  const since = '2026-10-22T14:00:00.000Z';
  const until = '2026-10-22T15:00:00.000Z';
  renderActivity(`/activity?since=${since}&until=${until}&kind=orders`);

  expect(await screen.findByText(/^Showing /)).toBeInTheDocument();
  expect(screen.queryByRole('group', { name: 'Time range' })).toBeNull();
  await waitFor(() => expect(lastQuery(fetch, '/api/activity')?.get('since')).toBe(since));
  expect(lastQuery(fetch, '/api/activity')?.get('until')).toBe(until);
  expect(lastQuery(fetch, '/api/activity')?.get('range')).toBeNull();

  await userEvent.click(screen.getByRole('button', { name: 'Show the whole range' }));

  expect(screen.getByRole('group', { name: 'Time range' })).toBeInTheDocument();
  expect(address().get('since')).toBeNull();
  expect(address().get('kind')).toBe('orders');
  await waitFor(() => expect(lastQuery(fetch, '/api/activity')?.get('range')).toBe('live'));
  expect(lastQuery(fetch, '/api/activity')?.get('since')).toBeNull();
});

it('marks rows that come from the sample history', async () => {
  const sample = row(2, 'order_cancelled', { was: 'failed', sample: true });
  stubApi({ ...api, '/api/activity': page([sample]) });
  renderActivity('/activity?range=month');

  expect(await screen.findByText('sample')).toBeInTheDocument();
  expect(screen.getByText('was failed')).toBeInTheDocument();
});

it('says it is loading before the first answer instead of showing an empty box', () => {
  vi.stubGlobal('fetch', () => new Promise(() => {}));
  renderActivity();

  expect(screen.getByRole('status')).toHaveTextContent('Loading…');
  expect(screen.queryByRole('region', { name: 'Activity' })).toBeNull();
});
