import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderPage } from '../../test/render';
import { BarChart, type Series } from './BarChart';
import styles from './BarChart.module.css';

const SHOP = 'var(--chart-shop)';
const EMAG = 'var(--chart-emag)';
const series: Series[] = [
  { key: 'shop', name: 'Shop', color: SHOP, values: [1, 2] },
  { key: 'emag', name: 'eMAG', color: EMAG, values: [3, 4] },
];

// Every bar has started unless a test moves the clock back.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-10-26T00:00:00.000Z'));
});

afterEach(() => {
  vi.useRealTimers();
});

function renderChart(labels = ['00:00', '01:00'], values = series, route = '/flow') {
  const { container } = renderPage(
    <BarChart
      title="Orders per hour"
      note="by channel"
      ids={['2026-10-25T00:00:00.000Z', '2026-10-25T01:00:00.000Z']}
      labels={labels}
      series={values}
      eventsLink={(index) => `/activity?bucket=${index}`}
    />,
    { route },
  );
  return (color: string) => container.querySelectorAll(`.recharts-rectangle[fill="${color}"]`);
}

it('legend toggles a series', async () => {
  const bars = renderChart();
  const shop = screen.getByRole('button', { name: 'Shop' });
  expect(bars(SHOP)).toHaveLength(2);

  await userEvent.click(shop);

  expect(shop).toHaveAttribute('aria-pressed', 'false');
  expect(bars(SHOP)).toHaveLength(0);
  expect(bars(EMAG)).toHaveLength(2);

  await userEvent.click(shop);

  expect(bars(SHOP)).toHaveLength(2);
});

it('clicking a bar opens its detail', async () => {
  const bars = renderChart();

  await userEvent.click(bars(EMAG)[1]);

  const detail = screen.getByRole('group', { name: 'Numbers for 01:00' });
  expect(detail).toHaveTextContent('Shop 2');
  expect(detail).toHaveTextContent('eMAG 4');
  const open = within(detail).getByRole('link', { name: 'Open these events' });
  expect(open).toHaveAttribute('href', '/activity?bucket=1&range=live');
  expect(bars(EMAG)[1]).toHaveClass(styles.picked);
  expect(bars(EMAG)[0]).toHaveClass(styles.dim);

  await userEvent.click(within(detail).getByRole('button', { name: 'Close' }));

  expect(screen.queryByRole('group', { name: /Numbers for/ })).not.toBeInTheDocument();
  expect(bars(EMAG)[0]).not.toHaveClass(styles.dim);
});

it('the bars can be picked with the keyboard', async () => {
  renderChart();
  const first = screen.getByRole('button', { name: '00:00: Shop 1, eMAG 3' });
  expect(screen.getByRole('button', { name: '01:00: Shop 2, eMAG 4' })).toHaveAttribute(
    'tabindex',
    '-1',
  );

  await userEvent.tab();
  await userEvent.tab();
  await userEvent.tab();
  expect(first).toHaveFocus();
  await userEvent.keyboard('{ArrowRight}');
  const second = screen.getByRole('button', { name: '01:00: Shop 2, eMAG 4' });
  expect(second).toHaveFocus();
  await userEvent.keyboard('{Enter}');

  expect(second).toHaveAttribute('aria-pressed', 'true');
  const detail = screen.getByRole('group', { name: 'Numbers for 01:00' });
  await userEvent.tab();
  expect(within(detail).getByRole('link', { name: 'Open these events' })).toHaveFocus();
});

it('keeps two bars with the same label apart, as on the day clocks go back', async () => {
  const bars = renderChart(['03:00', '03:00']);

  await userEvent.click(bars(EMAG)[1]);

  const detail = screen.getByRole('group', { name: 'Numbers for 03:00' });
  expect(detail).toHaveTextContent('Shop 2');
  const open = within(detail).getByRole('link', { name: 'Open these events' });
  expect(open).toHaveAttribute('href', '/activity?bucket=1&range=live');
  expect(bars(EMAG)[1]).toHaveClass(styles.picked);
  expect(bars(EMAG)[0]).toHaveClass(styles.dim);
  expect(screen.getByRole('button', { name: '03:00: Shop 2, eMAG 4' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  expect(screen.getByRole('button', { name: '03:00: Shop 1, eMAG 3' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
});

it('leaves off the hours that have not started yet, so the bars use the width', () => {
  vi.setSystemTime(new Date('2026-10-25T00:30:00.000Z'));
  const bars = renderChart();

  expect(bars(EMAG)).toHaveLength(1);
  expect(screen.getByRole('button', { name: '00:00: Shop 1, eMAG 3' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^01:00/ })).toBeNull();
});

it('says so when nothing happened in the period', () => {
  const quiet = series.map((one) => ({ ...one, values: [0, 0] }));
  renderChart(['00:00', '01:00'], quiet);

  expect(screen.getByText('Nothing in this period')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^00:00/ })).toBeNull();
});

it('the events link keeps the range the chart shows, so clearing the bar goes back to it', async () => {
  const bars = renderChart(
    ['00:00', '01:00'],
    series,
    '/flow?range=custom&from=2026-10-01&to=2026-10-25',
  );

  await userEvent.click(bars(EMAG)[1]);

  const open = screen.getByRole('link', { name: 'Open these events' });
  const link = new URL(open.getAttribute('href')!, 'http://glue').searchParams;
  expect([link.get('bucket'), link.get('range'), link.get('from'), link.get('to')]).toEqual([
    '1',
    'custom',
    '2026-10-01',
    '2026-10-25',
  ]);
});
