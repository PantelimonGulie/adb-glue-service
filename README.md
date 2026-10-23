# ADB Glue Service

A sync service for an electronics reseller that sells on its own shop (Electronic Market, shaped like Adobe Commerce) and on the eMAG Marketplace, from one Bucharest warehouse.
It routes orders from both channels to the warehouse and pushes the warehouse's true stock back to both channels. It handles duplicates, retries, partial failures and cross-channel oversell.
What it will not decide alone goes to a review queue in an operator dashboard, with the reason.

## Quickstart

Requires Docker Desktop.

```sh
docker compose up --build
```

This builds one image (the React dashboard is built in a first stage), starts the three mocks, waits until they are healthy, then starts Glue. A local model server (Ollama) starts next to them.

| URL | What it is |
|---|---|
| http://localhost:8000 | Glue dashboard, the thing this repo is about |
| http://localhost:8001 | Electronic Market, the reseller's own shop (mock, Adobe Commerce shape) |
| http://localhost:8002 | eMAG Marketplace seller center (mock, Marketplace API v4 shape) |
| http://localhost:8003 | Bucharest warehouse terminal (mock) |

Sign in at :8000 with one of the demo users. The passwords are the defaults in `docker-compose.yml`; set `VIEWER_PASSWORD`, `OPERATOR_PASSWORD`, `ADMIN_PASSWORD` and `SESSION_SECRET` in `.env` (copy `.env.example`) to change them.

| User | Password | Can |
|---|---|---|
| `viewer` | `viewer` | Read every page |
| `operator` | `operator` | Also decide review items, push stock now, ask the assistant, ask for a triage suggestion |
| `admin` | `admin` | Also change rules and settings, and use the demo controls |

The walkthrough below needs the demo controls, so sign in as `admin`.

**First run.** The assistant's local model (`qwen2.5:3b`) downloads once, about 2 GB, into the `ollama-models` volume. The Assistant page shows the progress. Everything else works immediately; until the model is ready, the assistant and triage buttons say why they wait.

Stop with `docker compose down`. Glue's SQLite database lives in the `glue-data` volume and survives restarts; its schema upgrades in place (see [Operability](#operability)). The mocks keep their state in memory and restart with seed stock. They number orders from the clock, so a restarted mock never reuses an order number Glue has already seen.

## Read this first

The sync core is six files. Read them in this order:

1. [`glue/inbox.py`](glue/inbox.py): verifies the signature, validates the payload, saves the event, answers 202. No other work happens in the request.
2. [`glue/worker.py`](glue/worker.py): claims pending events, takes a per-order lock, runs the handler, turns any unexpected error into a failed event and a review item.
3. [`glue/router.py`](glue/router.py): the only code that changes an order's status. Places, imports from eMAG, cancels, ships.
4. [`glue/retry.py`](glue/retry.py): the one retry policy every outbound call goes through.
5. [`glue/reconciler.py`](glue/reconciler.py): reads the warehouse's stock and pushes it to both channels; a refused push leaves a dirty flag that the next run clears.
6. [`glue/review.py`](glue/review.py) and [`glue/settle.py`](glue/settle.py): a person's decision on a failed order, carried out crash-safe, and the items Glue closes itself when they become moot.

Then [`tests/conftest.py`](tests/conftest.py): all four apps in one process, which is how every test and the load probe run.

Underneath: [`glue/db.py`](glue/db.py) (all SQL and the migrations), [`glue/context.py`](glue/context.py) (shared state and locks), [`glue/audit.py`](glue/audit.py) (audit rows and JSON logs).

Everything else is the operator console (JSON API, React dashboard, analytics, AI helpers) and the demo layer (mocks, demo traffic, sample history, fault switches).

## Customer context and value

A Romanian electronics reseller sells Apple products on its own shop and on eMAG, from one warehouse in Bucharest. Today staff copy orders into the warehouse system by hand and type stock back into both channels a few times a day. In between, both channels show stale stock. The last unit sells twice, eMAG orders get missed or entered twice, and every oversell on eMAG counts against the seller's cancellation rate, which eMAG penalises.

Glue takes orders as they happen, reserves them at the warehouse, keeps both channels on the warehouse's figure, and puts the decisions that cost money (cancel a paid order or not) in front of a person.

