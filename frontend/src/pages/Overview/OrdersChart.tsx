import type { Analytics } from '../../api/types';
import { bucketIds, bucketLabels } from '../../lib/buckets';
import { formatNumber } from '../../lib/format';
import styles from './OrdersChart.module.css';

// Past this many bars the gaps alone would be wider than a phone.
const DENSE = 60;

// Hours or days that have not started yet are left off, so the bars use the width.
function bars({ range, series }: Analytics, now = Date.now()) {
  const { orders, problems } = series;
  const totals = orders.shop.map((count, i) => count + orders.emag[i]);
  const max = Math.max(1, ...totals);
  const ids = bucketIds(range);
  const labels = bucketLabels(range).slice(0, ids.filter((id) => !(Date.parse(id) > now)).length);
  return labels.map((label, i) => {
    const bad = problems.retried[i] + problems.failed[i];
    const note = bad ? `, ${formatNumber(bad)} needed a retry or were not reserved` : '';
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
          grey = reserved first time · red = needed a retry or not reserved · hover a bar
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
