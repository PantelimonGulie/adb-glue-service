import { useMutation, useQueryClient, type MutationKey } from '@tanstack/react-query';
import { api } from './client';
import type {
  Answer,
  Assistant,
  AssistantLimits,
  Decision,
  DemoAction,
  DemoResult,
  ReviewItem,
  Rule,
  Settings,
  StockBufferConfig,
  Tuning,
  Turn,
} from './types';

type RuleChange = { name: Rule['name']; enabled: boolean; config?: StockBufferConfig };
export type DemoCommand =
  | { action: DemoAction }
  | { action: 'recount'; body: { sku: string; on_hand: number } };

// The key lets a page read how a command ended after the component that sent it is gone.
function useCommand<V = void, R = unknown>(
  run: (variables: V) => Promise<R>,
  mutationKey?: MutationKey,
) {
  const client = useQueryClient();
  // Any change can move counters, queues and stock at once, so everything is reloaded.
  return useMutation({ mutationKey, mutationFn: run, onSettled: () => client.invalidateQueries() });
}

const post = <R>(path: string, body?: unknown) => api<R>(path, { method: 'POST', body });
const put = <R>(path: string, body: unknown) => api<R>(path, { method: 'PUT', body });

export const useDecide = () =>
  useCommand(
    ({ id, action }: { id: number; action: Decision }) =>
      post<ReviewItem>(`/api/review/${id}/${action}`),
    ['review', 'decide'],
  );

export const useRetryAll = () =>
  useCommand(
    () => post<{ retried: number }>('/api/review/retry-all', { cause: 'outage' }),
    ['review', 'retry-all'],
  );

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
  }, ['demo']);

export const usePushStock = () => useCommand(() => post<null>('/api/stock/push'));
