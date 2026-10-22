import { forwardRef } from 'react';
import { Tag } from '../../components/Tag/Tag';
import styles from './CardButton.module.css';

interface Props {
  label: string;
  state?: string;
  disabled?: boolean;
  // Not usable right now but still focusable: a disabled button drops the keyboard focus.
  blocked?: boolean;
  title?: string;
  type?: 'button' | 'submit';
  onClick?: () => void;
}

export const CardButton = forwardRef<HTMLButtonElement, Props>(function CardButton(
  { label, state, blocked, type = 'button', onClick, ...button },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={styles.button}
      data-on={Boolean(state)}
      aria-disabled={blocked || undefined}
      onClick={blocked ? undefined : onClick}
      {...button}
    >
      {label}
      {state && <Tag tone="amber">{state}</Tag>}
    </button>
  );
});
