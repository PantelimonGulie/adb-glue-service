import { useDemoAction, type DemoCommand } from '../../api/hooks';
import type { DemoResult } from '../../api/types';
import { useDenied } from '../../auth/useDenied';

// One per card, so each card shows the answer to its own last action.
export function useDemoRun() {
  const action = useDemoAction();
  const denied = useDenied('demo');
  const busy = action.isPending;
  const result: DemoResult | undefined = action.error
    ? { ok: false, message: action.error.message }
    : action.data;

  function run(command: DemoCommand) {
    if (!busy) action.mutate(command);
  }

  return {
    run,
    busy,
    result,
    denied,
    lock: { disabled: Boolean(denied), blocked: busy, title: denied },
  };
}
