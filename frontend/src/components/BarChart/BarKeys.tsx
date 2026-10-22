import { useRef, useState, type KeyboardEvent } from 'react';
import type { Series } from './BarChart';
import styles from './BarKeys.module.css';

interface Props {
  labels: string[];
  series: Series[];
  format: (value: number) => string;
  picked: number;
  onPick: (index: number) => void;
}

const MOVES: Record<string, (index: number, last: number) => number> = {
  ArrowLeft: (index) => index - 1,
  ArrowRight: (index) => index + 1,
  Home: () => 0,
  End: (_, last) => last,
};

function describe({ labels, series, format }: Omit<Props, 'picked' | 'onPick'>) {
  return labels.map((label, i) => {
    const values = series.map((one) => `${one.name} ${format(one.values[i])}`);
    return `${label}: ${values.join(', ')}`;
  });
}

// One tab stop per chart: the arrow keys move between bars and Enter picks one, like a click.
export function BarKeys({ picked, onPick, ...data }: Props) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const [focused, setFocused] = useState(0);
  const names = describe(data);
  const last = names.length - 1;
  const current = picked >= 0 ? picked : Math.min(focused, last);

  function move(event: KeyboardEvent, index: number) {
    const to = MOVES[event.key];
    if (!to) return;
    event.preventDefault();
    buttons.current[Math.max(0, Math.min(last, to(index, last)))]?.focus();
  }

  return (
    <div className={styles.keys}>
      {names.map((name, i) => (
        <button
          key={i}
          ref={(button) => {
            buttons.current[i] = button;
          }}
          type="button"
          tabIndex={i === current ? 0 : -1}
          aria-label={name}
          aria-pressed={i === picked}
          onFocus={() => setFocused(i)}
          onKeyDown={(event) => move(event, i)}
          onClick={() => onPick(i)}
        />
      ))}
    </div>
  );
}
