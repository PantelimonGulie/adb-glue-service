import type { Analytics } from '../../api/types';
import { bucketIds, bucketLabels } from '../../lib/buckets';
import { formatNumber } from '../../lib/format';
import styles from './OrdersChart.module.css';

// Past this many bars the gaps alone would be wider than a phone.
const DENSE = 60;

function bars({ range, series }: Analytics) {
  const { orders, problems } = series;
  const totals = orders.shop.map((count, i) => count + orders.emag[i]);
  const max = Math.max(1, ...totals);
  const ids = bucketIds(range);
  return bucketLabels(range).map((label, i) => {
    const trouble = problems.retried[i] + problems.failed[i];
    // Retries count tries, not orders, so the red part never outgrows the bar.
    const bad = Math.min(totals[i], trouble);
    const note = trouble ? `, ${formatNumber(trouble)} retries or failures` : '';
    return {
      id: ids[i],
      label,
      fine: `${((totals[i] - bad) / max) * 100}%`,
      bad: `${(bad / max) * 100}%`,
      title: `${label}: ${formatNumber(totals[i])} orders${note}`,
    };
  });
}

export function OrdersChart({ analytics }: { analytics: Analytics }) {
  const items = bars(analytics);
  return (
    <div className={styles.chart}>
      <div className={styles.heading}>
        <b>Orders per {analytics.range.unit}</b>
        <span className={styles.note}>
          grey = handled fine · red = retried or failed · hover a bar
        </span>
      </div>
      <div className={styles.bars} data-dense={items.length > DENSE}>
        {items.map((bar) => (
          <div key={bar.id} className={styles.bar} title={bar.title}>
            <i className={styles.bad} style={{ height: bar.bad }} />
            <i className={styles.fine} style={{ height: bar.fine }} />
          </div>
        ))}
      </div>
      <div className={styles.axis}>
        <span>{items[0]?.label}</span>
        <span>{items.at(-1)?.label}</span>
      </div>
    </div>
  );
}
