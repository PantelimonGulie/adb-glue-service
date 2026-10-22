import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { Demo as DemoState } from '../../api/types';
import { demo, stock } from '../../test/fixtures';
import { lastBody, renderPage, stubApi, users } from '../../test/render';
import { Demo } from './Demo';

const said = (message: string, ok = true) => ({ ok, message });

afterEach(() => {
  vi.unstubAllGlobals();
});

const card = (name: string) => screen.getByRole('region', { name });

it('an admin stops the warehouse and reads what happened', async () => {
  const fetch = stubApi({
    '/api/demo': demo,
    '/api/stock': stock,
    '/api/demo/warehouse-down': said('The warehouse answers 503 to every call.'),
  });
  renderPage(<Demo />, { user: users.admin });

  await userEvent.click(await screen.findByRole('button', { name: 'Stop answering' }));

  const warehouse = card('Warehouse');
  expect(await within(warehouse).findByRole('status')).toHaveTextContent(
    'The warehouse answers 503 to every call.',
  );
  const post = expect.objectContaining({ method: 'POST' });
  expect(fetch).toHaveBeenCalledWith('/api/demo/warehouse-down', post);
});

it('the cards follow the faults, traffic and speed that are on now', async () => {
  const state: DemoState = {
    ...demo,
    traffic: { running: false, speed: 'fast' },
    faults: {
      emag: { ...demo.faults.emag!, freeze_stock: true },
      warehouse: { down: true, slow_seconds: 0, fail_next: 2 },
    },
  };
  stubApi({ '/api/demo': state, '/api/stock': stock });
  renderPage(<Demo />, { user: users.admin });

  const back = await screen.findByRole('button', { name: /Bring the warehouse back/ });
  expect(back).toHaveTextContent('fault on');
  expect(screen.getByRole('button', { name: /Fail the next 2 orders only/ })).toHaveTextContent(
    '2 to fail',
  );
  expect(screen.getByRole('button', { name: /Apply stock updates again/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Ask Glue to slow down' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Resume new orders' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Fast' })).toHaveAttribute('aria-pressed', 'true');
});

it('an admin changes how fast new orders arrive', async () => {
  const fetch = stubApi({
    '/api/demo': demo,
    '/api/stock': stock,
    '/api/demo/speed-fast': said('New orders arrive every 0.45 seconds.'),
  });
  renderPage(<Demo />, { user: users.admin });

  await userEvent.click(await screen.findByRole('button', { name: 'Fast' }));

  expect(await within(card('Simulation')).findByRole('status')).toHaveTextContent('0.45 seconds');
  expect(fetch).toHaveBeenCalledWith('/api/demo/speed-fast', expect.anything());
});

it('an operator sees every card read-only with the reason', async () => {
  stubApi({ '/api/demo': demo, '/api/stock': stock });
  renderPage(<Demo />, { user: users.operator });

  const stop = await screen.findByRole('button', { name: 'Stop answering' });
  expect(stop).toBeDisabled();
  expect(stop).toHaveAttribute('title', 'Your role (operator) cannot do this');
  expect(screen.getByRole('button', { name: 'Fast' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save the count' })).toBeDisabled();
  expect(screen.getByText(/Only admins can use them/)).toBeInTheDocument();
});

it('a recount takes a whole number of units, zero or more', async () => {
  const fetch = stubApi({
    '/api/demo': demo,
    '/api/stock': stock,
    '/api/demo/recount': said('The warehouse now counts 4 MacBook Air M4 on the shelf.'),
  });
  renderPage(<Demo />, { user: users.admin });
  const recount = await screen.findByRole('region', { name: 'Warehouse recount' });
  await within(recount).findByRole('option', { name: 'MacBook Air M4' });
  const units = within(recount).getByRole('spinbutton', { name: 'Units on the shelf' });
  const save = within(recount).getByRole('button', { name: 'Save the count' });

  await userEvent.clear(units);
  await userEvent.type(units, '-1');
  expect(save).toBeDisabled();
  expect(within(recount).getByText('Enter a whole number from 0 to 100,000.')).toBeInTheDocument();

  await userEvent.clear(units);
  await userEvent.type(units, '4');
  await userEvent.click(save);

  await waitFor(() =>
    expect(lastBody(fetch, '/api/demo/recount')).toEqual({ sku: 'MBA-M4', on_hand: 4 }),
  );
  expect(await within(recount).findByRole('status')).toHaveTextContent('now counts 4');
});

it('clearing the sample history asks first', async () => {
  const fetch = stubApi({
    '/api/demo': { ...demo, sample_history: true },
    '/api/stock': stock,
    '/api/demo/history-clear': said('Removed the sample history (1,985 orders). Real orders stay.'),
  });
  renderPage(<Demo />, { user: users.admin });

  await userEvent.click(await screen.findByRole('button', { name: 'Clear sample history' }));
  expect(fetch).not.toHaveBeenCalledWith('/api/demo/history-clear', expect.anything());
  await userEvent.click(screen.getByRole('button', { name: 'Yes, clear it' }));

  expect(await within(card('Sample history')).findByRole('status')).toHaveTextContent(
    'Real orders stay.',
  );
});

it('says so when a system did not do what was asked', async () => {
  stubApi({
    '/api/demo': demo,
    '/api/stock': stock,
    '/api/demo/ship-oldest': said('The warehouse has no reserved order to ship.', false),
  });
  renderPage(<Demo />, { user: users.admin });

  const ship = await screen.findByRole('button', { name: 'Ship the oldest reserved order' });
  await userEvent.click(ship);

  expect(await within(card('Warehouse')).findByRole('alert')).toHaveTextContent(
    'The warehouse has no reserved order to ship.',
  );
});
