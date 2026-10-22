import { useSaveAssistantSettings } from '../../api/hooks';
import type { Assistant, Effort } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { Segmented } from '../../components/Segmented/Segmented';
import { Tag } from '../../components/Tag/Tag';
import { formatNumber } from '../../lib/format';
import { modelState } from '../../lib/model';
import controls from '../../styles/controls.module.css';
import { Bar } from './Bar';
import { Limits } from './Limits';
import styles from './ModelPanel.module.css';

const EFFORTS: { value: Effort; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];
const WARN_SHARE = 0.8;

export function ModelPanel({ assistant }: { assistant: Assistant }) {
  const denied = useDenied('settings');
  const save = useSaveAssistantSettings();
  const { model, used_today: used, daily_token_budget: budget } = assistant;
  const state = modelState(model);
  const downloaded = Math.round(model.progress * 100);
  const questions = assistant.questions_today;
  const nearlySpent = used > budget * WARN_SHARE;
  const asked = `${formatNumber(questions)} question${questions === 1 ? '' : 's'}`;
  const usage = `${formatNumber(used)} of ${formatNumber(budget)} tokens · ${asked}`;
  const models = assistant.models.map((option) => ({
    ...option,
    text: option.available ? option.label : `${option.label} · coming soon`,
  }));

  return (
    <section className={styles.panel} aria-label="Assistant settings">
      <div className={styles.title}>
        <h2>Model</h2>
        <Tag tone={state.tone}>{state.label}</Tag>
      </div>
      {model.status === 'downloading' && (
        <Bar role="progressbar" label="Download" value={downloaded} max={100} />
      )}
      <label className={controls.field}>
        Which model answers
        <select defaultValue={model.id} disabled={Boolean(denied)} title={denied}>
          {models.map((option) => (
            <option key={option.id} value={option.id} disabled={!option.available}>
              {option.text}
            </option>
          ))}
        </select>
      </label>
      <div className={controls.field}>
        Effort
        <span title={denied}>
          <Segmented
            label="Effort"
            options={EFFORTS}
            value={assistant.effort}
            disabled={Boolean(denied) || save.isPending}
            onChange={(effort) => save.mutate({ effort })}
          />
        </span>
        <span className={styles.note}>
          How much it looks up before answering. Higher is more thorough, slower and uses more
          tokens.
        </span>
      </div>
      <h2>Cost control</h2>
      <Limits assistant={assistant} denied={denied} saving={save.isPending} onSave={save.mutate} />
      <div className={controls.field}>
        Used today
        <Bar role="meter" label="Used today" value={used} max={budget} warn={nearlySpent} />
        <span className={styles.note}>
          {usage} · local model: no money spent. Cloud models will show cost in euros here.
        </span>
      </div>
      {save.error && (
        <p className={styles.error} role="alert">
          {save.error.message}
        </p>
      )}
      {denied && <p className={styles.note}>Only admins can change these.</p>}
    </section>
  );
}
