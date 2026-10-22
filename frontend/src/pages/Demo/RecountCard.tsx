import { useState, type FormEvent } from 'react';
import { useStock } from '../../api/hooks';
import { NumberField } from '../../components/NumberField/NumberField';
import { numberIn } from '../../lib/numbers';
import controls from '../../styles/controls.module.css';
import { CardButton } from './CardButton';
import { DemoCard } from './DemoCard';
import styles from './RecountCard.module.css';
import { useDemoRun } from './useDemoRun';

// The same bounds the API checks.
const SHELF = { min: 0, max: 100_000, whole: true };

export function RecountCard() {
  const { run, busy, result, denied, lock } = useDemoRun();
  const { data: stock } = useStock();
  const [chosen, setChosen] = useState<string>();
  const [typed, setTyped] = useState('');
  const rows = stock?.rows ?? [];
  const product = rows.find((row) => row.sku === chosen) ?? rows[0];
  const onHand = numberIn(typed, SHELF);
  const wrong = typed !== '' && onHand === undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (product && onHand !== undefined) {
      run({ action: 'recount', body: { sku: product.sku, on_hand: onHand } });
    }
  }

  return (
    <DemoCard
      title="Warehouse recount"
      text="Change how many units are on the shelf. Below what is reserved, orders go to review."
      busy={busy}
      result={result}
    >
      <form className={styles.form} onSubmit={submit}>
        <label className={controls.field}>
          Product
          <select
            value={product?.sku ?? ''}
            disabled={Boolean(denied)}
            title={denied}
            onChange={(event) => setChosen(event.target.value)}
          >
            {rows.map((row) => (
              <option key={row.sku} value={row.sku}>
                {row.product}
              </option>
            ))}
          </select>
        </label>
        <NumberField
          label="Units on the shelf"
          value={typed}
          min={SHELF.min}
          max={SHELF.max}
          step={1}
          disabled={Boolean(denied)}
          title={denied}
          hint={product && `${product.on_hand} there now`}
          error={wrong ? 'Enter a whole number from 0 to 100,000.' : undefined}
          onChange={setTyped}
        />
        <CardButton
          type="submit"
          label="Save the count"
          {...lock}
          disabled={lock.disabled || !product || onHand === undefined}
        />
      </form>
    </DemoCard>
  );
}
