import { Link } from 'react-router-dom';
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

export function BarDetail({ label, link, onClose, ...rest }: DetailProps) {
  return (
    <div className={styles.detail} role="group" aria-label={`Numbers for ${label}`}>
      <b>{label}</b>
      <Values {...rest} />
      <span className={styles.actions}>
        <Link className={controls.button} to={link}>
          Open these events
        </Link>
        <button type="button" className={controls.button} onClick={onClose}>
          Close
        </button>
      </span>
    </div>
  );
}
