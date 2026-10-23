import { expect, it } from 'vitest';
import type { ReviewItem } from '../../api/types';
import { formatTime } from '../../lib/format';
import { order, reviewItem } from '../../test/fixtures';
import { consequence, done, facts, outcome, story, suggested, unavailable } from './explain';

const cancelling = {
  ...reviewItem,
  kind: 'order_failed',
  cause: 'outage' as const,
  order: { ...order, status: 'allocated' as const },
  payload: { operation: 'cancel' },
};

it('a failed customer cancellation is told as one, and retry asks to cancel again', () => {
  expect(story(cancelling)).toBe(
    'The customer cancelled, but Glue could not cancel the order at the Bucharest warehouse.',
  );
  expect(consequence('retry', cancelling)).toBe('Asks the Bucharest warehouse again to cancel it.');
  expect(consequence('retry', reviewItem)).toMatch(/^Sends the order to the Bucharest warehouse/);
});

it('a missed ship notice is told as one, and retry tells the channel again', () => {
  const shipping = {
    ...cancelling,
    order: { ...order, status: 'shipped' as const },
    payload: { operation: 'ship' },
  };

  expect(story(shipping)).toBe(
    'The Bucharest warehouse shipped this order, but Glue could not tell eMAG, so the customer does not see it as shipped yet.',
  );
  expect(consequence('retry', shipping)).toBe('Tells eMAG again that the order shipped.');
});

it('an item whose decision is being carried out says so instead of offering choices', () => {
  const acting = { ...reviewItem, status: 'acting' as const, allowed: [] };

  expect(unavailable('retry', acting)).toBe('Glue is carrying out a decision on this item');
});

it('an item Glue closed because the order no longer needs it says so plainly', () => {
  const resolved = { ...reviewItem, status: 'decided' as const, action: 'resolved' as const };

  expect(outcome(resolved)).toBe('Closed as no longer needed');
  expect(outcome({ ...resolved, action: 'dismiss' })).toBe('Closed without changes');
});

it('a suggestion without a usable choice says so', () => {
  expect(suggested(null, reviewItem)).toBe('No single choice');
  expect(suggested('shout', reviewItem)).toBe('No single choice');
  expect(suggested('cancel', reviewItem)).toBe('Cancel on eMAG');
});

it('a decided item tells what happened in the past tense', () => {
  const outage: ReviewItem = { ...reviewItem, kind: 'order_failed', cause: 'outage' };
  const decided = { status: 'decided' as const, action: 'retry' as const };

  expect(story({ ...outage, ...decided })).toBe(
    'The Bucharest warehouse did not answer, so this order was not reserved then.',
  );
  expect(story({ ...reviewItem, ...decided })).toBe(
    'An eMAG customer ordered 1 × MacBook Air M4, but the last unit went to another customer first.',
  );
});

it('an item without a saved order says only closing it is possible', () => {
  const lost = { ...reviewItem, cause: 'other' as const, order: null, allowed: ['dismiss' as const] };

  expect(story(lost)).toBe(
    'Glue could not save this order, so there is nothing to retry or cancel. Read what Glue saw, then close the item.',
  );
});

it('shows what Glue saw in plain words, and who got the last unit', () => {
  const reservedAt = '2026-10-22T10:41:54.000+00:00';
  const winner = { order_id: 'shop-1041', channel: 'shop' as const, reserved_at: reservedAt };
  const soldOut = { ...reviewItem, winner };

  expect(story(soldOut)).toBe(
    'An eMAG customer ordered 1 × MacBook Air M4, but the last unit went to shop-1041 first. The Bucharest warehouse has none left.',
  );
  expect(facts(soldOut)).toContainEqual([
    'Got the unit',
    `shop-1041, reserved ${formatTime(reservedAt)}`,
  ]);
  expect(facts({ ...reviewItem, reason: 'HTTP 503 after 5 attempts' })[0]).toEqual([
    'What Glue saw',
    'not available after 5 tries',
  ]);
});

it('names the order and the choice once a decision went through', () => {
  const decided = (action: ReviewItem['action']) => ({ ...reviewItem, status: 'decided' as const, action });

  expect(done(decided('cancel'))).toBe('Cancelled emag-500124 on eMAG');
  expect(done(decided('retry'))).toBe('Retried emag-500124');
  expect(done(decided('dismiss'))).toBe('Closed emag-500124 without changes');
});
