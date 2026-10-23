import type { SystemName } from '../../api/types';

export type Route = 'shopIn' | 'mktIn' | 'shopOut' | 'mktOut' | 'whOut' | 'whBack';
export type Part = SystemName | 'glue';

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Spot {
  left: number;
  top: number;
  width?: number;
}

export interface Geometry {
  width: number;
  height: number;
  paths: Record<Route, string>;
  nodes: Record<Part, Box>;
  labelAt: Partial<Record<Route, Spot>>;
}

export const NODE_TEXT: Record<Part, { kicker: string; title: string }> = {
  shop: { kicker: 'SHOP · ADOBE COMMERCE', title: 'Electronic Market' },
  emag: { kicker: 'MARKETPLACE · EMAG', title: 'Seller account' },
  glue: { kicker: 'GLUE', title: '' },
  warehouse: { kicker: 'WAREHOUSE', title: 'Bucharest warehouse' },
};

export const BASE_WIDTH = 1000;
// Past this the type would outgrow the page's; the spare width goes between the columns.
const MAX_SCALE = 1.25;
// Below this the wide drawing is too small to read, so the stacked one takes over.
const MIN_WIDE_SCALE = 0.7;

// The mockup drawing. `extra` widens the two gaps between the three columns.
function wide(extra = 0): Geometry {
  const glue = extra / 2;
  const curve = extra / 4;
  return {
    width: BASE_WIDTH + extra,
    height: 340,
    paths: {
      shopIn: `M240 78 C${320 + curve} 78 ${320 + curve} 112 ${400 + glue} 112`,
      mktIn: `M240 262 C${320 + curve} 262 ${320 + curve} 228 ${400 + glue} 228`,
      shopOut: `M${400 + glue} 132 C${320 + curve} 132 ${320 + curve} 100 240 100`,
      mktOut: `M${400 + glue} 208 C${320 + curve} 208 ${320 + curve} 240 240 240`,
      whOut: `M${620 + glue} 150 L${760 + extra} 150`,
      whBack: `M${760 + extra} 192 L${620 + glue} 192`,
    },
    nodes: {
      shop: { left: 20, top: 30, width: 220, height: 96 },
      emag: { left: 20, top: 214, width: 220, height: 96 },
      glue: { left: 400 + glue, top: 30, width: 220, height: 280 },
      warehouse: { left: 760 + extra, top: 104, width: 220, height: 116 },
    },
    // Labels above a line end above it: each has a second line for its number. The eMAG one
    // starts as far left as its box allows, so the protocol fits the gap before Glue.
    labelAt: {
      shopIn: { left: 256, top: 40 },
      mktIn: { left: 242, top: 276 },
      whOut: { left: 628 + glue, top: 112 },
      whBack: { left: 632 + glue, top: 200 },
    },
  };
}

const COMPACT_WIDTH = 320;

// The same nodes and lines stacked for phones: both channels on top, Glue, then the warehouse.
// `extra` widens the boxes, so a tablet fills its width instead of drawing a phone-sized map.
function compact(extra = 0): Geometry {
  const half = extra / 2;
  const x = (value: number) => value + half;
  return {
    width: COMPACT_WIDTH + extra,
    height: 610,
    paths: {
      shopIn: `M${x(100)} 130 C${x(100)} 165 ${x(130)} 165 ${x(130)} 200`,
      shopOut: `M${x(145)} 200 C${x(145)} 165 ${x(120)} 165 ${x(120)} 130`,
      mktOut: `M${x(175)} 200 C${x(175)} 165 ${x(200)} 165 ${x(200)} 130`,
      mktIn: `M${x(220)} 130 C${x(220)} 165 ${x(190)} 165 ${x(190)} 200`,
      whOut: `M${x(140)} 420 L${x(140)} 490`,
      whBack: `M${x(180)} 490 L${x(180)} 420`,
    },
    nodes: {
      shop: { left: 0, top: 0, width: 150 + half, height: 130 },
      emag: { left: x(170), top: 0, width: 150 + half, height: 130 },
      glue: { left: 40, top: 200, width: 240 + extra, height: 220 },
      warehouse: { left: 40, top: 490, width: 240 + extra, height: 110 },
    },
    labelAt: {
      shopIn: { left: 0, top: 138, width: 92 + half },
      mktIn: { left: x(228), top: 138, width: 92 + half },
      whOut: { left: 40, top: 440, width: 96 + half },
      whBack: { left: x(188), top: 446 },
    },
  };
}

export function fit(frameWidth: number): { geometry: Geometry; scale: number } {
  if (frameWidth < BASE_WIDTH * MIN_WIDE_SCALE) {
    const scale = Math.min(MAX_SCALE, frameWidth / COMPACT_WIDTH);
    return {
      geometry: compact(Math.max(0, Math.floor(frameWidth / scale - COMPACT_WIDTH))),
      scale,
    };
  }
  const scale = Math.min(MAX_SCALE, frameWidth / BASE_WIDTH);
  return { geometry: wide(Math.floor(frameWidth / scale - BASE_WIDTH)), scale };
}
