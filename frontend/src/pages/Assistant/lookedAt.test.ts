import { expect, it } from 'vitest';
import { lookedAt } from './lookedAt';

it('names what an answer looked at in plain words, once each', () => {
  expect(lookedAt(['get_order', 'get_order', 'get_stock'], 912)).toBe(
    'Looked at: order history, stock · 912 tokens',
  );
  expect(lookedAt(['get_weather'], 1200)).toBe('Looked at: other records · 1,200 tokens');
  expect(lookedAt([], 80)).toBe('Answered without looking anything up · 80 tokens');
});
