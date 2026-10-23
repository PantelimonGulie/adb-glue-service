import { afterEach, expect, it } from 'vitest';
import {
  formatDate,
  formatDateTime,
  formatDay,
  formatDayLabel,
  formatDecimal,
  formatHours,
  formatLatency,
  formatNumber,
  formatSeconds,
  formatTime,
  formatWindow,
  setTimeZone,
  zonedDate,
  zonedMidnight,
} from './format';

afterEach(() => setTimeZone(undefined));

it('groups thousands', () => {
  expect(formatNumber(12345)).toBe('12,345');
});

it('shows a set number of seconds as it was set', () => {
  expect(formatSeconds(0.04)).toBe('0.04 s');
  expect(formatSeconds(1.456)).toBe('1.46 s');
  expect(formatSeconds(0)).toBe('0 s');
});

it('shows measured seconds always with two decimals and other decimals with one', () => {
  const measured = [0.1, 0.14, 0, 12.5].map(formatLatency);
  const decimals = [0.4, 2, 1234.56].map((value) => formatDecimal(value));

  expect(measured).toEqual(['0.10 s', '0.14 s', '0.00 s', '12.50 s']);
  expect(decimals).toEqual(['0.4', '2.0', '1,234.6']);
});

it('shows times in the business timezone, whatever the browser is set to', () => {
  // 21:30 UTC is already 00:30 the next day in Bucharest.
  const ts = '2026-10-22T21:30:00.000+00:00';

  expect(formatTime(ts)).toBe('00:30:00');
  expect(formatHours(ts)).toBe('00:30');
  expect(formatDate(ts)).toBe('23 Oct');
  expect(formatDateTime(ts)).toBe('23 Oct, 00:30');
  expect(zonedDate(new Date(ts))).toBe('2026-10-23');

  setTimeZone('UTC');
  expect(formatDateTime(ts)).toBe('22 Oct, 21:30');
});

it('finds midnight in Bucharest, also on the day the clocks go back', () => {
  expect(zonedMidnight('2026-10-25')).toBe('2026-10-24T21:00:00.000Z');
  expect(zonedMidnight('2026-10-26')).toBe('2026-10-25T22:00:00.000Z');
});

it('names a calendar day the same way as every other date', () => {
  expect(formatDayLabel('2026-10-01')).toBe('1 Oct');
});

it('names a time window by its hours and day', () => {
  expect(formatWindow('2026-10-22T11:00:00.000Z', '2026-10-22T11:05:00.000Z')).toBe(
    '14:00–14:05, 22 Oct',
  );
  expect(formatWindow('2026-09-30T21:00:00.000Z', '2026-10-07T21:00:00.000Z')).toBe(
    '00:00, 1 Oct – 00:00, 8 Oct',
  );
});

it('adds the day only to times that are not from today in Bucharest', () => {
  const now = new Date('2026-10-22T21:30:00.000Z');
  expect(formatDay('2026-10-22T21:10:00.000Z', now)).toBe('');
  expect(formatDay('2026-10-22T20:50:00.000Z', now)).toBe('22 Oct');
});

it('keeps a window that ends at midnight on its own day', () => {
  expect(formatWindow('2026-10-22T20:00:00.000Z', '2026-10-22T21:00:00.000Z')).toBe(
    '23:00–00:00, 22 Oct',
  );
});
