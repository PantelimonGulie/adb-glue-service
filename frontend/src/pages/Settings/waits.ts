import { formatSeconds } from '../../lib/format';

// Doubling after every failed try, as glue/retry.py does (plus up to a fifth at random).
export function retryWaits(attempts: number, firstWait: number): number[] {
  return Array.from({ length: Math.max(attempts - 1, 0) }, (_, index) => firstWait * 2 ** index);
}

export function waitSentence(attempts?: number, firstWait?: number): string {
  if (attempts === undefined || firstWait === undefined) {
    return 'Enter values within the limits to see how long Glue waits between tries.';
  }
  if (attempts === 1) {
    return 'With one try Glue does not wait: an order that fails goes straight to a person.';
  }
  const waits = retryWaits(attempts, firstWait).map(formatSeconds).join(', ');
  return (
    `With these values Glue waits about ${waits} between tries, doubling each time. ` +
    'When the warehouse says how long to wait, Glue waits that long instead.'
  );
}
