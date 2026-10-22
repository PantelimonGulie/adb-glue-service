import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRefreshInterval } from './autoRefresh';
import { api } from './client';
import type { AuditRow, EventsPage, Page } from './types';

export interface EventsPoll {
  rows: AuditRow[];
  lastId: number;
}

const EVENTS_KEY = ['events'];

async function newestEventId(): Promise<number> {
  const newest = await api<Page<AuditRow>>('/api/activity?per_page=1');
  return newest.rows[0]?.id ?? 0;
}

// Each poll returns only the rows that are new since the previous poll. The first poll starts
// at the newest event, so the live view never replays old history.
export function useEvents() {
  const client = useQueryClient();
  const refetchInterval = useRefreshInterval();
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
    refetchInterval,
  });
}