The full note, with the cost of the problem, what the customer must provide, the rollout, the first 30 days' success measures and the risks, is in [docs/customer-context.md](docs/customer-context.md).

## Demo walkthrough

About ten minutes. Keep the dashboard open in one tab and the mock you are using in another. Everything under **Demo controls** needs `admin`. **Turn every fault off** on the Simulation card resets all faults.

Compose starts demo traffic (`DEMO_TRAFFIC: slow`): a random order on the shop or eMAG every 5 seconds, a shipment every sixth tick, and a restock when a product runs low.

1. **Watch it run.** **Overview** on **Live · 15 min** shows the flow map: each dot is one real event from the audit log, moving from a channel through Glue to the Bucharest warehouse. The map's nodes and the sidebar show each system's health; the counters, **Waiting for you** and **Latest activity** sit around it. Click any order on **Orders** for its timeline: the inbound event, retries, the reservation, the stock pushes it caused and any decision. Ctrl+K (Cmd+K on a Mac) opens a command palette that finds orders and pages.
2. **Pause for the scripted steps.** On **Demo controls**, Simulation card, click **Pause new orders** so each step below is easy to follow.
3. **A shop order.** On the shop (:8001) buy an iPhone 16 128GB. On the dashboard, **Orders** shows it **Reserved**, and **Stock** shows the same lower figure for the warehouse, the shop and eMAG.
4. **An eMAG order.** On the marketplace (:8002), buy AirPods Pro 3 in the Offers table. The order row starts at "1 · New" and moves to "2 · In progress" once Glue has read the order, reserved it and acknowledged it. The marketplace's API activity log shows the callback to Glue, `order/read` and `order/acknowledge`.
5. **Duplicates.** Shop card, **Send the same order twice**: the shop re-sends its last event with the same event id. **Activity log** shows "Duplicate ignored" and no second order appears.
6. **Warehouse outage.** Warehouse card, **Stop answering**, then buy anything on the shop. **Activity log** shows "Retrying" lines that wait the 2 seconds the warehouse asks for in `Retry-After`, then "Failed, needs you". The warehouse terminal (:8003) shows the outage banner and the refused order in its outbox. **Review queue** groups the order under "Warehouse outage". Click **Bring the warehouse back**, then **Retry all** on that group: the order is reserved. (With the auto-retry rule on, under **Rules**, Glue retries by itself when the warehouse answers again.)
7. **Oversell.** On **Stock**, note how many MacBook Air M4 are reserved, then use the **Warehouse recount** card to set the shelf to that number plus one, so exactly one unit is free. eMAG card, **Ignore stock updates**: eMAG now keeps showing its old figure. Buy the MacBook Air M4 on the shop. eMAG still shows 1, so buy it there too. The warehouse refuses the second order; it lands in **Review queue** under "Sold on the other channel". Click **Cancel on eMAG**: the marketplace shows the order as "0 · Cancelled by seller". Click **Apply stock updates again**.
8. **eMAG rate limit and a missed ship notice.** eMAG card, **Ask Glue to slow down**: eMAG answers every API call with 429 and `Retry-After: 1`. On the warehouse terminal, click **Ship** on the eMAG order from step 4. Glue marks it shipped, cannot tell eMAG, and opens a review item that says so. **Stock** marks eMAG's figures as refused for the same reason. Click **Stop asking to slow down**, then **Retry** on the item: the marketplace shows "4 · Finalized", and the next reconcile run (every 10 seconds) clears the stock flags.
9. **Partial batch rejection.** eMAG card, **Refuse updates for MacBook Air M4**. On the next reconcile run the batch applies every other product and only MacBook Air M4 is flagged on **Stock**; the marketplace's Offers table shows "rejected: validation error" for it. **Accept all updates again** clears it on the next run.
10. **Recount below reserved.** With at least one iPhone 16 128GB reserved, use **Warehouse recount** (or the warehouse terminal) to set it to 0. Both channels drop to 0 and every reserved order for it appears under "Shelf count too low". Retry is not offered: those orders still hold their reservation, so a person decides which to cancel.
11. **A forged message.** Security card, **Send a message with a fake signature**: Glue answers 401, and **Activity log** shows "Fake message blocked".
12. **History and analytics.** History card, **Load sample history** (30 days of generated orders, the same every time). Open **Flow** on **This month**: the funnel from received to reserved, p50 and p95 time to reserve, retries and failures per bucket, a panel per system (including "Orders lost"), a breakdown by product and **Export CSV**. A banner says sample data is included until **Clear sample history** removes it; real orders stay.
13. **Assistant and triage.** Once the model is ready, ask the **Assistant** "Which orders need a decision?". The answer cites order ids from the database and lists which read-only lookups it used. On a review card, the triage button asks the model for a suggestion; it is shown on the card and never acts.

