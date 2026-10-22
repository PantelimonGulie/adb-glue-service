import type { Analytics } from '../api/types';
import { formatHours } from './format';

type Range = Analytics['range'];

const STEP_MS = { minute: 60_000, hour: 3_600_000, day: 86_400_000 };

// Like the backend, buckets start at the range start cut down to a whole minute, hour or UTC day.
export function bucketBounds(range: Range, index: number) {
  const step = STEP_MS[range.unit];
  const since = Date.parse(range.since);
  const start = since - (since % step) + index * step;
  return { since: new Date(start).toISOString(), until: new Date(start + step).toISOString() };
}

// Minutes and hours read in the browser's time, like every other time on screen.
export function bucketLabels(range: Range): string[] {
  if (range.unit === 'day') return range.labels;
  return range.labels.map((_, index) => formatHours(bucketBounds(range, index).since));
}

export const bucketIds = (range: Range): string[] =>
  range.labels.map((_, index) => bucketBounds(range, index).since);
