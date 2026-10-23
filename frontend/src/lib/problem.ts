const STATUSES: Record<string, string> = {
  '404': 'not found',
  '408': 'no answer in time',
  '429': 'asked Glue to slow down',
  '503': 'not available',
};
const MESSAGES: Record<string, string> = {
  'order.placed': 'a shop order',
  'order.cancelled': 'a cancellation',
  'order.shipped': 'a shipment',
  'stock.adjusted': 'a shelf count',
  'emag.notification': 'an eMAG message',
};

function status(code: string): string {
  return STATUSES[code] ?? (code.startsWith('5') ? 'a server error' : 'the request was refused');
}

function failure(name: string): string {
  if (name.endsWith('Timeout')) return 'no answer in time';
  if (name.startsWith('Connect')) return 'could not connect';
  return /^(Read|Write|RemoteProtocol|Network)Error$/.test(name)
    ? 'the connection failed'
    : 'an unexpected error';
}

// Older rows keep the raw text the backend wrote: HTTP codes, exception names and URLs.
export function plainProblem(text: string): string {
  return text
    .replace(/\s*For more information check:[\s\S]*$/, '')
    .replace(/ for url '[^']*'/g, '')
    .replace(/HTTPStatusError: \w+ error '(\d{3})[^']*'/g, (_, code) => status(code))
    .replace(/\bHTTP (\d{3})\b/g, (_, code) => status(code))
    .replace(/\b([A-Z]\w*(?:Error|Timeout))\b[\s\S]*?(?= after \d+ attempts|$)/g, (_, name) =>
      failure(name),
    )
    .replace(/ after (\d+) attempts/g, ' after $1 tries')
    .replace(/unexpected while handling ([\w.]+)/, (_, type) => {
      return `could not handle ${MESSAGES[type] ?? 'a message'}`;
    });
}

export function seconds(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toLocaleString('en-US')} second${rounded === 1 ? '' : 's'}`;
}