Click **Resume new orders** when done.

## Architecture

Four services from one image: three mocks and Glue. Glue is one FastAPI process with one SQLite file. It serves the webhooks, a JSON API under `/api`, and the built React dashboard.

- **Inbox.** Webhooks from the shop and the warehouse, and notifications from eMAG, are verified, validated, saved and answered 202. Nothing is processed in the request, so nothing is lost if processing fails.
- **Worker.** Claims pending events, at most 10 at a time, one task each. Events for the same order run one at a time.
- **Router.** The only writer of order status.
- **Reconciler.** Pulls the warehouse's stock and pushes the sellable figure to both channels: at startup, every 10 seconds, after every reservation or cancellation, and on every stock event.
- **Review queue.** The orders Glue would not decide alone, with retry, cancel and dismiss.
- **Audit log.** One row per thing that happened, with a correlation id, mirrored as one JSON log line.

What runs in production and what exists for the walkthrough:

| Layer | Where | In production |
|---|---|---|
| Sync core | `glue/inbox.py`, `worker.py`, `router.py`, `retry.py`, `reconciler.py`, `review.py`, `settle.py`, `rules.py`, `db.py`, `schema.sql`, `context.py`, `audit.py`, `clients.py`, `settings.py`, `tuning.py`, `main.py` | Yes |
| Operator console | `glue/api/`, `queries.py`, `analytics*.py`, `ranges.py`, `auth.py`, `guard.py`, `spa.py`, `frontend/` | Yes |
| AI helpers | `glue/ai/` (read-only assistant, triage suggestions), Ollama | Optional |
| Demo layer | `glue/demo/` (traffic, sample history), `glue/api/demo.py`, the `/chaos` switches, `shop/`, `emag/`, `warehouse/` | No: real systems replace the mocks, and demo traffic is off unless `DEMO_TRAFFIC` is set |

