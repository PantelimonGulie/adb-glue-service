import { useState } from 'react';
import {
  Bar,
  BarChart as Chart,
  Rectangle,
  Tooltip,
  XAxis,
  YAxis,
  type BarShapeProps,
  type TooltipContentProps,
} from 'recharts';
import { formatNumber } from '../../lib/format';
import { useFrameWidth } from '../../lib/useFrameWidth';
import { BarDetail, BarTip } from './BarDetail';
import styles from './BarChart.module.css';

export interface Series {
  key: string;
  name: string;
  color: string;
  values: number[];
}

interface Props {
  title: string;
  note: string;
  labels: string[];
  series: Series[];
  grouped?: boolean;
  format?: (value: number) => string;
  eventsLink: (index: number) => string;
}

const HEIGHT = 120;
const MARGIN = { top: 4, right: 0, bottom: 0, left: 0 };
// A transparent background makes the whole column clickable, not only the coloured part.
const COLUMN = { fill: 'transparent' };
const CURSOR = { fill: 'var(--hover)' };

export function BarChart({
  title,
  note,
  labels,
  series,
  grouped,
  format = formatNumber,
  eventsLink,
}: Props) {
  const [frame, width] = useFrameWidth(480);
  const [hidden, setHidden] = useState<string[]>([]);
  // Kept by label: in the live range the same minute moves left as new minutes arrive.
  const [picked, setPicked] = useState<string | null>(null);
  const pickedIndex = picked === null ? -1 : labels.indexOf(picked);
  const rows = labels.map((label, i) => ({
    label,
    ...Object.fromEntries(series.map((one) => [one.key, one.values[i]])),
  }));

  const toggle = (key: string) =>
    setHidden((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));
  const pick = (index: number) =>
    setPicked((current) => (current === labels[index] ? null : labels[index]));
  const barClass = (index: number) => {
    if (pickedIndex < 0) return undefined;
    return index === pickedIndex ? styles.picked : styles.dim;
  };
  const drawBar = (props: BarShapeProps) => (
    <Rectangle {...props} className={barClass(props.index)} />
  );
  const tip = ({ active, label }: TooltipContentProps) =>
    active && (
      <BarTip
        label={String(label)}
        index={labels.indexOf(String(label))}
        series={series}
        format={format}
      />
    );

  return (
    <section className={styles.chart} aria-label={`${title}, ${note}`}>
      <div className={styles.heading}>
        <b>{title}</b>
        <span className={styles.note}>{note}</span>
        <div className={styles.legend} role="group" aria-label="Show or hide">
          {series.map((one) => (
            <button
              key={one.key}
              type="button"
              aria-pressed={!hidden.includes(one.key)}
              title={`Show or hide ${one.name}`}
              onClick={() => toggle(one.key)}
            >
              <i className={styles.swatch} style={{ background: one.color }} />
              {one.name}
            </button>
          ))}
        </div>
      </div>
      <div ref={frame} className={styles.plot}>
        <Chart width={width} height={HEIGHT} data={rows} margin={MARGIN} barGap={2}>
          <XAxis dataKey="label" hide />
          <YAxis hide />
          <Tooltip cursor={CURSOR} isAnimationActive={false} content={tip} />
          {series
            .filter((one) => !hidden.includes(one.key))
            .map((one) => (
              <Bar
                key={one.key}
                dataKey={one.key}
                fill={one.color}
                stackId={grouped ? undefined : 'stack'}
                background={COLUMN}
                shape={drawBar}
                isAnimationActive={false}
                onClick={(_, index) => pick(index)}
              />
            ))}
        </Chart>
      </div>
      <div className={styles.axis}>
        <span>{labels[0]}</span>
        <span>{labels.at(-1)}</span>
      </div>
      {pickedIndex >= 0 && (
        <BarDetail
          label={labels[pickedIndex]}
          index={pickedIndex}
          link={eventsLink(pickedIndex)}
          series={series}
          format={format}
          onClose={() => setPicked(null)}
        />
      )}
    </section>
  );
}
