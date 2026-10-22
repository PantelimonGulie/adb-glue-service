import { useId, type ReactNode } from 'react';
import type { DemoResult } from '../../api/types';
import styles from './DemoCard.module.css';

interface Props {
  title: string;
  text: string;
  busy: boolean;
  result?: DemoResult;
  note?: string;
  children: ReactNode;
}

export function DemoCard({ title, text, busy, result, note, children }: Props) {
  const id = useId();
  return (
    <section className={styles.card} aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <p className={styles.text}>{text}</p>
      {note && <p className={styles.note}>{note}</p>}
      {children}
      {busy && <p className={styles.result}>Working…</p>}
      {!busy && result && (
        <p className={styles.result} data-ok={result.ok} role={result.ok ? 'status' : 'alert'}>
          {result.message}
        </p>
      )}
    </section>
  );
}
