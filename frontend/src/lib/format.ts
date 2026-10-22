export const formatNumber = (value: number) => value.toLocaleString('en-US');

export const formatSeconds = (value: number) =>
  `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })} s`;

export const formatTime = (ts: string) => new Date(ts).toLocaleTimeString('en-GB');
