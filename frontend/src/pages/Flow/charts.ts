import type { ActivityKind, Analytics, Channel } from '../../api/types';
import type { Series } from '../../components/BarChart/BarChart';
import { bucketBounds, bucketIds, bucketLabels } from '../../lib/buckets';
import { formatLatency } from '../../lib/format';

type Range = Analytics['range'];

interface Chart {
  id: string;
  title: string;
  note: string;
  // Left out when a bar mixes kinds, so the log shows everything in that time.
  kind?: ActivityKind;
  series: Series[];
  grouped?: boolean;
  format?: (value: number) => string;
}

export function bucketEvents(range: Range, index: number, kind?: ActivityKind): string {
  const params = new URLSearchParams(bucketBounds(range, index));
  if (kind) params.set('kind', kind);
  return `/activity?${params}`;
}

const byChannel = (values: Record<Channel, number[]>): Series[] => [
  { key: 'shop', name: 'Shop', color: 'var(--chart-shop)', values: values.shop },
  { key: 'emag', name: 'eMAG', color: 'var(--chart-emag)', values: values.emag },
];

export function flowCharts({ range, series }: Analytics) {
  const { orders, problems, latency } = series;
  const per = `per ${range.unit}`;
  const totals = orders.shop.map((count, i) => count + orders.emag[i]);
  // Both count orders by when they came in, so the red part is a part of the bar.
  const troubled = problems.retried.map((retried, i) => retried + problems.failed[i]);
  const charts: Chart[] = [
    {
      id: 'all',
      title: `Orders ${per}`,
      note: 'all channels · red: needed a retry or not reserved',
      kind: 'orders',
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
      title: `Orders with problems ${per}`,
      note: 'reserved after a retry, or not reserved',
      series: [
        {
          key: 'retried',
          name: 'Reserved after a retry',
          color: 'var(--chart-retried)',
          values: problems.retried,
        },
        {
          key: 'failed',
          name: 'Not reserved',
          color: 'var(--tone-red-dot)',
          values: problems.failed,
        },
      ],
    },
    {
      id: 'latency',
      title: 'Time from order to reserved',
      note: 'in seconds, side by side',
      kind: 'orders',
      grouped: true,
      format: formatLatency,
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
    ids: bucketIds(range),
    labels: bucketLabels(range),
    eventsLink: (index: number) => bucketEvents(range, index, kind),
  }));
}
