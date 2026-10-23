import { describe, expect, it } from 'vitest';
import { action, cause, status } from './labels';

describe('action', () => {
  it('uses the label and explanation from the design', () => {
    expect(action('order_allocated').label).toBe('Reserved at warehouse');
    expect(action('order_allocated').explanation).toBe(
      'The warehouse accepted the order and set the item aside for this customer.',
    );
  });

  it('falls back to a readable label for an unknown action', () => {
    expect(action('stock_counted_twice')).toEqual({
      label: 'Stock counted twice',
      tone: 'grey',
      explanation: 'Glue recorded this step.',
    });
  });

  it('tells a repeated cancellation apart from a repeated order', () => {
    expect(action('cancel_repeated').label).toBe('Cancellation repeated');
    expect(action('cancel_repeated').explanation).toBe(
      'The order was already cancelled when the cancellation arrived again, so Glue ignored it.',
    );
  });

  it('names a review item Glue closed because it was no longer needed', () => {
    expect(action('review_resolved')).toEqual({
      label: 'Closed as no longer needed',
      tone: 'green',
      explanation: "The order's state made this review item moot, so Glue closed it.",
    });
  });

  it('does not mistake built-in object names for actions', () => {
    expect(action('constructor').label).toBe('Constructor');
  });
});

it('names statuses and causes in plain words', () => {
  expect(status('failed').label).toBe('Needs a decision');
  expect(cause('soldout').label).toBe('Sold out');
  expect(cause('recount').label).toBe('Shelf count too low');
});

