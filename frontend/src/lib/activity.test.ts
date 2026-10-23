import { expect, it } from 'vitest';
import { row } from '../test/fixtures';
import { describe, entityOf, labelOf } from './activity';

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

it('describes the details in plain words', () => {
  const lines = { lines: [{ sku: 'MBA-M4', qty: 1 }] };
  const pushed = { channel: 'emag', qty: 3, rule: 'stock-buffer', held_back: 1 };
  expect(describe(on('order', 'shop-1', 'order_allocated', lines), productName)).toBe(
    '1 × MacBook Air M4',
  );
  expect(describe(on('stock', 'MBA-M4', 'stock_pushed', pushed), productName)).toBe(
    'eMAG now shows 3 · 1 held back by a rule',
  );
  expect(describe(row(3, 'event_received', { type: 'order.placed' }), productName)).toBe(
    'signature checked and saved',
  );
  expect(describe(row(4, 'rule_changed', { enabled: true, by: 'admin' }), productName)).toBe(
    'enabled true · by admin',
  );
  expect(describe(on('order', 'shop-1', 'cancel_repeated'), productName)).toBe(
    'the order was already cancelled',
  );
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
