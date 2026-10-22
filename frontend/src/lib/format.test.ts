import { expect, it } from 'vitest';
import { formatNumber, formatTime } from './format';

it('groups thousands', () => {
  expect(formatNumber(12345)).toBe('12,345');
});

it('shows the time of day of a server timestamp', () => {
  const ts = '2026-10-22T10:41:58.123+00:00';
  expect(formatTime(ts)).toBe(new Date(ts).toLocaleTimeString('en-GB'));
});
