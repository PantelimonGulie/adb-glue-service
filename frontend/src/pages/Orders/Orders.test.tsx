import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { order } from '../../test/fixtures';
import { Address, address, lastQuery, renderPage, stubApi } from '../../test/render';
import { Orders } from './Orders';

const api = { '/api/orders': { rows: [order], total: 60, page: 3, per_page: 25 } };

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderOrders(route: string) {
  return renderPage(
    <>
      <Orders />
      <Address />
    </>,
    { route },
  );
}

it('searching keeps the search in the address and starts again from page 1', async () => {
  const fetch = stubApi(api);
  renderOrders('/orders?status=failed&page=3');
  expect(await screen.findByRole('link', { name: 'emag-500124' })).toBeInTheDocument();

  await userEvent.type(screen.getByRole('searchbox', { name: 'Search order or product' }), 'mac');

  expect(address().get('q')).toBe('mac');
  expect(address().get('page')).toBeNull();
  expect(address().get('status')).toBe('failed');
  await waitFor(() => expect(lastQuery(fetch, '/api/orders')?.get('q')).toBe('mac'));
  expect(lastQuery(fetch, '/api/orders')?.get('page')).toBe('1');
});

it('filters by status in plain words', async () => {
  const fetch = stubApi(api);
  renderOrders('/orders?page=2');

  const statuses = screen.getByRole('group', { name: 'Status' });
  const names = within(statuses)
    .getAllByRole('button')
    .map((button) => button.textContent);
  expect(names).toEqual([
    'Any status',
    'Received',
    'Reserved',
    'Needs a decision',
    'Shipped',
    'Cancelled',
  ]);

  await userEvent.click(within(statuses).getByRole('button', { name: 'Needs a decision' }));

  expect(address().get('status')).toBe('failed');
  expect(address().get('page')).toBeNull();
  await waitFor(() => expect(lastQuery(fetch, '/api/orders')?.get('status')).toBe('failed'));
});

it('lists each order with its channel, product, status and latest step', async () => {
  stubApi(api);
  renderOrders('/orders');

  const link = await screen.findByRole('link', { name: 'emag-500124' });
  expect(link).toHaveAttribute('href', '/orders/emag-500124');
  const row = link.closest('tr')!;
  expect(within(row).getByText('eMAG')).toBeInTheDocument();
  expect(within(row).getByText('MacBook Air M4')).toBeInTheDocument();
  expect(within(row).getByText('Needs a decision')).toBeInTheDocument();
  expect(within(row).getByText(/^sold on the shop first/)).toBeInTheDocument();
  expect(screen.getByText('51–60 of 60')).toBeInTheDocument();
});
