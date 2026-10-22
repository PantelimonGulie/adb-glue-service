import type { AuditRow } from '../../api/types';
import { isPlacement } from '../../lib/activity';
import type { Tone } from '../../lib/labels';
import type { Route } from './layout';

export type Motion = 'travel' | 'knock' | 'drop';

export interface Dot {
  id: number;
  route: Route;
  tone: Tone;
  motion: Motion;
  delay: number;
}

export interface LiveDots {
  dots: Dot[];
  summary: string | null;
}

const MAX_DOTS = 30;
// One poll brings its rows at once; spreading them over most of the poll keeps them apart.
const SPREAD_SECONDS = 1.5;

export const LEGEND: { tone: Tone; label: string }[] = [
  { tone: 'blue', label: 'order in' },
  { tone: 'green', label: 'reserved' },
  { tone: 'amber', label: 'retrying' },
  { tone: 'grey', label: 'duplicate' },
  { tone: 'slate', label: 'stock update' },
];

const INTO_GLUE = new Map<string, Route>([
  ['shop', 'shopIn'],
  ['emag', 'mktIn'],
  ['warehouse', 'whBack'],
]);
const TO_CHANNEL = new Map<string, Route>([
  ['shop', 'shopOut'],
  ['emag', 'mktOut'],
]);

function dotFor(row: AuditRow): Omit<Dot, 'id' | 'delay'> | null {
  const source = String(row.detail.source ?? row.entity_id.split('-')[0]);
  const inbound = INTO_GLUE.get(source);
  const outbound = TO_CHANNEL.get(String(row.detail.channel ?? row.entity_id));
  switch (row.action) {
    case 'event_received':
      // Only a new order is an "order in"; cancellations, shipments and shelf counts are not.
      if (!inbound) return null;
      return { route: inbound, tone: isPlacement(row) ? 'blue' : 'slate', motion: 'travel' };
    case 'duplicate_dropped':
    case 'order_known':
      return inbound ? { route: inbound, tone: 'grey', motion: 'drop' } : null;
    case 'order_allocated':
      return { route: 'whOut', tone: 'green', motion: 'travel' };
    case 'retry_scheduled': {
      const route = row.entity_type === 'order' ? 'whOut' : outbound;
      return route ? { route, tone: 'amber', motion: 'knock' } : null;
    }
    case 'stock_pushed':
      return outbound ? { route: outbound, tone: 'slate', motion: 'travel' } : null;
    case 'stock_push_failed':
      return outbound ? { route: outbound, tone: 'amber', motion: 'knock' } : null;
    default:
      return null;
  }
}

export function dotsForRows(rows: AuditRow[]): LiveDots {
  const all = rows.flatMap((row) => {
    const dot = dotFor(row);
    return dot ? [{ id: row.id, ...dot }] : [];
  });
  const shown = all.slice(-MAX_DOTS);
  const hidden = all.length - shown.length;
  return {
    dots: shown.map((dot, i) => ({ ...dot, delay: (i * SPREAD_SECONDS) / shown.length })),
    summary: hidden > 0 ? `+${hidden} more` : null,
  };
}
