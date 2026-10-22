import type { AuditRow } from '../api/types';

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
const MESSAGES = new Map([
  ['order.placed', 'new order'],
  ['order.cancelled', 'cancellation'],
  ['emag.notification', 'order notification'],
  ['order.shipped', 'shipment'],
  ['stock.adjusted', 'stock change'],
]);
const DECISIONS = new Map([
  ['retry', 'Retried'],
  ['cancel', 'Cancelled'],
  ['dismiss', 'Closed without changes'],
]);

const systemName = (name: string) => SYSTEMS.get(name) ?? name;

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

function plain(detail: AuditRow['detail']): string {
  return Object.entries(detail)
    .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
    .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`)
    .join(' · ');
}

export function describe(row: AuditRow, productName: ProductName): string {
  const detail = row.detail;
  const text = (key: string) => String(detail[key] ?? '');
  switch (row.action) {
    case 'event_received':
      return MESSAGES.get(text('type')) ?? text('type');
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
