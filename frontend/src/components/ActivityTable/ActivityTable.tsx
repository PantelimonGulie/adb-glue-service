import { Link } from 'react-router-dom';
import type { AuditRow } from '../../api/types';
import { entityOf, labelOf, type Entity, type ProductName } from '../../lib/activity';
import { describe } from '../../lib/describe';
import { formatDay, formatTime } from '../../lib/format';
import { Tag } from '../Tag/Tag';
import styles from './ActivityTable.module.css';

const SAMPLE_HINT = 'This row comes from the sample history loaded on the Demo controls page.';

interface Props {
  rows: AuditRow[];
  productName: ProductName;
}

function EntityCell({ entity }: { entity: Entity }) {
  if (entity.kind === 'order') {
    return (
      <Link className={styles.order} to={`/orders/${encodeURIComponent(entity.id)}`}>
        {entity.id}
      </Link>
    );
  }
  if (entity.kind === 'product') {
    return (
      <Link className={styles.product} to="/stock">
        {entity.name}
      </Link>
    );
  }
  return <span className={styles.text}>{entity.text}</span>;
}

export function ActivityTable({ rows, productName }: Props) {
  const items = rows.map((row) => ({
    id: row.id,
    time: formatTime(row.ts),
    day: formatDay(row.ts),
    label: labelOf(row),
    entity: entityOf(row, productName),
    detail: describe(row, productName),
    sample: row.detail.sample === true,
  }));
  return (
    <div className={styles.scroll}>
      <div className={styles.table}>
        <div className={styles.head}>
          <span>Time</span>
          <span>What happened</span>
          <span>Order or product</span>
          <span>Details</span>
        </div>
        {items.map((item) => (
          <div key={item.id} className={styles.row}>
            <span className={styles.time}>
              {item.time}
              {item.day && <small>{item.day}</small>}
            </span>
            <span className={styles.label}>
              <Tag tone={item.label.tone} title={item.label.explanation}>
                {item.label.label}
              </Tag>
            </span>
            <span className={styles.entity}>
              <EntityCell entity={item.entity} />
            </span>
            <span className={styles.details}>
              {item.sample && (
                <Tag tone="grey" title={SAMPLE_HINT}>
                  sample
                </Tag>
              )}
              <span className={styles.text}>{item.detail}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
