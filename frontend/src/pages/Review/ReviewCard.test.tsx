import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { ReviewItem } from '../../api/types';
import { assistant, order, reviewItem, stock } from '../../test/fixtures';
import { failure, renderPage, stubApi, users } from '../../test/render';
import { ReviewCard } from './ReviewCard';

const api = { '/api/assistant': assistant, '/api/stock': stock };
const downloading = {
  ...assistant,
  model: { ...assistant.model, status: 'downloading', progress: 0.34 },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const renderCard = (item: ReviewItem, user = users.operator) =>
  renderPage(<ReviewCard item={item} />, { user });

it('explains the order, what Glue saw and what each choice does', async () => {
  stubApi(api);
  renderCard(reviewItem);

  expect(screen.getByText(/An eMAG customer ordered 1 × MacBook Air M4/)).toBeInTheDocument();
  expect(screen.getByText(reviewItem.reason)).toBeInTheDocument();
  expect(await screen.findByText('1 on hand, 1 reserved, 0 free')).toBeInTheDocument();
  expect(screen.getByText(/counts against the store's seller rating on eMAG/)).toBeInTheDocument();
  expect(screen.getByText(/never reserves twice/)).toBeInTheDocument();
  const link = screen.getByRole('link', { name: 'emag-500124' });
  expect(link).toHaveAttribute('href', '/orders/emag-500124');
});

it('a choice the order does not allow is disabled with the reason', () => {
  stubApi(api);
  const reserved = { ...order, status: 'allocated' as const };
  renderCard({ ...reviewItem, cause: 'recount', order: reserved, allowed: ['cancel', 'dismiss'] });

  const retry = screen.getByRole('button', { name: 'Retry' });
  const why = 'The order already holds a reservation, so retrying would not change anything';
  expect(retry).toBeDisabled();
  expect(retry).toHaveAttribute('title', why);
  expect(screen.getByRole('button', { name: 'Cancel on eMAG' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Close without changes' })).toBeEnabled();
});

it('a viewer sees every decision disabled with the reason', () => {
  stubApi(api);
  renderCard(reviewItem, users.viewer);

  for (const name of ['Retry', 'Cancel on eMAG', 'Close without changes', 'Suggest an action']) {
    const button = screen.getByRole('button', { name });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('title', 'Your role (viewer) cannot do this');
  }
});

it('sends an operator decision for this item', async () => {
  const fetch = stubApi({ ...api, '/api/review/7/retry': { ...reviewItem, status: 'decided' } });
  renderCard(reviewItem);

  await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

  const post = expect.objectContaining({ method: 'POST' });
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/review/7/retry', post));
});

it('asks before it cancels, since cancelling refunds the customer', async () => {
  const fetch = stubApi({ ...api, '/api/review/7/cancel': { ...reviewItem, status: 'decided' } });
  renderCard(reviewItem);

  await userEvent.click(screen.getByRole('button', { name: 'Cancel on eMAG' }));

  const question = screen.getByRole('group', { name: 'Cancel emag-500124 on eMAG?' });
  expect(fetch).not.toHaveBeenCalledWith('/api/review/7/cancel', expect.anything());
  await userEvent.click(within(question).getByRole('button', { name: 'Keep the order' }));
  expect(screen.queryByRole('group', { name: /Cancel emag-500124/ })).toBeNull();

  await userEvent.click(screen.getByRole('button', { name: 'Cancel on eMAG' }));
  await userEvent.click(screen.getByRole('button', { name: 'Yes, cancel it' }));

  const post = expect.objectContaining({ method: 'POST' });
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/review/7/cancel', post));
});

it('shows why a decision failed on the card', async () => {
  const refused = failure(502, 'cancel failed: eMAG refused the cancellation');
  stubApi({ ...api, '/api/review/7/cancel': refused });
  renderCard(reviewItem);

  await userEvent.click(screen.getByRole('button', { name: 'Cancel on eMAG' }));
  await userEvent.click(screen.getByRole('button', { name: 'Yes, cancel it' }));

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('cancel failed: eMAG refused the cancellation');
});

it('shows the triage suggestion as a suggestion that does not act', () => {
  stubApi(api);
  const suggestion = { action: 'cancel', reason: 'shop-1041 already holds the only unit.' };
  renderCard({ ...reviewItem, suggestion });

  const box = screen.getByText('Triage suggestion · it does not act').parentElement;
  expect(box).toHaveTextContent('Cancel on eMAG. shop-1041 already holds the only unit.');
  expect(screen.queryByRole('button', { name: 'Suggest an action' })).toBeNull();
});

it('says the local model is downloading instead of suggesting an action', async () => {
  stubApi({ ...api, '/api/assistant': downloading });
  renderCard(reviewItem);

  const notice = 'Downloading the local model, about 2 GB, one time · 34%';
  expect(await screen.findByText(notice)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Suggest an action' })).toBeDisabled();
});

it('shows why no suggestion could be made', async () => {
  const spent = failure(429, "Today's token budget is spent.");
  const fetch = stubApi({ ...api, '/api/review/7/triage': spent });
  renderCard(reviewItem);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/assistant', expect.anything()));

  await userEvent.click(screen.getByRole('button', { name: 'Suggest an action' }));

  expect(await screen.findByRole('alert')).toHaveTextContent("Today's token budget is spent.");
});

it('a decided item says who decided, instead of the choices', () => {
  stubApi(api);
  const decided = { status: 'decided', action: 'cancel', decided_by: 'operator', allowed: [] };
  const at = '2026-10-22T10:45:00.000+00:00';
  renderCard({ ...reviewItem, ...decided, decided_at: at } as ReviewItem);

  expect(screen.getByText('Cancelled on eMAG').parentElement).toHaveTextContent(
    /^Cancelled on eMAG by operator at .+\. Saved in the activity log\.$/,
  );
  expect(screen.queryByRole('button')).toBeNull();
});

it('an item without a saved order shows the id without a link to a missing page', () => {
  stubApi(api);
  renderCard({ ...reviewItem, cause: 'other', order: null, allowed: ['dismiss'] });

  expect(screen.queryByRole('link', { name: 'emag-500124' })).toBeNull();
  expect(screen.getByText('emag-500124')).toBeInTheDocument();
  expect(screen.getByText(/nothing to retry or cancel/)).toBeInTheDocument();
});
