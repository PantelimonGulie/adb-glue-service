import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import styles from './Chip.module.css';

interface Props {
  children: ReactNode;
  clearLabel: string;
  onClear: () => void;
}

export function Chip({ children, clearLabel, onClear }: Props) {
  return (
    <span className={styles.chip}>
      {children}
      <button type="button" aria-label={clearLabel} title={clearLabel} onClick={onClear}>
        <X size={14} />
      </button>
    </span>
  );
}
