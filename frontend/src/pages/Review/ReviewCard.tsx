import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { useStock } from '../../api/hooks';
import type { ReviewItem } from '../../api/types';
import { Tag } from '../../components/Tag/Tag';
import { formatDay, formatTime } from '../../lib/format';
import { cause, channel } from '../../lib/labels';
import { Decisions } from './Decisions';
import { facts, outcome, story } from './explain';
import styles from './ReviewCard.module.css';
import { Triage } from './Triage';

const when = (ts: string) => `${formatDay(ts)} ${formatTime(ts)}`.trim();

export function ReviewCard({ item }: { item: ReviewItem }) {
  const { data: stock } = useStock();
  const { order } = item;
  const shelf = stock?.rows.find((row) => row.sku === order?.sku);
  const kind = cause(item.cause);
  const source = order && channel(order.channel);
  const decided = item.status === 'decided';
  const name = item.order_id ?? 'an item without an order';
  const decidedAt = item.decided_at ? ` at ${when(item.decided_at)}` : '';

  return (
    <article className={styles.card} data-decided={decided} aria-label={`Review of ${name}`}>
      <div className={styles.head}>
        <Tag tone={kind.tone} title={kind.hint}>
          {kind.short}
        </Tag>
        {item.order_id && (
          <Link className={styles.order} to={`/orders/${encodeURIComponent(item.order_id)}`}>
            {item.order_id}
          </Link>
        )}
        {source && <Tag tone={source.tone}>{source.label}</Tag>}
        {order && (
          <span className={styles.product}>
            {order.qty} × {order.product}
          </span>
        )}
        <span className={styles.when}>{when(item.created_at)}</span>
      </div>
      <div className={styles.body}>
        <div className={styles.story}>
          <p>{story(item)}</p>
          <dl className={styles.facts}>
            {facts(item, shelf).map(([label, value]) => (
              <Fragment key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </Fragment>
            ))}
          </dl>
          <Triage item={item} />
        </div>
        <div className={styles.actions}>
          {decided ? (
            <p className={styles.outcome}>
              <b>{outcome(item)}</b> by {item.decided_by}
              {decidedAt}. Saved in the activity log.
            </p>
          ) : (
            <Decisions item={item} />
          )}
        </div>
      </div>
    </article>
  );
}
