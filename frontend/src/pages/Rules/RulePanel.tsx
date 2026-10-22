import type { ReactNode } from 'react';
import type { Rule } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { Switch } from '../../components/Switch/Switch';
import { formatDay, formatHours } from '../../lib/format';
import text from '../../styles/text.module.css';
import styles from './RulePanel.module.css';

interface Props {
  title: string;
  explanation: string;
  rule: Rule;
  // Why the switch cannot be used right now, if it cannot.
  locked?: string;
  saving: boolean;
  error: Error | null;
  onToggle: (enabled: boolean) => void;
  children?: ReactNode;
}

function lastChange({ updated_by: by, updated_at: at }: Rule): string {
  if (!by || !at) return 'Never changed: this is how Glue starts.';
  return `Last changed by ${by} · ${[formatDay(at), formatHours(at)].filter(Boolean).join(' ')}`;
}

export function RulePanel(props: Props) {
  const { title, explanation, rule, locked, saving, error, onToggle, children } = props;
  const toggle = (
    <Switch
      checked={rule.enabled}
      label={title}
      disabled={Boolean(locked) || saving}
      title={locked}
      onChange={onToggle}
    />
  );
  return (
    <Panel title={title} actions={toggle}>
      <div className={styles.body}>
        <p className={styles.explanation}>{explanation}</p>
        {children}
        <p className={text.note}>{lastChange(rule)}</p>
        {error && (
          <p className={text.error} role="alert">
            {error.message}
          </p>
        )}
      </div>
    </Panel>
  );
}
