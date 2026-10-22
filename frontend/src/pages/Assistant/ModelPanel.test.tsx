import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { Assistant } from '../../api/types';
import { assistant } from '../../test/fixtures';
import { failure, lastBody, renderPage, stubApi, users } from '../../test/render';
import { ModelPanel } from './ModelPanel';

const SETTINGS = '/api/assistant/settings';

afterEach(() => {
  vi.unstubAllGlobals();
});

const renderPanel = (data: Assistant = assistant, user = users.admin) =>
  renderPage(<ModelPanel assistant={data} />, { user });

it('shows how far the local model has downloaded', () => {
  stubApi({});
  const model = { ...assistant.model, status: 'downloading', progress: 0.34 } as const;
  renderPanel({ ...assistant, model });

  expect(screen.getByText('Downloading the local model · 34%')).toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Download' })).toHaveAttribute(
    'aria-valuenow',
    '34',
  );
});

it.each([
  ['missing', 'Not downloaded yet'],
  ['offline', 'Not answering'],
] as const)('says clearly when the local model is %s', (status, label) => {
  stubApi({});
  renderPanel({ ...assistant, model: { ...assistant.model, status } });

  expect(screen.getByText(label)).toBeInTheDocument();
});

it('answers with the local model; Claude, GPT and Gemini are coming soon', () => {
  stubApi({});
  renderPanel();

  const select = screen.getByRole('combobox', { name: 'Which model answers' });
  expect(select).toHaveValue('local');
  for (const name of ['Claude', 'GPT', 'Gemini']) {
    expect(within(select).getByRole('option', { name: `${name} · coming soon` })).toBeDisabled();
  }
});

it('an admin changes the effort', async () => {
  const fetch = stubApi({ [SETTINGS]: assistant });
  renderPanel();

  await userEvent.click(screen.getByRole('button', { name: 'High' }));

  await waitFor(() => expect(lastBody(fetch, SETTINGS)).toEqual({ effort: 'high' }));
});

it('an admin saves the token limits', async () => {
  const fetch = stubApi({ [SETTINGS]: assistant });
  renderPanel();
  const longest = screen.getByRole('spinbutton', { name: 'Longest answer (tokens)' });

  await userEvent.clear(longest);
  await userEvent.type(longest, '1500');
  await userEvent.click(screen.getByRole('button', { name: 'Save limits' }));

  const limits = { max_tokens_per_question: 1500, daily_token_budget: 200000 };
  await waitFor(() => expect(lastBody(fetch, SETTINGS)).toEqual(limits));
});

it('shows why a change was refused', async () => {
  stubApi({ [SETTINGS]: failure(422, 'Input should be less than or equal to 8000') });
  renderPanel();

  await userEvent.click(screen.getByRole('button', { name: 'Low' }));

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('Input should be less than or equal to 8000');
});

it('an operator sees the settings read-only, with the reason', () => {
  stubApi({});
  renderPanel(assistant, users.operator);

  const effort = screen.getByRole('button', { name: 'High' });
  const longest = screen.getByRole('spinbutton', { name: 'Longest answer (tokens)' });
  expect(effort).toBeDisabled();
  expect(longest).toBeDisabled();
  expect(longest).toHaveAttribute('title', 'Your role (operator) cannot do this');
  expect(screen.getByRole('combobox', { name: 'Which model answers' })).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Save limits' })).toBeNull();
  expect(screen.getByText('Only admins can change these.')).toBeInTheDocument();
});

it('shows the tokens used today against the daily budget', () => {
  stubApi({});
  renderPanel();

  const used = screen.getByRole('meter', { name: 'Used today' });
  expect(used).toHaveAttribute('aria-valuenow', '7168');
  expect(used).toHaveAttribute('aria-valuemax', '200000');
  expect(screen.getByText(/7,168 of 200,000 tokens · 5 questions/)).toBeInTheDocument();
});
