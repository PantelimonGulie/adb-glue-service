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

it('shows each product against what each channel shows, read-only', async () => {
  stubApi(api);
  renderPage(<Stock />, { user: users.operator });

  const state = await screen.findByText('eMAG not updated yet');
  const row = state.closest('tr')!;
  expect(state).toHaveAttribute('title', expect.stringMatching(/next stock check/));
  expect(within(row).getByText('MacBook Air M4')).toBeInTheDocument();
  expect(within(row).getByTitle('eMAG has not applied the last update yet')).toHaveTextContent('1');
  expect(screen.getByText(/every 10 s/)).toBeInTheDocument();
  expect(screen.queryByRole('spinbutton')).toBeNull();
});

it('an operator can send the warehouse numbers to both channels now', async () => {
  const fetch = stubApi(api);
  renderPage(<Stock />, { user: users.operator });

  await userEvent.click(screen.getByRole('button', { name: 'Update channels now' }));

  const post = expect.objectContaining({ method: 'POST' });
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/stock/push', post));
});

it('a viewer sees why they cannot update the channels', () => {
  stubApi(api);
  renderPage(<Stock />, { user: users.viewer });

  const button = screen.getByRole('button', { name: 'Update channels now' });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute('title', 'Your role (viewer) cannot do this');
});
