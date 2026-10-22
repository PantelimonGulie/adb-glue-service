import { useQuery, type QueryKey } from '@tanstack/react-query';
import { rangeParams } from '../lib/range';
import { useRefreshInterval } from './autoRefresh';
import { api } from './client';
import type {
  ActivityKind,
  Analytics,
  Assistant,
  AuditRow,
  Cause,
  Channel,
  Demo,
  Order,
  OrderDetail,
  OrderStatus,
  Overview,
  Page,
  RangeQuery,
  Review,
  Rule,
  Settings,
  Stock,
  User,
} from './types';

export interface OrdersQuery {
  range?: RangeQuery;
  q?: string;
  channel?: Channel;
  status?: OrderStatus;
  page?: number;
  per_page?: number;
}

export interface ActivityQuery {
  range?: RangeQuery;
  kind?: ActivityKind;
  entity?: string;
  page?: number;
  per_page?: number;
}

export interface ReviewQuery {
  status?: 'open' | 'decided';
  cause?: Cause;
}

type Params = Record<string, string | number | undefined>;

function withQuery(path: string, params: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `${path}?${text}` : path;
}

// Keys start with the resource name, so a page can refresh one resource:
// invalidateQueries({ queryKey: ['orders'] }) reaches every orders list and order.
function usePolled<T>(queryKey: QueryKey, path: string) {
  const refetchInterval = useRefreshInterval();
  return useQuery({ queryKey, queryFn: () => api<T>(path), refetchInterval });
}

export function useOverview(range: RangeQuery) {
  const params = { ...rangeParams(range) };
  return usePolled<Overview>(['overview', params], withQuery('/api/overview', params));
}

export function useOrders({ range, ...filters }: OrdersQuery) {
  const params = { ...(range && rangeParams(range)), ...filters };
  return usePolled<Page<Order>>(['orders', params], withQuery('/api/orders', params));
}

export const useOrder = (id: string) =>
  usePolled<OrderDetail>(['orders', id], `/api/orders/${encodeURIComponent(id)}`);

export function useReview(query: ReviewQuery) {
  const params = { ...query };
  return usePolled<Review>(['review', params], withQuery('/api/review', params));
}

export function useActivity({ range, ...filters }: ActivityQuery) {
  const params = { ...(range && rangeParams(range)), ...filters };
  return usePolled<Page<AuditRow>>(['activity', params], withQuery('/api/activity', params));
}

export function useAnalytics(range: RangeQuery, compare: boolean) {
  const params = { ...rangeParams(range), compare: compare ? 1 : 0 };
  return usePolled<Analytics>(['analytics', params], withQuery('/api/analytics', params));
}

export const useStock = () => usePolled<Stock>(['stock'], '/api/stock');
export const useRules = () => usePolled<Rule[]>(['rules'], '/api/rules');
export const useSettings = () => usePolled<Settings>(['settings'], '/api/settings');
export const useUsers = () => usePolled<User[]>(['users'], '/api/users');
export const useAssistant = () => usePolled<Assistant>(['assistant'], '/api/assistant');
export const useDemo = () => usePolled<Demo>(['demo'], '/api/demo');
