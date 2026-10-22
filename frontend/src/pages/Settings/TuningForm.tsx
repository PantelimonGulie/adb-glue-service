import { useState, type FormEvent } from 'react';
import type { useSaveSettings } from '../../api/hooks';
import type { Settings } from '../../api/types';
import { NumberField } from '../../components/NumberField/NumberField';
import { Panel } from '../../components/Panel/Panel';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import { changed, complete, LIMITS, parseTuning, textOf, type TuningKey } from './limits';
import styles from './TuningForm.module.css';
import { waitSentence } from './waits';

interface Props {
  settings: Settings;
  denied?: string;
  save: ReturnType<typeof useSaveSettings>;
}

export function TuningForm({ settings, denied, save }: Props) {
  const [typed, setTyped] = useState(() => textOf(settings));
  const values = parseTuning(typed);
  const dirty = changed(values, settings);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (complete(values)) save.mutate(values);
  }

  const field = (key: TuningKey, label: string) => {
    const { min, max, step } = LIMITS[key];
    return (
      <NumberField
        label={label}
        value={typed[key]}
        min={min}
        max={max}
        step={step}
        disabled={Boolean(denied)}
        title={denied}
        error={values[key] === undefined ? `From ${min} to ${max}` : undefined}
        onChange={(value) => setTyped({ ...typed, [key]: value })}
      />
    );
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <Panel title="Retries" note="what Glue does when the warehouse does not answer">
        <div className={styles.fields}>
          {field('retry_attempts', 'Tries before asking a person')}
          {field('retry_base_seconds', 'First wait (seconds)')}
          <NumberField
            label="Give up on one call after (seconds)"
            value={settings.http_timeout_seconds}
            disabled
            title="Set when Glue starts. It cannot be changed here."
            hint="Set when Glue starts"
          />
        </div>
        <p className={`${text.note} ${styles.sentence}`}>
          {waitSentence(values.retry_attempts, values.retry_base_seconds)}
        </p>
      </Panel>
      <Panel title="Stock check" note="how often the true stock goes to both channels again">
        <div className={styles.fields}>
          {field(
            'reconcile_interval_seconds',
            'Send warehouse numbers to both channels every (seconds)',
          )}
        </div>
      </Panel>
      <div className={styles.actions}>
        <button
          type="submit"
          className={controls.button}
          disabled={Boolean(denied) || !complete(values) || !dirty || save.isPending}
          title={denied}
        >
          Save settings
        </button>
        {save.error && (
          <p className={text.error} role="alert">
            {save.error.message}
          </p>
        )}
        {save.isSuccess && !dirty && (
          <p className={text.note} role="status">
            Saved. Glue uses the new values now.
          </p>
        )}
      </div>
    </form>
  );
}
