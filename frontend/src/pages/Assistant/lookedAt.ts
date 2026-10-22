import { formatNumber } from '../../lib/format';

const SOURCES: Record<string, string> = {
  get_summary: 'recent orders',
  list_review_items: 'review queue',
  get_order: 'order history',
  get_stock: 'stock',
};

export function lookedAt(tools: string[], tokens: number): string {
  const sources = new Set(tools.map((tool) => SOURCES[tool] ?? tool.replaceAll('_', ' ')));
  const used = `${formatNumber(tokens)} tokens`;
  if (sources.size === 0) return `Answered without looking anything up · ${used}`;
  return `Looked at: ${[...sources].join(', ')} · ${used}`;
}
