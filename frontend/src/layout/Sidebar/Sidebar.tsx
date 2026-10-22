import {
  Activity,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileText,
  LayoutDashboard,
  MessageSquareMore,
  Package,
  Settings,
  SlidersHorizontal,
  Users,
  Workflow,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useOverview } from '../../api/hooks';
import type { SystemName } from '../../api/types';
import { system } from '../../lib/labels';
import styles from './Sidebar.module.css';
import { useNarrow } from './useNarrow';

interface Item {
  to: string;
  label: string;
  icon: LucideIcon;
}

const MAIN: Item[] = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/flow', label: 'Flow', icon: Workflow },
  { to: '/orders', label: 'Orders', icon: FileText },
  { to: '/stock', label: 'Stock', icon: Package },
  { to: '/review', label: 'Review queue', icon: CircleAlert },
  { to: '/activity', label: 'Activity log', icon: Activity },
  { to: '/assistant', label: 'Assistant', icon: MessageSquareMore },
  { to: '/demo', label: 'Demo controls', icon: Wrench },
];
const PLATFORM: Item[] = [
  { to: '/rules', label: 'Rules', icon: SlidersHorizontal },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/users', label: 'Users and roles', icon: Users },
];
const SYSTEMS: { name: SystemName; label: string }[] = [
  { name: 'shop', label: 'Shop' },
  { name: 'emag', label: 'eMAG' },
  { name: 'warehouse', label: 'Warehouse' },
];

export function Sidebar() {
  const narrow = useNarrow();
  const [collapsed, setCollapsed] = useState(false);
  const [openOnNarrow, setOpenOnNarrow] = useState(false);
  // Same query as the Overview page on its default range, so both share one request.
  const { data: overview } = useOverview({ range: 'live' });
  const mini = narrow ? !openOnNarrow : collapsed;
  const waiting = overview?.open_reviews ?? 0;
  const systems = SYSTEMS.map((item) => ({ ...item, state: system(overview?.systems[item.name]) }));

  const toggle = () => (narrow ? setOpenOnNarrow(!openOnNarrow) : setCollapsed(!collapsed));
  const closeOnNarrow = () => setOpenOnNarrow(false);

  const link = ({ to, label, icon: Icon }: Item) => (
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
            <li key={name} className={styles.system} title={`${label}: ${state.label}`}>
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
