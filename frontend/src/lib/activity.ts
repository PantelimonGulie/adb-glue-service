import type { AuditRow } from '../api/types';
import { action, message, type Label, type Message } from './labels';

export type ProductName = (sku: string) => string;

export type Entity =
  | { kind: 'order'; id: string }
  | { kind: 'product'; name: string }
  | { kind: 'text'; text: string };

const SYSTEMS = new Map([
  ['shop', 'Shop'],
  ['emag', 'eMAG'],
  ['warehouse', 'Warehouse'],
  ['unknown', 'Unknown sender'],
]);
export const RULES = new Map([
  ['stock-buffer', 'Stock buffer rule'],
  ['auto-retry', 'Auto-retry rule'],
]);
const ORDER_ID = /^(shop|emag)-/;

export const systemName = (name: string) => SYSTEMS.get(name) ?? name;

// Who decided, in words: a person's name, Glue itself, or a rule such as "rule:auto-retry".
export function decider(name: string): string {
  if (name === 'glue') return 'Glue';
  const rule = name.startsWith('rule:') && RULES.get(name.slice('rule:'.length));
  return rule ? `the ${rule.toLowerCase()}` : name;
}

// Same rule as the backend's db.PLACEMENT: eMAG event ids end with -new or -cancelled.
export function messageOf(row: AuditRow): Message | null {
  switch (row.detail.type) {
    case 'order.placed':
      return 'order';
    case 'order.cancelled':
      return 'cancellation';
    case 'order.shipped':
      return 'shipment';
    case 'stock.adjusted':
      return 'shelf-count';
    case 'emag.notification':
      return row.entity_id.endsWith('-new') ? 'emag-order' : 'cancellation';
    default:
      return null;
  }
}

export function isPlacement(row: AuditRow): boolean {
  const kind = messageOf(row);
  return kind === 'order' || kind === 'emag-order';
}

// The backend tells a recount from a sold-out order by the same words (review.cause_of).
const isRecount = (row: AuditRow) => /recount|shelf count/i.test(String(row.detail.reason ?? ''));

export function labelOf(row: AuditRow): Label {
  if (row.action === 'unfulfillable' && isRecount(row)) return action('recount_conflict');
  const kind = row.action === 'event_received' ? messageOf(row) : null;
  return kind ? message(kind) : action(row.action);
}

function eventOrder(row: AuditRow): string | null {
  const said = row.detail.order_id;
  if (typeof said === 'string' && ORDER_ID.test(said)) return said;
  const notified = /^emag-notify-(\d+)-/.exec(row.entity_id);
  return notified ? `emag-${notified[1]}` : null;
}

export function entityOf(row: AuditRow, productName: ProductName): Entity {
  const id = row.entity_id;
  if (row.entity_type === 'order' && ORDER_ID.test(id)) return { kind: 'order', id };
  if (row.entity_type === 'stock' && !SYSTEMS.has(id)) {
    return { kind: 'product', name: productName(id) };
  }
  if (row.entity_type === 'event') {
    const order = eventOrder(row);
    if (order) return { kind: 'order', id: order };
    const source = row.detail.source;
    return { kind: 'text', text: typeof source === 'string' ? systemName(source) : 'Message' };
  }
  if (row.entity_type === 'settings') return { kind: 'text', text: 'Settings' };
  if (row.entity_type === 'rule') return { kind: 'text', text: RULES.get(id) ?? id };
  return { kind: 'text', text: systemName(id) };
}
