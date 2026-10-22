import { useId, type ReactNode } from 'react';
import styles from './Panel.module.css';

interface Props {
  title: string;
  note?: string;
  actions?: ReactNode;
  alert?: boolean;
  children: ReactNode;
}

export function Panel({ title, note, actions, alert, children }: Props) {
  const id = useId();
  return (
    <section className={styles.panel} data-alert={alert} aria-labelledby={id}>
      <div className={styles.head}>
        <h2 id={id}>{title}</h2>
        {note && <span className={styles.note}>{note}</span>}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
      {children}
    </section>
  );
}
