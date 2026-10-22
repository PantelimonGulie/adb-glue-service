import { useId } from 'react';
import { useRetryAll } from '../../api/hooks';
import type { Cause, ReviewItem } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { formatNumber } from '../../lib/format';
import { cause } from '../../lib/labels';
import controls from '../../styles/controls.module.css';
import styles from './ReviewGroup.module.css';
import { ReviewCard } from './ReviewCard';

const RETRY_ALL_HINT = 'Send every order of this outage to the warehouse again';

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
  const { label, hint } = cause(name);
  const orders = `${formatNumber(count)} order${count === 1 ? '' : 's'}`;
  const more = count - items.length;
  const retried = retryAll.data?.retried;

  return (
    <section className={styles.group} aria-labelledby={id}>
      <div className={styles.head}>
        <h2 id={id}>{label}</h2>
        <span className={styles.note}>
          {orders} · {hint}
        </span>
        {name === 'outage' && (
          <span className={styles.retry}>
            {retryAll.error && (
              <span className={styles.error} role="alert">
                {retryAll.error.message}
              </span>
            )}
            {retried !== undefined && (
              <span className={styles.note} role="status">
                Sent {formatNumber(retried)} again
              </span>
            )}
            <button
              type="button"
              className={controls.button}
              disabled={Boolean(denied) || retryAll.isPending}
              title={denied ?? RETRY_ALL_HINT}
              onClick={() => retryAll.mutate()}
            >
              Retry all {formatNumber(count)}
            </button>
          </span>
        )}
      </div>
      <div className={styles.cards}>
        {items.map((item) => (
          <ReviewCard key={item.id} item={item} />
        ))}
      </div>
      {more > 0 && (
        <p className={styles.more}>
          and {formatNumber(more)} more with the same cause.{' '}
          <button type="button" className={styles.link} onClick={onShowAll}>
            Show all {formatNumber(count)}
          </button>
        </p>
      )}
    </section>
  );
}
