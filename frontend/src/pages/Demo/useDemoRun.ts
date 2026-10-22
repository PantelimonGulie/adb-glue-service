import { useDemoAction } from '../../api/hooks';
import type { DemoResult } from '../../api/types';
import { useDenied } from '../../auth/useDenied';

// One per card, so each card shows the answer to its own last action.
export function useDemoRun() {
  const action = useDemoAction();
  const denied = useDenied('demo');
  const result: DemoResult | undefined = action.error
    ? { ok: false, message: action.error.message }
    : action.data;
  return {
    run: action.mutate,
    busy: action.isPending,
    result,
    denied,
    lock: { disabled: Boolean(denied) || action.isPending, title: denied },
  };
}
