import type { Channel, StockRow } from '../api/types';
import { formatNumber } from './format';
import { channel as channelLabel } from './labels';

export const CHANNELS: Channel[] = ['shop', 'emag'];

const STATES: Record<StockRow['state'], { ok: boolean; explanation: string }> = {
  in_sync: {
    ok: true,
    explanation: 'Both channels show exactly what the warehouse has free to sell.',
  },
  held: {
    ok: true,
    explanation: 'The stock buffer rule keeps a few units back on a channel as a safety margin.',
  },
  behind: {
    ok: false,
    explanation: 'A channel does not show the warehouse number yet. The next stock check sends it.',
  },
  refused: {
    ok: false,
    explanation: 'A channel refused the last stock update. Glue tries again on the next stock check.',
  },
};

const name = (channel: Channel) => channelLabel(channel).label;

export function shown(row: StockRow, channel: Channel) {
  const told = row[channel];
  const target = Math.max(0, row.free - row.held_back[channel]);
  if (!told) return { text: '—', behind: true, hint: `Not sent to ${name(channel)} yet` };
  const text = formatNumber(told.qty);
  if (told.dirty) {
    const hint = `${name(channel)} refused the last update; Glue tries again`;
    return { text, behind: true, hint };
  }
  if (told.qty !== target) {
    return { text, behind: true, hint: `${name(channel)} has not applied the last update yet` };
  }
  return { text, behind: false, hint: undefined };
}

function stateLabel(row: StockRow): string {
  const where = (test: (channel: Channel) => boolean) =>
    CHANNELS.filter(test).map(name).join(' and ');
  switch (row.state) {
    case 'refused':
      return `${where((channel) => Boolean(row[channel]?.dirty))} refused the update, retrying`;
    case 'behind':
      return `${where((channel) => shown(row, channel).behind)} not updated yet`;
    case 'held': {
      const held = CHANNELS.filter((channel) => row.held_back[channel] > 0);
      const parts = held.map((ch) => `${row.held_back[ch]} held back on ${name(ch)}`);
      return `${parts.join(', ')} (rule)`;
    }
    default:
      return 'in sync';
  }
}

export const stockState = (row: StockRow) => ({ label: stateLabel(row), ...STATES[row.state] });
