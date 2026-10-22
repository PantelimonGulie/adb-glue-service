import { Link } from 'react-router-dom';
import type { CauseCount } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { formatNumber } from '../../lib/format';
import { cause } from '../../lib/labels';
import styles from './Waiting.module.css';

interface Props {
  total: number;
  groups: CauseCount[];
}

export function Waiting({ total, groups }: Props) {
  if (groups.length === 0) return null;
  const items = groups.map(({ cause: name, count }) => {
    const orders = `${formatNumber(count)} order${count === 1 ? '' : 's'}`;
    return { key: name, title: cause(name).label, line: `${orders} · ${cause(name).hint}` };
  });
  return (
    <Panel title="Waiting for you" alert actions={<span className={styles.total}>{total}</span>}>
      <div className={styles.body}>
        {items.map((item) => (
          <div key={item.key} className={styles.group}>
            <b>{item.title}</b>
            <span className={styles.line}>{item.line}</span>
          </div>
        ))}
        <Link className={styles.open} to="/review">
          Open review queue
        </Link>
      </div>
    </Panel>
  );
}
