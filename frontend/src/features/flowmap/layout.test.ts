import { expect, it } from 'vitest';
import { fit } from './layout';

it('keeps the mockup drawing at the base width', () => {
  const { geometry, scale } = fit(1000);

  expect(scale).toBe(1);
  expect(geometry.width).toBe(1000);
  expect(geometry.paths).toEqual({
    shopIn: 'M240 78 C320 78 320 112 400 112',
    mktIn: 'M240 262 C320 262 320 228 400 228',
    shopOut: 'M400 132 C320 132 320 100 240 100',
    mktOut: 'M400 208 C320 208 320 240 240 240',
    whOut: 'M620 150 L760 150',
    whBack: 'M760 192 L620 192',
  });
});

it('spreads the columns instead of magnifying past 1.25', () => {
  const { geometry, scale } = fit(2258);

  expect(scale).toBe(1.25);
  expect(geometry.width).toBe(1806);
  expect(geometry.nodes.shop.left).toBe(20);
  expect(geometry.nodes.glue.left).toBe(803);
  expect(geometry.nodes.warehouse.left).toBe(1566);
  expect(geometry.paths.whOut).toBe('M1023 150 L1566 150');
  expect(geometry.paths.shopIn).toBe('M240 78 C521.5 78 521.5 112 803 112');
});

it('stacks the four systems on a phone so none is cut off', () => {
  const { geometry, scale } = fit(276);

  expect(geometry.width).toBe(320);
  expect(scale).toBeCloseTo(0.8625);
  for (const box of Object.values(geometry.nodes)) {
    expect(box.left + box.width).toBeLessThanOrEqual(geometry.width);
    expect(box.top + box.height).toBeLessThanOrEqual(geometry.height);
  }
});

it('widens the stacked drawing on a tablet instead of leaving half the width empty', () => {
  const { geometry, scale } = fit(690);

  expect(scale).toBe(1.25);
  expect(geometry.width * scale).toBeGreaterThan(685);
  expect(geometry.width * scale).toBeLessThanOrEqual(690);
  expect(geometry.nodes.emag.left + geometry.nodes.emag.width).toBe(geometry.width);
  expect(geometry.nodes.glue.width).toBe(geometry.width - 80);
  for (const box of Object.values(geometry.nodes)) {
    expect(box.left + box.width).toBeLessThanOrEqual(geometry.width);
  }
});
