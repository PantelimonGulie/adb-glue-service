import { expect, it } from 'vitest';
import { row } from '../test/fixtures';
import { entityOf, labelOf } from './activity';
import { describe } from './describe';

const names: Record<string, string> = { 'MBA-M4': 'MacBook Air M4' };
const productName = (sku: string) => names[sku] ?? sku;
const on = (entity_type: string, entity_id: string, action: string, detail = {}) => ({
  ...row(1, action, detail),
  entity_type,
  entity_id,
});

it('names the order, product or system a row is about', () => {
  expect(entityOf(on('order', 'emag-9', 'order_allocated'), productName)).toEqual({
    kind: 'order',
    id: 'emag-9',
  });
  expect(entityOf(on('stock', 'MBA-M4', 'stock_pushed'), productName)).toEqual({
    kind: 'product',
    name: 'MacBook Air M4',
  });
  expect(entityOf(on('stock', 'emag', 'retry_scheduled'), productName)).toEqual({
    kind: 'text',
    text: 'eMAG',
  });
  expect(entityOf(row(2, 'event_received', { source: 'shop' }), productName)).toEqual({
    kind: 'text',
    text: 'Shop',
  });
});

it('names the order an incoming message is about', () => {
  const notified = on('event', 'emag-notify-7-new', 'duplicate_dropped', { source: 'emag' });
  const placed = on('event', 'f3c1', 'event_received', { source: 'shop', order_id: 'shop-1041' });
  const failed = on('event', 'f3c2', 'event_failed', { type: 'order.placed' });

  expect(entityOf(notified, productName)).toEqual({ kind: 'order', id: 'emag-7' });
  expect(entityOf(placed, productName)).toEqual({ kind: 'order', id: 'shop-1041' });
  expect(entityOf(failed, productName)).toEqual({ kind: 'text', text: 'Message' });
  expect(entityOf(on('rule', 'auto-retry', 'rule_changed'), productName)).toEqual({
    kind: 'text',
    text: 'Auto-retry rule',
  });
});

it('describes the details in plain words', () => {
  const lines = { lines: [{ sku: 'MBA-M4', qty: 1 }] };
  const pushed = { channel: 'emag', qty: 3, rule: 'stock-buffer', held_back: 1 };
  expect(describe(on('order', 'shop-1', 'order_allocated', lines), productName)).toBe(
    '1 × MacBook Air M4',
  );
  expect(describe(on('stock', 'MBA-M4', 'stock_pushed', pushed), productName)).toBe(
    'eMAG accepted 3 · 1 held back by a rule',
  );
  expect(describe(row(3, 'event_received', { type: 'order.placed' }), productName)).toBe(
    'signature checked and saved',
  );
  expect(describe(row(4, 'rule_changed', { enabled: true, by: 'admin' }), productName)).toBe(
    'turned on by admin',
  );
  expect(describe(on('order', 'shop-1', 'cancel_repeated'), productName)).toBe(
    'the order was already cancelled',
  );
  const resolved = { review_id: 7, kind: 'unfulfillable', why: 'the order is cancelled' };
  expect(describe(on('order', 'emag-9', 'review_resolved', resolved), productName)).toBe(
    'the order is cancelled',
  );
});

it('never shows exception names, HTTP codes or rule ids', () => {
  const said = (action: string, detail: Record<string, unknown>) =>
    describe(on('order', 'shop-1', action, detail), productName);

  expect(
    said('retry_scheduled', { attempt: 1, delay_seconds: 0.56, problem: 'ReadTimeout: ' }),
  ).toBe('no answer in time · try 1, next in 0.6 seconds');
  expect(said('order_failed', { reason: 'HTTP 503 after 5 attempts' })).toBe(
    'not available after 5 tries',
  );
  expect(said('review_decided', { decision: 'retry', decided_by: 'rule:auto-retry' })).toBe(
    'Retried by the auto-retry rule',
  );
  expect(said('rule_applied', { rule: 'auto-retry', review_id: 228 })).toBe(
    'the auto-retry rule sends it again',
  );
  expect(
    said('triage_suggested', { review_id: 25, suggested: 'cancel', reason: 'Sold out.' }),
  ).toBe('Cancel. Sold out.');
  expect(said('order_cancelled', { was: 'allocated' })).toBe(
    'the reserved unit went back on the shelf',
  );
  expect(said('order_cancelled', { was: 'failed' })).toBe('nothing was reserved');
  const unreadable = { source: 'shop', error: 'x-adobe-event-id: missing or malformed' };
  expect(describe(on('event', '-', 'event_rejected', unreadable), productName)).toBe(
    'Glue could not read the message, so it refused it',
  );
  expect(
    describe(on('webhook', 'shop', 'signature_rejected', { path: '/events' }), productName),
  ).toBe('no valid signature, so Glue refused it');
});

it('says a failure went to review once, not twice with the same words', () => {
  const opened = on('order', 'shop-1', 'review_opened', { reason: 'HTTP 503 after 5 attempts' });

  expect(describe(opened, productName)).toBe('waiting for a person in the review queue');
});

it('calls a recount conflict a shelf count, as the review queue does', () => {
  const recount = on('order', 'shop-1', 'unfulfillable', {
    reason: 'recount: 18 on hand, 20 reserved',
  });
  const soldOut = on('order', 'shop-1', 'unfulfillable', {
    reason: 'sold on another channel first',
  });

  expect(labelOf(recount).label).toBe('Shelf count too low');
  expect(labelOf(soldOut).label).toBe('Sold out, needs you');
});

it('labels an incoming message by what it is about', () => {
  const event = (type: string, entity_id = 'evt-1') => ({
    ...row(5, 'event_received', { type }),
    entity_id,
  });
  const labels = [
    event('order.placed'),
    event('emag.notification', 'emag-notify-7-new'),
    event('emag.notification', 'emag-notify-7-cancelled'),
    event('order.cancelled'),
    event('order.shipped'),
    event('stock.adjusted'),
  ].map((received) => [labelOf(received).label, labelOf(received).tone]);

  expect(labels).toEqual([
    ['Order received', 'blue'],
    ['Order received from eMAG', 'blue'],
    ['Cancellation received', 'slate'],
    ['Cancellation received', 'slate'],
    ['Shipment reported', 'slate'],
    ['Shelf count changed', 'slate'],
  ]);
  expect(labelOf(row(6, 'order_allocated')).label).toBe('Reserved at warehouse');
});
