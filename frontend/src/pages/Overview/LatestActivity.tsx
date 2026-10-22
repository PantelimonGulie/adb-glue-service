import { Link } from 'react-router-dom';
import type { AuditRow } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Panel } from '../../components/Panel/Panel';
import { Tag } from '../../components/Tag/Tag';
import { describe, entityOf, labelOf, type Entity, type ProductName } from '../../lib/activity';
import { formatTime } from '../../lib/format';
import controls from '../../styles/controls.module.css';
import styles from './LatestActivity.module.css';

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

export function LatestActivity({ rows, productName }: Props) {
  const items = rows.map((row) => ({
    id: row.id,
    time: formatTime(row.ts),
    label: labelOf(row),
    entity: entityOf(row, productName),
    detail: describe(row, productName),
  }));
  return (
    <Panel
      title="Latest activity"
      note="hover a label to see what it means"
      actions={
        <Link className={controls.button} to="/activity">
          Full activity log
        </Link>
      }
    >
      {items.length === 0 ? (
        <EmptyState title="Nothing has happened yet" />
      ) : (
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
                <span className={styles.time}>{item.time}</span>
                <Tag tone={item.label.tone} title={item.label.explanation}>
                  {item.label.label}
                </Tag>
                <EntityCell entity={item.entity} />
                <span className={styles.text}>{item.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
