import { expect, it } from 'vitest';
import type { Analytics } from '../../api/types';
import { bucketEvents } from './charts';

const range = (unit: Analytics['range']['unit'], since: string): Analytics['range'] => ({
  since,
  until: '',
  unit,
  labels: [],
});

const query = (link: string) => {
  const url = new URL(link, 'http://glue');
  return { path: url.pathname, ...Object.fromEntries(url.searchParams) };
};

it('opens exactly the time of the picked bar', () => {
  const day = bucketEvents(range('day', '2026-10-01T00:00:00.000+00:00'), 4, 'stock');
  const hour = bucketEvents(range('hour', '2026-10-22T00:00:00.000+00:00'), 13, 'orders');
  const minute = bucketEvents(range('minute', '2026-10-22T23:58:31.250+00:00'), 2);

  expect(query(day)).toEqual({
    path: '/activity',
    since: '2026-10-05T00:00:00.000Z',
    until: '2026-10-06T00:00:00.000Z',
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
