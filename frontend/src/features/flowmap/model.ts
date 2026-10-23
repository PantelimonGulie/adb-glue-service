import type { Analytics, Counters, Overview, SystemHealth, SystemName } from '../../api/types';
import { formatNumber } from '../../lib/format';
import { system } from '../../lib/labels';
import type { Route } from './layout';

export type Mode = 'live' | 'period';

export interface Edge {
  route: Route;
  label: string | null;
  hint?: string;
  width: number;
  main: boolean;
  bad: boolean;
}

interface Status {
  text: string;
  bad: boolean;
}

export interface MapView {
  edges: Edge[];
  status: Record<SystemName, Status>;
  glue: { reserved: string; rows: { label: string; value: string; tone?: string }[] };
  stockCheck: string;
}

const LIVE_WIDTH = 2;
const RETURN_WIDTH = 1.5;

const lineWidth = (volume: number) =>
  Math.min(9, 1.5 + Math.log10(Math.max(10, volume)) * 1.6);

const number = (value: number | undefined) => formatNumber(value ?? 0);

const perMinute = (count: number, minutes: number) =>
  `${(count / minutes).toLocaleString('en-US', { maximumFractionDigits: 1 })}/min`;

// Minutes in the live window when an order came in. Rates average over these, so a window that
// started after a restart, or traffic that was paused, does not water them down.
function busyMinutes(totals: Analytics | undefined): number {
  const { shop, emag } = totals?.series.orders ?? { shop: [], emag: [] };
  return shop.filter((count, i) => count + emag[i] > 0).length;
}

function health(reported: SystemHealth | undefined): Status {
  const { label, tone } = system(reported);
  const latency = tone === 'green' && reported?.latency_ms != null;
  return { text: latency ? `${label} · ${reported.latency_ms} ms` : label, bad: tone === 'red' };
}

function periodStatus(warehouse: Status, counters: Counters | undefined): Status {
  if (warehouse.bad || !counters) return warehouse;
  const { reserved, retries, failed } = counters;
  return {
    text: `${number(reserved)} reserved · ${number(retries)} retried · ${number(failed)} failed`,
    bad: false,
  };
}

function edges(totals: Analytics | undefined, live: boolean, warehouse: Status): Edge[] {
  const parts = totals?.parts;
  const busy = busyMinutes(totals);
  // The number goes on its own line, so a label never wraps in the middle of a phrase.
  function amount(base: string, count: number | undefined) {
    if (count === undefined || (live && busy === 0)) return base;
    return `${base}\n${live ? perMinute(count, busy) : formatNumber(count)}`;
  }
  const main = (route: Route, label: string, hint: string, count = 0, bad = false): Edge => ({
    route,
    label,
    hint,
    width: live ? LIVE_WIDTH : lineWidth(count),
    main: true,
    bad,
  });
  const back = (route: Route, label: string | null = null): Edge => ({
    route,
    label,
    width: RETURN_WIDTH,
    main: false,
    bad: false,
  });
  const liveSent = warehouse.bad ? 'NOT ANSWERING' : 'ORDERS';
  const sent = live ? liveSent : amount('SENT', parts?.warehouse.received);
  return [
    back('shopOut'),
    back('mktOut'),
    back('whBack', 'STOCK'),
    main(
      'shopIn',
      amount('ORDERS', parts?.shop.orders),
      'Open the activity log for orders',
      parts?.shop.orders,
    ),
    main(
      'mktIn',
      // Commas, not the map's middle dots: the label has to fit between the eMAG box and Glue.
      amount('NOTIFY, FETCH, CONFIRM', parts?.emag.orders),
      'eMAG sends only the order number, Glue fetches the order, then confirms it',
      parts?.emag.orders,
    ),
    main(
      'whOut',
      sent,
      'Open the activity log for orders sent to the warehouse',
      parts?.warehouse.received,
      warehouse.bad,
    ),
  ];
}

export function mapView(
  mode: Mode,
  totals: Analytics | undefined,
  overview: Overview | undefined,
  reconcileSeconds: number | undefined,
): MapView {
  const live = mode === 'live';
  const counters = totals?.totals;
  const warehouse = health(overview?.systems.warehouse);
  return {
    edges: edges(totals, live, warehouse),
    status: {
      shop: health(overview?.systems.shop),
      emag: health(overview?.systems.emag),
      warehouse: live ? warehouse : periodStatus(warehouse, counters),
    },
    glue: {
      reserved: `${number(counters?.reserved)} reserved`,
      rows: [
        { label: 'orders in', value: number(counters?.received) },
        { label: 'duplicates ignored', value: number(counters?.duplicates) },
        { label: 'retries', value: number(counters?.retries), tone: 'amber' },
        { label: 'waiting for you', value: number(overview?.open_reviews), tone: 'red' },
      ],
    },
    stockCheck: reconcileSeconds ? `STOCK CHECK EVERY ${reconcileSeconds} S` : 'STOCK CHECK',
  };
}
