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
    labelAt: {
      shopIn: { left: 256, top: 52 },
      mktIn: { left: 246, top: 276 },
      whOut: { left: 628 + glue, top: 124 },
      whBack: { left: 632 + glue, top: 200 },
    },
  };
}

// The same nodes and lines stacked for phones: both channels on top, Glue, then the warehouse.
export const COMPACT: Geometry = {
  width: 320,
  height: 610,
  paths: {
    shopIn: 'M100 130 C100 165 130 165 130 200',
    shopOut: 'M145 200 C145 165 120 165 120 130',
    mktOut: 'M175 200 C175 165 200 165 200 130',
    mktIn: 'M220 130 C220 165 190 165 190 200',
    whOut: 'M140 420 L140 490',
    whBack: 'M180 490 L180 420',
  },
  nodes: {
    shop: { left: 0, top: 0, width: 150, height: 130 },
    emag: { left: 170, top: 0, width: 150, height: 130 },
    glue: { left: 40, top: 200, width: 240, height: 220 },
    warehouse: { left: 40, top: 490, width: 240, height: 110 },
  },
  labelAt: {
    shopIn: { left: 0, top: 138, width: 92 },
    mktIn: { left: 228, top: 138, width: 92 },
    whOut: { left: 40, top: 440, width: 96 },
    whBack: { left: 188, top: 446 },
  },
};

export function fit(frameWidth: number): { geometry: Geometry; scale: number } {
  if (frameWidth < BASE_WIDTH * MIN_WIDE_SCALE) {
    return { geometry: COMPACT, scale: Math.min(MAX_SCALE, frameWidth / COMPACT.width) };
  }
  const scale = Math.min(MAX_SCALE, frameWidth / BASE_WIDTH);
  return { geometry: wide(Math.floor(frameWidth / scale - BASE_WIDTH)), scale };
}
