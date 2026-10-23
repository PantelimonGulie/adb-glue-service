import type { Series } from './BarChart';

interface Bars {
  ids: string[];
  labels: string[];
  series: Series[];
}

// Buckets that have not started yet (the rest of today or of this month) are left off, so the
// bars use the width for the time that has passed. Ids that are not times are all kept.
export function started({ ids, labels, series }: Bars, now = Date.now()): Bars {
  const count = ids.filter((id) => !(Date.parse(id) > now)).length;
  return {
    ids: ids.slice(0, count),
    labels: labels.slice(0, count),
    series: series.map((one) => ({ ...one, values: one.values.slice(0, count) })),
  };
}
