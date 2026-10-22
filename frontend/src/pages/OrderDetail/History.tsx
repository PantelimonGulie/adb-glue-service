import type { AuditRow } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Panel } from '../../components/Panel/Panel';
import { Tag } from '../../components/Tag/Tag';
import { describe, labelOf, type ProductName } from '../../lib/activity';
import { formatDay, formatTime } from '../../lib/format';
import styles from './History.module.css';

interface Props {
  rows: AuditRow[];
  productName: ProductName;
}

export function History({ rows, productName }: Props) {
  const steps = rows.map((row) => ({
    id: row.id,
    time: formatTime(row.ts),
    day: formatDay(row.ts),
    label: labelOf(row),
    detail: describe(row, productName),
  }));
  return (
    <Panel title="History" note="every step, in order, with the reason">
      {steps.length === 0 ? (
        <EmptyState title="No steps recorded yet" />
      ) : (
        <ol className={styles.steps} aria-label="History">
          {steps.map((step) => (
            <li key={step.id} className={styles.step}>
              <span className={styles.rail}>
                <i className={styles.dot} data-tone={step.label.tone} />
              </span>
              <span className={styles.time}>
                {step.time}
                {step.day && <small>{step.day}</small>}
              </span>
              <span className={styles.body}>
                <Tag tone={step.label.tone} title={step.label.explanation}>
                  {step.label.label}
                </Tag>
                <span className={styles.detail}>{step.detail}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
