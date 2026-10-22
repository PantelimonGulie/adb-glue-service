import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { analytics } from '../../test/fixtures';
import { OrdersChart } from './OrdersChart';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

it('draws every hour on the day clocks go back, though two hours read the same', () => {
  vi.stubEnv('TZ', 'Europe/Bucharest');
  const consoleError = vi.spyOn(console, 'error');
  const range = {
    since: '2026-10-25T00:00:00.000+00:00',
    until: '2026-10-25T02:00:00.000+00:00',
    unit: 'hour' as const,
    labels: ['00:00', '01:00'],
  };

  render(<OrdersChart analytics={{ ...analytics, range }} />);

  expect(screen.getByTitle('03:00: 15 orders')).toBeInTheDocument();
  expect(screen.getByTitle('03:00: 25 orders, 4 retries or failures')).toBeInTheDocument();
  expect(consoleError).not.toHaveBeenCalled();
});
