import { ChevronDown, LogOut, UserRound } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { User } from '../../api/types';
import { useSignOut } from '../../auth/session';
import controls from '../../styles/controls.module.css';
import styles from './UserMenu.module.css';

export function UserMenu({ me }: { me: User }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { pathname, search } = useLocation();
  const signOut = useSignOut();

  useEffect(() => {
    if (!open) return;
    const clickAway = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', clickAway);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', clickAway);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  return (
    <div className={styles.box} ref={box}>
      <button
        type="button"
        className={controls.button}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {me.name} · {me.role}
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className={styles.menu}>
          <p className={styles.note}>
            Signed in as <b>{me.name}</b> ({me.role}).
          </p>
          <Link
            className={styles.item}
            to={`/sign-in?next=${encodeURIComponent(pathname + search)}`}
            onClick={() => setOpen(false)}
          >
            <UserRound size={16} />
            Sign in as another user
          </Link>
          <hr className={styles.line} />
          <button
            type="button"
            className={styles.item}
            disabled={signOut.isPending}
            onClick={() => signOut.mutate()}
          >
            <LogOut size={16} />
            Sign out
          </button>
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
