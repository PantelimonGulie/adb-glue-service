export const formatNumber = (value: number) => value.toLocaleString('en-US');

export const formatSeconds = (value: number) =>
  `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })} s`;

export const formatTime = (ts: string) => new Date(ts).toLocaleTimeString('en-GB');

const hours = (date: Date) =>
  date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
const day = (date: Date) => date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

// Empty for today, so a time of day is enough on its own.
export function formatDay(ts: string, now = new Date()): string {
  const date = new Date(ts);
  return date.toDateString() === now.toDateString() ? '' : day(date);
}

export function formatWindow(since: string, until: string): string {
  const start = new Date(since);
  const end = new Date(until);
  const sameDay = start.toDateString() === end.toDateString();
  if (sameDay) return `${hours(start)}–${hours(end)}, ${day(start)}`;
  return `${hours(start)}, ${day(start)} – ${hours(end)}, ${day(end)}`;
}
