import { Link, useLocation } from 'react-router-dom';
import type { Order, OrderStatus } from '../../api/types';
import { Product } from '../../components/Product/Product';
import { Tag } from '../../components/Tag/Tag';
import { formatDay, formatTime } from '../../lib/format';
import { channel as channelLabel, status as statusLabel } from '../../lib/labels';
import table from '../../styles/table.module.css';
import styles from './OrdersTable.module.css';

const LATEST: Record<OrderStatus, string> = {
  received: 'received',
  allocated: 'reserved at warehouse',
  shipped: 'shipped',
  failed: 'every try failed',
  cancelled: 'cancelled',
};

function latest(order: Order): string {
  const when = `${formatDay(order.updated_at)} ${formatTime(order.updated_at)}`.trim();
  return `${order.last_error ?? LATEST[order.status]} · ${when}`;
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
    <div className={table.scroll}>
      <table className={`${table.table} ${styles.table}`}>
        <thead>
          <tr>
            <th>Order</th>
            <th>Channel</th>
            <th>Product</th>
            <th>Status</th>
            <th>Tries</th>
            <th>Latest</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ order, ...row }) => (
            <tr key={order.order_id}>
              <td>
                <Link
                  className={styles.order}
                  to={`/orders/${encodeURIComponent(order.order_id)}`}
                  state={{ back: search }}
                >
                  {order.order_id}
                </Link>
              </td>
              <td>
                <Tag tone={row.channel.tone}>{row.channel.label}</Tag>
              </td>
              <td>
                <Product name={order.product} sku={order.sku} />
              </td>
              <td>
                <Tag tone={row.status.tone}>{row.status.label}</Tag>
              </td>
              <td className={table.number}>{order.attempts}</td>
              <td className={styles.latest}>{row.latest}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
