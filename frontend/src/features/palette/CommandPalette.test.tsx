import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { Order } from '../../api/types';
import { order, stock } from '../../test/fixtures';
import { renderPage, stubApi, users } from '../../test/render';
import { CommandPalette } from './CommandPalette';

const found: Order = { ...order, order_id: 'shop-1042', channel: 'shop', status: 'allocated' };
const api = {
  '/api/stock': stock,
  '/api/orders': { rows: [found], total: 1, page: 1, per_page: 8 },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function Where() {
  const { pathname } = useLocation();
  return <p aria-label="Page">{pathname}</p>;
}

function renderPalette() {
  return renderPage(
    <>
      <CommandPalette />
      <Where />
    </>,
    { user: users.operator },
  );
}

const orderSearches = (fetch: ReturnType<typeof stubApi>) =>
  fetch.mock.calls
    .map(([path]) => new URL(path, 'http://glue'))
    .filter((url) => url.pathname === '/api/orders')
    .map((url) => url.searchParams.get('q'));

it('opens on Ctrl+K with the pages and the products in plain names', async () => {
  const fetch = stubApi(api);
  renderPalette();

  await userEvent.keyboard('{Control>}k{/Control}');

  const dialog = screen.getByRole('dialog', { name: 'Search' });
  expect(within(dialog).getByRole('option', { name: /Review queue/ })).toBeInTheDocument();
  expect(await within(dialog).findByRole('option', { name: /MacBook Air M4/ })).toBeInTheDocument();
  expect(screen.getByRole('combobox')).toHaveFocus();
  expect(orderSearches(fetch)).toEqual([]);
});

it('typing shop-10 lists matching orders and Enter opens the order', async () => {
  const fetch = stubApi(api);
  renderPalette();
  await userEvent.keyboard('{Control>}k{/Control}');

  await userEvent.type(screen.getByRole('combobox'), 'shop-10');

  const option = await screen.findByRole('option', {
    name: /shop-1042 · MacBook Air M4 · Reserved/,
  });
  expect(option).toHaveAttribute('aria-selected', 'true');
  expect(orderSearches(fetch)).toEqual(['shop-10']);

  await userEvent.keyboard('{Enter}');

  expect(screen.getByLabelText('Page')).toHaveTextContent('/orders/shop-1042');
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('finds pages by name and leaves orders alone for one letter', async () => {
  const fetch = stubApi(api);
  renderPalette();
  await userEvent.keyboard('{Control>}k{/Control}');

  await userEvent.type(screen.getByRole('combobox'), 'r');
  await userEvent.clear(screen.getByRole('combobox'));
  await userEvent.type(screen.getByRole('combobox'), 'rules');

  expect(screen.getAllByRole('option').map((item) => item.textContent)).toEqual(['Rulespage']);
  await userEvent.keyboard('{Enter}');
  expect(screen.getByLabelText('Page')).toHaveTextContent('/rules');
  expect(orderSearches(fetch).every((q) => q === 'rules')).toBe(true);
});

it('closes on Escape and gives focus back to the search button', async () => {
  stubApi(api);
  renderPalette();
  const trigger = screen.getByRole('button', { name: 'Search' });

  await userEvent.click(trigger);
  expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument();
  await userEvent.keyboard('{Escape}');

  expect(screen.queryByRole('dialog')).toBeNull();
  expect(trigger).toHaveFocus();
});

it('while a search is on its way it says so, without old rows or "Nothing found."', async () => {
  stubApi(api);
  renderPalette();
  await userEvent.keyboard('{Control>}k{/Control}');
  const input = screen.getByRole('combobox');

  await userEvent.type(input, 'shop-10');
  expect(screen.queryByText('Nothing found.')).toBeNull();
  expect(screen.getByText('Searching orders…')).toBeInTheDocument();
  await screen.findByRole('option', { name: /shop-1042/ });

  await userEvent.type(input, '4');
  expect(screen.queryByRole('option', { name: /shop-1042/ })).toBeNull();
  expect(screen.getByText('Searching orders…')).toBeInTheDocument();
  expect(await screen.findByRole('option', { name: /shop-1042/ })).toBeInTheDocument();
});

it('opens on Ctrl+K but not on Ctrl+Shift+K', async () => {
  stubApi(api);
  renderPalette();

  await userEvent.keyboard('{Control>}{Shift>}K{/Shift}{/Control}');
  expect(screen.queryByRole('dialog')).toBeNull();

  await userEvent.keyboard('{Control>}k{/Control}');
  expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument();
});
