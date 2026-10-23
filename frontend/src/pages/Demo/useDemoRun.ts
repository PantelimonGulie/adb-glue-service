import { useMutationState } from '@tanstack/react-query';
import { useDemoAction, type DemoCommand } from '../../api/hooks';
import type { DemoResult } from '../../api/types';
import { useDenied } from '../../auth/useDenied';

// One per card. Only the card that ran the latest action shows its answer, so answers to
// earlier actions do not pile up across the page.
export function useDemoRun() {
  const action = useDemoAction();
  const denied = useDenied('demo');
  const sent = useMutationState({
    filters: { mutationKey: ['demo'] },
    select: (mutation) => mutation.state.submittedAt,
  });
  const latest = action.submittedAt === sent.at(-1);
  const busy = action.isPending;
  const answer: DemoResult | undefined = action.error
    ? { ok: false, message: action.error.message }
    : action.data;

  function run(command: DemoCommand) {
    if (!busy) action.mutate(command);
  }

  return {
    run,
    busy,
    result: latest ? answer : undefined,
    denied,
    lock: { disabled: Boolean(denied), blocked: busy, title: denied },
  };
}
