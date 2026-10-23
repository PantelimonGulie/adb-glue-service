import type { Analytics, CauseCount } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Panel } from '../../components/Panel/Panel';
import { Product } from '../../components/Product/Product';
import { formatLatency, formatNumber } from '../../lib/format';
import { cause } from '../../lib/labels';
import styles from './Breakdowns.module.css';

type ProductRow = Analytics['by_product'][number];

const typicalTime = (row: ProductRow) => (row.reserved ? formatLatency(row.p50_seconds) : '—');

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
  // Review items, not orders: one order can go to review more than once, and a short shelf
  // count or a failed cancel opens an item for an order that was reserved.
  const reviews = causes.reduce((sum, item) => sum + item.count, 0);
  const times = `${formatNumber(reviews)} review item${reviews === 1 ? '' : 's'} opened`;
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
        <Panel title="Why items went to review" note={times}>
          {reviews === 0 ? (
            <EmptyState title="Nothing went to review in this period" />
          ) : (
            <CauseList causes={causes} total={reviews} />
          )}
        </Panel>
      </div>
    </div>
  );
}
