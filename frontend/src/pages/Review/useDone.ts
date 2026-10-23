import { useMutationState } from '@tanstack/react-query';
import type { ReviewItem } from '../../api/types';
import { formatNumber } from '../../lib/format';
import { done } from './explain';

function said(command: unknown, data: unknown): string {
  if (command !== 'retry-all') return done(data as ReviewItem);
  const { retried } = data as { retried: number };
  if (retried === 0) return 'No order was sent again';
  return `Sent ${formatNumber(retried)} order${retried === 1 ? '' : 's'} again`;
}

// What the latest decision or Retry all did. Its card is gone by then, so the page says it.
// The mutation cache keeps the order they were sent in.
export function useDone(): string | undefined {
  const finished = useMutationState({
    filters: { mutationKey: ['review'], status: 'success' },
    select: (mutation) => said(mutation.options.mutationKey?.[1], mutation.state.data),
  });
  return finished.at(-1);
}
