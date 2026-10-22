import type { ActivityKind, Analytics, Channel } from '../../api/types';
import type { Series } from '../../components/BarChart/BarChart';
import { formatSeconds } from '../../lib/format';
import { rangeSearch } from '../../lib/range';

type Range = Analytics['range'];

interface Chart {
  id: string;
  title: string;
  note: string;
  kind: ActivityKind;
  series: Series[];
  grouped?: boolean;
  format?: (value: number) => string;
}

// The activity log filters by whole days, so an hour opens its day and a minute the live window.
export function bucketEvents(range: Range, label: string, kind: ActivityKind): string {
  const day = range.unit === 'day' ? label : range.since.slice(0, 10);
  const window =
    range.unit === 'minute' ? 'range=live' : rangeSearch({ range: 'custom', from: day, to: day });
  return `/activity?kind=${kind}&${window}`;
}

const byChannel = (values: Record<Channel, number[]>): Series[] => [
  { key: 'shop', name: 'Shop', color: 'var(--chart-shop)', values: values.shop },
  { key: 'emag', name: 'eMAG', color: 'var(--chart-emag)', values: values.emag },
];

export function flowCharts({ range, series }: Analytics) {
  const { orders, problems, latency } = series;
  const per = `per ${range.unit}`;
  const totals = orders.shop.map((count, i) => count + orders.emag[i]);
  // Retries count tries, not orders, so the red part never outgrows the bar.
  const troubled = totals.map((total, i) =>
    Math.min(total, problems.retried[i] + problems.failed[i]),
  );
  const charts: Chart[] = [
    {
      id: 'all',
      title: `Orders ${per}`,
      note: 'all channels · red part had problems',
      kind: 'all',
      series: [
        {
          key: 'fine',
          name: 'Fine',
          color: 'var(--chart-fine)',
          values: totals.map((total, i) => total - troubled[i]),
        },
        { key: 'problems', name: 'Problems', color: 'var(--tone-red-dot)', values: troubled },
      ],
    },
    {
      id: 'channels',
      title: `Orders ${per}`,
      note: 'by channel',
      kind: 'orders',
      series: byChannel(orders),
    },
    {
      id: 'problems',
      title: `Problems ${per}`,
      note: 'retries and failures',
      kind: 'all',
      series: [
        { key: 'retried', name: 'Retried', color: 'var(--chart-retried)', values: problems.retried },
        { key: 'failed', name: 'Failed', color: 'var(--tone-red-dot)', values: problems.failed },
      ],
    },
    {
      id: 'latency',
      title: 'Time from order to reserved',
      note: 'in seconds, side by side',
      kind: 'orders',
      grouped: true,
      format: formatSeconds,
      series: [
        { key: 'p50', name: 'Typical', color: 'var(--chart-typical)', values: latency.p50 },
        { key: 'p95', name: 'Slowest 5%', color: 'var(--blue)', values: latency.p95 },
      ],
    },
    {
      id: 'sync',
      title: 'Channels out of sync',
      note: 'products where a channel showed the wrong stock',
      kind: 'stock',
      series: byChannel(series.out_of_sync),
    },
  ];
  return charts.map(({ kind, ...chart }) => ({
    ...chart,
    labels: range.labels,
    eventsLink: (label: string) => bucketEvents(range, label, kind),
  }));
}
