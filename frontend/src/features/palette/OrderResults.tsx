import { Command } from 'cmdk';
import { useOrders } from '../../api/hooks';
import { status } from '../../lib/labels';
import styles from './CommandPalette.module.css';

const ORDERS_SHOWN = 8;

interface Props {
  q: string;
  onOpen: (to: string) => void;
}

export const Searching = () => (
  <Command.Loading label="Searching orders">Searching orders…</Command.Loading>
);

export function OrderResults({ q, onOpen }: Props) {
  // Rows kept from the previous search would answer the wrong question.
  const { data, error, isPending, isPlaceholderData } = useOrders({ q, per_page: ORDERS_SHOWN });
  if (error) return <p className={styles.note}>{error.message}</p>;
  if (isPending || isPlaceholderData) return <Searching />;
  return (
    <>
      {data.rows.map((order) => (
        <Command.Item
          key={order.order_id}
          value={`order ${order.order_id}`}
          onSelect={() => onOpen(`/orders/${encodeURIComponent(order.order_id)}`)}
        >
          {order.order_id} · {order.product} · {status(order.status).label}
          <span className={styles.kind}>order</span>
        </Command.Item>
      ))}
      <Command.Empty>Nothing found.</Command.Empty>
    </>
  );
}
