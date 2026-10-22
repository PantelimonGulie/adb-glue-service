import { useSaveRule } from '../../api/hooks';
import type { Rule } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { RulePanel } from './RulePanel';

export function RetryRule({ rule }: { rule: Rule }) {
  const save = useSaveRule();
  const denied = useDenied('rules');
  return (
    <RulePanel
      title="Retry by itself after the warehouse recovers"
      explanation="When the warehouse answers again after an outage, retry every order that failed because of it, without waiting for a person."
      rule={rule}
      locked={denied}
      saving={save.isPending}
      error={save.error}
      onToggle={(enabled) => save.mutate({ name: 'auto-retry', enabled })}
    />
  );
}
