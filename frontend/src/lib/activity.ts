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
const MESSAGE_DETAILS: Record<Message, string> = {
  order: 'signature checked and saved',
  'emag-order': 'Glue fetched the full order from eMAG',
  cancellation: 'the customer cancelled',
  shipment: 'the warehouse shipped an order',
  'shelf-count': 'the warehouse counted a shelf again',
};
const DECISIONS = new Map([
  ['retry', 'Retried'],
  ['cancel', 'Cancelled'],
  ['dismiss', 'Closed without changes'],
]);

const systemName = (name: string) => SYSTEMS.get(name) ?? name;

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

export function labelOf(row: AuditRow): Label {
  const kind = row.action === 'event_received' ? messageOf(row) : null;
  return kind ? message(kind) : action(row.action);
}

export function entityOf(row: AuditRow, productName: ProductName): Entity {
  const id = row.entity_id;
  if (row.entity_type === 'order' && /^(shop|emag)-/.test(id)) return { kind: 'order', id };
  if (row.entity_type === 'stock' && !SYSTEMS.has(id)) {
    return { kind: 'product', name: productName(id) };
  }
  if (row.entity_type === 'event') {
    return { kind: 'text', text: systemName(String(row.detail.source)) };
  }
  if (row.entity_type === 'settings') return { kind: 'text', text: 'Settings' };
  return { kind: 'text', text: systemName(id) };
}

function orderLines(lines: unknown, productName: ProductName): string {
  if (!Array.isArray(lines)) return '';
  return lines.map((line) => `${line.qty} × ${productName(String(line.sku))}`).join(', ');
}

// `sample` marks rows from the sample history; the tables show that as a tag instead.
function plain(detail: AuditRow['detail']): string {
  return Object.entries(detail)
    .filter(([key]) => key !== 'sample')
    .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
    .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`)
    .join(' · ');
}

export function describe(row: AuditRow, productName: ProductName): string {
  const detail = row.detail;
  const text = (key: string) => String(detail[key] ?? '');
  switch (row.action) {
    case 'event_received': {
      const kind = messageOf(row);
      return kind ? MESSAGE_DETAILS[kind] : text('type');
    }
    case 'duplicate_dropped':
      return 'the same message arrived again';
    case 'order_known':
      return 'the channel sent an order Glue already had';
    case 'emag_acknowledged':
      return 'eMAG will stop re-sending this order';
    case 'order_shipped':
      return `shipped; ${systemName(text('channel'))} was told`;
    case 'order_allocated':
      return orderLines(detail.lines, productName);
    case 'retry_scheduled': {
      const next = `next in ${text('delay_seconds')} seconds`;
      return `${text('problem')} · try ${text('attempt')}, ${next}`;
    }
    case 'stock_pushed': {
      const held = detail.held_back ? ` · ${text('held_back')} held back by a rule` : '';
      return `${systemName(text('channel'))} now shows ${text('qty')}${held}`;
    }
    case 'stock_push_failed':
      return `${systemName(text('channel'))} refused ${text('qty')} · ${text('problem')}`;
    case 'order_failed':
    case 'unfulfillable':
    case 'review_opened':
      return text('reason');
    case 'warehouse_unreachable':
      return text('problem');
    case 'review_decided':
      return `${DECISIONS.get(text('decision')) ?? text('decision')} by ${text('decided_by')}`;
    case 'signed_in':
      return `as ${text('role')}`;
    default:
      return plain(detail);
  }
}
