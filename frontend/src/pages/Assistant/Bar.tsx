import styles from './Bar.module.css';

interface Props {
  role: 'progressbar' | 'meter';
  label: string;
  value: number;
  max: number;
  warn?: boolean;
}

export function Bar({ role, label, value, max, warn }: Props) {
  const width = `${Math.min(100, max ? (value / max) * 100 : 0)}%`;
  return (
    <div
      className={styles.track}
      role={role}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <i className={styles.fill} data-warn={warn} style={{ width }} />
    </div>
  );
}
