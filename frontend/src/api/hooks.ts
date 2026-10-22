import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { rangeParams } from '../lib/range';
import { REFRESH_MS, useAutoRefresh } from './autoRefresh';
import { api } from './client';
import type {
  ActivityKind,
  Analytics,
  Answer,
  Assistant,
  AssistantLimits,
  AuditRow,
  Cause,
  Channel,
  Decision,
  Demo,
  DemoAction,
  DemoResult,
  EventsPage,
  Order,
  OrderDetail,
  OrderStatus,
  Overview,
  Page,
  RangeQuery,
  Review,
  ReviewItem,
  Rule,
  Settings,
  Stock,
  StockBufferConfig,
  Tuning,
  Turn,
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

export interface EventsPoll {
  rows: AuditRow[];
  lastId: number;
}

type RuleChange = { name: Rule['name']; enabled: boolean; config?: StockBufferConfig };
type DemoCommand =
  | { action: DemoAction }
  | { action: 'recount'; body: { sku: string; on_hand: number } };

function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `${path}?${text}` : path;
}

function usePolled<T>(path: string) {
  const { on } = useAutoRefresh();
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    refetchInterval: on ? REFRESH_MS : false,
  });
}

export const useOverview = (range: RangeQuery) =>
  usePolled<Overview>(withQuery('/api/overview', { ...rangeParams(range) }));

export const useOrders = ({ range, ...query }: OrdersQuery) =>
  usePolled<Page<Order>>(withQuery('/api/orders', { ...(range && rangeParams(range)), ...query }));

export const useOrder = (id: string) =>
  usePolled<OrderDetail>(`/api/orders/${encodeURIComponent(id)}`);

export const useStock = () => usePolled<Stock>('/api/stock');

export const useReview = (query: ReviewQuery) =>
  usePolled<Review>(withQuery('/api/review', { ...query }));

export const useActivity = ({ range, ...query }: ActivityQuery) =>
  usePolled<Page<AuditRow>>(
    withQuery('/api/activity', { ...(range && rangeParams(range)), ...query }),
  );

export const useAnalytics = (range: RangeQuery, compare: boolean) =>
  usePolled<Analytics>(
    withQuery('/api/analytics', { ...rangeParams(range), compare: compare ? 1 : 0 }),
  );

export const useRules = () => usePolled<Rule[]>('/api/rules');
export const useSettings = () => usePolled<Settings>('/api/settings');
export const useUsers = () => usePolled<User[]>('/api/users');
export const useAssistant = () => usePolled<Assistant>('/api/assistant');
export const useDemo = () => usePolled<Demo>('/api/demo');

const EVENTS_KEY = ['/api/events'];

async function newestEventId(): Promise<number> {
  const newest = await api<Page<AuditRow>>('/api/activity?per_page=1');
  return newest.rows[0]?.id ?? 0;
}

// Each poll returns only the rows that are new since the previous poll. The first poll starts
// at the newest event, so the live view never replays old history.
export function useEvents() {
  const client = useQueryClient();
  const { on } = useAutoRefresh();
  return useQuery({
    queryKey: EVENTS_KEY,
    queryFn: async (): Promise<EventsPoll> => {
      const previous = client.getQueryData<EventsPoll>(EVENTS_KEY);
      if (!previous) return { rows: [], lastId: await newestEventId() };
      const rows: AuditRow[] = [];
      let page: EventsPage = { rows: [], last_id: previous.lastId, more: true };
      while (page.more) {
        page = await api<EventsPage>(`/api/events?after=${page.last_id}`);
        rows.push(...page.rows);
      }
      return { rows, lastId: page.last_id };
    },
    refetchInterval: on ? REFRESH_MS : false,
  });
}

function useCommand<V = void, R = unknown>(run: (variables: V) => Promise<R>) {
  const client = useQueryClient();
  // Any change can move counters, queues and stock at once, so everything is reloaded.
  return useMutation({ mutationFn: run, onSettled: () => client.invalidateQueries() });
}

const post = <R>(path: string, body?: unknown) => api<R>(path, { method: 'POST', body });
const put = <R>(path: string, body: unknown) => api<R>(path, { method: 'PUT', body });

export const useDecide = () =>
  useCommand(({ id, action }: { id: number; action: Decision }) =>
    post<ReviewItem>(`/api/review/${id}/${action}`),
  );

export const useRetryAll = () =>
  useCommand(() => post<{ retried: number }>('/api/review/retry-all', { cause: 'outage' }));

export const useTriage = () =>
  useCommand((id: number) => post<ReviewItem>(`/api/review/${id}/triage`));

export const useSaveRule = () =>
  useCommand(({ name, ...change }: RuleChange) => put<Rule>(`/api/rules/${name}`, change));

export const useSaveSettings = () =>
  useCommand((change: Partial<Tuning>) => put<Settings>('/api/settings', change));

export const useSaveAssistantSettings = () =>
  useCommand((change: Partial<AssistantLimits>) =>
    put<Assistant>('/api/assistant/settings', change),
  );

export const useAsk = () =>
  useCommand((question: { question: string; history: Turn[] }) =>
    post<Answer>('/api/assistant/ask', question),
  );

export const useDemoAction = () =>
  useCommand((command: DemoCommand) => {
    const body = command.action === 'recount' ? command.body : undefined;
    return post<DemoResult>(`/api/demo/${command.action}`, body);
  });

export const usePushStock = () => useCommand(() => post<null>('/api/stock/push'));
