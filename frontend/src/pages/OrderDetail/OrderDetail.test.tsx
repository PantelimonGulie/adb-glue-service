import { act, screen, within } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { order, row, stock } from '../../test/fixtures';
import { renderPage, stubApi, users } from '../../test/render';
import { OrderDetail } from './OrderDetail';

const step = (id: number, action: string, detail = {}) => ({
  ...row(id, action, detail),
  entity_type: 'order',
  entity_id: order.order_id,
});
const timeline = [
  {
    ...row(1, 'event_received', { source: 'emag', type: 'emag.notification' }),
    entity_id: 'emag-notify-500124-new',
  },
  step(2, 'unfulfillable', { reason: 'the shop sold the last unit first' }),
  step(3, 'emag_acknowledged'),
];
const api = {
  '/api/orders/emag-500124': { order, timeline },
  '/api/stock': stock,
  '/api/settings': { retry_attempts: 5 },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderOrder(user = users.operator, id = order.order_id) {
  return renderPage(
    <Routes>
      <Route path="/orders/:id" element={<OrderDetail />} />
    </Routes>,
    { user, route: `/orders/${id}` },
  );
}

it('tells the history of an order step by step, with the reason', async () => {
  stubApi(api);
  renderOrder();

  const history = await screen.findByRole('list', { name: 'History' });
  const steps = within(history).getAllByRole('listitem');
  expect(steps.map((item) => within(item).getByTitle(/./).textContent)).toEqual([
    'Order received from eMAG',
    'Sold out, needs you',
    'Confirmed to eMAG',
  ]);
  expect(within(steps[1]).getByText('the shop sold the last unit first')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'emag-500124' })).toBeInTheDocument();
  expect(screen.getByText('eMAG, fetched by Glue')).toBeInTheDocument();
  expect(await screen.findByText('1 of 5 allowed')).toBeInTheDocument();
});

it('links to the assistant with the question already asked', async () => {
  stubApi(api);
  renderOrder();

  const ask = await screen.findByRole('link', { name: 'Ask the assistant about this order' });

  expect(ask).toHaveAttribute('href', '/assistant?q=What+happened+to+emag-500124%3F');
});

it('a viewer sees why they cannot ask the assistant', async () => {
  stubApi(api);
  renderOrder(users.viewer);

  const ask = await screen.findByRole('button', { name: 'Ask the assistant about this order' });

  expect(ask).toBeDisabled();
  expect(ask).toHaveAttribute('title', 'Your role (viewer) cannot do this');
});

it('says when an order does not exist', async () => {
  stubApi(api);
  renderOrder(users.operator, 'shop-404');

  expect(await screen.findByText('This order does not exist')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '← Orders' })).toHaveAttribute('href', '/orders');
});

it('stops asking for an order that does not exist', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetch = stubApi(api);
  renderOrder(users.operator, 'shop-404');
  expect(await screen.findByText('This order does not exist')).toBeInTheDocument();
  const asked = () => fetch.mock.calls.filter(([path]) => path === '/api/orders/shop-404').length;
  const before = asked();

  await act(() => vi.advanceTimersByTimeAsync(10_000));

  expect(asked()).toBe(before);
});
