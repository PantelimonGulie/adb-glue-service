import { expect, it } from 'vitest';
import type { StockRow } from '../api/types';
import { stock } from '../test/fixtures';
import { stockState } from './stock';

const base: StockRow = {
  ...stock.rows[0],
  free: 5,
  shop: { qty: 5, dirty: false },
  emag: { qty: 5, dirty: false },
  state: 'in_sync',
};

it('says in plain words whether both channels show the warehouse numbers', () => {
  const label = (row: Partial<StockRow>) => {
    const state = stockState({ ...base, ...row });
    return [state.label, state.ok];
  };

  expect(label({})).toEqual(['in sync', true]);
  expect(
    label({ state: 'held', emag: { qty: 4, dirty: false }, held_back: { shop: 0, emag: 1 } }),
  ).toEqual(['1 held back on eMAG (rule)', true]);
  expect(label({ state: 'behind', emag: { qty: 7, dirty: false } })).toEqual([
    'eMAG not updated yet',
    false,
  ]);
  expect(label({ state: 'behind', shop: null, emag: { qty: 7, dirty: false } })).toEqual([
    'Shop and eMAG not updated yet',
    false,
  ]);
  expect(label({ state: 'refused', shop: { qty: 9, dirty: true } })).toEqual([
    'Shop refused the update, retrying',
    false,
  ]);
});
