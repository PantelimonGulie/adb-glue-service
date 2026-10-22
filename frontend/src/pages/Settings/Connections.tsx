import type { Settings, SystemName } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { Tag } from '../../components/Tag/Tag';
import { system } from '../../lib/labels';
import table from '../../styles/table.module.css';
import styles from './Connections.module.css';

const NAMES: Record<SystemName, string> = {
  shop: 'Shop (Electronic Market)',
  emag: 'eMAG Marketplace',
  warehouse: 'Bucharest warehouse',
};

export function Connections({ connections }: { connections: Settings['connections'] }) {
  const rows = connections.map((connection) => ({
    ...connection,
    label: NAMES[connection.name],
    status: system(connection),
  }));
  return (
    <Panel title="Connections" note="the systems Glue talks to">
      <div className={table.scroll}>
        <table className={table.table}>
          <thead>
            <tr>
              <th>System</th>
              <th>Address</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name}>
                <td>
                  <b>{row.label}</b>
                </td>
                <td className={table.number}>{row.url}</td>
                <td>
                  <span className={styles.status}>
                    <Tag tone={row.status.tone}>{row.status.label}</Tag>
                    {!row.ok && <span className={styles.problem}>{row.state}</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
