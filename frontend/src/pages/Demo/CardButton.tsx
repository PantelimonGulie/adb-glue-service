import { Tag } from '../../components/Tag/Tag';
import styles from './CardButton.module.css';

interface Props {
  label: string;
  state?: string;
  disabled?: boolean;
  title?: string;
  type?: 'button' | 'submit';
  onClick?: () => void;
}

export function CardButton({ label, state, type = 'button', ...button }: Props) {
  return (
    <button type={type} className={styles.button} data-on={Boolean(state)} {...button}>
      {label}
      {state && <Tag tone="amber">{state}</Tag>}
    </button>
  );
}
