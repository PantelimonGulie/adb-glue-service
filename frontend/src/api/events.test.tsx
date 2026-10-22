import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { testClient, withClient } from '../test/render';
import { useEvents } from './events';

const row = (id: number) => ({
  id,
  ts: '2026-10-22T10:00:00.000+00:00',
  correlation_id: `c-${id}`,
  entity_type: 'order',
  entity_id: `shop-${id}`,
  action: 'event_received',
  detail: {},
});
const ids = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => row(from + i));

const answers: Record<string, unknown> = {
  '/api/activity?per_page=1': { rows: [row(40)], total: 40, page: 1, per_page: 1 },
  '/api/events?after=40': { rows: ids(41, 240), last_id: 240, more: true },
  '/api/events?after=240': { rows: ids(241, 250), last_id: 250, more: false },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

it('useEvents starts at the newest event, then pages until caught up', async () => {
  const fetch = vi.fn((path: string) =>
    Promise.resolve(new Response(JSON.stringify(answers[path]))),
  );
  vi.stubGlobal('fetch', fetch);
  const { result } = renderHook(() => useEvents(), { wrapper: withClient(testClient()) });

  await waitFor(() => expect(result.current.data).toEqual({ rows: [], lastId: 40 }));
  await result.current.refetch();

  await waitFor(() => expect(result.current.data?.lastId).toBe(250));
  expect(result.current.data?.rows.map((r) => r.id)).toEqual(ids(41, 250).map((r) => r.id));
});
