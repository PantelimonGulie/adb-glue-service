import { Link } from 'react-router-dom';
import type { Overview, RangeQuery } from '../../api/types';
import { formatNumber } from '../../lib/format';
import styles from './Counters.module.css';
import { counterCells } from './counterCells';

interface Props {
  range: RangeQuery;
  overview: Overview | undefined;
}

export function Counters({ range, overview }: Props) {
  const waiting = overview?.open_reviews ?? 0;
  return (
    <section className={styles.counters} aria-label="Counters">
      {counterCells(range, overview).map((cell) => (
        <div key={cell.key} className={styles.cell} title={cell.hint} data-counter={cell.key}>
          <div className={styles.label}>{cell.label}</div>
          <div className={styles.number} data-tone={cell.tone}>
            {cell.value}
          </div>
          {cell.change && (
            <div className={styles.change} data-good={cell.change.good}>
              {cell.change.text}
            </div>
          )}
        </div>
      ))}
      <Link
        to="/review"
        className={styles.cell}
        title="Orders a person has to decide on"
        data-waiting={waiting > 0}
      >
        <div className={styles.label}>Waiting for you</div>
        <div className={styles.number}>{formatNumber(waiting)}</div>
      </Link>
    </section>
  );
}