The diagrams (components, both order flows, stock with a partial batch failure, the live map's cursor, the oversell, the review and order state machines) and the detail on analytics, concurrency, idempotency and migrations are in [docs/architecture.md](docs/architecture.md).

## Technologies

**Chosen:**

- **Python 3.12, FastAPI, pydantic.** One language for Glue, the mocks and the tests; typed endpoints and strict validation of every inbound payload.
- **httpx (async).** Explicit timeouts, and `ASGITransport` lets the tests and the load probe run every service in one process.
- **SQLite (stdlib `sqlite3`, WAL).** A durable inbox, orders, stock, review queue and audit log with no extra service. Migrations are an ordered list counted by `PRAGMA user_version`.
- **React 18, TypeScript, Vite** for the dashboard. It is an operator console with live views (the flow map, auto-refreshing tables, a command palette), which is easier to build and test as a single-page app. **TanStack Query** for server state and polling, **React Router**, **Recharts** for the Flow charts (loaded only with that page), **cmdk** for the palette, **lucide-react** icons, **CSS Modules** with design tokens in one file, IBM Plex fonts from `@fontsource` bundled into the build.
- **Jinja2** for the three mock systems: server-rendered pages with plain HTML forms and no JavaScript, fonts vendored in `common/static/fonts/` with their licences.
- **Ollama with `qwen2.5:3b`**, called through the **openai** SDK (Ollama's OpenAI-compatible endpoint). Free, local, no key, nothing leaves the machine.
- **Docker Compose** with a multi-stage `Dockerfile` (Node builds the dashboard, the Python image serves it). The same first run on any machine.
- **pytest, pytest-asyncio, ruff** for the backend; **Vitest, Testing Library, ESLint, tsc** for the dashboard.

**Not used, and why:**

- **A message broker (Kafka, RabbitMQ, SQS).** The inbox table already works as a durable queue (claim, process, mark done or failed) for one reseller's volume. Handlers are idempotent, so a broker can replace the table without touching them.
- **Postgres.** One file and no service is enough for one instance. All SQL is in `glue/db.py`, so the move is contained.
- **An ORM or Alembic.** About fifty queries in one file, and two migration steps. The ordered list is the whole mechanism.
- **Celery or a task framework.** Four asyncio loops in one process.
- **WebSockets or server-sent events.** The dashboard polls every 2 seconds; the live map asks only for rows after a cursor. Fine for a handful of operators.
- **A component library, Tailwind or Redux.** CSS Modules and tokens keep the bundle small and the styles local; TanStack Query already holds the server state.
- **An agent framework.** The assistant is one tool loop of about forty lines over four read-only functions.
- **A hosted model by default.** A reviewer should not need a key. The usage limits exist for when it points at a paid model.

## Assumptions

1. **Adobe Commerce events** are delivered at least once, not necessarily in order, and may be duplicated, as Adobe's event documentation states. Each carries an event id (`x-adobe-event-id` here). A redelivery may come under a new id, so Glue also deduplicates by order id.
2. **eMAG notifications** carry only the order id and type; the full order is read with `order/read`. eMAG re-sends a new-order notification until the seller calls `order/acknowledge`. Statuses are numeric (0 cancelled, 1 new, 2 in progress, 3 prepared, 4 finalized). Stock goes in batches through `product_offer/save`, and a batch can fail for one item while the rest apply. The mock follows public copies of the Marketplace API v4 documentation, which may be out of date; real rate limits are unverified, so Glue honours `Retry-After` on 429.
3. **The warehouse owns stock.** Its figure (`on_hand − reserved`) is the truth; the channels show only what Glue last told them. Its order endpoint is atomic and accepts an `Idempotency-Key`.
4. **First to reach the warehouse wins.** Neither channel is preferred. Holding units back from one channel is a rule (off by default), not part of the conflict logic.
5. **Payments are out of scope.** The customer has paid when an order reaches Glue; cancelling means the channel refunds them. Glue never sees payment data.
6. **One warehouse, one currency, and one order line per mock checkout.** The models and the warehouse accept several lines.
7. **Signing.** Each source signs with a shared-secret HMAC. Adobe I/O Events uses its own public-key scheme, and whether real eMAG callbacks can be signed is unverified. Because Glue pulls every eMAG order through the authenticated API, a forged eMAG notification could at most trigger a read.
8. **SKUs are the same everywhere.** The shop's SKU, eMAG's `part_number` and the warehouse's code are one value. A real rollout needs a mapping table.

## Trade-offs

- **SQLite and one process instead of a queue and a worker pool.** The inbox survives restarts and is all one reseller needs. The cost is one writer and no horizontal scaling; the path is under [Scalability](#scalability).
- **Pull stock from the warehouse instead of trusting events alone.** Every run pushes every SKU it covers, even when nothing seems to have changed. That costs calls but heals any drift: a missed event, a restarted channel, a refused update. Events make it fast; the periodic pull makes it correct.
- **First come, first served across channels.** Simple, explainable and fair. It does not protect eMAG's seller rating; the stock buffer rule does, at the cost of selling less, so it is a switch for the business, not the default.
- **A person decides oversells.** Cancelling a paid order is a business decision: stock may arrive tomorrow, the customer may take a different model. Glue does the safe part (reserve nothing it cannot fill, cap both channels at 0) and queues the rest with the reason.
- **Per-order serialisation instead of a global lock.** Events and decisions for one order run one at a time; different orders run in parallel. At scale this becomes workers partitioned by order id.
- **Decisions run inside the HTTP request.** Simple, and the operator sees the outcome at once. The cost is that a retry against a slow warehouse holds the request; the `acting` state makes a cut-off decision safe, but not fast.
- **Triage: the policy is in code, the model explains it.** The 3B local model follows a rule that names one choice but not a conditional one, so `glue/ai/triage_prompt.py` decides the recommendation and the model writes the reason. It is testable, and the model cannot steer the outcome.
- **Polling instead of push to the browser.** Two-second polling with a cursor is simple and survives proxies; push would matter only with many operators.
- **Mocks instead of real sandboxes.** The mocks copy the behaviour that matters for the logic (at-least-once delivery, acknowledge, per-item batch results, numeric statuses) and add fault switches, so every failure can be shown on demand. Real API quirks stay untested.

## Known limitations

- **One instance only.** The per-order locks, the reconcile lock and the "warehouse is down" flag live in process memory. A second process on the same file would not share them.
- **Decisions run inside the request.** **Retry all** with a slow warehouse can take longer than a browser waits. Moving decisions onto the worker is the fix.
- **In-memory state.** `warehouse_down` and `last_reconcile_ok_at` reset on restart, so an outage that ended while Glue was stopped is not seen as a recovery and auto-retry does not fire for it; **Retry all** covers it.
- **Shutdown does not wait for in-flight event handlers.** The loops are cancelled and awaited, but an event a handler was working on stays `processing` and goes back to `pending` on the next start. Handlers are idempotent, so it is handled once.
- **The mocks keep state in memory.** A rebuilt warehouse mock forgets its reservations while Glue keeps its orders, so after `docker compose up --build` Glue can show reserved orders the warehouse no longer holds. A real warehouse system is durable; in a long demo this shows as recount items.
- **The shop mock sends each event once,** and Glue does not poll the shop. An event sent while Glue is down is lost in the demo. Real Adobe Commerce retries delivery.
- **No retention.** `events_inbox` and `audit_log` grow forever. See [Operability](#operability).
- **Analytics read the audit log on every request.** Fine for months of one reseller; at scale it needs pre-aggregated buckets, and an index on `review_queue.order_id` for the lost-orders count. "Longest outage" is an estimate from retry rows, because nothing is logged when the warehouse comes back.
- **Demo sign-in.** Three fixed users with passwords from the environment, no password hashing, no sign-in rate limit, no `Secure` cookie flag (it runs on plain HTTP locally). Real sign-in belongs to the customer's identity provider; the roles and per-route checks would stay.
- **Demo secrets are in `docker-compose.yml`.** In production they come from a secret store, and webhook secrets need rotation with an overlap window, which is not built.
- **No real connectors.** API shapes follow the public documentation but are not tested against sandboxes.
- **Left out on purpose:** courier and AWB, returns and refunds, payments, invoices, several warehouses, catalogue sync. None changes the conflict and retry design.
- **Small leftovers.** Uvicorn's own access lines are plain text next to the JSON audit lines. `glue/context.py` imports the demo `Traffic` dataclass, so the core depends on one demo type. `router.allocate` still checks for a cancel that landed while the warehouse call was in flight; the per-order lock now prevents that in-process, so the branch is a guard that does not fire.

## Testing

```sh
# Backend, in the same image Compose runs: lint, format check, 167 tests in about 5 seconds
docker compose run --rm --build glue sh -c "ruff check . && ruff format --check . && pytest -q"

# Dashboard, with Node 24 as in the Dockerfile: lint, typecheck, 169 tests in 41 files
cd frontend && npm ci && npm run lint && npm run typecheck && npm test
```

`--build` puts the current code in the image; drop it if the image is up to date. Without Docker, with Python 3.12 or newer: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -q`.

**How the backend tests run.** [`tests/conftest.py`](tests/conftest.py) starts all four apps in one process and connects them with one `httpx.AsyncClient` whose mounts route `http://shop`, `http://emag`, `http://warehouse` and `http://glue` to the apps directly: no network, no ports. Each test gets a fresh SQLite file, zero back-off, a stub Ollama and a session signed in as `operator`. The background loops do not start; tests drive the worker and the reconciler step by step, so each test reads like a demo step and asserts end state (one reservation, eMAG status 4, which items are open), not call counts.

**What they prove**, one failure mode each:

- **Duplicates.** A repeated shop event, a redelivery under a new event id, and eMAG re-notifications each make one order and one reservation; an event id from one sender cannot hide another sender's event.
- **Retries.** Warehouse 503, 503, 201 reserves on the third try; `Retry-After` is honoured as seconds or an HTTP date, capped at 30 seconds, and ignored when unreadable; 4xx answers are not retried.
- **Partial failures.** A ship notice the channel missed is retried from review; an acknowledge that fails after the reservation heals on eMAG's next notification; a failed event sent again goes back to the queue; items whose order reached a good state by another path close themselves.
- **Concurrency.** Two cancels for one order in one batch cancel it once; an operator cancel racing a customer cancel cancels it once; the production worker loop refills a slot as soon as one frees.
- **Crash recovery.** An event claimed when Glue stopped is handled once after a restart; a decision cut short is reopened or closed depending on where the order got to; a database from before versioning upgrades in place.
- **Conflicts.** The oversell is queued and the operator's cancel sets the eMAG order to 0; a recount below reserved caps both channels at 0 and queues each affected order once; a rejected SKU in an eMAG batch is flagged and fixed on the next run.
- **Security.** Unsigned, forged, wrong-source and replayed-under-a-new-id webhooks get 401; a shop order without lines gets 422 and an eMAG order without products is never reserved; an empty secret verifies nothing; dashboard writes without `X-Glue-Request` or from another origin get 403; each role gets 403 on what it may not do.
- **Console, AI and demo.** Filters, paging, the events cursor, analytics (including lost orders), settings, rules, the model download, budgets, and triage that hands the model the facts and never acts.

**A mutation check.** Each of these bugs, planted one at a time, makes the backend suite fail: inbox dedupe off, order-id dedupe off, no `Idempotency-Key`, `Retry-After` ignored, `Retry-After` uncapped, 4xx retried, no per-order lock, `processing` not reset at start, cut-off decisions not settled at start, stale items not settled, event id left out of the signature, an empty secret accepted, dirty flag never set, negative stock pushed, a cancel that does not release stock, ship notices not retryable, eMAG never acknowledged, CSRF header not checked.

The dashboard tests (Vitest, Testing Library, jsdom) cover each page's states, the API client, the events cursor, the flow map's dot mapping and layout, and the formatting helpers.

**Not covered by automated tests:** the assistant against the real model, timeouts (the in-process transport does not enforce them), and the background loops' timing. These were checked by hand in the browser on Docker.

## Observability

- **JSON logs.** Every audit row is also one JSON line on stdout with `ts`, `level`, `action`, `entity_type`, `entity_id`, `correlation_id` and the details. The correlation id is the inbound event id (`run-<time>` for a reconcile run, `review-<id>` for a decision), so one `grep` follows a piece of work across retries and stock pushes: `docker compose logs glue | grep emag-notify-500123-new`.
- **Audit log and timelines.** **Activity log** filters by kind, by order id, SKU or correlation id, and by time. Each order's page shows its timeline, including the rows that share its correlation id.
- **`GET /health`** is liveness plus a database read. It calls no other system, so a channel outage never restarts Glue. Compose uses it as the health check.
- **`GET /metrics`** needs a session that can view. In production it would be scraped on an internal port or with a token; it is JSON today, and the Prometheus text format would be a small addition. It returns counts per audit action for the last hour and in total, and these gauges:

```json
{
  "open_review_items": 2,
  "inbox": {"pending": 1, "processing": 1, "failed": 1, "oldest_pending_seconds": 120.4},
  "stock": {"dirty_rows": 1, "oldest_dirty_seconds": 61.2},
  "review": {"open": 1, "acting": 1, "oldest_open_seconds": 300.9},
  "warehouse_down": true,
  "last_reconcile_ok_at": "2026-10-23T09:14:02.511+00:00"
}
```

`oldest_dirty_seconds` measures from the last push the channel accepted, so it says how long a channel has been behind. `last_reconcile_ok_at` is the last full run that read the warehouse and attempted the pushes; refused pushes show in the `stock` gauges.

**Alert rules, as sentences** (thresholds are starting points):

- Page when the oldest pending event is older than 60 seconds: the worker is stuck or overwhelmed.
- Page when the warehouse has been down for more than 5 minutes: orders are piling up in review.
- Page when the last good reconcile is older than three intervals while the warehouse is up: the reconcile loop has stopped.
- Warn when any inbox event is `failed`: each one has a review item, and someone should look.
- Warn when a channel's stock has been behind for more than 5 minutes: customers see the wrong figure.
- Warn when the oldest open review item is older than 30 minutes in business hours: a paid order is waiting for a person.
- Warn when an item stays `acting` for more than 5 minutes: a decision is stuck inside a request.
- Warn on any `signature_rejected` in the last hour: a secret is wrong or someone is probing.

**Troubleshooting "eMAG order 500123 is missing":**

1. Open `/orders/emag-500123`. If it exists, its timeline says where it stopped; "Failed, needs you" or "Sold out, needs you" means it is in **Review queue** with the reason.
2. If there is no order, search **Activity log** for `emag-500123`. A "Sent to review" row whose reason starts with "unexpected while handling emag.notification" means Glue could not read the order from eMAG. eMAG keeps re-notifying until the order is acknowledged, and the next notification retries it.
3. If there is nothing at all, the notification never arrived. Look for "Fake message blocked" or "Message refused" (wrong secret or bad payload) and check eMAG's health on **Overview**.
4. Or ask the assistant: "What happened to emag-500123?"

## Scalability

**Measured.** [`scripts/load_probe.py`](scripts/load_probe.py) runs the four apps in-process, sends N signed shop orders through the real inbox, and drains them with the production worker loop at concurrency 10. It reads latency from the audit log with the same functions the Flow page uses, and asserts N reservations and no duplicates. On the author's laptop (Apple M4 Pro, outside Docker):

```sh
python -m scripts.load_probe --orders 300
```

| Orders | Ingest | Worker | Received → reserved p50 / p95 | Reservations / duplicates |
|---|---|---|---|---|
| 300 | 3,829 events/s | 526 orders/s | 0.31 s / 0.53 s | 300 / 0 |
| 1,000 | 4,413 events/s | 528 orders/s | 1.03 s / 1.78 s | 1,000 / 0 |

Every order is queued before the worker starts, so the latency is mostly time waiting in the inbox, not work.

**What the probe found.** Its first run showed the production loop capped at about 20 orders/s: with all 10 slots busy it slept for the 0.5-second poll interval instead of claiming as soon as a slot freed. The tests had not seen it because they drain the inbox in batches. The loop now waits for the first free slot, and a test pins it (`test_the_worker_loop_refills_a_slot_as_soon_as_it_frees`). The numbers above are after the fix.

**Where it breaks first.** Not in Glue: in eMAG's rate limits. Every reservation triggers a stock push for its SKUs, so a flash sale means many pushes for the same products, and each 429 holds a worker slot for the retry budget. Next come the single SQLite writer, the full reconcile every 10 seconds (fine for six SKUs, not for 20,000), and a slow warehouse holding slots for a whole retry budget.

**How it would scale:**

- **A real queue and N workers, partitioned by order id,** so per-order ordering survives without a shared lock. Handlers are already idempotent.
- **Postgres** with `SELECT … FOR UPDATE SKIP LOCKED` for claiming, if the queue stays in the database. All SQL is in one file.
- **Coalesced, changed-only pushes:** collect changed SKUs for a second and send one eMAG batch, so a flash sale becomes a few calls, with a slow full sweep as the safety net.
- **A circuit breaker per target system,** so a dead warehouse fails fast instead of holding slots for the retry budget.
- **One reconciler** across instances, elected with a lock (a Postgres advisory lock or a lease).
- **The stock buffer rule** switched on for scarce products, so the last units are not offered on both channels at once.

## Security

- **Signed webhooks.** `/events` requires `x-signature: sha256=<HMAC-SHA256 of event id + "\n" + raw body>`, with a separate secret per source. Signing the id with the body means a captured body cannot be replayed under a fresh event id. `/emag/notifications` signs the body alone; Glue builds the event id from the signed body (`emag-notify-<order id>-<type>`), so a replay always lands on the same id and is dropped as a duplicate. Signatures are compared in constant time, and an empty secret verifies nothing. Rejections are audited as `signature_rejected`. See [`common/signing.py`](common/signing.py) and [`glue/inbox.py`](glue/inbox.py).
- **Each source may only say what it owns.** The shop may only post `order.placed` and `order.cancelled` about `shop-` orders; the warehouse may only post `order.shipped` and `stock.adjusted`; eMAG has its own endpoint.
- **Strict validation at the edge.** Event ids, order ids, SKUs, quantities and line counts have patterns and limits. A payload that fails gets 422 and an `event_rejected` row and never reaches the inbox.
- **Cross-site request guard.** Every non-GET request under `/api` must carry `X-Glue-Request: 1`, and its `Origin`, when present, must match the host ([`glue/guard.py`](glue/guard.py)). A cross-site form cannot set that header, and a cross-site script would need a CORS preflight Glue never grants.
- **Sessions and roles.** The session cookie is `user:expiry:HMAC-SHA256`, verified in constant time with `SESSION_SECRET`, HttpOnly, SameSite=Lax, 12 hours. Three roles: `viewer` (view), `operator` (view, decide, ask), `admin` (also rules, settings, demo). Every protected route declares its permission with one FastAPI dependency ([`glue/auth.py`](glue/auth.py)), so hiding a button is never the only guard. Sign-ins and refused attempts are audited.
- **Health and metrics.** `/health` is open and reveals nothing but liveness. `/metrics` needs a viewer session.
- **Read-only AI.** The assistant's four tools only read, with arguments clamped; only the last 12 turns of history go back, each trimmed. Triage gets facts assembled in code, with text from other systems collapsed to one short line, and its suggestion is kept only if it is an action the item allows and the reason does not name a different order. Neither can change anything.
- **Outbound calls** are built from validated ids and URL-encoded. SQL is parameterised; the only SQL built from strings uses column names and filters written in `glue/db.py`, never request input.

## Operability

- **Migrations.** `glue/db.py` keeps an ordered list of steps; `PRAGMA user_version` records how many a database has had. On start, each missing step runs in its own transaction together with its version bump. The first step is `glue/schema.sql`, frozen as every existing database already has it; later changes are new steps, never edits to that file. The second step re-keyed the inbox on `(source, event_id)`. An existing `glue-data` volume upgrades in place; `tests/test_restart.py` covers a database from before versioning.
- **Recovery on start.** Events left `processing` go back to `pending`. Review items left `acting` are reopened if their action is still possible, or closed if the order has moved on or a newer item holds the same failure.
- **Shutdown.** The background loops are cancelled and awaited before the database closes.
- **Configuration is split in two.** Environment variables hold what is fixed per deployment: system URLs, webhook secrets, the database path, the HTTP timeout, worker concurrency, the model, sign-in passwords, demo traffic. The `settings` table holds what an admin tunes live on **Settings**: retry attempts, back-off base, the reconcile interval, and the assistant's effort and token limits. Those are bounded, audited as `settings_changed` and survive restarts; until an admin saves one, the environment or built-in default applies.
- **Backups (not built).** The database is one WAL-mode file in a volume. Production would run `sqlite3 glue.db ".backup …"` on a schedule, or stream it to object storage with Litestream.
- **Retention (not built).** A nightly job would delete `done` inbox events older than about 7 days. The audit log is the record, so it would be archived rather than deleted.

## Use of AI

<!--
PLACEHOLDER. The author writes this section before submission; delete this comment then.
Points to draw on (keep only what is true for you):
- Delegated to AI assistants: most of the implementation under your direction (sync core, React dashboard, mock UIs), test drafting, independent review passes on each change, the load probe, drafts of these docs.
- Decided by you: the scenario and the two channels, first-to-the-warehouse-wins, a person in the loop for oversells, policy in code for triage, what to leave out, core first.
- Checked by hand: the demo on Docker in a browser, the mutation check, each review finding before it was fixed.
- Found in review and fixed: three partial-failure gaps in the core (missed ship notice, crash mid-decision, stale review items), a hard-coded "Orders lost: 0", a worker loop capped at 20 orders/s that the tests could not see.
- Not delegated: final design decisions, what counts as done, the wording of this section.
-->

Written by the author before submission.

## Possible extensions

- **More rules.** Channel priority for the last unit, auto-cancel of unfulfillable orders under a value threshold, a per-SKU stop-selling threshold. The two existing rules show the shape: a row in `rules`, one function applied in the reconciler or the review flow, every effect audited.
- **Decisions on the worker.** Queue the operator's decision as an event so the request returns at once and the outcome shows on the card.
- **Real sign-in.** The customer's identity provider instead of the demo users, and finer permissions (who may cancel on eMAG versus only retry).
- **Triage that learns.** Compare suggestions with the decisions people took and surface the disagreements; a stronger model could be given the open choice.
- **Real connectors.** Adobe Commerce through Adobe I/O Events and the REST API, eMAG through the Marketplace API with its authentication, the warehouse through whatever it offers.
- **A real queue and Postgres,** as under [Scalability](#scalability).
