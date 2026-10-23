export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

type ApiInit = Omit<RequestInit, 'body'> & { body?: unknown };

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { body, ...rest } = init;
  const method = rest.method ?? 'GET';
  const headers = new Headers(rest.headers);
  if (method !== 'GET') headers.set('X-Glue-Request', '1');
  if (body !== undefined) headers.set('Content-Type', 'application/json');

  const response = await fetch(path, {
    ...rest,
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // On the sign-in page a 401 means a wrong password, not an expired session. /api/me is the
  // first call of a visit, so a 401 anywhere else means a session that was working has ended.
  if (response.status === 401 && window.location.pathname !== '/sign-in') {
    const next = window.location.pathname + window.location.search;
    const ended = path === '/api/me' ? '' : '&ended=1';
    window.location.assign(`/sign-in?next=${encodeURIComponent(next)}${ended}`);
  }
  const text = await response.text();
  if (!response.ok) throw new ApiError(response.status, detailOf(text, response));
  return (text ? JSON.parse(text) : undefined) as T;
}

function detailOf(text: string, response: Response): string {
  let detail: unknown;
  try {
    detail = JSON.parse(text).detail;
  } catch {
    detail = undefined;
  }
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg;
  return response.statusText || `The server answered HTTP ${response.status}.`;
}
