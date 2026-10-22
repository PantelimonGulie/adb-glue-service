import { useOrders } from '../../api/hooks';
import type { Channel, OrderStatus } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Pager } from '../../components/Pager/Pager';
import { RangePicker } from '../../components/RangePicker/RangePicker';
import { Segmented } from '../../components/Segmented/Segmented';
import { Tag } from '../../components/Tag/Tag';
import { oneOf, useBackToFirstPage, useFilters } from '../../lib/filters';
import { channel as channelLabel, status as statusLabel } from '../../lib/labels';
import { useRange } from '../../lib/range';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import { OrdersTable } from './OrdersTable';
import { SearchBox } from './SearchBox';

const CHANNELS: { value: Channel | ''; label: string }[] = [
  { value: '', label: 'All channels' },
  { value: 'shop', label: channelLabel('shop').label },
  { value: 'emag', label: channelLabel('emag').label },
];
const STATUSES: { value: OrderStatus | ''; label: string }[] = [
  { value: '', label: 'Any status' },
  ...(['received', 'allocated', 'failed', 'shipped', 'cancelled'] as const).map((name) => ({
    value: name,
    label: statusLabel(name).label,
  })),
];

export function Orders() {
  const [range, setRange] = useRange();
  const filters = useFilters();
  const { params, change } = filters;
  const q = params.get('q') ?? '';
  const channel = oneOf(CHANNELS, params.get('channel'));
  const status = oneOf(STATUSES, params.get('status'));
  const { data, error, isPending, isPlaceholderData } = useOrders({
    range,
    q,
    channel: channel || undefined,
    status: status || undefined,
    page: filters.page,
  });
  useBackToFirstPage(data, filters);
  const loading = isPending || isPlaceholderData;

  return (
    <>
      <div className={page.top}>
        <h1>Orders</h1>
        <span className={page.sub}>click an order to see everything that happened to it</span>
        <span role="status">{loading && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      <RangePicker value={range} onChange={setRange} />
      <div className={page.toolbar}>
        <SearchBox value={q} onChange={(text) => change({ q: text }, { replace: true })} />
        <Segmented
          label="Channel"
          options={CHANNELS}
          value={channel}
          onChange={(value) => change({ channel: value })}
        />
        <Segmented
          label="Status"
          options={STATUSES}
          value={status}
          onChange={(value) => change({ status: value })}
        />
      </div>
      {(error || data) && (
        <section className={table.box} aria-label="Orders">
          {error && <EmptyState title="The orders could not be loaded">{error.message}</EmptyState>}
          {data?.total === 0 && (
            <EmptyState title="No orders match these filters">
              Try a longer time range, another status or a shorter search.
            </EmptyState>
          )}
          {data && data.total > 0 && (
            <>
              <OrdersTable orders={data.rows} />
              <Pager
                page={data.page}
                perPage={data.per_page}
                total={data.total}
                onPage={(next) => change({ page: String(next) })}
              />
            </>
          )}
        </section>
      )}
    </>
  );
}
