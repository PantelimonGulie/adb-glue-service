import type { Analytics, AuditRow, Counters, Overview, Stock } from '../api/types';

const working = { ok: true, state: 'Healthy', latency_ms: 2 };
const counters: Counters = { received: 110, duplicates: 4, reserved: 99, retries: 6, failed: 1 };

export const row = (id: number, action: string, detail: AuditRow['detail'] = {}): AuditRow => ({
  id,
  ts: '2026-10-22T10:00:00.000+00:00',
  correlation_id: `c-${id}`,
  entity_type: 'event',
  entity_id: `e-${id}`,
  action,
  detail,
});

export const overview: Overview = {
  counters,
  previous: { received: 100, duplicates: 4, reserved: 90, retries: 4, failed: 2 },
  systems: { shop: working, emag: working, warehouse: working },
  open_reviews: 3,
  review_groups: [
    { cause: 'outage', count: 2 },
    { cause: 'soldout', count: 1 },
  ],
  latest: [row(7, 'event_received', { source: 'shop', type: 'order.placed' })],
};

export const stock: Stock = {
  rows: [
    {
      sku: 'MBA-M4',
      product: 'MacBook Air M4',
      on_hand: 1,
      reserved: 1,
      free: 0,
      shop: { qty: 0, dirty: false },
      emag: { qty: 1, dirty: false },
      held_back: { shop: 0, emag: 0 },
      state: 'behind',
    },
  ],
  reconcile_seconds: 10,
};

const zeros = (n: number) => Array.from({ length: n }, () => 0);

export const analytics: Analytics = {
  range: { since: '', until: '', unit: 'hour', labels: ['00:00', '01:00'] },
  totals: { received: 3406, duplicates: 126, reserved: 3246, retries: 123, failed: 20 },
  previous: null,
  funnel: {
    received: 3406,
    duplicates: 126,
    sent: 3266,
    first_try: 3143,
    after_retry: 103,
    failed: 20,
  },
  series: {
    orders: { shop: [10, 20], emag: [5, 5] },
    problems: { retried: [0, 3], failed: [0, 1] },
    latency: { p50: zeros(2), p95: zeros(2) },
    out_of_sync: { shop: zeros(2), emag: zeros(2) },
  },
  parts: {
    shop: { orders: 2180, duplicates: 100, refused: 0 },
    emag: { orders: 1226, renotified: 26, slowdowns: 0, refused_updates: 0, sold_out: 1 },
    glue: { handled: 3406, duplicates: 126, p50_seconds: 0.6, p95_seconds: 1.4, lost: 0 },
    warehouse: {
      received: 3266,
      first_try_pct: 96.2,
      retries: 123,
      failed: 20,
      longest_outage_minutes: 14,
    },
  },
  by_product: [],
  failure_causes: [],
  sample: false,
};
