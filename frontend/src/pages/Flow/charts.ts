import type { ActivityKind, Analytics, Channel } from '../../api/types';
import type { Series } from '../../components/BarChart/BarChart';
import { formatSeconds } from '../../lib/format';

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

const STEP_MS = { minute: 60_000, hour: 3_600_000, day: 86_400_000 };

// Like the backend, buckets start at the range start cut down to a whole minute, hour or UTC day.
export function bucketEvents(range: Range, index: number, kind?: ActivityKind): string {
  const step = STEP_MS[range.unit];
  const since = Date.parse(range.since);
  const start = since - (since % step) + index * step;
  const params = new URLSearchParams({
    since: new Date(start).toISOString(),
    until: new Date(start + step).toISOString(),
  });
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
  // Retries count tries, not orders, so the red part never outgrows the bar.
  const troubled = totals.map((total, i) =>
    Math.min(total, problems.retried[i] + problems.failed[i]),
  );
  const charts: Chart[] = [
    {
      id: 'all',
      title: `Orders ${per}`,
      note: 'all channels · red part had problems',
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
    eventsLink: (index: number) => bucketEvents(range, index, kind),
  }));
}
