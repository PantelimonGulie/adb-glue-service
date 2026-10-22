import type { SystemName } from '../../api/types';

export type Route = 'shopIn' | 'mktIn' | 'shopOut' | 'mktOut' | 'whOut' | 'whBack';
export type Part = SystemName | 'glue';

interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export const MAP = { width: 1000, height: 340 };

export const PATHS: Record<Route, string> = {
  shopIn: 'M240 78 C320 78 320 112 400 112',
  mktIn: 'M240 262 C320 262 320 228 400 228',
  shopOut: 'M400 132 C320 132 320 100 240 100',
  mktOut: 'M400 208 C320 208 320 240 240 240',
  whOut: 'M620 150 L760 150',
  whBack: 'M760 192 L620 192',
};

export const LABEL_AT: Partial<Record<Route, { left: number; top: number }>> = {
  shopIn: { left: 256, top: 52 },
  mktIn: { left: 246, top: 276 },
  whOut: { left: 628, top: 124 },
  whBack: { left: 632, top: 200 },
};

export const NODES: Record<Part, Box & { kicker: string; title: string }> = {
  shop: {
    left: 20,
    top: 30,
    width: 220,
    height: 96,
    kicker: 'SHOP · ADOBE COMMERCE',
    title: 'Electronic Market',
  },
  emag: {
    left: 20,
    top: 214,
    width: 220,
    height: 96,
    kicker: 'MARKETPLACE · EMAG',
    title: 'Seller account',
  },
  glue: { left: 400, top: 30, width: 220, height: 280, kicker: 'GLUE', title: '' },
  warehouse: {
    left: 760,
    top: 104,
    width: 220,
    height: 116,
    kicker: 'WAREHOUSE',
    title: 'Bucharest warehouse',
  },
};
