import { expect, it } from 'vitest';
import { analytics } from '../../test/fixtures';
import { mapView } from './model';

const minutes = (busy: number[]) =>
  Array.from({ length: 15 }, (_, i) => busy[i - 15 + busy.length] ?? 0);

it('averages a live rate over the minutes orders came in, not over paused or quiet ones', () => {
  const live = {
    ...analytics,
    series: { ...analytics.series, orders: { shop: minutes([6, 6, 0]), emag: minutes([1, 2, 1]) } },
    parts: {
      ...analytics.parts,
      shop: { ...analytics.parts.shop, orders: 12 },
      emag: { ...analytics.parts.emag, orders: 4 },
    },
  };

  const labels = mapView('live', live, undefined, 10).edges.map((edge) => edge.label);

  expect(labels).toContain('ORDERS\n4/min');
  expect(labels).toContain('NOTIFY · FETCH · CONFIRM\n1.3/min');
});

it('says nothing about a rate before any order came in', () => {
  const quiet = {
    ...analytics,
    series: { ...analytics.series, orders: { shop: minutes([]), emag: minutes([]) } },
  };

  expect(mapView('live', quiet, undefined, 10).edges.map((edge) => edge.label)).toContain('ORDERS');
});

it('names the stock check in a few words', () => {
  expect(mapView('live', undefined, undefined, 10).stockCheck).toBe('STOCK CHECK EVERY 10 S');
});
