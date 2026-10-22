import { Link } from 'react-router-dom';
import type { Channel, Order } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import controls from '../../styles/controls.module.css';
import styles from './Details.module.css';

const CAME_FROM: Record<Channel, string> = {
  shop: 'the shop, signature checked',
  emag: 'eMAG, fetched by Glue',
};
const RESEND_HINT =
  'The warehouse remembers this id, so sending the order twice never reserves twice';
const ASK = 'Ask the assistant about this order';

interface Props {
  order: Order;
  triesAllowed: number | undefined;
}

export function Details({ order, triesAllowed }: Props) {
  const denied = useDenied('ask');
  const question = new URLSearchParams({ q: `What happened to ${order.order_id}?` });
  const tries = triesAllowed ? `${order.attempts} of ${triesAllowed} allowed` : order.attempts;
  const ask = `${controls.button} ${styles.ask}`;
  return (
    <section className={styles.details} aria-label="Details">
      <h2>Details</h2>
      <dl className={styles.facts}>
        <dt>Came from</dt>
        <dd>{CAME_FROM[order.channel]}</dd>
        <dt>Tries</dt>
        <dd>{tries}</dd>
        <dt>Safe to resend</dt>
        <dd title={RESEND_HINT}>yes, the warehouse knows this order id</dd>
      </dl>
      {denied ? (
        <button type="button" className={ask} disabled title={denied}>
          {ASK}
        </button>
      ) : (
        <Link className={ask} to={`/assistant?${question}`}>
          {ASK}
        </Link>
      )}
    </section>
  );
}
