import type { Channel, StockRow } from '../api/types';
import { formatNumber } from './format';
import { channel as channelLabel } from './labels';

export const CHANNELS: Channel[] = ['shop', 'emag'];

// Glue knows what it sent and whether the channel accepted it, not what the channel displays.
const STATES: Record<StockRow['state'], { ok: boolean; explanation: string }> = {
  in_sync: {
    ok: true,
    explanation:
      'Both channels accepted the free-to-sell number Glue sent last. Glue does not read back what they display.',
  },
  held: {
    ok: true,
    explanation:
      'Both channels accepted the last number. The stock buffer rule keeps a few units back on one as a safety margin.',
  },
  behind: {
    ok: false,
    explanation:
      'Glue has not sent the latest free-to-sell number to a channel yet. The next stock check sends it.',
  },
  refused: {
    ok: false,
    explanation:
      'A channel refused the last number for this product. Glue sends it again at every stock check, but a channel that keeps refusing needs a look on its side.',
  },
};

const name = (channel: Channel) => channelLabel(channel).label;

export function shown(row: StockRow, channel: Channel) {
  const told = row[channel];
  const target = Math.max(0, row.free - row.held_back[channel]);
  if (!told) {
    return { text: '—', behind: true, hint: `Glue has not sent ${name(channel)} a number yet` };
  }
  const text = formatNumber(told.qty);
  if (told.dirty) return { text, behind: true, hint: `${name(channel)} refused the last number` };
  if (told.qty !== target) {
    const hint = `Glue has not sent the latest number to ${name(channel)} yet`;
    return { text, behind: true, hint };
  }
  return { text, behind: false, hint: `${name(channel)} accepted this number` };
}

function stateLabel(row: StockRow): string {
  const where = (test: (channel: Channel) => boolean) =>
    CHANNELS.filter(test).map(name).join(' and ');
  switch (row.state) {
    case 'refused':
      return `${where((channel) => Boolean(row[channel]?.dirty))} refused`;
    case 'behind':
      return `${where((channel) => shown(row, channel).behind)} behind`;
    case 'held': {
      const held = CHANNELS.filter((channel) => row.held_back[channel] > 0);
      const parts = held.map((ch) => `${row.held_back[ch]} held back on ${name(ch)}`);
      return `sent · ${parts.join(', ')}`;
    }
    default:
      return 'sent to both';
  }
}

export const stockState = (row: StockRow) => ({ label: stateLabel(row), ...STATES[row.state] });
