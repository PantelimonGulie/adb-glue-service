import { useOrders } from '../../api/hooks';
import type { Channel, OrderStatus } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Pager } from '../../components/Pager/Pager';
import { RangePicker } from '../../components/RangePicker/RangePicker';
import { Segmented } from '../../components/Segmented/Segmented';
import { Tag } from '../../components/Tag/Tag';
import { oneOf, useFilters } from '../../lib/filters';
import { channel as channelLabel, status as statusLabel } from '../../lib/labels';
import { useRange } from '../../lib/range';
import table from '../../styles/table.module.css';
import styles from './Orders.module.css';
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
  const { params, page, change } = useFilters();
  const q = params.get('q') ?? '';
  const channel = oneOf(CHANNELS, params.get('channel'));
  const status = oneOf(STATUSES, params.get('status'));
  const filters = { q, channel: channel || undefined, status: status || undefined, page };
  const { data, isPlaceholderData: loading } = useOrders({ range, ...filters });

  return (
    <>
      <div className={styles.top}>
        <h1>Orders</h1>
        <span className={styles.sub}>click an order to see everything that happened to it</span>
        <span role="status">{loading && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      <RangePicker value={range} onChange={setRange} />
      <div className={styles.toolbar}>
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
      <section className={table.box} aria-label="Orders">
        {data && data.total === 0 ? (
          <EmptyState title="No orders match these filters">
            Try a longer time range, another status or a shorter search.
          </EmptyState>
        ) : (
          <OrdersTable orders={data?.rows ?? []} />
        )}
        {data && data.total > 0 && (
          <Pager
            page={data.page}
            perPage={data.per_page}
            total={data.total}
            onPage={(next) => change({ page: String(next) })}
          />
        )}
      </section>
    </>
  );
}
