import { expect, it } from 'vitest';
import { numberIn } from './numbers';

it('takes a typed number only within its bounds', () => {
  const tries = { min: 1, max: 10, whole: true };
  expect(numberIn('3', tries)).toBe(3);
  expect(numberIn('10', tries)).toBe(10);
  expect(numberIn('', tries)).toBeUndefined();
  expect(numberIn('0', tries)).toBeUndefined();
  expect(numberIn('2.5', tries)).toBeUndefined();
  expect(numberIn('0.1', { min: 0.1, max: 10 })).toBe(0.1);
});
