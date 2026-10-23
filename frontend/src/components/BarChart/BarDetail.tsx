import { Link } from 'react-router-dom';
import { rangeSearch, useRange } from '../../lib/range';
import controls from '../../styles/controls.module.css';
import type { Series } from './BarChart';
import styles from './BarDetail.module.css';

interface Props {
  label: string;
  index: number;
  series: Series[];
  format: (value: number) => string;
}

function Values({ index, series, format }: Omit<Props, 'label'>) {
  return series.map((one) => (
    <span key={one.key} className={styles.value}>
      <i className={styles.swatch} style={{ background: one.color }} />
      {one.name} <b>{format(one.values[index])}</b>
    </span>
  ));
}

export function BarTip({ label, ...rest }: Props) {
  return (
    <div className={styles.tip}>
      <b>{label}</b>
      <Values {...rest} />
      <span className={styles.hint}>click to see details</span>
    </div>
  );
}

interface DetailProps extends Props {
  link: string;
  onClose: () => void;
}

// The bar's window replaces the range on the Activity page. The range goes along, so clearing
// the window there returns to the range this chart showed.
function withRange(link: string, range: string): string {
  const url = new URL(link, window.location.origin);
  if (!url.searchParams.has('range')) {
    for (const [key, value] of new URLSearchParams(range)) url.searchParams.set(key, value);
  }
  return url.pathname + url.search;
}

export function BarDetail({ label, link, onClose, ...rest }: DetailProps) {
  const [range] = useRange();
  return (
    <div className={styles.detail} role="group" aria-label={`Numbers for ${label}`}>
      <b>{label}</b>
      <Values {...rest} />
      <span className={styles.actions}>
        <Link className={controls.button} to={withRange(link, rangeSearch(range))}>
          Open these events
        </Link>
        <button type="button" className={controls.button} onClick={onClose}>
          Close
        </button>
      </span>
    </div>
  );
}
