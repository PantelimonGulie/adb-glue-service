import type { Tuning } from '../../api/types';
import { numberIn } from '../../lib/numbers';

export type TuningKey = keyof Tuning;
export type TuningText = Record<TuningKey, string>;

// The same limits the API checks (glue/tuning.py), so a wrong value is caught before saving.
export const LIMITS: Record<TuningKey, { min: number; max: number; step: number; whole: boolean }> =
  {
    retry_attempts: { min: 1, max: 10, step: 1, whole: true },
    retry_base_seconds: { min: 0.1, max: 10, step: 0.1, whole: false },
    reconcile_interval_seconds: { min: 2, max: 300, step: 1, whole: false },
  };

const KEYS = Object.keys(LIMITS) as TuningKey[];

export const textOf = (tuning: Tuning): TuningText => ({
  retry_attempts: String(tuning.retry_attempts),
  retry_base_seconds: String(tuning.retry_base_seconds),
  reconcile_interval_seconds: String(tuning.reconcile_interval_seconds),
});

// Only the values within their limits.
export function parseTuning(text: TuningText): Partial<Tuning> {
  const values: Partial<Tuning> = {};
  for (const key of KEYS) {
    const value = numberIn(text[key], LIMITS[key]);
    if (value !== undefined) values[key] = value;
  }
  return values;
}

export const complete = (values: Partial<Tuning>): values is Tuning =>
  KEYS.every((key) => values[key] !== undefined);

export const changed = (values: Partial<Tuning>, saved: Tuning) =>
  KEYS.some((key) => values[key] !== saved[key]);
