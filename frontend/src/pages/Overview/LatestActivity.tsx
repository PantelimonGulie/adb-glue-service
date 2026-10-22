import { Link } from 'react-router-dom';
import type { AuditRow } from '../../api/types';
import { ActivityTable } from '../../components/ActivityTable/ActivityTable';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Panel } from '../../components/Panel/Panel';
import type { ProductName } from '../../lib/activity';
import controls from '../../styles/controls.module.css';

interface Props {
  rows: AuditRow[];
  productName: ProductName;
}

export function LatestActivity({ rows, productName }: Props) {
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
      {rows.length === 0 ? (
        <EmptyState title="Nothing has happened yet" />
      ) : (
        <ActivityTable rows={rows} productName={productName} />
      )}
    </Panel>
  );
}
