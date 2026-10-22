import { useQueryClient } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useAutoRefresh } from '../../api/autoRefresh';
import type { User } from '../../api/types';
import { Brand } from '../../components/Brand/Brand';
import { Switch } from '../../components/Switch/Switch';
import controls from '../../styles/controls.module.css';
import { UserMenu } from '../UserMenu/UserMenu';
import styles from './Header.module.css';

export function Header({ me }: { me: User }) {
  const client = useQueryClient();
  const autoRefresh = useAutoRefresh();
  return (
    <header className={styles.header}>
      <Brand />
      <button type="button" className={styles.search} aria-label="Search">
        <Search size={14} />
        <span className={styles.searchText}>Search orders, products, pages</span>
        <kbd className={styles.key}>⌘K</kbd>
      </button>
      <div className={styles.controls}>
        <span
          className={styles.auto}
          title="When on, the screen updates by itself every 2 seconds. Turn it off to read without things moving."
        >
          Auto-refresh
          <Switch checked={autoRefresh.on} onChange={autoRefresh.setOn} label="Auto-refresh" />
        </span>
        <button
          type="button"
          className={controls.button}
          title="Load the latest data now"
          onClick={() => client.invalidateQueries()}
        >
          Refresh
        </button>
        <UserMenu me={me} />
      </div>
    </header>
  );
}
