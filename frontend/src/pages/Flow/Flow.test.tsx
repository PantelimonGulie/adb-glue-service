import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { analytics, overview, stock } from '../../test/fixtures';
import { renderPage, stubApi } from '../../test/render';
import { Flow } from './Flow';

const api = { '/api/analytics': analytics, '/api/overview': overview, '/api/stock': stock };

afterEach(() => {
  vi.unstubAllGlobals();
});

it('clicking a box on the map shows that part and the export follows the range', async () => {
  stubApi(api);
  renderPage(<Flow />, { route: '/flow?range=today' });

  expect(await screen.findByRole('heading', { name: 'Glue' })).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Bucharest warehouse/ }));

  expect(screen.getByRole('heading', { name: 'Bucharest warehouse' })).toBeInTheDocument();
  expect(screen.getByText('about 14 minutes')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    '/api/analytics.csv?range=today',
  );
});

it('keeps the last numbers on screen while a new range loads', async () => {
  const answer = stubApi(api);
  vi.stubGlobal('fetch', (path: string) =>
    path.includes('range=month') ? new Promise(() => {}) : answer(path),
  );
  renderPage(<Flow />, { route: '/flow?range=today' });
  expect(await screen.findByText('Order messages received')).toBeInTheDocument();

  const ranges = screen.getByRole('group', { name: 'Time range' });
  await userEvent.click(within(ranges).getByRole('button', { name: 'This month' }));

  expect(screen.getByRole('status')).toHaveTextContent('Loading…');
  expect(screen.getByText('Order messages received')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Flow · This month' })).toBeInTheDocument();
});

it('says on hover what each by-product column counts', async () => {
  const row = { sku: 'MBA-M4', product: 'MacBook Air M4', orders: 3, reserved: 2, failed: 1 };
  const by_product = [{ ...row, p50_seconds: 0.4 }];
  stubApi({ ...api, '/api/analytics': { ...analytics, by_product } });
  renderPage(<Flow />, { route: '/flow?range=today' });

  const table = (await screen.findByText('MacBook Air M4')).closest('table') as HTMLElement;
  const hints = within(table)
    .getAllByRole('columnheader')
    .map((header) => header.getAttribute('title'));

  expect(hints).toEqual([
    null,
    'Orders that came in',
    'Reserved at the warehouse',
    'Failed and not reserved',
    'Typical time from order to reserved',
  ]);
});
