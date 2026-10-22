import { Link } from 'react-router-dom';
import { useAnalytics, useOverview, useStock } from '../../api/hooks';
import { Panel } from '../../components/Panel/Panel';
import { RangePicker } from '../../components/RangePicker/RangePicker';
import { Tag } from '../../components/Tag/Tag';
import { FlowMap } from '../../features/flowmap/FlowMap';
import { MapLegend } from '../../features/flowmap/MapLegend';
import { formatTime } from '../../lib/format';
import { useProductName } from '../../lib/products';
import { rangeLabel, rangeSearch, useRange } from '../../lib/range';
import controls from '../../styles/controls.module.css';
import { Counters } from './Counters';
import { LatestActivity } from './LatestActivity';
import { OrdersChart } from './OrdersChart';
import styles from './Overview.module.css';
import { StockWatch } from './StockWatch';
import { Waiting } from './Waiting';

const LIVE_NOTE = 'each dot is one real event';
const PERIOD_NOTE =
  'totals for the period · lines get thicker with volume · click a label to see those events';

export function Overview() {
  const [range, setRange] = useRange();
  const { data: overview, dataUpdatedAt, isPlaceholderData: oldOverview } = useOverview(range);
  const { data: analytics, isPlaceholderData: oldAnalytics } = useAnalytics(range, false);
  const loading = oldOverview || oldAnalytics;
  const { data: stock } = useStock();
  const live = range.range === 'live';
  const updated = dataUpdatedAt
    ? ` · updated ${formatTime(new Date(dataUpdatedAt).toISOString())}`
    : '';
  const productName = useProductName();

  return (
    <>
      <div className={styles.top}>
        <h1>Overview</h1>
        <span className={styles.sub}>
          Electronic Market · shop and eMAG, one warehouse{updated}
        </span>
        <span role="status">{loading && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      <RangePicker value={range} onChange={setRange} />
      <Counters range={range} overview={overview} />
      <Panel
        title={live ? 'Live flow' : `Flow · ${rangeLabel(range)}`}
        note={live ? LIVE_NOTE : PERIOD_NOTE}
        actions={
          <>
            <Link className={controls.button} to={`/flow?${rangeSearch(range)}`}>
              Open Flow details →
            </Link>
            {live && <MapLegend />}
          </>
        }
      >
        <FlowMap mode={live ? 'live' : 'period'} totals={analytics} />
        {!live && analytics && <OrdersChart analytics={analytics} />}
      </Panel>
      <div className={styles.bottom}>
        <div className={styles.wide}>
          <LatestActivity rows={overview?.latest ?? []} productName={productName} />
        </div>
        <div className={styles.side}>
          <Waiting total={overview?.open_reviews ?? 0} groups={overview?.review_groups ?? []} />
          <StockWatch rows={stock?.rows ?? []} />
        </div>
      </div>
    </>
  );
}
