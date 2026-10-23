import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { analytics } from '../../test/fixtures';
import { OrdersChart } from './OrdersChart';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const range = {
  since: '2026-10-25T00:00:00.000+00:00',
  until: '2026-10-25T02:00:00.000+00:00',
  unit: 'hour' as const,
  labels: ['00:00', '01:00'],
};

it('draws every hour on the day clocks go back, though two hours read the same', () => {
  vi.stubEnv('TZ', 'Europe/Bucharest');
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-10-26T00:00:00.000Z'));
  const consoleError = vi.spyOn(console, 'error');

  render(<OrdersChart analytics={{ ...analytics, range }} />);

  expect(screen.getByTitle('03:00: 15 orders')).toBeInTheDocument();
  expect(screen.getByTitle('03:00: 25 orders, 4 needed a retry or were not reserved')).toBeInTheDocument();
  expect(consoleError).not.toHaveBeenCalled();
});

it('leaves off the hours that have not started yet', () => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-10-25T00:30:00.000Z'));

  render(<OrdersChart analytics={{ ...analytics, range }} />);

  expect(screen.getAllByTitle(/orders/)).toHaveLength(1);
});
