import type { Analytics, CauseCount } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Panel } from '../../components/Panel/Panel';
import { Product } from '../../components/Product/Product';
import { formatNumber, formatSeconds } from '../../lib/format';
import { cause } from '../../lib/labels';
import styles from './Breakdowns.module.css';

type ProductRow = Analytics['by_product'][number];

const typicalTime = (row: ProductRow) => (row.reserved ? formatSeconds(row.p50_seconds) : '—');

function ProductTable({ rows }: { rows: ProductRow[] }) {
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Product</th>
            <th>Orders</th>
            <th>Reserved</th>
            <th>Failed</th>
            <th>Typical time</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sku}>
              <td>
                <Product name={row.product} sku={row.sku} />
              </td>
              <td>{formatNumber(row.orders)}</td>
              <td>{formatNumber(row.reserved)}</td>
              <td data-bad={row.failed > 0}>{formatNumber(row.failed)}</td>
              <td>{typicalTime(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function causeRows(causes: CauseCount[], total: number) {
  return causes.map((item) => ({
    ...cause(item.cause),
    key: item.cause,
    count: formatNumber(item.count),
    width: `${(item.count / total) * 100}%`,
  }));
}

function CauseList({ causes, total }: { causes: CauseCount[]; total: number }) {
  return (
    <ul className={styles.causes}>
      {causeRows(causes, total).map((row) => (
        <li key={row.key} className={styles.cause}>
          <span className={styles.causeHead}>
            {row.label}
            <b>{row.count}</b>
          </span>
          <span className={styles.track}>
            <i style={{ width: row.width }} />
          </span>
          <span className={styles.advice}>{row.advice}</span>
        </li>
      ))}
    </ul>
  );
}

export function Breakdowns({ analytics }: { analytics: Analytics }) {
  const products = analytics.by_product;
  const causes = analytics.failure_causes;
  // Counts each time an order went to review, also orders later retried and reserved, so it
  // can exceed the funnel's failed orders.
  const reviews = causes.reduce((sum, item) => sum + item.count, 0);
  const times = `${formatNumber(reviews)} time${reviews === 1 ? '' : 's'} sent to review`;
  return (
    <div className={styles.breakdowns}>
      <div className={styles.products}>
        <Panel title="By product">
          {products.length === 0 ? (
            <EmptyState title="No orders in this period" />
          ) : (
            <ProductTable rows={products} />
          )}
        </Panel>
      </div>
      <div className={styles.failures}>
        <Panel title="Why orders failed" note={times}>
          {reviews === 0 ? (
            <EmptyState title="No orders failed in this period" />
          ) : (
            <CauseList causes={causes} total={reviews} />
          )}
        </Panel>
      </div>
    </div>
  );
}
