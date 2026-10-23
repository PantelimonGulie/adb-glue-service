import { useSearchParams } from 'react-router-dom';
import type { RangeName, RangeQuery } from '../api/types';
import { formatDayLabel, zonedDate } from './format';

export const RANGES: { value: RangeName; label: string }[] = [
  { value: 'live', label: 'Live · 15 min' },
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'Last 7 days' },
  { value: 'month', label: 'This month' },
  { value: 'custom', label: 'Custom' },
];

const DEFAULT: RangeQuery = { range: 'live' };
const YEAR_MS = 366 * 24 * 3600 * 1000;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function customRangeError(from: string, to: string): string | null {
  if (!DATE.test(from) || !DATE.test(to)) return 'Pick both dates.';
  if (from > to) return 'The first day must not be after the last day.';
  if (Date.parse(to) - Date.parse(from) >= YEAR_MS) {
    return 'A custom range can cover at most a year.';
  }
  return null;
}

export function readRange(params: URLSearchParams): RangeQuery {
  const name = params.get('range');
  if (name === 'custom') {
    const from = params.get('from') ?? '';
    const to = params.get('to') ?? '';
    return customRangeError(from, to) ? DEFAULT : { range: 'custom', from, to };
  }
  const known = RANGES.find((range) => range.value === name);
  return known ? { range: known.value } : DEFAULT;
}

export function rangeParams(query: RangeQuery): RangeQuery {
  if (query.range !== 'custom') return { range: query.range };
  return { range: 'custom', from: query.from, to: query.to };
}

export function rangeSearch(query: RangeQuery): string {
  const params = rangeParams(query);
  const search = new URLSearchParams({ range: params.range });
  if (params.from && params.to) {
    search.set('from', params.from);
    search.set('to', params.to);
  }
  return search.toString();
}

export function rangeLabel(query: RangeQuery): string {
  if (query.range === 'custom') {
    const { from = '', to = '' } = query;
    // The year only when the range crosses one, as "29 Dec 2025 to 4 Jan 2026".
    const sameYear = from.slice(0, 4) === to.slice(0, 4);
    const day = (date: string) =>
      sameYear ? formatDayLabel(date) : `${formatDayLabel(date)} ${date.slice(0, 4)}`;
    return `${day(from)} to ${day(to)}`;
  }
  return RANGES.find((range) => range.value === query.range)?.label ?? query.range;
}

// The month and the day as the business counts them, like the API's own ranges.
export function thisMonth(now = new Date()): RangeQuery {
  const today = zonedDate(now);
  return { range: 'custom', from: `${today.slice(0, 8)}01`, to: today };
}

export type SetRange = (next: RangeQuery, options?: { replace?: boolean }) => void;

export function useRange(): [RangeQuery, SetRange] {
  const [params, setParams] = useSearchParams();
  const setRange: SetRange = (next, options) =>
    setParams((current) => {
      const updated = new URLSearchParams(current);
      for (const key of ['range', 'from', 'to', 'page']) updated.delete(key);
      for (const [key, value] of Object.entries(rangeParams(next))) {
        if (value) updated.set(key, value);
      }
      return updated;
    }, options);
  return [readRange(params), setRange];
}
