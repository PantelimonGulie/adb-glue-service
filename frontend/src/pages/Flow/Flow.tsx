import { useState } from 'react';
import { useAnalytics } from '../../api/hooks';
import { BarChart } from '../../components/BarChart/BarChart';
import { Panel } from '../../components/Panel/Panel';
import { RangePicker } from '../../components/RangePicker/RangePicker';
import { Switch } from '../../components/Switch/Switch';
import { Tag } from '../../components/Tag/Tag';
import { FlowMap } from '../../features/flowmap/FlowMap';
import type { Part } from '../../features/flowmap/layout';
import { MapLegend } from '../../features/flowmap/MapLegend';
import { rangeLabel, rangeSearch, useRange } from '../../lib/range';
import controls from '../../styles/controls.module.css';
import { Breakdowns } from './Breakdowns';
import { flowCharts } from './charts';
import { Comparison } from './Comparison';
import styles from './Flow.module.css';
import { Funnel } from './Funnel';
import { PartPanel } from './PartPanel';

const LIVE_NOTE = 'each dot is one real event · click a box to see its numbers';
const PERIOD_NOTE = 'totals for the period · click a box to see its numbers';

export function Flow() {
  const [range, setRange] = useRange();
  const [compare, setCompare] = useState(false);
  const [part, setPart] = useState<Part>('glue');
  const { data: analytics, isPlaceholderData: loading } = useAnalytics(range, compare);
  const live = range.range === 'live';
  const period = rangeLabel(range);
  const search = rangeSearch(range);

  return (
    <>
      <div className={styles.top}>
        <h1>Flow</h1>
        <span className={styles.sub}>
          how orders and stock move between the shop, eMAG and the warehouse
        </span>
        <span role="status">{loading && <Tag tone="grey">Loading…</Tag>}</span>
        <span className={styles.tools}>
          <span className={styles.sub}>Compare with previous period</span>
          <Switch checked={compare} onChange={setCompare} label="Compare with previous period" />
          <a className={controls.button} href={`/api/analytics.csv?${search}`} download>
            Export CSV
          </a>
        </span>
      </div>
      <RangePicker value={range} onChange={setRange} />
      <Panel
        title={`Flow · ${period}`}
        note={live ? LIVE_NOTE : PERIOD_NOTE}
        actions={live && <MapLegend />}
      >
        <FlowMap
          mode={live ? 'live' : 'period'}
          totals={analytics}
          selected={part}
          onSelect={setPart}
        />
      </Panel>
      {compare && <Comparison range={range} analytics={analytics} />}
      {analytics && (
        <>
          <Funnel funnel={analytics.funnel} period={period} />
          <div className={styles.board}>
            <PartPanel part={part} parts={analytics.parts} range={range} />
            {flowCharts(analytics).map(({ id, ...chart }) => (
              // A new range starts each chart afresh, with nothing picked.
              <BarChart key={`${id} ${search}`} {...chart} />
            ))}
          </div>
          <Breakdowns analytics={analytics} />
        </>
      )}
    </>
  );
}
