import { useId } from 'react';
import { useOverview, useRetryAll } from '../../api/hooks';
import type { Cause, ReviewItem } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { formatNumber } from '../../lib/format';
import { cause } from '../../lib/labels';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import cards from './cards.module.css';
import styles from './ReviewGroup.module.css';
import { ReviewCard } from './ReviewCard';

const RETRY_ALL_HINT = 'Send every order of this outage to the warehouse again';
const WAREHOUSE_DOWN = 'Bucharest warehouse is not answering';

interface Props {
  name: Cause;
  count: number;
  items: ReviewItem[];
  onShowAll: () => void;
}

export function ReviewGroup({ name, count, items, onShowAll }: Props) {
  const id = useId();
  const denied = useDenied('decide');
  const retryAll = useRetryAll();
  const { data: overview } = useOverview({ range: 'live' });
  const down = overview?.systems.warehouse.ok === false ? WAREHOUSE_DOWN : undefined;
  const blocked = denied ?? down;
  const { label, hint } = cause(name);
  const orders = `${formatNumber(count)} order${count === 1 ? '' : 's'}`;
  const more = count - items.length;
  const retried = retryAll.data?.retried;

  return (
    <section className={styles.group} aria-labelledby={id}>
      <div className={styles.head}>
        <h2 id={id}>{label}</h2>
        <span className={text.note}>
          {orders} · {hint}
        </span>
        {name === 'outage' && (
          <span className={styles.retry}>
            {retryAll.error && (
              <span className={text.error} role="alert">
                {retryAll.error.message}
              </span>
            )}
            {retried !== undefined && (
              <span className={text.note} role="status">
                Sent {formatNumber(retried)} again
              </span>
            )}
            <button
              type="button"
              className={controls.button}
              disabled={Boolean(blocked) || retryAll.isPending}
              title={blocked ?? RETRY_ALL_HINT}
              onClick={() => retryAll.mutate()}
            >
              Retry all {formatNumber(count)}
            </button>
          </span>
        )}
      </div>
      <div className={`${cards.cards} ${styles.cards}`}>
        {items.map((item) => (
          <ReviewCard key={item.id} item={item} />
        ))}
      </div>
      {more > 0 && (
        <p className={`${text.note} ${styles.more}`}>
          and {formatNumber(more)} more with the same cause.{' '}
          <button type="button" className={styles.link} onClick={onShowAll}>
            Show all {formatNumber(count)}
          </button>
        </p>
      )}
    </section>
  );
}
