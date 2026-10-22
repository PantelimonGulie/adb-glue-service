import { expect, it } from 'vitest';
import { formatDay, formatNumber, formatSeconds, formatTime, formatWindow } from './format';

it('groups thousands', () => {
  expect(formatNumber(12345)).toBe('12,345');
});

it('shows seconds to at most two decimals', () => {
  expect(formatSeconds(0.04)).toBe('0.04 s');
  expect(formatSeconds(1.456)).toBe('1.46 s');
  expect(formatSeconds(0)).toBe('0 s');
});

it('shows the time of day of a server timestamp', () => {
  const ts = '2026-10-22T10:41:58.123+00:00';
  expect(formatTime(ts)).toBe(new Date(ts).toLocaleTimeString('en-GB'));
});

it('names a time window by its hours and day', () => {
  const hours = (ts: string) =>
    new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  const day = (ts: string) =>
    new Date(ts).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const since = '2026-10-22T11:00:00.000Z';
  const until = '2026-10-22T11:05:00.000Z';
  expect(formatWindow(since, until)).toBe(`${hours(since)}–${hours(until)}, ${day(since)}`);

  const first = '2026-10-01T00:00:00.000Z';
  const week = '2026-10-08T00:00:00.000Z';
  expect(formatWindow(first, week)).toBe(
    `${hours(first)}, ${day(first)} – ${hours(week)}, ${day(week)}`,
  );
});

it('adds the day only to times that are not from today', () => {
  const now = new Date('2026-10-22T12:00:00.000Z');
  expect(formatDay(now.toISOString(), now)).toBe('');
  expect(formatDay('2026-10-01T12:00:00.000Z', now)).toBe('1 Oct');
});

it('keeps a window that ends at midnight on its own day', () => {
  const since = new Date(2026, 9, 22, 23, 0).toISOString();
  const until = new Date(2026, 9, 23, 0, 0).toISOString();

  expect(formatWindow(since, until)).toBe('23:00–00:00, 22 Oct');
});
