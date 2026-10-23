import { Link, useLocation } from 'react-router-dom';
import type { Order, OrderStatus } from '../../api/types';
import { Product } from '../../components/Product/Product';
import { Tag } from '../../components/Tag/Tag';
import { formatDay, formatTime } from '../../lib/format';
import { channel as channelLabel, status as statusLabel } from '../../lib/labels';
import { plainProblem } from '../../lib/problem';
import table from '../../styles/table.module.css';
import styles from './OrdersTable.module.css';

const LATEST: Record<OrderStatus, string> = {
  received: 'received',
  allocated: 'reserved at warehouse',
  shipped: 'shipped',
  failed: 'every try failed',
  cancelled: 'cancelled',
};

const COLUMNS = [
  { name: 'Order', hint: 'Open it to see everything that happened to it' },
  { name: 'Channel', hint: 'Where the customer ordered' },
  { name: 'Product', hint: undefined },
  { name: 'Status', hint: 'Where the order is now' },
  { name: 'Tries', hint: 'How many times Glue sent it to the warehouse' },
  { name: 'Latest', hint: 'The last thing that happened to it, and when' },
];

function latest(order: Order): string {
  const when = `${formatDay(order.updated_at)} ${formatTime(order.updated_at)}`.trim();
  const what = order.last_error ? plainProblem(order.last_error) : LATEST[order.status];
  return `${what} · ${when}`;
}

export function OrdersTable({ orders }: { orders: Order[] }) {
  // The order page links back to the list with the same filters.
  const { search } = useLocation();
  const rows = orders.map((order) => ({
    order,
    channel: channelLabel(order.channel),
    status: statusLabel(order.status),
    latest: latest(order),
  }));
  return (
    <div className={`${table.scroll} ${styles.frame}`}>
      <table className={`${table.table} ${styles.table}`}>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column.name} title={column.hint}>
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ order, ...row }) => (
            <tr key={order.order_id}>
              <td className={styles.id}>
                <Link
                  className={styles.order}
                  to={`/orders/${encodeURIComponent(order.order_id)}`}
                  state={{ back: search }}
                >
                  {order.order_id}
                </Link>
              </td>
              <td className={styles.channel}>
                <Tag tone={row.channel.tone}>{row.channel.label}</Tag>
              </td>
              <td className={styles.product}>
                <Product name={order.product} sku={order.sku} />
              </td>
              <td className={styles.status}>
                <Tag tone={row.status.tone} title={row.status.explanation}>
                  {row.status.label}
                </Tag>
              </td>
              <td className={`${table.number} ${styles.tries}`} data-label="Tries">
                {order.attempts}
              </td>
              <td className={styles.latest}>{row.latest}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
