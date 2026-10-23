import { expect, it } from 'vitest';
import { change, comparedWith, counterCells } from './counterCells';

it('names the period the API compares with', () => {
  const now = new Date('2026-10-22T09:00:00Z');
  expect(comparedWith({ range: 'live' }, now)).toBeNull();
  expect(comparedWith({ range: 'today' }, now)).toBe('yesterday');
  expect(comparedWith({ range: 'month' }, now)).toBe('the 22 days before');
  // Still 31 October in UTC, already the first of November in Bucharest.
  expect(comparedWith({ range: 'month' }, new Date('2026-10-31T22:30:00Z'))).toBe('the day before');
  expect(comparedWith({ range: 'custom', from: '2026-10-01', to: '2026-10-01' }, now)).toBe(
    'the day before',
  );
});

it('describes a change without dividing by zero', () => {
  expect(change('yesterday', 5, 0, true)).toEqual({ text: '+5 vs yesterday', good: true });
  expect(change('yesterday', 0, 4, false)).toEqual({ text: '-100% vs yesterday', good: true });
  expect(change('yesterday', 1001, 1000, true)).toEqual({ text: 'about the same as yesterday' });
});

it('says what each counter counts', () => {
  const hints = Object.fromEntries(
    counterCells({ range: 'today' }, undefined).map((c) => [c.key, c.hint]),
  );

  expect(hints.reserved).toMatch(/^Of the orders in this period/);
  expect(hints.failed).toMatch(/^Of the orders in this period/);
  expect(hints.retries).toMatch(/warehouse, eMAG or the shop/);
});
