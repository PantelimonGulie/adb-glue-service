import type { ReactNode } from 'react';
import type { Tone } from '../../lib/labels';
import styles from './Tag.module.css';

interface Props {
  tone: Tone;
  title?: string;
  children: ReactNode;
}

export function Tag({ tone, title, children }: Props) {
  return (
    <span className={styles.tag} data-tone={tone} title={title}>
      {children}
    </span>
  );
}
