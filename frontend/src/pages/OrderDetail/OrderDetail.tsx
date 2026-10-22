import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { useOrder, useSettings } from '../../api/hooks';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import { channel, status } from '../../lib/labels';
import { useProductName } from '../../lib/products';
import controls from '../../styles/controls.module.css';
import { Details } from './Details';
import { History } from './History';
import styles from './OrderDetail.module.css';

export function OrderDetail() {
  const id = useParams().id ?? '';
  const { state } = useLocation();
  const { data, error } = useOrder(id);
  const { data: settings } = useSettings();
  const productName = useProductName();
  // Orders links pass their filters, so going back keeps them.
  const back = `/orders${(state as { back?: string } | null)?.back ?? ''}`;
  const backLink = (
    <Link className={controls.button} to={back}>
      ← Orders
    </Link>
  );

  if (!data) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <>
        <div className={styles.top}>{backLink}</div>
        {missing && (
          <EmptyState title="This order does not exist">
            Check the order number, or find the order on the Orders page.
          </EmptyState>
        )}
        {error && !missing && (
          <EmptyState title="This order could not be loaded">{error.message}</EmptyState>
        )}
      </>
    );
  }

  const { order, timeline } = data;
  const from = channel(order.channel);
  const now = status(order.status);
  return (
    <>
      <div className={styles.top}>
        {backLink}
        <h1 className={styles.id}>{order.order_id}</h1>
        <Tag tone={from.tone}>{from.label}</Tag>
        <Tag tone={now.tone}>{now.label}</Tag>
        <span className={styles.lines}>
          {order.qty} × {order.product}
        </span>
      </div>
      <div className={styles.columns}>
        <div className={styles.history}>
          <History rows={timeline} productName={productName} />
        </div>
        <div className={styles.side}>
          <Details order={order} triesAllowed={settings?.retry_attempts} />
        </div>
      </div>
    </>
  );
}
