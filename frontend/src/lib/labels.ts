import type { Cause, Channel, OrderStatus, SystemHealth } from '../api/types';

export type Tone = 'blue' | 'green' | 'amber' | 'red' | 'grey' | 'slate' | 'plum' | 'gold';

export interface Label {
  label: string;
  tone: Tone;
  explanation: string;
}

const ACTIONS: Record<string, Label> = {
  event_received: {
    label: 'Order received',
    tone: 'blue',
    explanation: 'An order arrived from the shop or eMAG and was saved before anything else happened.',
  },
  order_allocated: {
    label: 'Reserved at warehouse',
    tone: 'green',
    explanation: 'The warehouse accepted the order and set the item aside for this customer.',
  },
  retry_scheduled: {
    label: 'Retrying',
    tone: 'amber',
    explanation:
      'The warehouse did not answer. Glue waits a little and tries again, waiting longer each time.',
  },
  order_failed: {
    label: 'Failed, needs you',
    tone: 'red',
    explanation: 'Every attempt failed. The order is kept safe and a person decides what happens.',
  },
  unfulfillable: {
    label: 'Sold out, needs you',
    tone: 'red',
    explanation:
      'The last unit was already sold on the other channel. A person decides what to tell the customer.',
  },
  recount_conflict: {
    label: 'Shelf count too low',
    tone: 'red',
    explanation:
      'The warehouse counted fewer units than were promised to customers. A person decides which orders to cancel.',
  },
  duplicate_dropped: {
    label: 'Duplicate ignored',
    tone: 'grey',
    explanation: 'The same message arrived twice. Glue handled it once and ignored the copy.',
  },
  order_known: {
    label: 'Order already known',
    tone: 'grey',
    explanation: 'A channel sent an order Glue already had. Glue kept the first one and ignored this.',
  },
  cancel_repeated: {
    label: 'Cancellation repeated',
    tone: 'grey',
    explanation:
      'The order was already cancelled when the cancellation arrived again, so Glue ignored it.',
  },
  emag_acknowledged: {
    label: 'Confirmed to eMAG',
    tone: 'plum',
    explanation: 'Glue told eMAG it has the order, so eMAG stops sending it again.',
  },
  stock_pushed: {
    label: 'Stock updated',
    tone: 'slate',
    explanation: 'The real stock from the warehouse was sent to the shop and to eMAG.',
  },
  stock_push_failed: {
    label: 'Stock update failed',
    tone: 'amber',
    explanation: 'A channel refused a stock update. Glue tries again on the next stock check.',
  },
  warehouse_unreachable: {
    label: 'Warehouse not answering',
    tone: 'amber',
    explanation: 'Glue could not reach the warehouse during a stock check. It tries again on the next one.',
  },
  review_opened: {
    label: 'Sent to review',
    tone: 'red',
    explanation: 'Glue could not decide this alone and put it in the review queue for a person.',
  },
  review_decided: {
    label: 'Decision made',
    tone: 'green',
    explanation: 'A person, or a rule, decided what happens with this order.',
  },
  review_resolved: {
    label: 'Closed as no longer needed',
    tone: 'green',
    explanation: "The order's state made this review item moot, so Glue closed it.",
  },
  triage_suggested: {
    label: 'Suggestion ready',
    tone: 'blue',
    explanation: 'The triage assistant suggested what to do. It only suggests; a person decides.',
  },
  order_cancelled: {
    label: 'Cancelled',
    tone: 'slate',
    explanation: 'The order was cancelled and the reserved item went back on the shelf.',
  },
  placed_after_cancel: {
    label: 'Already cancelled',
    tone: 'grey',
    explanation: 'The order arrived after it had already been cancelled, so Glue did not reserve it.',
  },
  order_shipped: {
    label: 'Shipped',
    tone: 'slate',
    explanation: 'The warehouse shipped the order and the channel was told.',
  },
  allocation_resumed: {
    label: 'Sent again after a restart',
    tone: 'blue',
    explanation:
      'Glue stopped before the warehouse answered, so it sent the order again. The warehouse never reserves it twice.',
  },
  signature_rejected: {
    label: 'Fake message blocked',
    tone: 'red',
    explanation: 'A message arrived without a valid signature, so Glue refused it.',
  },
  event_rejected: {
    label: 'Message refused',
    tone: 'red',
    explanation: 'A message arrived that Glue could not read, so it refused it and kept a note.',
  },
  event_failed: {
    label: 'Could not handle a message',
    tone: 'red',
    explanation: 'Something unexpected went wrong while handling a message. The order went to review.',
  },
  rule_applied: {
    label: 'Rule applied',
    tone: 'blue',
    explanation: 'An automation rule acted on its own and recorded it here.',
  },
  rule_changed: {
    label: 'Rule changed',
    tone: 'slate',
    explanation: 'An admin turned a rule on or off, or changed how it works.',
  },
  settings_changed: {
    label: 'Settings changed',
    tone: 'slate',
    explanation: 'An admin changed a setting.',
  },
  signed_in: {
    label: 'Signed in',
    tone: 'slate',
    explanation: 'Someone signed in to the dashboard.',
  },
  sign_in_rejected: {
    label: 'Sign-in refused',
    tone: 'amber',
    explanation: 'Someone tried to sign in with a wrong user name or password.',
  },
};

