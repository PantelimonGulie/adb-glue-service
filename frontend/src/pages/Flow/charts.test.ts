import { expect, it } from 'vitest';
import type { Analytics } from '../../api/types';
import { formatWindow } from '../../lib/format';
import { analytics } from '../../test/fixtures';
import { bucketEvents, flowCharts } from './charts';

const range = (
  unit: Analytics['range']['unit'],
  since: string,
  labels: string[] = [],
): Analytics['range'] => ({ since, until: '', unit, labels });

const query = (link: string) => {
  const url = new URL(link, 'http://glue');
  return { path: url.pathname, ...Object.fromEntries(url.searchParams) };
};

it('opens exactly the time of the picked bar', () => {
  const days = ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05'];
  const day = bucketEvents(range('day', '2026-09-30T21:00:00.000+00:00', days), 4, 'stock');
  const hour = bucketEvents(range('hour', '2026-10-22T00:00:00.000+00:00'), 13, 'orders');
  const minute = bucketEvents(range('minute', '2026-10-22T23:58:31.250+00:00'), 2);

  expect(query(day)).toEqual({
    path: '/activity',
    since: '2026-10-04T21:00:00.000Z',
    until: '2026-10-05T21:00:00.000Z',
    kind: 'stock',
  });
  expect(query(hour)).toMatchObject({
    since: '2026-10-22T13:00:00.000Z',
    until: '2026-10-22T14:00:00.000Z',
  });
  expect(query(minute)).toEqual({
    path: '/activity',
    since: '2026-10-23T00:00:00.000Z',
    until: '2026-10-23T00:01:00.000Z',
  });
});

it('names each bar by the start of the activity window it opens', () => {
  for (const chart of flowCharts(analytics)) {
    const link = new URL(chart.eventsLink(1), 'http://glue').searchParams;
    const window = formatWindow(link.get('since')!, link.get('until')!);
    expect(window).toMatch(new RegExp(`^${chart.labels[1]}–`));
  }
});
