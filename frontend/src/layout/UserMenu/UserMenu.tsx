import { ChevronDown, LogOut, UserRound } from 'lucide-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { User } from '../../api/types';
import { useSignOut } from '../../auth/session';
import controls from '../../styles/controls.module.css';
import styles from './UserMenu.module.css';

const ITEM = '[role="menuitem"]';

export function UserMenu({ me }: { me: User }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const { pathname, search } = useLocation();
  const signOut = useSignOut();

  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLElement>(ITEM)?.focus();
    const clickAway = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    // The focused item disappears with the menu, so focus goes back to the button.
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener('mousedown', clickAway);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', clickAway);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  function moveFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(ITEM));
    const step = event.key === 'ArrowDown' ? 1 : -1;
    const current = items.indexOf(document.activeElement as HTMLElement);
    items[(current + step + items.length) % items.length].focus();
  }

  return (
    <div className={styles.box} ref={box}>
      <button
        ref={trigger}
        type="button"
        className={controls.button}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen(!open)}
      >
        {me.name} · {me.role}
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className={styles.popup}>
          <p className={styles.note}>
            Signed in as <b>{me.name}</b> ({me.role}).
          </p>
          <div id={menuId} ref={menu} role="menu" aria-label="Account" onKeyDown={moveFocus}>
            <Link
              role="menuitem"
              className={styles.item}
              to={`/sign-in?next=${encodeURIComponent(pathname + search)}`}
              onClick={() => setOpen(false)}
            >
              <UserRound size={16} />
              Sign in as another user
            </Link>
            <hr className={styles.line} />
            <button
              role="menuitem"
              type="button"
              className={styles.item}
              disabled={signOut.isPending}
              onClick={() => signOut.mutate()}
            >
              <LogOut size={16} />
              Sign out
            </button>
          </div>
          {signOut.error && (
            <p className={styles.error} role="alert">
              {signOut.error.message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
