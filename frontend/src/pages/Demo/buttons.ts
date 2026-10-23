import type { Demo, DemoAction } from '../../api/types';

export interface DemoButton {
  action: DemoAction;
  label: string;
  state?: string;
}

type Faults = Demo['faults'];

const toggle = (on: boolean, whenOn: DemoButton, whenOff: DemoButton): DemoButton =>
  on ? { ...whenOn, state: 'fault on' } : whenOff;

// Unknown faults (the mock did not answer) show as off, so the button offers to turn them on.
export function warehouseButtons(faults: Faults['warehouse']): DemoButton[] {
  const failing = faults?.fail_next ?? 0;
  return [
    toggle(
      faults?.down ?? false,
      { action: 'warehouse-up', label: 'Bring the warehouse back' },
      { action: 'warehouse-down', label: 'Stop answering' },
    ),
    toggle(
      (faults?.slow_seconds ?? 0) > 0,
      { action: 'warehouse-slow-off', label: 'Back to normal speed' },
      { action: 'warehouse-slow-on', label: 'Answer slowly (3 s)' },
    ),
    {
      action: 'warehouse-fail-2',
      label: 'Fail the next 2 orders only',
      state: failing > 0 ? `${failing} to fail` : undefined,
    },
    { action: 'ship-oldest', label: 'Ship the oldest reserved order' },
  ];
}

export function emagButtons(faults: Faults['emag']): DemoButton[] {
  return [
    toggle(
      faults?.freeze_stock ?? false,
      { action: 'emag-freeze-off', label: 'Apply stock updates again' },
      { action: 'emag-freeze-on', label: 'Ignore stock updates' },
    ),
    toggle(
      faults?.rate_limit ?? false,
      { action: 'emag-rate-limit-off', label: 'Stop asking to slow down' },
      { action: 'emag-rate-limit-on', label: 'Ask Glue to slow down' },
    ),
    toggle(
      Boolean(faults?.reject_sku),
      { action: 'emag-reject-off', label: 'Accept updates for MacBook Air M4 again' },
      { action: 'emag-reject-on', label: 'Refuse updates for MacBook Air M4' },
    ),
    { action: 'emag-renotify', label: 'Send unconfirmed orders again' },
  ];
}

export const SHOP_BUTTONS: DemoButton[] = [
  { action: 'shop-duplicate', label: 'Send the same order twice' },
  { action: 'shop-flash-sale', label: 'Flash sale: 10 orders at once' },
  { action: 'customer-cancel', label: 'A customer cancels their order' },
];

export const SECURITY_BUTTONS: DemoButton[] = [
  { action: 'fake-signature', label: 'Send a message with a fake signature' },
];

export const trafficButton = (running: boolean): DemoButton =>
  running
    ? { action: 'traffic-stop', label: 'Pause new orders' }
    : { action: 'traffic-start', label: 'Resume new orders' };
