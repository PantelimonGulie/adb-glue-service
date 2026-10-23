import type { Channel, Decision, Order, OrderStatus, ReviewItem, StockRow } from '../../api/types';
import { formatTime } from '../../lib/format';
import { status } from '../../lib/labels';
import { plainProblem } from '../../lib/problem';

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

const NO_ORDER =
  'Glue could not save this order, so there is nothing to retry or cancel. Read what Glue saw, then close the item.';

function soldOut(item: ReviewItem, order: Order): string {
  const ordered = `${CUSTOMER[order.channel]} ordered ${order.qty} × ${order.product}`;
  const went = `${ordered}, but the last unit went to ${item.winner?.order_id ?? 'another customer'} first.`;
  return item.status === 'decided' ? went : `${went} The Bucharest warehouse has none left.`;
}

export function story(item: ReviewItem): string {
  const { cause, order, payload } = item;
  const decided = item.status === 'decided';
  if (payload.operation === 'cancel') {
    return 'The customer cancelled, but Glue could not cancel the order at the Bucharest warehouse.';
  }
  if (payload.operation === 'ship') {
    const channel = order ? WHERE[order.channel] : 'its sales channel';
    const sees = decided ? 'did not see it as shipped then' : 'does not see it as shipped yet';
    return `The Bucharest warehouse shipped this order, but Glue could not tell ${channel}, so the customer ${sees}.`;
  }
  if (!order) return decided ? 'Glue could not save this order.' : NO_ORDER;
  if (cause === 'outage') {
    return decided
      ? 'The Bucharest warehouse did not answer, so this order was not reserved then.'
      : 'The Bucharest warehouse did not answer, so this order is not reserved yet. Retrying is safe once the warehouse works again.';
  }
  if (cause === 'recount') {
    const ship = decided ? 'might not have shipped' : 'may not ship';
    return `The Bucharest warehouse counted fewer units than were promised to customers, so this order ${ship}.`;
  }
  if (cause === 'other') {
    return decided
      ? 'Glue could not finish this order on its own.'
      : 'Glue could not finish this order on its own. Check what Glue saw and the order history, then decide.';
  }
  return soldOut(item, order);
}

export function facts(item: ReviewItem, stock?: StockRow): [string, string][] {
  const { order, winner } = item;
  const list: [string, string][] = [['What Glue saw', plainProblem(item.reason)]];
  if (winner) {
    list.push(['Got the unit', `${winner.order_id}, reserved ${formatTime(winner.reserved_at)}`]);
  }
  if (order) {
    list.push(['Order now', status(order.status).label]);
    // The choice on a sold-out or short shelf is about units, not about how often Glue tried.
    if (item.cause === 'outage' || item.cause === 'other') {
      list.push(['Tries', String(order.attempts)]);
    }
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
  if (payload.operation === 'ship') {
    return `Tells ${order ? WHERE[order.channel] : 'its sales channel'} again that the order shipped.`;
  }
  return 'Sends the order to the Bucharest warehouse again. It never reserves twice.';
}

// Why the API would refuse this choice, or undefined when it is allowed.
export function unavailable(action: Decision, item: ReviewItem): string | undefined {
  if (item.allowed.includes(action)) return undefined;
  if (item.status === 'acting') return 'Glue is carrying out a decision on this item';
  return item.order ? NOT_NOW[item.order.status] : 'No order is attached to this item';
}

export function outcome(item: ReviewItem): string {
  if (item.action === 'retry') return 'Retried';
  if (item.action === 'resolved') return 'Closed as no longer needed';
  if (item.action !== 'cancel') return 'Closed without changes';
  return item.order ? `Cancelled on ${WHERE[item.order.channel]}` : 'Cancelled';
}

export function suggested(action: string | null, item: ReviewItem): string {
  const known = DECISIONS.find((decision) => decision === action);
  return known ? choice(known, item) : 'No single choice';
}
