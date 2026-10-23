// The API cuts days in the business's timezone and names it in /api/me; every time and date on
// screen follows that zone, whatever the browser is set to.
const BUSINESS_ZONE = 'Europe/Bucharest';
let zone = BUSINESS_ZONE;

export function setTimeZone(name: string | undefined) {
  zone = name ?? BUSINESS_ZONE;
}

const inZone = (ts: string | number | Date, options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat('en-GB', { ...options, timeZone: zone }).format(new Date(ts));

export const formatNumber = (value: number) => value.toLocaleString('en-US');

// A value someone set, such as a wait between tries, reads as it was set.
export const formatSeconds = (value: number) =>
  `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })} s`;

export const formatDecimal = (value: number, digits = 1) =>
  value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });

// A measured time always has two decimals, so a column of them lines up.
export const formatLatency = (value: number) => `${formatDecimal(value, 2)} s`;

export const formatTime = (ts: string) =>
  inZone(ts, { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });

export const formatHours = (ts: string) =>
  inZone(ts, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

export const formatDate = (ts: string | Date) => inZone(ts, { day: 'numeric', month: 'short' });

export const formatDateTime = (ts: string) => `${formatDate(ts)}, ${formatHours(ts)}`;

// A calendar day such as 2026-10-01, which belongs to no timezone.
export const formatDayLabel = (day: string) =>
  new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${day}T00:00:00Z`),
  );

export function zonedDate(moment: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: zone,
  }).formatToParts(moment);
  const part = (type: string) => parts.find((item) => item.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

function offsetMs(instant: number): number {
  const wall = inZone(instant, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  });
  const [day, month, year, hour, minute, second] = wall.split(/\D+/).map(Number);
  return Date.UTC(year, month - 1, day, hour, minute, second) - (instant - (instant % 1000));
}

// When the zone's clocks read 00:00 on that day, as a UTC timestamp. The second pass corrects
// the guess on days the clocks change.
export function zonedMidnight(day: string): string {
  const wall = Date.parse(`${day}T00:00:00Z`);
  const guess = wall - offsetMs(wall);
  return new Date(wall - offsetMs(guess)).toISOString();
}

// Empty for today, so a time of day is enough on its own.
export function formatDay(ts: string, now = new Date()): string {
  const date = new Date(ts);
  return zonedDate(date) === zonedDate(now) ? '' : formatDate(date);
}

export function formatWindow(since: string, until: string): string {
  const start = new Date(since);
  const end = new Date(until);
  // The end is exclusive, so a window that ends at midnight still belongs to its first day.
  const sameDay = zonedDate(start) === zonedDate(new Date(end.getTime() - 1));
  if (sameDay) return `${formatHours(since)}–${formatHours(until)}, ${formatDate(start)}`;
  return `${formatHours(since)}, ${formatDate(start)} – ${formatHours(until)}, ${formatDate(end)}`;
}
