import { expect, it } from 'vitest';
import type { Analytics } from '../api/types';
import { bucketBounds, bucketLabels } from './buckets';
import { formatWindow } from './format';

const range = (unit: Analytics['range']['unit'], since: string, labels: string[]) => ({
  since,
  until: '',
  unit,
  labels,
});

it('names hour and minute bars by their local start, as the activity window reads', () => {
  const hours = range('hour', '2026-10-22T00:00:00.000+00:00', Array(24).fill('UTC'));
  const minutes = range('minute', '2026-10-22T13:58:31.250+00:00', Array(15).fill('UTC'));

  for (const bars of [hours, minutes]) {
    const labels = bucketLabels(bars);
    const { since, until } = bucketBounds(bars, 3);
    expect(formatWindow(since, until)).toMatch(new RegExp(`^${labels[3]}–${labels[4]}, `));
  }
});

it('keeps the dates of day bars', () => {
  const days = range('day', '2026-10-01T00:00:00.000+00:00', ['2026-10-01', '2026-10-02']);

  expect(bucketLabels(days)).toEqual(['2026-10-01', '2026-10-02']);
});
