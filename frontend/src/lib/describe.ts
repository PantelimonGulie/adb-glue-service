import type { AuditRow } from '../api/types';
import { decider, messageOf, RULES, systemName, type ProductName } from './activity';
import type { Message } from './labels';
import { plainProblem, seconds } from './problem';

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
const SUGGESTIONS = new Map([
  ['retry', 'Retry'],
  ['cancel', 'Cancel'],
  ['dismiss', 'Close without changes'],
]);

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

function cancelled(detail: AuditRow['detail']): string {
  if (detail.note) return 'the cancellation came before the order';
  return detail.was === 'allocated' ? 'the reserved unit went back on the shelf' : 'nothing was reserved';
}

export function describe(row: AuditRow, productName: ProductName): string {
  const detail = row.detail;
  const text = (key: string) => String(detail[key] ?? '');
  const channel = () => systemName(text('channel'));
  switch (row.action) {
    case 'event_received': {
      const kind = messageOf(row);
      return kind ? MESSAGE_DETAILS[kind] : text('type');
    }
    case 'duplicate_dropped':
      return 'the same message arrived again';
    case 'order_known':
      return 'the channel sent an order Glue already had';
    case 'cancel_repeated':
      return 'the order was already cancelled';
    case 'emag_acknowledged':
      return 'eMAG will stop re-sending this order';
    case 'order_shipped':
      return `shipped; ${channel()} was told`;
    case 'order_allocated':
      return orderLines(detail.lines, productName);
    case 'order_cancelled':
      return cancelled(detail);
    case 'retry_scheduled': {
      const next = `next in ${seconds(Number(detail.delay_seconds))}`;
      return `${plainProblem(text('problem'))} · try ${text('attempt')}, ${next}`;
    }
    case 'stock_pushed': {
      const held = detail.held_back ? ` · ${text('held_back')} held back by a rule` : '';
      return `${channel()} accepted ${text('qty')}${held}`;
    }
    case 'stock_push_failed':
      return `${channel()} did not take ${text('qty')} · ${plainProblem(text('problem'))}`;
    case 'order_failed':
    case 'unfulfillable':
      return plainProblem(text('reason'));
    case 'event_failed':
      return plainProblem(text('error'));
    case 'warehouse_unreachable':
      return plainProblem(text('problem'));
    case 'review_opened':
      return 'waiting for a person in the review queue';
    case 'review_resolved':
      return text('why');
    case 'review_decided':
      return `${DECISIONS.get(text('decision')) ?? text('decision')} by ${decider(text('decided_by'))}`;
    case 'rule_applied':
      return `the ${(RULES.get(text('rule')) ?? 'rule').toLowerCase()} sends it again`;
    case 'rule_changed':
      return `turned ${detail.enabled ? 'on' : 'off'} by ${text('by')}`;
    case 'triage_suggested':
      return `${SUGGESTIONS.get(text('suggested')) ?? 'No single choice'}. ${text('reason')}`;
    case 'signature_rejected':
      return 'no valid signature, so Glue refused it';
    case 'signed_in':
      return `as ${text('role')}`;
    default:
      return plain(detail);
  }
}
