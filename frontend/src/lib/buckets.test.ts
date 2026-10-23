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

it('names hour and minute bars by their Bucharest start, as the activity window reads', () => {
  const hours = range('hour', '2026-10-21T21:00:00.000+00:00', Array(24).fill('UTC'));
  const minutes = range('minute', '2026-10-22T13:58:31.250+00:00', Array(15).fill('UTC'));

  expect(bucketLabels(hours).slice(0, 3)).toEqual(['00:00', '01:00', '02:00']);
  for (const bars of [hours, minutes]) {
    const labels = bucketLabels(bars);
    const { since, until } = bucketBounds(bars, 3);
    expect(formatWindow(since, until)).toMatch(new RegExp(`^${labels[3]}–${labels[4]}, `));
  }
});

it('cuts day bars at Bucharest midnight, 25 hours long when the clocks go back', () => {
  const days = range('day', '2026-10-23T21:00:00.000+00:00', [
    '2026-10-24',
    '2026-10-25',
    '2026-10-26',
  ]);
  const { since, until } = bucketBounds(days, 1);

  expect(bucketLabels(days)).toEqual(['24 Oct', '25 Oct', '26 Oct']);
  expect({ since, until }).toEqual({
    since: '2026-10-24T21:00:00.000Z',
    until: '2026-10-25T22:00:00.000Z',
  });
  expect(formatWindow(since, until)).toBe('00:00–00:00, 25 Oct');
});
