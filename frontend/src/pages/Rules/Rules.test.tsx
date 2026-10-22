import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { rules, stock } from '../../test/fixtures';
import { failure, lastBody, renderPage, stubApi, users } from '../../test/render';
import { Rules } from './Rules';

const BUFFER = '/api/rules/stock-buffer';
const RETRY = '/api/rules/auto-retry';
const api = { '/api/rules': rules, '/api/stock': stock, [BUFFER]: rules[0], [RETRY]: rules[1] };

afterEach(() => {
  vi.unstubAllGlobals();
});

it('lists each rule in plain words with whether it is on', async () => {
  stubApi(api);
  renderPage(<Rules />, { user: users.viewer });

  const buffer = await screen.findByRole('region', { name: 'Keep a safety buffer on eMAG' });
  expect(within(buffer).getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  expect(within(buffer).getByText(/Last changed by admin/)).toBeInTheDocument();
  const retry = screen.getByRole('region', {
    name: 'Retry by itself after the warehouse recovers',
  });
  expect(within(retry).getByRole('switch')).toHaveAttribute('aria-checked', 'false');
});

it('a viewer sees the rules read-only with the reason', async () => {
  stubApi(api);
  renderPage(<Rules />, { user: users.viewer });

  const switches = await screen.findAllByRole('switch');
  for (const toggle of switches) {
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAttribute('title', 'Your role (viewer) cannot do this');
  }
  expect(screen.getByRole('spinbutton', { name: 'Units to hold back' })).toBeDisabled();
  expect(
    screen.getByText('You can see the rules. Only admins can change them.'),
  ).toBeInTheDocument();
});

it('an admin turns a rule on', async () => {
  const fetch = stubApi(api);
  renderPage(<Rules />, { user: users.admin });
  const retry = await screen.findByRole('region', {
    name: 'Retry by itself after the warehouse recovers',
  });

  await userEvent.click(within(retry).getByRole('switch'));

  await waitFor(() => expect(lastBody(fetch, RETRY)).toEqual({ enabled: true }));
});

it('an admin changes how much the buffer holds back and on which product', async () => {
  const fetch = stubApi(api);
  renderPage(<Rules />, { user: users.admin });
  const units = await screen.findByRole('spinbutton', { name: 'Units to hold back' });
  await screen.findByRole('option', { name: 'MacBook Air M4' });

  await userEvent.clear(units);
  await userEvent.type(units, '2');
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Product' }), 'MBA-M4');
  await userEvent.click(screen.getByRole('button', { name: 'Save the buffer' }));

  await waitFor(() =>
    expect(lastBody(fetch, BUFFER)).toEqual({
      enabled: true,
      config: { channel: 'emag', units: 2, sku: 'MBA-M4' },
    }),
  );
});

it('shows why the API refused a rule change', async () => {
  stubApi({ ...api, [BUFFER]: failure(422, 'Input should be less than or equal to 99') });
  renderPage(<Rules />, { user: users.admin });
  const buffer = await screen.findByRole('region', { name: 'Keep a safety buffer on eMAG' });

  await userEvent.click(within(buffer).getByRole('switch'));

  expect(await within(buffer).findByRole('alert')).toHaveTextContent(
    'Input should be less than or equal to 99',
  );
});

it('the buffer switch saves the units on screen instead of dropping them', async () => {
  const fetch = stubApi(api);
  renderPage(<Rules />, { user: users.admin });
  const units = await screen.findByRole('spinbutton', { name: 'Units to hold back' });
  const buffer = screen.getByRole('region', { name: 'Keep a safety buffer on eMAG' });

  await userEvent.clear(units);
  await userEvent.type(units, '3');
  await userEvent.click(within(buffer).getByRole('switch'));

  await waitFor(() =>
    expect(lastBody(fetch, BUFFER)).toEqual({
      enabled: false,
      config: { channel: 'emag', units: 3, sku: '' },
    }),
  );
});

it('the buffer switch waits for valid units, and says why', async () => {
  stubApi(api);
  renderPage(<Rules />, { user: users.admin });
  const units = await screen.findByRole('spinbutton', { name: 'Units to hold back' });
  const buffer = screen.getByRole('region', { name: 'Keep a safety buffer on eMAG' });

  await userEvent.clear(units);
  await userEvent.type(units, '120');

  const toggle = within(buffer).getByRole('switch');
  expect(toggle).toBeDisabled();
  expect(toggle).toHaveAttribute('title', 'Enter units from 0 to 99 first');
});
