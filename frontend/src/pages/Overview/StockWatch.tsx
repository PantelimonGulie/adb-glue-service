import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import type { StockRow } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { Product } from '../../components/Product/Product';
import { formatNumber } from '../../lib/format';
import { CHANNELS, shown } from '../../lib/stock';
import controls from '../../styles/controls.module.css';
import styles from './StockWatch.module.css';

const SENT = 'The last number this channel accepted from Glue';

function watched(rows: StockRow[]) {
  const all = rows.map((row) => ({ row, channels: CHANNELS.map((ch) => shown(row, ch)) }));
  const behind = (item: (typeof all)[number]) => Number(item.channels.some((c) => c.behind));
  // Products a channel is behind on come first.
  return all.sort((a, b) => behind(b) - behind(a));
}

export function StockWatch({ rows }: { rows: StockRow[] }) {
  return (
    <Panel
      title="Stock"
      note="free to sell vs the last number Glue sent"
      actions={
        <Link className={controls.button} to="/stock">
          All stock
        </Link>
      }
    >
      <div className={styles.grid}>
        <span className={styles.head}>Product</span>
        <span className={styles.head} title="On the shelf minus reserved">
          Free to sell
        </span>
        <span className={styles.head} title={SENT}>
          Shop
        </span>
        <span className={styles.head} title={SENT}>
          eMAG
        </span>
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
