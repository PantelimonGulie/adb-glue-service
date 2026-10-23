import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useOverview } from '../../api/hooks';
import type { SystemName } from '../../api/types';
import { system } from '../../lib/labels';
import { MAIN, PLATFORM, type Page } from '../../lib/pages';
import styles from './Sidebar.module.css';
import { useNarrow } from './useNarrow';

const SYSTEMS: { name: SystemName; label: string }[] = [
  { name: 'shop', label: 'Shop' },
  { name: 'emag', label: 'eMAG' },
  { name: 'warehouse', label: 'Warehouse' },
];
const COLLAPSED = 'glue.menu-collapsed';

// Storage can be missing or blocked (private windows); the menu then simply starts open.
function stored(): boolean {
  try {
    return localStorage.getItem(COLLAPSED) === 'true';
  } catch {
    return false;
  }
}

function store(collapsed: boolean) {
  try {
    localStorage.setItem(COLLAPSED, String(collapsed));
  } catch {
    // Not remembered, but the menu still collapses.
  }
}

export function Sidebar() {
  const narrow = useNarrow();
  const [collapsed, setCollapsed] = useState(stored);
  const [openOnNarrow, setOpenOnNarrow] = useState(false);
  // Same query as the Overview page on its default range, so both share one request.
  const { data: overview } = useOverview({ range: 'live' });
  const mini = narrow ? !openOnNarrow : collapsed;
  const waiting = overview?.open_reviews ?? 0;
  const systems = SYSTEMS.map((item) => ({ ...item, state: system(overview?.systems[item.name]) }));

  function toggle() {
    if (narrow) {
      setOpenOnNarrow(!openOnNarrow);
    } else {
      setCollapsed(!collapsed);
      store(!collapsed);
    }
  }
  const closeOnNarrow = () => setOpenOnNarrow(false);

  const link = ({ to, label, icon: Icon }: Page) => (
    <NavLink
      key={to}
      to={to}
      end={to === '/'}
      className={styles.link}
      title={mini ? label : undefined}
      onClick={closeOnNarrow}
    >
      <Icon size={18} strokeWidth={1.8} />
      <span className={styles.label}>{label}</span>
      {to === '/review' && waiting > 0 && <span className={styles.badge}>{waiting}</span>}
    </NavLink>
  );

  return (
    <div className={styles.rail} data-slim={mini || narrow}>
      {narrow && !mini && <div className={styles.backdrop} onClick={closeOnNarrow} />}
      <nav
        className={styles.panel}
        aria-label="Main"
        data-mini={mini}
        data-overlay={narrow && !mini}
      >
        <button
          type="button"
          className={styles.collapse}
          title={mini ? 'Expand menu' : 'Collapse menu'}
          onClick={toggle}
        >
          {mini ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          <span className={styles.label}>{mini ? 'Expand menu' : 'Collapse menu'}</span>
        </button>
        {MAIN.map(link)}
        <div className={styles.section}>Systems</div>
        <ul className={styles.systems}>
          {systems.map(({ name, label, state }) => (
            <li
              key={name}
              className={styles.system}
              title={`${label}: ${state.label}. ${state.explanation}`}
            >
              <span className={styles.light} data-tone={state.tone} />
              <span className={styles.label}>{label}</span>
              <span className={styles.state} data-tone={state.tone}>
                {state.label}
              </span>
            </li>
          ))}
        </ul>
        <div className={styles.section}>Platform</div>
        {PLATFORM.map(link)}
      </nav>
    </div>
  );
}
