import { expect, it } from 'vitest';
import { order, reviewItem } from '../../test/fixtures';
import { consequence, story, suggested } from './explain';

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

it('a suggestion without a usable choice says so', () => {
  expect(suggested(null, reviewItem)).toBe('No single choice');
  expect(suggested('shout', reviewItem)).toBe('No single choice');
  expect(suggested('cancel', reviewItem)).toBe('Cancel on eMAG');
});
