import { Link } from 'react-router-dom';
import { useOverview, useStock } from '../../api/hooks';
import type { Analytics } from '../../api/types';
import { rangeSearch, useRange } from '../../lib/range';
import styles from './FlowMap.module.css';
import { LABEL_AT, MAP, PATHS, type Part } from './layout';
import { LiveDots } from './LiveDots';
import { MapNodes } from './MapNodes';
import { mapView, type Mode } from './model';
import { useFitScale } from './useFitScale';

// Below this the labels are too small to read, so a narrow frame scrolls instead.
const MIN_SCALE = 0.6;

interface Props {
  mode: Mode;
  totals?: Analytics;
  selected?: Part;
  onSelect?: (part: Part) => void;
}

export function FlowMap({ mode, totals, selected, onSelect }: Props) {
  // System health and the review count do not depend on the range; the sidebar shares this.
  const { data: overview } = useOverview({ range: 'live' });
  const { data: stock } = useStock();
  const [range] = useRange();
  const [frame, scale] = useFitScale(MAP.width, MIN_SCALE);
  const view = mapView(mode, totals, overview, stock?.reconcile_seconds);
  const activity = `/activity?kind=orders&${rangeSearch(range)}`;

  return (
    <div ref={frame} className={styles.frame}>
      <div style={{ width: MAP.width * scale, height: MAP.height * scale }}>
        <div className={styles.stage} style={{ ...MAP, transform: `scale(${scale})` }}>
          <svg
            className={styles.lines}
            viewBox={`0 0 ${MAP.width} ${MAP.height}`}
            aria-hidden="true"
          >
            {view.edges.map((edge) => (
              <path
                key={edge.route}
                d={PATHS[edge.route]}
                strokeWidth={edge.width}
                data-main={edge.main}
                data-bad={edge.bad}
              />
            ))}
          </svg>
          {view.edges.map(({ route, label, hint, main, bad }) =>
            !label ? null : main ? (
              <Link
                key={route}
                to={activity}
                className={styles.label}
                style={LABEL_AT[route]}
                title={hint}
                data-bad={bad}
              >
                {label}
              </Link>
            ) : (
              <span key={route} className={styles.label} style={LABEL_AT[route]}>
                {label}
              </span>
            ),
          )}
          <MapNodes view={view} selected={selected} onSelect={onSelect} />
          {mode === 'live' && <LiveDots />}
        </div>
      </div>
    </div>
  );
}
