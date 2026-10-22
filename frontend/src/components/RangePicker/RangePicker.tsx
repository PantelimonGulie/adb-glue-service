import { useState } from 'react';
import type { RangeName, RangeQuery } from '../../api/types';
import { customRangeError, RANGES, thisMonth } from '../../lib/range';
import controls from '../../styles/controls.module.css';
import { Segmented } from '../Segmented/Segmented';
import styles from './RangePicker.module.css';

interface Props {
  value: RangeQuery;
  onChange: (range: RangeQuery) => void;
}

type Days = { from: string; to: string };

export function RangePicker({ value, onChange }: Props) {
  // Holds the dates only while they are invalid; valid dates go straight to onChange.
  const [draft, setDraft] = useState<Days | null>(null);
  const days = draft ?? { from: value.from ?? '', to: value.to ?? '' };
  const error = draft && customRangeError(draft.from, draft.to);

  function pick(name: RangeName) {
    setDraft(null);
    onChange(name === 'custom' ? thisMonth() : { range: name });
  }

  function edit(change: Partial<Days>) {
    const next = { ...days, ...change };
    const valid = customRangeError(next.from, next.to) === null;
    setDraft(valid ? null : next);
    if (valid) onChange({ range: 'custom', ...next });
  }

  return (
    <div className={styles.picker}>
      <Segmented label="Time range" options={RANGES} value={value.range} onChange={pick} />
      {value.range === 'custom' && (
        <span className={styles.days}>
          <input
            type="date"
            className={controls.input}
            aria-label="First day"
            value={days.from}
            onChange={(event) => edit({ from: event.target.value })}
          />
          <span>to</span>
          <input
            type="date"
            className={controls.input}
            aria-label="Last day"
            value={days.to}
            onChange={(event) => edit({ to: event.target.value })}
          />
        </span>
      )}
      {error && (
        <span className={styles.error} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
