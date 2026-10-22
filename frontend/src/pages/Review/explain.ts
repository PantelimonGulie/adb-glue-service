import type { Channel, Decision, OrderStatus, ReviewItem, StockRow } from '../../api/types';
import { status } from '../../lib/labels';

const WHERE: Record<Channel, string> = { shop: 'the shop', emag: 'eMAG' };
const CUSTOMER: Record<Channel, string> = { shop: 'A shop customer', emag: 'An eMAG customer' };
const CANCELLING: Record<Channel, string> = {
  shop: 'Tells the shop customer and refunds them.',
  emag: "Refunds the eMAG customer and counts against the store's seller rating on eMAG.",
};
const NOT_NOW: Record<OrderStatus, string> = {
  received: 'Glue is still sending this order to the warehouse',
  allocated: 'The order already holds a reservation, so retrying would not change anything',
  shipped: 'The order has already shipped',
  cancelled: 'The order is already cancelled',
  failed: 'Retrying would not change anything',
};

export const DECISIONS: Decision[] = ['retry', 'cancel', 'dismiss'];

export function story({ cause, order, payload }: ReviewItem): string {
  if (payload.operation === 'cancel') {
    return 'The customer cancelled, but Glue could not cancel the order at the Bucharest warehouse.';
  }
  if (cause === 'outage') {
    return 'The Bucharest warehouse did not answer, so this order is not reserved yet. Retrying is safe once the warehouse works again.';
  }
  if (cause === 'recount') {
    return 'The Bucharest warehouse counted fewer units than were promised to customers, so this order may not ship.';
  }
  if (cause === 'other' || !order) {
    return 'Glue could not finish this order on its own. Check what Glue saw and the order history, then decide.';
  }
  const ordered = `${CUSTOMER[order.channel]} ordered ${order.qty} × ${order.product}`;
  return `${ordered}, but the last unit went to another customer first. The Bucharest warehouse has none left.`;
}

export function facts({ reason, order }: ReviewItem, stock?: StockRow): [string, string][] {
  const list: [string, string][] = [['What Glue saw', reason]];
  if (order) {
    list.push(['Order now', status(order.status).label], ['Tries', String(order.attempts)]);
  }
  if (stock) {
    const counts = `${stock.on_hand} on hand, ${stock.reserved} reserved, ${stock.free} free`;
    list.push(['Bucharest warehouse', counts]);
  }
  return list;
}

export function choice(action: Decision, { order }: ReviewItem): string {
  if (action === 'retry') return 'Retry';
  if (action === 'dismiss') return 'Close without changes';
  return order ? `Cancel on ${WHERE[order.channel]}` : 'Cancel the order';
}

export function consequence(action: Decision, { order, payload }: ReviewItem): string {
  if (action === 'dismiss') return 'Closes this item and leaves the order as it is.';
  if (action === 'cancel') return order ? CANCELLING[order.channel] : 'Cancels the order.';
  if (payload.operation === 'cancel') return 'Asks the Bucharest warehouse again to cancel it.';
  return 'Sends the order to the Bucharest warehouse again. It never reserves twice.';
}

// Why the API would refuse this choice, or undefined when it is allowed.
export function unavailable(action: Decision, { allowed, order }: ReviewItem): string | undefined {
  if (allowed.includes(action)) return undefined;
  return order ? NOT_NOW[order.status] : 'No order is attached to this item';
}

export function outcome(item: ReviewItem): string {
  if (item.action === 'retry') return 'Retried';
  if (item.action !== 'cancel') return 'Closed without changes';
  return item.order ? `Cancelled on ${WHERE[item.order.channel]}` : 'Cancelled';
}

export function suggested(action: string | null, item: ReviewItem): string {
  const known = DECISIONS.find((decision) => decision === action);
  return known ? choice(known, item) : 'No single choice';
}
