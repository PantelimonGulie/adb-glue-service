import type { RangeName, RangeQuery } from '../../api/types';
import { customRangeError, RANGES, thisMonth, type SetRange } from '../../lib/range';
import { useAddressText } from '../../lib/useAddressText';
import controls from '../../styles/controls.module.css';
import { Segmented } from '../Segmented/Segmented';
import styles from './RangePicker.module.css';

interface Props {
  value: RangeQuery;
  onChange: SetRange;
}

type Days = { from: string; to: string };

export function RangePicker({ value, onChange }: Props) {
  const [from, setFrom] = useAddressText(value.from ?? '');
  const [to, setTo] = useAddressText(value.to ?? '');
  const custom = value.range === 'custom';
  // Dates that make no range stay in the inputs only; valid ones go to the address.
  const error = custom && customRangeError(from, to);

  function pick(name: RangeName) {
    onChange(name === 'custom' ? thisMonth() : { range: name });
  }

  function edit(next: Days) {
    setFrom(next.from);
    setTo(next.to);
    if (customRangeError(next.from, next.to) === null) {
      onChange({ range: 'custom', ...next }, { replace: true });
    }
  }

  return (
    <div className={styles.picker}>
      <Segmented label="Time range" options={RANGES} value={value.range} onChange={pick} />
      {custom && (
        <span className={styles.days}>
          <input
            type="date"
            className={controls.input}
            aria-label="First day"
            value={from}
            onChange={(event) => edit({ from: event.target.value, to })}
          />
          <span>to</span>
          <input
            type="date"
            className={controls.input}
            aria-label="Last day"
            value={to}
            onChange={(event) => edit({ from, to: event.target.value })}
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
