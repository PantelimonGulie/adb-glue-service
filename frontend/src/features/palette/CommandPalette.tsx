import { Command } from 'cmdk';
import { Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './CommandPalette.module.css';
import { PaletteBody } from './PaletteBody';

const SHORTCUT = /Mac|iPhone|iPad/.test(navigator.userAgent) ? '⌘K' : 'Ctrl K';

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLElement | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const toggle = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'k' || !(event.metaKey || event.ctrlKey)) return;
      event.preventDefault();
      if (!open) opener.current = document.activeElement as HTMLElement | null;
      setOpen(!open);
    };
    document.addEventListener('keydown', toggle);
    return () => {
      document.removeEventListener('keydown', toggle);
    };
  }, [open]);

  // The dialog has no trigger of its own, so focus goes back to whatever opened it.
  useEffect(() => {
    if (!open) opener.current?.focus();
  }, [open]);

  function go(to: string) {
    setOpen(false);
    navigate(to);
  }

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        aria-label="Search"
        onClick={(event) => {
          opener.current = event.currentTarget;
          setOpen(true);
        }}
      >
        <Search size={14} />
        <span className={styles.text}>Search orders, products, pages</span>
        <kbd className={styles.key}>{SHORTCUT}</kbd>
      </button>
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Search"
        shouldFilter={false}
        overlayClassName={styles.overlay}
        contentClassName={styles.dialog}
      >
        <PaletteBody onOpen={go} />
      </Command.Dialog>
    </>
  );
}
