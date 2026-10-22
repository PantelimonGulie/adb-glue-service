import { describe, expect, it } from 'vitest';
import { customRangeError, rangeLabel, rangeParams, rangeSearch, readRange } from './range';

const read = (search: string) => readRange(new URLSearchParams(search));

describe('readRange', () => {
  it('defaults to the live range', () => {
    expect(read('')).toEqual({ range: 'live' });
    expect(read('range=yesterday')).toEqual({ range: 'live' });
  });

  it('reads a named or custom range', () => {
    expect(read('range=week')).toEqual({ range: 'week' });
    expect(read('range=custom&from=2026-10-01&to=2026-10-22')).toEqual({
      range: 'custom',
      from: '2026-10-01',
      to: '2026-10-22',
    });
  });

  it('ignores a custom range the server would refuse', () => {
    expect(read('range=custom&from=2026-10-22&to=2026-10-01')).toEqual({ range: 'live' });
  });
});

describe('customRangeError', () => {
  it('accepts a range in order', () => {
    expect(customRangeError('2026-10-01', '2026-10-01')).toBeNull();
  });

  it('explains what is wrong', () => {
    expect(customRangeError('', '2026-10-22')).toBe('Pick both dates.');
    expect(customRangeError('2026-10-22', '2026-10-01')).toBe(
      'The first day must not be after the last day.',
    );
    expect(customRangeError('2025-01-01', '2026-10-22')).toBe(
      'A custom range can cover at most a year.',
    );
  });
});

it('sends dates only for a custom range', () => {
  expect(rangeParams({ range: 'week', from: '2026-10-01' })).toEqual({ range: 'week' });
  expect(rangeParams({ range: 'custom', from: '2026-10-01', to: '2026-10-02' })).toEqual({
    range: 'custom',
    from: '2026-10-01',
    to: '2026-10-02',
  });
});

it('names a range and writes it into a link', () => {
  const custom = { range: 'custom', from: '2026-10-01', to: '2026-10-22' } as const;
  expect(rangeLabel({ range: 'month' })).toBe('This month');
  expect(rangeLabel(custom)).toBe('2026-10-01 to 2026-10-22');
  expect(rangeSearch({ range: 'today' })).toBe('range=today');
  expect(rangeSearch(custom)).toBe('range=custom&from=2026-10-01&to=2026-10-22');
});
