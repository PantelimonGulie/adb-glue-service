import type { StockRow } from '../../api/types';
import { Product } from '../../components/Product/Product';
import { formatNumber } from '../../lib/format';
import { CHANNELS, shown, stockState } from '../../lib/stock';
import table from '../../styles/table.module.css';
import styles from './StockTable.module.css';

export function StockTable({ stock }: { stock: StockRow[] }) {
  const rows = stock.map((row) => ({
    row,
    channels: CHANNELS.map((channel) => ({ channel, ...shown(row, channel) })),
    state: stockState(row),
  }));
  return (
    <div className={table.scroll}>
      <table className={`${table.table} ${styles.table}`}>
        <thead>
          <tr>
            <th>Product</th>
            <th>On the shelf</th>
            <th>Reserved for orders</th>
            <th>Free to sell</th>
            <th>Shop shows</th>
            <th>eMAG shows</th>
            <th>State</th>
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
              <td className={styles.state} title={state.explanation}>
                {state.label}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
