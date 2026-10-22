import type { Analytics, RangeQuery } from '../../api/types';
import { comparedWith, counterCells } from '../Overview/counterCells';
import styles from './Comparison.module.css';

interface Props {
  range: RangeQuery;
  analytics: Analytics | undefined;
}

export function Comparison({ range, analytics }: Props) {
  const vs = comparedWith(range);
  if (!vs) {
    return (
      <p className={styles.note}>
        Comparison needs a past period: pick Today, a week, a month or custom dates.
      </p>
    );
  }
  const counters = analytics && { counters: analytics.totals, previous: analytics.previous };
  return (
    <section className={styles.strip} aria-label={`Compared with ${vs}`}>
      {counterCells(range, counters).map((cell) => (
        <span key={cell.key} className={styles.cell} title={cell.hint}>
          {cell.label}
          <b className={styles.number}>{cell.value}</b>
          {cell.change && (
            <span className={styles.change} data-good={cell.change.good}>
              {cell.change.text}
            </span>
          )}
        </span>
      ))}
    </section>
  );
}
