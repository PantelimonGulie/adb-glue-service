import { describe, expect, it } from 'vitest';
import { row } from '../../test/fixtures';
import { dotsForRows } from './dots';

const order = (id: number, action: string, orderId = 'shop-1') => ({
  ...row(id, action),
  entity_type: 'order',
  entity_id: orderId,
});
const stock = (id: number, action: string, channel: string) => ({
  ...row(id, action, { channel, qty: 3 }),
  entity_type: 'stock',
  entity_id: 'MBA-M4',
});

describe('dotsForRows', () => {
  it('dotsForRows caps at 30', () => {
    const rows = Array.from({ length: 100 }, (_, i) =>
      row(i + 1, 'event_received', { source: 'shop' }),
    );
    const live = dotsForRows(rows);

    expect(live.dots).toHaveLength(30);
    expect(live.summary).toBe('+70 more');
    expect(live.dots[0].id).toBe(71);
  });

  it('duplicate maps to the fade-out dot', () => {
    const [dot] = dotsForRows([row(1, 'duplicate_dropped', { source: 'emag' })]).dots;

    expect(dot).toMatchObject({ route: 'mktIn', tone: 'grey', motion: 'drop' });
  });

  it('maps each action to the line and colour of the legend', () => {
    const rows = [
      row(1, 'event_received', { source: 'shop' }),
      order(2, 'order_allocated'),
      order(3, 'retry_scheduled'),
      stock(4, 'stock_pushed', 'emag'),
      order(5, 'order_known', 'emag-9'),
      order(6, 'emag_acknowledged'),
    ];

    expect(dotsForRows(rows).dots.map(({ route, tone, motion }) => [route, tone, motion])).toEqual([
      ['shopIn', 'blue', 'travel'],
      ['whOut', 'green', 'travel'],
      ['whOut', 'amber', 'knock'],
      ['mktOut', 'slate', 'travel'],
      ['mktIn', 'grey', 'drop'],
    ]);
  });

  it('spreads the dots of one poll over time and has no summary when all fit', () => {
    const live = dotsForRows([1, 2, 3].map((id) => row(id, 'event_received', { source: 'shop' })));

    expect(live.summary).toBeNull();
    expect(live.dots.map((dot) => dot.delay)).toEqual([0, 0.5, 1]);
  });
});
