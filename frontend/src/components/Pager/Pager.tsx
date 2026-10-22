import { formatNumber } from '../../lib/format';
import controls from '../../styles/controls.module.css';
import styles from './Pager.module.css';

interface Props {
  page: number;
  perPage: number;
  total: number;
  onPage: (page: number) => void;
}

export function Pager({ page, perPage, total, onPage }: Props) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  const first = total ? (page - 1) * perPage + 1 : 0;
  const last = Math.min(page * perPage, total);
  return (
    <nav className={styles.pager} aria-label="Pages">
      <span>
        {formatNumber(first)}–{formatNumber(last)} of {formatNumber(total)}
      </span>
      <span className={styles.pages}>
        <button
          type="button"
          className={controls.button}
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          ← Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button
          type="button"
          className={controls.button}
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Next →
        </button>
      </span>
    </nav>
  );
}
