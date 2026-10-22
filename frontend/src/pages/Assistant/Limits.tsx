import { useState, type FormEvent } from 'react';
import type { Assistant, AssistantLimits } from '../../api/types';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import styles from './Limits.module.css';

type TokenLimits = Pick<AssistantLimits, 'max_tokens_per_question' | 'daily_token_budget'>;

interface Props {
  assistant: Assistant;
  denied?: string;
  saving: boolean;
  onSave: (limits: TokenLimits) => void;
}

export function Limits({ assistant, denied, saving, onSave }: Props) {
  const [longest, setLongest] = useState(String(assistant.max_tokens_per_question));
  const [daily, setDaily] = useState(String(assistant.daily_token_budget));
  const changed =
    Number(longest) !== assistant.max_tokens_per_question ||
    Number(daily) !== assistant.daily_token_budget;

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({ max_tokens_per_question: Number(longest), daily_token_budget: Number(daily) });
  }

  return (
    <form className={styles.limits} onSubmit={submit}>
      <label className={controls.field}>
        Longest answer (tokens)
        <input
          type="number"
          min={200}
          max={8000}
          step={100}
          required
          value={longest}
          disabled={Boolean(denied)}
          title={denied}
          onChange={(event) => setLongest(event.target.value)}
        />
      </label>
      <label className={controls.field}>
        Most tokens per day
        <input
          type="number"
          min={1000}
          max={2000000}
          step={1000}
          required
          value={daily}
          disabled={Boolean(denied)}
          title={denied}
          onChange={(event) => setDaily(event.target.value)}
        />
      </label>
      <span className={text.note}>
        The longest answer caps each reply of the model. The daily budget is the real ceiling.
      </span>
      {!denied && (
        <button type="submit" className={controls.button} disabled={!changed || saving}>
          Save limits
        </button>
      )}
    </form>
  );
}
