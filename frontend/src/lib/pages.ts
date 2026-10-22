import {
  Activity,
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

export interface Page {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const MAIN: Page[] = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/flow', label: 'Flow', icon: Workflow },
  { to: '/orders', label: 'Orders', icon: FileText },
  { to: '/stock', label: 'Stock', icon: Package },
  { to: '/review', label: 'Review queue', icon: CircleAlert },
  { to: '/activity', label: 'Activity log', icon: Activity },
  { to: '/assistant', label: 'Assistant', icon: MessageSquareMore },
  { to: '/demo', label: 'Demo controls', icon: Wrench },
];

export const PLATFORM: Page[] = [
  { to: '/rules', label: 'Rules', icon: SlidersHorizontal },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/users', label: 'Users and roles', icon: Users },
];
