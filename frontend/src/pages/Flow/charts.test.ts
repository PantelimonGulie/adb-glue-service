import { expect, it } from 'vitest';
import type { Analytics } from '../../api/types';
import { bucketEvents } from './charts';

const range = (unit: Analytics['range']['unit']): Analytics['range'] => ({
  since: '2026-10-22T00:00:00.000+00:00',
  until: '2026-10-23T00:00:00.000+00:00',
  unit,
  labels: [],
});

it('opens the narrowest window the activity log can filter by', () => {
  expect(bucketEvents(range('day'), '2026-10-05', 'stock')).toBe(
    '/activity?kind=stock&range=custom&from=2026-10-05&to=2026-10-05',
  );
  expect(bucketEvents(range('hour'), '13:00', 'orders')).toBe(
    '/activity?kind=orders&range=custom&from=2026-10-22&to=2026-10-22',
  );
  expect(bucketEvents(range('minute'), '13:07', 'all')).toBe('/activity?kind=all&range=live');
});
