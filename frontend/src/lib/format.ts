export const formatNumber = (value: number) => value.toLocaleString('en-US');

export const formatTime = (ts: string) => new Date(ts).toLocaleTimeString('en-GB');
