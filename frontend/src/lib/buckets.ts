import type { Analytics } from '../api/types';
import { formatDayLabel, formatHours, zonedMidnight } from './format';

type Range = Analytics['range'];

const STEP_MS = { minute: 60_000, hour: 3_600_000 };

const nextDay = (day: string) =>
  new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);

// Like the backend: minutes and hours from the range start, days from Bucharest midnight,
// named by the dates the API labels them with.
export function bucketBounds(range: Range, index: number) {
  if (range.unit === 'day') {
    const day = range.labels[index];
    return { since: zonedMidnight(day), until: zonedMidnight(nextDay(day)) };
  }
  const step = STEP_MS[range.unit];
  const since = Date.parse(range.since);
  const start = since - (since % step) + index * step;
  return { since: new Date(start).toISOString(), until: new Date(start + step).toISOString() };
}

// Every bar reads in the business timezone, like every other time on screen.
export function bucketLabels(range: Range): string[] {
  if (range.unit === 'day') return range.labels.map(formatDayLabel);
  return range.labels.map((_, index) => formatHours(bucketBounds(range, index).since));
}

export const bucketIds = (range: Range): string[] =>
  range.labels.map((_, index) => bucketBounds(range, index).since);
