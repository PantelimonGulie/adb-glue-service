import { Inbox } from 'lucide-react';
import type { ReactNode } from 'react';
import styles from './EmptyState.module.css';

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <Inbox size={20} />
      <p className={styles.title}>{title}</p>
      {children && <p className={styles.hint}>{children}</p>}
    </div>
  );
}
