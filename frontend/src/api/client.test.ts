import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';

function respond(status: number, body?: unknown) {
  const fetch = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), { status }),
  );
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

function sentHeaders(fetch: ReturnType<typeof respond>) {
  return new Headers(fetch.mock.calls[0][1].headers);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api', () => {
  it('client redirects on 401', async () => {
    respond(401, { detail: 'sign in first' });
    const assign = vi.fn();
    vi.stubGlobal('location', { pathname: '/orders', search: '', assign });

    await expect(api('/api/orders')).rejects.toMatchObject({ status: 401 });
    expect(assign).toHaveBeenCalledWith('/sign-in?next=%2Forders');
  });

  it('stays on the sign-in page when the password is wrong', async () => {
    respond(401, { detail: 'Wrong user name or password.' });
    const assign = vi.fn();
    vi.stubGlobal('location', { pathname: '/sign-in', search: '', assign });

    await expect(api('/api/session', { method: 'POST' })).rejects.toMatchObject({
      status: 401,
      detail: 'Wrong user name or password.',
    });
    expect(assign).not.toHaveBeenCalled();
  });

  it('non-GET sends X-Glue-Request: 1', async () => {
    const fetch = respond(202, null);

    await api('/api/stock/push', { method: 'POST' });

    expect(sentHeaders(fetch).get('X-Glue-Request')).toBe('1');
    expect(fetch.mock.calls[0][1].credentials).toBe('same-origin');
  });

  it('GET sends no X-Glue-Request header', async () => {
    const fetch = respond(200, { rows: [] });

    expect(await api('/api/stock')).toEqual({ rows: [] });
    expect(sentHeaders(fetch).has('X-Glue-Request')).toBe(false);
  });

  it('sends the body as JSON', async () => {
    const fetch = respond(200, { retried: 2 });

    await api('/api/review/retry-all', { method: 'POST', body: { cause: 'outage' } });

    expect(fetch.mock.calls[0][1].body).toBe('{"cause":"outage"}');
    expect(sentHeaders(fetch).get('Content-Type')).toBe('application/json');
  });

  it('accepts an empty answer', async () => {
    respond(204);

    await expect(api('/api/session', { method: 'DELETE' })).resolves.toBeUndefined();
  });

  it('uses the first validation message as the detail', async () => {
    respond(422, {
      detail: [{ loc: ['query', 'range'], msg: 'from must not be after to', type: 'value_error' }],
    });

    await expect(api('/api/orders?range=custom')).rejects.toMatchObject({
      status: 422,
      detail: 'from must not be after to',
    });
  });
});