export type Message = 'order' | 'emag-order' | 'cancellation' | 'shipment' | 'shelf-count';

// Incoming messages are all logged as event_received; these say what each one was about.
const MESSAGES: Record<Message, Label> = {
  order: ACTIONS.event_received,
  'emag-order': {
    label: 'Order received from eMAG',
    tone: 'blue',
    explanation:
      'eMAG sent only the order number. Glue fetched the full order and saved it before anything else happened.',
  },
  cancellation: {
    label: 'Cancellation received',
    tone: 'slate',
    explanation: 'A channel said the customer cancelled. Glue cancels the order at the warehouse.',
  },
  shipment: {
    label: 'Shipment reported',
    tone: 'slate',
    explanation: 'The warehouse said it shipped an order. Glue tells the channel it is on its way.',
  },
  'shelf-count': {
    label: 'Shelf count changed',
    tone: 'slate',
    explanation: 'The warehouse counted a shelf again. Glue sends the new stock to the shop and eMAG.',
  },
};

const STATUSES: Record<OrderStatus, Label> = {
  received: {
    label: 'Received',
    tone: 'blue',
    explanation: 'Glue saved the order and is sending it to the warehouse.',
  },
  allocated: {
    label: 'Reserved',
    tone: 'green',
    explanation: 'The warehouse set the item aside for this customer.',
  },
  shipped: {
    label: 'Shipped',
    tone: 'slate',
    explanation: 'The warehouse shipped it and the channel was told.',
  },
  failed: {
    label: 'Needs a decision',
    tone: 'red',
    explanation: 'Glue could not finish it alone. It waits in the review queue for a person.',
  },
  cancelled: {
    label: 'Cancelled',
    tone: 'grey',
    explanation: 'The order was cancelled. A unit it held went back on the shelf.',
  },
};

const CAUSES: Record<Cause, { label: string; hint: string; advice: string; tone: Tone }> = {
  outage: {
    label: 'Warehouse outage',
    hint: 'the warehouse did not answer; safe to retry once it works',
    advice: 'retry once the warehouse works',
    tone: 'amber',
  },
  soldout: {
    label: 'Sold out',
    hint: 'the last unit went to another customer',
    advice: 'usually cancel the later order',
    tone: 'red',
  },
  recount: {
    label: 'Shelf count too low',
    hint: 'the warehouse counted fewer units than were promised',
    advice: 'cancel the newest orders',
    tone: 'red',
  },
  other: {
    label: 'Other',
    hint: 'check the order history',
    advice: 'check the order history',
    tone: 'grey',
  },
};

const CHANNELS: Record<Channel, { label: string; tone: Tone }> = {
  shop: { label: 'Shop', tone: 'gold' },
  emag: { label: 'eMAG', tone: 'plum' },
};

export function action(name: string): Label {
  if (Object.hasOwn(ACTIONS, name)) return ACTIONS[name];
  const words = name.replaceAll('_', ' ');
  return {
    label: words.charAt(0).toUpperCase() + words.slice(1),
    tone: 'grey',
    explanation: 'Glue recorded this step.',
  };
}

export const message = (name: Message) => MESSAGES[name];
export const status = (name: OrderStatus) => STATUSES[name];
export const cause = (name: Cause) => CAUSES[name];
export const channel = (name: Channel) => CHANNELS[name];

const SYSTEM_STATES: Record<string, Label> = {
  ok: { label: 'working', tone: 'green', explanation: 'It answers quickly.' },
  slow: {
    label: 'slow',
    tone: 'amber',
    explanation: 'It answers, but slower than Glue waits for, or a call timed out.',
  },
  rate_limited: {
    label: 'limiting requests',
    tone: 'amber',
    explanation: 'It asks Glue to slow down, so Glue waits before it sends more.',
  },
  down: { label: 'not answering', tone: 'red', explanation: 'It does not answer at all.' },
};

export function system(health: SystemHealth | undefined): Label {
  if (!health) return { label: 'checking', tone: 'grey', explanation: 'Glue is checking it.' };
  if (Object.hasOwn(SYSTEM_STATES, health.state)) return SYSTEM_STATES[health.state];
  return health.ok ? SYSTEM_STATES.ok : SYSTEM_STATES.down;
}
