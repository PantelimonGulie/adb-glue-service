import { Link } from 'react-router-dom';
import { usePushStock, useStock } from '../../api/hooks';
import { useDenied } from '../../auth/useDenied';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import controls from '../../styles/controls.module.css';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import text from '../../styles/text.module.css';
import styles from './Stock.module.css';
import { StockTable } from './StockTable';

const PUSH_HINT = 'Send the warehouse numbers to both channels right now';

export function Stock() {
  const { data, error, isPending } = useStock();
  const push = usePushStock();
  const denied = useDenied('decide');
  const every = data ? ` every ${data.reconcile_seconds} s` : '';

  return (
    <>
      <div className={page.top}>
        <h1>Stock</h1>
        <span className={page.sub}>
          the warehouse is the source of truth · Glue sends its numbers to both channels{every}
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
        <span className={styles.push}>
          {push.error && (
            <span className={styles.error} role="alert">
              {push.error.message}
            </span>
          )}
          {push.isPending && <span className={text.note}>Sending…</span>}
          {push.isSuccess && (
            <span className={text.good} role="status">
              Sent the warehouse numbers to both channels
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
      {(error || data) && (
        <section className={table.box} aria-label="Stock">
          {error && (
            <EmptyState title="The stock list could not be loaded">{error.message}</EmptyState>
          )}
          {data?.rows.length === 0 && <EmptyState title="The warehouse has no products yet" />}
          {data && data.rows.length > 0 && <StockTable stock={data.rows} />}
        </section>
      )}
      <p className={styles.note}>
        Numbers here cannot be edited. Shelf counts change only in the warehouse (a recount), so
        Glue never invents stock. To keep a safety margin on eMAG, use the{' '}
        <Link to="/rules">stock buffer rule</Link>.
      </p>
    </>
  );
}
