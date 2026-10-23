import type { StockRow } from '../../api/types';
import { Product } from '../../components/Product/Product';
import { formatNumber } from '../../lib/format';
import { CHANNELS, shown, stockState } from '../../lib/stock';
import table from '../../styles/table.module.css';
import styles from './StockTable.module.css';

const SENT = (where: string) =>
  `The last number Glue sent ${where}. Glue knows whether ${where} accepted it, not what it displays.`;
const COLUMNS = [
  { name: 'Product', hint: undefined, width: styles.product },
  { name: 'On the shelf', hint: 'Units the Bucharest warehouse counted', width: styles.count },
  {
    name: 'Reserved for orders',
    hint: 'Units set aside for orders not shipped yet',
    width: styles.count,
  },
  {
    name: 'Free to sell',
    hint: 'On the shelf minus reserved: the number Glue sends',
    width: styles.count,
  },
  { name: 'Last sent to the shop', hint: SENT('the shop'), width: styles.channel },
  { name: 'Last sent to eMAG', hint: SENT('eMAG'), width: styles.channel },
  {
    name: 'State',
    hint: 'What Glue knows about the last update to each channel',
    width: styles.state,
  },
];

export function StockTable({ stock }: { stock: StockRow[] }) {
  const rows = stock.map((row) => ({
    row,
    channels: CHANNELS.map((channel) => ({ channel, ...shown(row, channel) })),
    state: stockState(row),
  }));
  return (
    <div className={table.scroll}>
      <table className={`${table.table} ${styles.table}`}>
        <colgroup>
          {COLUMNS.map((column) => (
            <col key={column.name} className={column.width} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column.name} title={column.hint}>
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ row, channels, state }) => (
            <tr key={row.sku} data-ok={state.ok}>
              <td>
                <Product name={row.product} sku={row.sku} />
              </td>
              <td className={table.number}>{formatNumber(row.on_hand)}</td>
              <td className={table.number}>{formatNumber(row.reserved)}</td>
              <td className={`${table.number} ${styles.free}`}>{formatNumber(row.free)}</td>
              {channels.map((shows) => (
                <td
                  key={shows.channel}
                  className={table.number}
                  data-behind={shows.behind}
                  title={shows.hint}
                >
                  {shows.text}
                </td>
              ))}
              <td className={styles.stateText} title={state.explanation}>
                {state.label}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
