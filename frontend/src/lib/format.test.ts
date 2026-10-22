import { expect, it } from 'vitest';
import { formatNumber, formatSeconds, formatTime } from './format';

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
