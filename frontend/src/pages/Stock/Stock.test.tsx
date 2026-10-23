import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { stock } from '../../test/fixtures';
import { renderPage, stubApi, users } from '../../test/render';
import { Stock } from './Stock';

const api = { '/api/stock': stock, '/api/stock/push': null };

afterEach(() => {
  vi.unstubAllGlobals();
});

it('shows each product against the last number Glue sent each channel, read-only', async () => {
  stubApi(api);
  renderPage(<Stock />, { user: users.operator });

  const state = await screen.findByText('eMAG behind');
  const row = state.closest('tr')!;
  expect(state).toHaveAttribute('title', expect.stringMatching(/next stock check/));
  expect(within(row).getByText('MacBook Air M4')).toBeInTheDocument();
  const sent = within(row).getByTitle('Glue has not sent the latest number to eMAG yet');
  expect(sent).toHaveTextContent('1');
  expect(screen.getByRole('columnheader', { name: 'Last sent to eMAG' })).toHaveAttribute(
    'title',
    expect.stringMatching(/does not read back/),
  );
  expect(screen.queryByText(/shows/)).toBeNull();
  expect(screen.getByText(/every 10 s/)).toBeInTheDocument();
  expect(screen.queryByRole('spinbutton')).toBeNull();
});

it('an operator can send the warehouse numbers to both channels now', async () => {
  const fetch = stubApi(api);
  renderPage(<Stock />, { user: users.operator });

  await userEvent.click(screen.getByRole('button', { name: 'Update channels now' }));

  const post = expect.objectContaining({ method: 'POST' });
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/stock/push', post));
  const sent = await screen.findByText('Sent the warehouse numbers to both channels');
  expect(sent).toHaveAttribute('role', 'status');
});

it('a viewer sees why they cannot update the channels', () => {
  stubApi(api);
  renderPage(<Stock />, { user: users.viewer });

  const button = screen.getByRole('button', { name: 'Update channels now' });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute('title', 'Your role (viewer) cannot do this');
});

it('shows why the stock list could not be loaded', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(new Response('{"detail":"The database is busy"}', { status: 503 })),
  );
  renderPage(<Stock />, { user: users.operator });

  expect(await screen.findByText('The stock list could not be loaded')).toBeInTheDocument();
  expect(screen.getByText('The database is busy')).toBeInTheDocument();
});

it('says it is loading and checking the role before the first answers', () => {
  vi.stubGlobal('fetch', () => new Promise(() => {}));
  renderPage(<Stock />);

  expect(screen.getByRole('status')).toHaveTextContent('Loading…');
  expect(screen.queryByRole('table')).toBeNull();
  const button = screen.getByRole('button', { name: 'Update channels now' });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute('title', 'Checking your role…');
});
