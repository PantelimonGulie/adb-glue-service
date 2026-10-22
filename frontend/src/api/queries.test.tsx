import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { testClient, withClient } from '../test/render';
import { useOrders } from './queries';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('keys a query by resource and filters, so a page can refresh one resource', async () => {
  const fetch = vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify({ rows: [], total: 0, page: 2, per_page: 25 }))),
  );
  vi.stubGlobal('fetch', fetch);
  const client = testClient();
  const useWeekPage2 = () => useOrders({ range: { range: 'week' }, page: 2 });
  renderHook(useWeekPage2, { wrapper: withClient(client) });

  const key = ['orders', { range: 'week', page: 2 }];
  await waitFor(() => expect(client.getQueryData(key)).toBeDefined());
  expect(fetch).toHaveBeenCalledWith('/api/orders?range=week&page=2', expect.anything());

  await client.invalidateQueries({ queryKey: ['orders'] });
  expect(fetch).toHaveBeenCalledTimes(2);
});
