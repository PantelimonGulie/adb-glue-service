import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it } from 'vitest';
import { renderPage } from '../../test/render';
import { BarChart, type Series } from './BarChart';
import styles from './BarChart.module.css';

const SHOP = 'var(--chart-shop)';
const EMAG = 'var(--chart-emag)';
const series: Series[] = [
  { key: 'shop', name: 'Shop', color: SHOP, values: [1, 2] },
  { key: 'emag', name: 'eMAG', color: EMAG, values: [3, 4] },
];

function renderChart() {
  const { container } = renderPage(
    <BarChart
      title="Orders per hour"
      note="by channel"
      labels={['00:00', '01:00']}
      series={series}
      eventsLink={(index) => `/activity?bucket=${index}`}
    />,
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
  expect(open).toHaveAttribute('href', '/activity?bucket=1');
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
