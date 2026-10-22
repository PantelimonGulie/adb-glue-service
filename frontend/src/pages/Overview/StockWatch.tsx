import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import type { Channel, StockRow } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { Product } from '../../components/Product/Product';
import { formatNumber } from '../../lib/format';
import { channel as channelLabel } from '../../lib/labels';
import controls from '../../styles/controls.module.css';
import styles from './StockWatch.module.css';

const WATCHED = 5;
const CHANNELS: Channel[] = ['shop', 'emag'];

function shown(row: StockRow, channel: Channel) {
  const told = row[channel];
  const name = channelLabel(channel).label;
  const target = Math.max(0, row.free - row.held_back[channel]);
  if (!told) return { text: '—', behind: true, hint: `Not sent to ${name} yet` };
  const text = formatNumber(told.qty);
  if (told.dirty) {
    return { text, behind: true, hint: `${name} refused the last update; Glue tries again` };
  }
  if (told.qty !== target) {
    return { text, behind: true, hint: `${name} has not applied the last update yet` };
  }
  return { text, behind: false, hint: undefined };
}

function watched(rows: StockRow[]) {
  const all = rows.map((row) => ({ row, channels: CHANNELS.map((ch) => shown(row, ch)) }));
  const behind = (item: (typeof all)[number]) => Number(item.channels.some((c) => c.behind));
  // Products a channel is behind on come first, so the short list never hides them.
  return all.sort((a, b) => behind(b) - behind(a)).slice(0, WATCHED);
}

export function StockWatch({ rows }: { rows: StockRow[] }) {
  return (
    <Panel
      title="Stock"
      note="warehouse vs what customers see"
      actions={
        <Link className={controls.button} to="/stock">
          All stock
        </Link>
      }
    >
      <div className={styles.grid}>
        <span className={styles.head}>Product</span>
        <span className={styles.head}>Warehouse</span>
        <span className={styles.head}>Shop</span>
        <span className={styles.head}>eMAG</span>
        {watched(rows).map(({ row, channels }) => (
          <Fragment key={row.sku}>
            <Product name={row.product} sku={row.sku} />
            <span className={styles.number}>{formatNumber(row.free)}</span>
            {channels.map((value, i) => (
              <span
                key={CHANNELS[i]}
                className={styles.number}
                data-behind={value.behind}
                title={value.hint}
              >
                {value.text}
              </span>
            ))}
          </Fragment>
        ))}
      </div>
    </Panel>
  );
}
