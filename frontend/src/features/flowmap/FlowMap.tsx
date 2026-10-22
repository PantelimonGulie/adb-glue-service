import { Link } from 'react-router-dom';
import { useOverview, useStock } from '../../api/hooks';
import type { Analytics } from '../../api/types';
import { rangeSearch, useRange } from '../../lib/range';
import styles from './FlowMap.module.css';
import { BASE_WIDTH, fit, type Part, type Spot } from './layout';
import { LiveDots } from './LiveDots';
import { MapNodes } from './MapNodes';
import { mapView, type Edge, type Mode } from './model';
import { useFrameWidth } from './useFrameWidth';

interface Props {
  mode: Mode;
  totals?: Analytics;
  selected?: Part;
  onSelect?: (part: Part) => void;
}

function EdgeLabel({ edge, at, to }: { edge: Edge; at?: Spot; to: string }) {
  if (!edge.main) {
    return (
      <span className={styles.label} style={at}>
        {edge.label}
      </span>
    );
  }
  return (
    <Link to={to} className={styles.label} style={at} title={edge.hint} data-bad={edge.bad}>
      {edge.label}
    </Link>
  );
}

export function FlowMap({ mode, totals, selected, onSelect }: Props) {
  // System health and the review count do not depend on the range; the sidebar shares this.
  const { data: overview } = useOverview({ range: 'live' });
  const { data: stock } = useStock();
  const [range] = useRange();
  const [frame, frameWidth] = useFrameWidth(BASE_WIDTH);
  const { geometry, scale } = fit(frameWidth);
  const { width, height, paths } = geometry;
  const view = mapView(mode, totals, overview, stock?.reconcile_seconds);
  const activity = `/activity?kind=orders&${rangeSearch(range)}`;

  return (
    <div ref={frame} className={styles.frame}>
      <div className={styles.sizer} style={{ width: width * scale, height: height * scale }}>
        <div className={styles.stage} style={{ width, height, transform: `scale(${scale})` }}>
          <svg className={styles.lines} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
            {view.edges.map((edge) => (
              <path
                key={edge.route}
                d={paths[edge.route]}
                strokeWidth={edge.width}
                data-main={edge.main}
                data-bad={edge.bad}
              />
            ))}
          </svg>
          {view.edges
            .filter((edge) => edge.label)
            .map((edge) => (
              <EdgeLabel
                key={edge.route}
                edge={edge}
                at={geometry.labelAt[edge.route]}
                to={activity}
              />
            ))}
          <MapNodes view={view} boxes={geometry.nodes} selected={selected} onSelect={onSelect} />
          {mode === 'live' && <LiveDots paths={paths} />}
        </div>
      </div>
    </div>
  );
}
