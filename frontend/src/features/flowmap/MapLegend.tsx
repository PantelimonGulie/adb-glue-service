import { LEGEND } from './dots';
import styles from './MapLegend.module.css';

export function MapLegend() {
  return (
    <ul className={styles.legend} aria-label="What the dots mean">
      {LEGEND.map(({ tone, label }) => (
        <li key={label}>
          <i className={styles.swatch} style={{ background: `var(--tone-${tone}-dot)` }} />
          {label}
        </li>
      ))}
    </ul>
  );
}
