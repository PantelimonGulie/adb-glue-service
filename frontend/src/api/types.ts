export type Channel = 'shop' | 'emag';
export type SystemName = Channel | 'warehouse';
export type OrderStatus = 'received' | 'allocated' | 'shipped' | 'failed' | 'cancelled';
export type Cause = 'outage' | 'soldout' | 'recount' | 'other';
export type Decision = 'retry' | 'cancel' | 'dismiss';
export type Role = 'viewer' | 'operator' | 'admin';
export type Permission = 'view' | 'decide' | 'ask' | 'rules' | 'settings' | 'demo';
export type RangeName = 'live' | 'today' | 'week' | 'month' | 'custom';
export type ActivityKind =
  | 'all'
  | 'orders'
  | 'retries'
  | 'problems'
  | 'duplicates'
  | 'stock'
  | 'decisions';

export interface RangeQuery {
  range: RangeName;
  from?: string;
  to?: string;
}

export interface Counters {
  received: number;
  duplicates: number;
  reserved: number;
  retries: number;
  failed: number;
}

export interface AuditRow {
  id: number;
  ts: string;
  correlation_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  detail: Record<string, unknown>;
}

export interface Order {
  order_id: string;
  channel: Channel;
  sku: string;
  product: string;
  qty: number;
  status: OrderStatus;
  attempts: number;
  last_error: string | null;
  // When Glue first saved the order; the Orders range follows it. Optional only until the test
  // fixtures carry it.
  received_at?: string;
  updated_at: string;
}

export interface ReviewItem {
  id: number;
  kind: string;
  cause: Cause;
  order_id: string | null;
  order: Order | null;
  reason: string;
  payload: Record<string, unknown>;
  created_at: string;
  status: 'open' | 'acting' | 'decided';
  action: Decision | 'resolved' | null;
  decided_by: string | null;
  decided_at: string | null;
  allowed: Decision[];
  suggestion: { action: string | null; reason: string } | null;
  // Sold-out items only: the order that got the last unit.
  winner?: { order_id: string; channel: Channel; reserved_at: string } | null;
}

export interface User {
  name: string;
  role: Role;
  permissions: Permission[];
  // The IANA zone the API cuts days in, e.g. Europe/Bucharest. Optional only until the test
  // fixtures carry it.
  timezone?: string;
}

export interface Page<T> {
  rows: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface SystemHealth {
  ok: boolean;
  state: string;
  latency_ms: number | null;
}

export interface CauseCount {
  cause: Cause;
  count: number;
}

export interface Overview {
  counters: Counters;
  previous: Counters | null;
  systems: Record<SystemName, SystemHealth>;
  open_reviews: number;
  review_groups: CauseCount[];
  latest: AuditRow[];
}

export interface EventsPage {
  rows: AuditRow[];
  last_id: number;
  more: boolean;
}

export interface OrderDetail {
  order: Order;
  timeline: AuditRow[];
}

export interface ChannelStock {
  qty: number;
  dirty: boolean;
}

export interface StockRow {
  sku: string;
  product: string;
  on_hand: number;
  reserved: number;
  free: number;
  shop: ChannelStock | null;
  emag: ChannelStock | null;
  held_back: Record<Channel, number>;
  state: 'in_sync' | 'behind' | 'refused' | 'held';
}

export interface Stock {
  rows: StockRow[];
  reconcile_seconds: number;
}

export interface Review {
  items: ReviewItem[];
  groups: CauseCount[];
}

export interface Analytics {
  range: { since: string; until: string; unit: 'minute' | 'hour' | 'day'; labels: string[] };
  totals: Counters;
  previous: Counters | null;
  funnel: {
    received: number;
    duplicates: number;
    sent: number;
    first_try: number;
    after_retry: number;
    failed: number;
  };
  series: {
    orders: Record<Channel, number[]>;
    problems: { retried: number[]; failed: number[] };
    latency: { p50: number[]; p95: number[] };
    out_of_sync: Record<Channel, number[]>;
  };
  parts: {
    shop: { orders: number; duplicates: number; refused: number };
    emag: {
      orders: number;
      renotified: number;
      slowdowns: number;
      refused_updates: number;
      sold_out: number;
    };
    glue: {
      handled: number;
      duplicates: number;
      p50_seconds: number;
      p95_seconds: number;
      lost: number;
    };
    warehouse: {
      received: number;
      first_try_pct: number;
      retries: number;
      failed: number;
      longest_outage_minutes: number;
    };
  };
  by_product: {
    sku: string;
    product: string;
    orders: number;
    reserved: number;
    failed: number;
    p50_seconds: number;
  }[];
  failure_causes: CauseCount[];
  sample: boolean;
}

export interface StockBufferConfig {
  channel: Channel;
  units: number;
  sku: string;
}

interface RuleBase {
  enabled: boolean;
  updated_by: string | null;
  updated_at: string | null;
}

export type Rule =
  | (RuleBase & { name: 'stock-buffer'; config: StockBufferConfig })
  | (RuleBase & { name: 'auto-retry'; config: Record<string, never> });

export interface Tuning {
  retry_attempts: number;
  retry_base_seconds: number;
  reconcile_interval_seconds: number;
}

export interface Settings extends Tuning {
  http_timeout_seconds: number;
  connections: ({ name: SystemName; url: string } & SystemHealth)[];
}

export type Effort = 'low' | 'medium' | 'high';

export interface AssistantLimits {
  effort: Effort;
  max_tokens_per_question: number;
  daily_token_budget: number;
}

export interface Assistant extends AssistantLimits {
  model: {
    id: string;
    label: string;
    status: 'ready' | 'downloading' | 'missing' | 'offline';
    progress: number;
  };
  models: { id: string; label: string; available: boolean }[];
  used_today: number;
  questions_today: number;
}

export interface Turn {
  role: 'user' | 'assistant';
  content: string;
}

export interface Answer {
  answer: string;
  tools: string[];
  tokens: number;
}

export interface Demo {
  traffic: { running: boolean; speed: 'slow' | 'normal' | 'fast' };
  faults: {
    emag: {
      rate_limit: boolean;
      reject_sku: string | null;
      freeze_stock: boolean;
      down: boolean;
    } | null;
    warehouse: { down: boolean; slow_seconds: number; fail_next: number } | null;
  };
  sample_history: boolean;
}

export type DemoAction =
  | 'shop-duplicate'
  | 'shop-flash-sale'
  | 'emag-freeze-on'
  | 'emag-freeze-off'
  | 'emag-rate-limit-on'
  | 'emag-rate-limit-off'
  | 'emag-reject-on'
  | 'emag-reject-off'
  | 'emag-renotify'
  | 'warehouse-down'
  | 'warehouse-up'
  | 'warehouse-slow-on'
  | 'warehouse-slow-off'
  | 'warehouse-fail-2'
  | 'reset'
  | 'traffic-start'
  | 'traffic-stop'
  | 'speed-slow'
  | 'speed-normal'
  | 'speed-fast'
  | 'ship-oldest'
  | 'customer-cancel'
  | 'fake-signature'
  | 'history-load'
  | 'history-clear';

export interface DemoResult {
  ok: boolean;
  message: string;
}
