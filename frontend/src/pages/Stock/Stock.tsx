import { Link } from 'react-router-dom';
import { usePushStock, useStock } from '../../api/hooks';
import { useDenied } from '../../auth/useDenied';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Product } from '../../components/Product/Product';
import { formatNumber } from '../../lib/format';
import { CHANNELS, shown, stockState } from '../../lib/stock';
import controls from '../../styles/controls.module.css';
import table from '../../styles/table.module.css';
import styles from './Stock.module.css';

const PUSH_HINT = 'Send the warehouse numbers to both channels right now';

export function Stock() {
  const { data } = useStock();
  const push = usePushStock();
  const denied = useDenied('decide');
  const every = data ? ` every ${data.reconcile_seconds} s` : '';
  const rows = (data?.rows ?? []).map((row) => ({
    row,
    channels: CHANNELS.map((channel) => ({ channel, ...shown(row, channel) })),
    state: stockState(row),
  }));

  return (
    <>
      <div className={styles.top}>
        <h1>Stock</h1>
        <span className={styles.sub}>
          the warehouse is the source of truth · Glue sends its numbers to both channels{every}
        </span>
        <span className={styles.push}>
          {push.error && (
            <span className={styles.error} role="alert">
              {push.error.message}
            </span>
          )}
          <button
            type="button"
            className={controls.button}
            disabled={Boolean(denied) || push.isPending}
            title={denied ?? PUSH_HINT}
            onClick={() => push.mutate()}
          >
            Update channels now
          </button>
        </span>
      </div>
      <section className={table.box} aria-label="Stock">
        {data && data.rows.length === 0 ? (
          <EmptyState title="The warehouse has no products yet" />
        ) : (
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
        )}
      </section>
      <p className={styles.note}>
        Numbers here cannot be edited. Shelf counts change only in the warehouse (a recount), so
        Glue never invents stock. To keep a safety margin on eMAG, use the{' '}
        <Link to="/rules">stock buffer rule</Link>.
      </p>
    </>
  );
}
