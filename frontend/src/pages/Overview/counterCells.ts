import type { Counters, Overview, RangeQuery } from '../../api/types';
import { formatNumber } from '../../lib/format';

interface Spec {
  key: keyof Counters;
  label: string;
  hint: string;
  upIsGood: boolean;
  tone?: 'good' | 'warn';
}

const SPECS: Spec[] = [
  {
    key: 'received',
    label: 'Orders in',
    hint: 'Orders placed on the shop and on eMAG',
    upIsGood: true,
  },
  {
    key: 'duplicates',
    label: 'Duplicates ignored',
    hint: 'Messages that arrived twice and were handled once',
    upIsGood: false,
  },
  {
    key: 'reserved',
    label: 'Reserved',
    hint: 'Orders the warehouse accepted',
    upIsGood: true,
    tone: 'good',
  },
  {
    key: 'retries',
    label: 'Retries',
    hint: 'Times Glue had to try the warehouse again',
    upIsGood: false,
    tone: 'warn',
  },
  { key: 'failed', label: 'Failed', hint: 'Orders where every try failed', upIsGood: false },
];

const DAY_MS = 24 * 3600 * 1000;

const daysBefore = (days: number) => (days === 1 ? 'the day before' : `the ${days} days before`);

// The API compares with the same length of time just before the range (UTC days).
export function comparedWith(query: RangeQuery, now = new Date()): string | null {
  switch (query.range) {
    case 'live':
      return null;
    case 'today':
      return 'yesterday';
    case 'week':
      return daysBefore(7);
    case 'month':
      return daysBefore(now.getUTCDate());
    case 'custom':
      return daysBefore((Date.parse(`${query.to}`) - Date.parse(`${query.from}`)) / DAY_MS + 1);
  }
}

export interface Change {
  text: string;
  good?: boolean;
}

export function change(vs: string, current: number, previous: number, upIsGood: boolean): Change {
  if (current === previous) return { text: `same as ${vs}` };
  const good = current > previous === upIsGood;
  if (previous === 0) return { text: `+${formatNumber(current)} vs ${vs}`, good };
  const percent = Math.round(((current - previous) / previous) * 100);
  if (percent === 0) return { text: `about the same as ${vs}` };
  return { text: `${percent > 0 ? '+' : ''}${percent}% vs ${vs}`, good };
}

export function counterCells(
  range: RangeQuery,
  overview: Pick<Overview, 'counters' | 'previous'> | undefined,
) {
  const vs = comparedWith(range);
  return SPECS.map(({ key, upIsGood, ...spec }) => {
    const current = overview?.counters[key];
    const previous = overview?.previous?.[key];
    return {
      ...spec,
      key,
      value: current === undefined ? '—' : formatNumber(current),
      change:
        vs && current !== undefined && previous !== undefined
          ? change(vs, current, previous, upIsGood)
          : null,
    };
  });
}
