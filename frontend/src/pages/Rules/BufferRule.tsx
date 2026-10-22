import { useState, type FormEvent } from 'react';
import { useSaveRule, useStock } from '../../api/hooks';
import type { Channel, Rule, StockBufferConfig } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { NumberField } from '../../components/NumberField/NumberField';
import { numberIn } from '../../lib/numbers';
import controls from '../../styles/controls.module.css';
import styles from './BufferRule.module.css';
import { RulePanel } from './RulePanel';

const CHANNELS: Record<Channel, { name: string; other: string }> = {
  emag: { name: 'eMAG', other: 'the shop' },
  shop: { name: 'the shop', other: 'eMAG' },
};
const UNITS = { min: 0, max: 99, whole: true };
const FIX_UNITS_FIRST = `Enter units from ${UNITS.min} to ${UNITS.max} first`;

const same = (a: StockBufferConfig, b: StockBufferConfig) =>
  a.channel === b.channel && a.units === b.units && a.sku === b.sku;

export function BufferRule({ rule }: { rule: Extract<Rule, { name: 'stock-buffer' }> }) {
  const save = useSaveRule();
  const denied = useDenied('rules');
  const { data: stock } = useStock();
  const [channel, setChannel] = useState(rule.config.channel);
  const [typedUnits, setTypedUnits] = useState(String(rule.config.units));
  const [sku, setSku] = useState(rule.config.sku);
  const units = numberIn(typedUnits, UNITS);
  const config = units === undefined ? undefined : { channel, units, sku };
  const { name, other } = CHANNELS[rule.config.channel];
  // The switch saves what is on screen, so it waits until that is valid.
  const locked = denied ?? (config ? undefined : FIX_UNITS_FIRST);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (config) save.mutate({ name: 'stock-buffer', enabled: rule.enabled, config });
  }

  return (
    <RulePanel
      title={`Keep a safety buffer on ${name}`}
      explanation={`Show ${name} fewer units than are really free, so the last units sell on ${other} first and ${name} oversells less.`}
      rule={rule}
      locked={locked}
      saving={save.isPending}
      error={save.error}
      onToggle={(enabled) => config && save.mutate({ name: 'stock-buffer', enabled, config })}
    >
      <form className={styles.form} onSubmit={submit}>
        <label className={controls.field}>
          Hold back on
          <select
            value={channel}
            disabled={Boolean(denied)}
            title={denied}
            onChange={(event) => setChannel(event.target.value as Channel)}
          >
            <option value="emag">eMAG</option>
            <option value="shop">Shop</option>
          </select>
        </label>
        <NumberField
          label="Units to hold back"
          value={typedUnits}
          min={UNITS.min}
          max={UNITS.max}
          step={1}
          disabled={Boolean(denied)}
          title={denied}
          error={units === undefined ? `From ${UNITS.min} to ${UNITS.max}` : undefined}
          onChange={setTypedUnits}
        />
        <label className={controls.field}>
          Product
          <select
            value={sku}
            disabled={Boolean(denied)}
            title={denied}
            onChange={(event) => setSku(event.target.value)}
          >
            <option value="">Every product</option>
            {stock?.rows.map((row) => (
              <option key={row.sku} value={row.sku}>
                {row.product}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className={`${controls.button} ${styles.save}`}
          disabled={Boolean(denied) || !config || same(config, rule.config) || save.isPending}
          title={denied}
        >
          Save the buffer
        </button>
      </form>
    </RulePanel>
  );
}
