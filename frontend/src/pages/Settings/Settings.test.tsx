import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { settings } from '../../test/fixtures';
import { failure, lastBody, renderPage, stubApi, users } from '../../test/render';
import { Settings } from './Settings';

afterEach(() => {
  vi.unstubAllGlobals();
});

const field = (name: string | RegExp) => screen.getByRole('spinbutton', { name });
const tries = () => screen.findByRole('spinbutton', { name: 'Tries before asking a person' });

async function retype(input: HTMLElement, value: string) {
  await userEvent.clear(input);
  await userEvent.type(input, value);
}

it('an operator sees the settings but every field is disabled', async () => {
  stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.operator });

  expect(await tries()).toBeDisabled();
  expect(field('First wait (seconds)')).toBeDisabled();
  expect(field(/Send warehouse numbers to both channels every/)).toBeDisabled();
  const save = screen.getByRole('button', { name: 'Save settings' });
  expect(save).toBeDisabled();
  expect(save).toHaveAttribute('title', 'Your role (operator) cannot do this');
  expect(screen.getByText('only admins can change settings')).toBeInTheDocument();
});

it('says how long Glue waits as the tries and the first wait change', async () => {
  stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.admin });
  const attempts = await tries();
  expect(screen.getByText(/waits about 0.5 s, 1 s, 2 s, 4 s between tries/)).toBeInTheDocument();

  await retype(attempts, '3');
  expect(screen.getByText(/waits about 0.5 s, 1 s between tries/)).toBeInTheDocument();

  await retype(field('First wait (seconds)'), '1.5');
  expect(screen.getByText(/waits about 1.5 s, 3 s between tries/)).toBeInTheDocument();

  await retype(attempts, '1');
  expect(screen.getByText(/does not wait/)).toBeInTheDocument();
});

it('keeps each value within its limits before saving', async () => {
  const fetch = stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.admin });
  const attempts = await tries();

  await retype(attempts, '11');

  expect(screen.getByText('From 1 to 10')).toBeInTheDocument();
  expect(attempts).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByRole('button', { name: 'Save settings' })).toBeDisabled();
  const put = expect.objectContaining({ method: 'PUT' });
  expect(fetch).not.toHaveBeenCalledWith('/api/settings', put);
});

it('an admin saves the new values', async () => {
  const fetch = stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.admin });
  await retype(await tries(), '3');
  await retype(field(/Send warehouse numbers/), '30');

  await userEvent.click(screen.getByRole('button', { name: 'Save settings' }));

  await waitFor(() =>
    expect(lastBody(fetch, '/api/settings')).toEqual({
      retry_attempts: 3,
      retry_base_seconds: 0.5,
      reconcile_interval_seconds: 30,
    }),
  );
});

it('shows why the API refused the change', async () => {
  const refuse = failure(422, 'retry_attempts must be between 1 and 10');
  stubApi({
    '/api/settings': (init?: RequestInit) =>
      init?.method === 'PUT' ? refuse() : new Response(JSON.stringify(settings)),
  });
  renderPage(<Settings />, { user: users.admin });
  await retype(await tries(), '3');

  await userEvent.click(screen.getByRole('button', { name: 'Save settings' }));

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'retry_attempts must be between 1 and 10',
  );
});

it('lists each connection with its address and whether it answers', async () => {
  stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.viewer });

  const row = (await screen.findByText('Bucharest warehouse')).closest('tr')!;
  expect(within(row).getByText('http://warehouse:8003')).toBeInTheDocument();
  expect(within(row).getByText('not answering')).toBeInTheDocument();
  expect(within(row).getByText('Answering HTTP 503')).toBeInTheDocument();
  expect(screen.getByRole('spinbutton', { name: /Give up on one call after/ })).toBeDisabled();
});

it('saves any value within the limits, not only whole steps', async () => {
  const fetch = stubApi({ '/api/settings': settings });
  renderPage(<Settings />, { user: users.admin });
  await tries();

  await retype(field('First wait (seconds)'), '0.25');
  await retype(field(/Send warehouse numbers/), '2.5');
  await userEvent.click(screen.getByRole('button', { name: 'Save settings' }));

  await waitFor(() =>
    expect(lastBody(fetch, '/api/settings')).toEqual({
      retry_attempts: 5,
      retry_base_seconds: 0.25,
      reconcile_interval_seconds: 2.5,
    }),
  );
});
