import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import type { ActivityKind, Analytics, RangeQuery } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import type { Part } from '../../features/flowmap/layout';
import { formatNumber, formatSeconds } from '../../lib/format';
import { rangeSearch } from '../../lib/range';
import controls from '../../styles/controls.module.css';
import styles from './PartPanel.module.css';

type Parts = Analytics['parts'];

interface About {
  title: string;
  kind: ActivityKind;
  text: string;
  numbers: (parts: Parts) => [string, string][];
}

// Nothing is logged when the warehouse comes back, so the backend estimates the length.
function outage({ longest_outage_minutes: minutes, retries }: Parts['warehouse']) {
  if (minutes) return `about ${formatNumber(minutes)} minute${minutes === 1 ? '' : 's'}`;
  return retries ? 'under a minute' : 'none';
}

const PARTS: Record<Part, About> = {
  shop: {
    title: 'Shop · Electronic Market',
    kind: 'orders',
    text:
      'The shop pushes every order to Glue as it happens. Its main problem is sending the same message twice, which Glue ignores safely.',
    numbers: ({ shop }) => [
      ['Orders sent to Glue', formatNumber(shop.orders)],
      ['Duplicates it sent', formatNumber(shop.duplicates)],
      ['Messages refused (fake or unreadable)', formatNumber(shop.refused)],
    ],
  },
  emag: {
    title: 'eMAG Marketplace',
    kind: 'orders',
    text:
      'eMAG only sends order numbers. Glue fetches each order and confirms it, so eMAG stops sending it again. Most oversells happen here, because eMAG applies stock updates with a delay.',
    numbers: ({ emag }) => [
      ['Orders fetched', formatNumber(emag.orders)],
      ['Notifications sent again', formatNumber(emag.renotified)],
      ['Times it asked Glue to slow down', formatNumber(emag.slowdowns)],
      ['Stock updates refused', formatNumber(emag.refused_updates)],
      ['Sold after it ran out', formatNumber(emag.sold_out)],
    ],
  },
  glue: {
    title: 'Glue',
    kind: 'all',
    text:
      'Every message is saved first, then processed. Nothing is lost if a system is down: Glue waits, tries again, and asks a person when it cannot decide.',
    numbers: ({ glue }) => [
      ['Order messages handled', formatNumber(glue.handled)],
      ['Duplicates ignored', formatNumber(glue.duplicates)],
      ['Typical time to reserve', formatSeconds(glue.p50_seconds)],
      ['Slowest 5% took', formatSeconds(glue.p95_seconds)],
      ['Orders lost', formatNumber(glue.lost)],
    ],
  },
  warehouse: {
    title: 'Bucharest warehouse',
    kind: 'retries',
    text:
      'The warehouse holds the real stock. When it does not answer, Glue tries again with longer waits, then sends the order to review.',
    numbers: ({ warehouse }) => [
      ['Orders received', formatNumber(warehouse.received)],
      ['Accepted on first try', `${warehouse.first_try_pct.toFixed(1)}%`],
      ['Retries needed', formatNumber(warehouse.retries)],
      ['Failed after all tries', formatNumber(warehouse.failed)],
      ['Longest outage', outage(warehouse)],
    ],
  },
};

interface Props {
  part: Part;
  parts: Parts;
  range: RangeQuery;
}

export function PartPanel({ part, parts, range }: Props) {
  const about = PARTS[part];
  return (
    <Panel title={about.title} note="click a box on the map to switch">
      <div className={styles.body}>
        <dl className={styles.numbers}>
          {about.numbers(parts).map(([label, value]) => (
            <Fragment key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </Fragment>
          ))}
        </dl>
        <p className={styles.text}>{about.text}</p>
        <Link className={controls.button} to={`/activity?kind=${about.kind}&${rangeSearch(range)}`}>
          See these events in the activity log
        </Link>
      </div>
    </Panel>
  );
}
