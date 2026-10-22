import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { FlowMap } from '../../features/flowmap/FlowMap';
import styles from '../../features/flowmap/LiveDots.module.css';
import { analytics, overview, row, stock } from '../../test/fixtures';
import { renderPage, stubApi, testClient, withClient } from '../../test/render';
import { Overview } from './Overview';

const page = (rows: unknown[]) => ({ rows, total: rows.length, page: 1, per_page: 1 });
const api = {
  '/api/overview': overview,
  '/api/stock': stock,
  '/api/analytics': analytics,
  '/api/demo': { traffic: { running: true, speed: 'slow' }, faults: {}, sample_history: false },
  '/api/activity': page([row(40, 'signed_in')]),
  '/api/events': {
    rows: [row(41, 'event_received', { source: 'shop', type: 'order.placed' })],
    last_id: 41,
    more: false,
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderMap(ui: React.ReactElement) {
  const client = testClient();
  const Wrapper = withClient(client);
  const view = render(
    <Wrapper>
      <MemoryRouter>{ui}</MemoryRouter>
    </Wrapper>,
  );
  return { client, dots: () => view.container.getElementsByClassName(styles.dot) };
}

it('live mode animates new events as dots', async () => {
  stubApi(api);
  const { client, dots } = renderMap(<FlowMap mode="live" />);
  await waitFor(() => expect(client.getQueryData(['events'])).toEqual({ rows: [], lastId: 40 }));
  expect(dots()).toHaveLength(0);

  await act(() => client.refetchQueries({ queryKey: ['events'] }));

  await waitFor(() => expect(dots()).toHaveLength(1));
  expect(dots()[0]).toHaveStyle({ background: 'var(--tone-blue-dot)' });
});

it('period mode shows totals instead of dots', async () => {
  const fetch = stubApi(api);
  const { dots } = renderMap(<FlowMap mode="period" totals={analytics} />);

  expect(await screen.findByText('ORDERS · 2,180')).toBeInTheDocument();
  expect(screen.getByText('NOTIFY · FETCH · CONFIRM · 1,226')).toBeInTheDocument();
  expect(screen.getByText('SENT · 3,266')).toBeInTheDocument();
  expect(screen.getByText('3,246 reserved')).toBeInTheDocument();
  expect(dots()).toHaveLength(0);
  const paths = fetch.mock.calls.map(([path]) => path);
  expect(paths).not.toContainEqual(expect.stringMatching(/events/));
});

it('a warehouse that is not answering turns its line red', async () => {
  const down = { ok: false, state: 'Answering HTTP 503', latency_ms: 3 };
  const systems = { ...overview.systems, warehouse: down };
  stubApi({ ...api, '/api/overview': { ...overview, systems } });
  renderMap(<FlowMap mode="live" />);

  expect(await screen.findByText('NOT ANSWERING')).toHaveAttribute('data-bad', 'true');
  expect(screen.getByText('not answering')).toBeInTheDocument();
});

it('colours each change by whether more is good', async () => {
  stubApi(api);
  renderPage(<Overview />, { route: '/?range=today' });

  const reserved = await screen.findByText('+10% vs yesterday', {
    selector: '[data-counter=reserved] *',
  });
  expect(reserved).toHaveAttribute('data-good', 'true');
  expect(screen.getByText('+50% vs yesterday')).toHaveAttribute('data-good', 'false');
  expect(screen.getByText('-50% vs yesterday')).toHaveAttribute('data-good', 'true');
  expect(screen.getByText('same as yesterday')).not.toHaveAttribute('data-good');
});

it('groups what waits for a person and links to the review queue', async () => {
  stubApi(api);
  renderPage(<Overview />);

  expect(await screen.findByText('Warehouse outage')).toBeInTheDocument();
  const outage = '2 orders · the warehouse did not answer; safe to retry once it works';
  expect(screen.getByText(outage)).toBeInTheDocument();
  const link = (name: string) => screen.getByRole('link', { name });
  expect(link('Open review queue')).toHaveAttribute('href', '/review');
  expect(link('Open Flow details →')).toHaveAttribute('href', '/flow?range=live');
});

it('keeps the last counters on screen while a new range loads', async () => {
  const answer = stubApi(api);
  vi.stubGlobal('fetch', (path: string) =>
    path.includes('range=month') ? new Promise(() => {}) : answer(path),
  );
  renderPage(<Overview />, { route: '/?range=today' });
  expect(await screen.findByText('same as yesterday')).toBeInTheDocument();

  const ranges = screen.getByRole('group', { name: 'Time range' });
  await userEvent.click(within(ranges).getByRole('button', { name: 'This month' }));

  expect(screen.getByRole('status')).toHaveTextContent('Loading…');
  expect(within(screen.getByLabelText('Counters')).getByText('99')).toBeInTheDocument();
});
