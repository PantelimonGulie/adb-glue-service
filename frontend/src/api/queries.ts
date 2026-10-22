import { keepPreviousData, useQuery, type QueryKey } from '@tanstack/react-query';
import { rangeParams } from '../lib/range';
import { useRefreshInterval } from './autoRefresh';
import { api, ApiError } from './client';
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
  // An exact window, e.g. one chart bar; the API uses it instead of the range.
  since?: string;
  until?: string;
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
// keepPreviousData leaves the last range on screen until the new one arrives (isPlaceholderData).
function usePolled<T>(
  queryKey: QueryKey,
  path: string,
  placeholderData?: typeof keepPreviousData,
) {
  const interval = useRefreshInterval();
  return useQuery({
    queryKey,
    queryFn: () => api<T>(path),
    // Something that does not exist will not appear by asking again.
    refetchInterval: (query) => (missing(query.state.error) ? false : interval),
    placeholderData,
  });
}

const missing = (error: unknown) => error instanceof ApiError && error.status === 404;

export function useOverview(range: RangeQuery) {
  const params = { ...rangeParams(range) };
  const path = withQuery('/api/overview', params);
  return usePolled<Overview>(['overview', params], path, keepPreviousData);
}

export function useOrders({ range, ...filters }: OrdersQuery) {
  const params = { ...(range && rangeParams(range)), ...filters };
  const path = withQuery('/api/orders', params);
  return usePolled<Page<Order>>(['orders', params], path, keepPreviousData);
}

export const useOrder = (id: string) =>
  usePolled<OrderDetail>(['orders', id], `/api/orders/${encodeURIComponent(id)}`);

export function useReview(query: ReviewQuery) {
  const params = { ...query };
  return usePolled<Review>(['review', params], withQuery('/api/review', params));
}

export function useActivity({ range, ...filters }: ActivityQuery) {
  const params = { ...(range && rangeParams(range)), ...filters };
  const path = withQuery('/api/activity', params);
  return usePolled<Page<AuditRow>>(['activity', params], path, keepPreviousData);
}

export function useAnalytics(range: RangeQuery, compare: boolean) {
  const params = { ...rangeParams(range), compare: compare ? 1 : 0 };
  const path = withQuery('/api/analytics', params);
  return usePolled<Analytics>(['analytics', params], path, keepPreviousData);
}

export const useStock = () => usePolled<Stock>(['stock'], '/api/stock');
export const useRules = () => usePolled<Rule[]>(['rules'], '/api/rules');
export const useSettings = () => usePolled<Settings>(['settings'], '/api/settings');
export const useUsers = () => usePolled<User[]>(['users'], '/api/users');
export const useAssistant = () => usePolled<Assistant>(['assistant'], '/api/assistant');
export const useDemo = () => usePolled<Demo>(['demo'], '/api/demo');
