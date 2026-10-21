# ADB Glue Service

Requires Docker Desktop.

```sh
docker compose up --build      # builds one image, starts four services, waits until all are healthy
```

Then open:

| URL | What it is |
|---|---|
| http://localhost:8000 | Glue dashboard (the thing this repo is about) |
| http://localhost:8001 | Electronic Market, the reseller's own shop (mock Adobe Commerce) |
| http://localhost:8002 | eMAG Marketplace (mock) |
| http://localhost:8003 | Warehouse (mock) |

```sh
docker compose down -v         # stop and reset
```

Use `-v` when you reset. It deletes the volume holding the glue's SQLite database. The three mocks keep their state in memory, so they always restart empty and number orders from the start again. A glue database kept from an earlier run would treat those new orders as duplicates of old ones.

The assistant page needs a free Gemini API key in `.env` (copy `.env.example`). Without one it says "assistant offline" and everything else works.

## Customer context and value

**The customer.** A Romanian electronics reseller sells Apple products through two channels: its own shop, Electronic Market (an Adobe Commerce store), and the eMAG Marketplace. Both channels sell from one warehouse.

**Today.** Nothing connects the three systems. Staff copy orders from eMAG and the shop into the warehouse system and type stock figures back into both channels a few times a day. In between, the channels show stale stock. Typical results:

- The last unit sells on both channels within minutes. One customer has paid for something that does not exist.
- An eMAG order is missed, or entered twice.
- One channel shows stock after a warehouse recount found less.
- eMAG measures the seller's cancellation rate and penalises sellers who cancel too often, so every oversell on eMAG costs more than the one sale.

**What the glue does.** It takes orders from both channels as they happen, reserves them at the warehouse, and pushes the warehouse's true stock back to both channels after every change. Duplicates, outages and slow systems are handled without anyone watching. When it cannot decide safely (the warehouse refused an order a customer already paid for), it does not guess: it puts the order in a review queue with the reason, and a person picks retry, cancel or dismiss.

**How we would measure value.**

- Oversells: orders accepted on a channel that the warehouse could not fulfil, per month. Each one shows up as an `unfulfillable` item, so the number is a query, not an estimate.
- eMAG cancellations by the seller, per month, before and after.
- Missed or duplicated orders found at month end. Target: zero.
- Staff hours spent copying orders and stock, before and after.
- Time from "customer paid" to "warehouse reserved" (seconds instead of hours).

## Demo walkthrough (5 minutes)

Keep the dashboard open in one tab and the mock you are using in another. Faults are under **Demo controls** at the top right of the dashboard. **Reset all faults** turns them all off.

1. **Stock is filled.** Open the shop (:8001). Every product shows stock: the glue read the warehouse at startup and pushed the figures to both channels. Click **Buy now** on an iPhone 16 128GB. On the dashboard, **Orders** shows it as allocated and **Stock** shows the same lower figure for the warehouse, the shop and eMAG.
2. **eMAG and duplicates.** On eMAG (:8002), click **Buy** on AirPods Pro 3. The glue receives a notification with only the order id, reads the order, reserves it and acknowledges it (eMAG status goes from new to in progress). In **Demo controls**, eMAG **Notifications: Re-send now** and Electronic Market **Last event: Send again**. The **Audit log** shows `duplicate_dropped`; no second order appears.
3. **Warehouse down.** Warehouse **Availability: Down**, then buy anything on the shop. The **Audit log** shows `retry_scheduled` lines honouring the warehouse's `Retry-After`, then `order_failed`. The order appears in **Review queue**. Set the warehouse **Up** and click **Retry allocation**: the order is allocated.
4. **Oversell.** eMAG **Freeze stock: On** (eMAG now ignores stock updates, which makes the race repeatable). Buy the only MacBook Air M4 on the shop. eMAG still shows 1, so buy it there too. The warehouse refuses the second order; it lands in **Review queue** as unfulfillable with the reason "sold on another channel first". Click **Cancel on eMAG**: the eMAG order goes to status cancelled and the decision is in the audit log. Turn **Freeze stock** off.
5. **eMAG rate limit and partial rejection.** eMAG **Rate limit: On**, then buy something on the shop. Stock pushes to eMAG retry after one second each time (`Retry-After: 1`), then mark the eMAG rows dirty on **Stock**. Turn **Rate limit** off; the next reconcile run (every 10 s) clears them. eMAG **Reject MBA-M4: On**: the batch push applies every other SKU and flags only MBA-M4 as dirty. Turn it off and it clears on the next run.
6. **Recount below reserved.** With at least one iPhone 16 128GB order allocated, open the warehouse (:8003), set the IPH16-128 count to 0 and click **Save count**. Both channels drop to 0 for that SKU and every allocated order for it appears in **Review queue**. **Retry allocation** is not offered: the orders still hold their reservation, so the person decides which to cancel.
7. **Assistant.** On **Assistant**, ask "Which orders need a decision?". The answer cites order ids and channels from the database. It can read but cannot change anything.

Every order has a page (click it in **Orders**) with its full timeline: the inbound event, retries, the allocation, the stock pushes it caused and any review decision.

## Architecture

Four services from one image: three mocks and the glue. The glue is one FastAPI process with a SQLite database.

- **Inbox.** Webhooks from the shop and the warehouse, and notifications from eMAG, are checked (signature, schema), saved, and answered 202 straight away. Nothing is processed inside the request, so nothing is lost if processing fails.
- **Worker.** Takes pending events from the inbox, up to 10 at a time, and runs the matching handler.
- **Router.** The only code that changes an order's status. Places orders at the warehouse, imports eMAG orders (read, place, acknowledge), handles cancellations and shipments.
- **Reconciler.** Reads the warehouse's stock and pushes the sellable figure to both channels. Runs at startup, every 10 seconds, after every allocation or cancellation, and on every warehouse stock event.
- **Review queue.** Orders the glue refused to decide alone, with three actions: retry, cancel, dismiss.
- **Audit log.** One row per thing that happened, with a correlation id, mirrored as a JSON log line.

Diagrams (components, both order flows, the oversell, the order state machine) and the reasoning behind them are in [docs/architecture.md](docs/architecture.md).

## Technologies

- **Python 3.12**: one language for the mocks, the glue and the tests.
- **FastAPI + pydantic**: typed HTTP endpoints, and strict validation of every inbound payload at the edge.
- **Jinja2 + HTMX**: server-rendered pages with live updates and no JavaScript build step.
- **httpx (async)**: explicit timeouts, and the tests run every service in-process through `ASGITransport`.
- **SQLite (stdlib `sqlite3`)**: durable inbox, orders and audit log with no extra service; the mocks keep state in memory.
- **Docker Compose**: the same first run on any machine.
- **openai SDK pointed at Gemini's OpenAI-compatible endpoint**: a free model with function calling for the read-only assistant.
- **pytest + pytest-asyncio**: the test suite. **ruff**: lint and format.

## Assumptions

1. **Adobe Commerce events** are delivered at least once, not necessarily in order, and may be duplicated, as Adobe's event documentation states. Each carries an event id (`x-adobe-event-id` here). A redelivery may also come under a new id, so the glue deduplicates by order id as well.
2. **eMAG notifications** carry only the order id and type; the full order is read through the API (`order/read`). eMAG re-sends a new-order notification until the seller calls `order/acknowledge`. Order statuses are numeric (0 cancelled, 1 new, 2 in progress, 3 prepared, 4 finalized), stock is pushed in batches through `product_offer/save`, and a batch can fail for one item while the rest succeed. The mock mirrors public copies of the eMAG Marketplace API v4 documentation. Those copies may be out of date, and exact rate limits are unverified, so the glue simply honours `Retry-After` on 429.
3. **The warehouse owns stock.** Its figure (`on_hand − reserved`) is the truth; the channels' figures are only what the glue last told them. Its order endpoint is atomic and accepts an `Idempotency-Key`.
4. **Channel priority: first to reach the warehouse wins.** Neither channel is preferred. A rule such as "keep the last unit for eMAG" belongs in the Rules screen marked "coming later".
5. **Money and payments** are out of scope. A customer has already paid when an order reaches the glue; cancelling means the channel refunds them. The glue never touches payment data.
6. **One warehouse, one order line per mock order**, single currency. The models and the warehouse accept several lines; the mock checkouts only create one.
7. **Webhook signing.** Every source signs its webhooks with a shared-secret HMAC. Adobe I/O Events uses its own public-key signature scheme, and whether real eMAG callbacks can be signed is unverified. Because the glue pulls each eMAG order through the authenticated API anyway, a forged eMAG notification could at most trigger a read.

## Trade-offs

- **SQLite and one process instead of a queue and a worker pool.** The inbox table works like a queue (claim, process, mark done or failed) and survives restarts, which is all one shop needs. The cost is one writer and no horizontal scaling. The code is shaped so the inbox can become a real queue without touching handlers.
- **Pulling stock from the warehouse instead of trusting events alone.** Every reconcile overwrites both channels with the warehouse's figure, even when nothing seems to have changed. That costs a few extra calls but heals any drift: a missed event, a restarted channel, a rejected update. Events make it fast; the periodic pull makes it correct.
- **First come, first served across channels.** Simple, explainable and fair. It does not protect eMAG's seller rating; a stock buffer per channel would, at the cost of selling less.
- **A person decides oversells instead of automatic cancellation.** Cancelling a paid order is a business decision: maybe stock arrives tomorrow, maybe the customer accepts a different model. The glue does the safe part (reserve nothing it cannot fulfil, cap the channels at 0) and queues the rest with the reason.
- **Mocks instead of real sandboxes.** The mocks copy the parts of the real APIs that matter for the logic (at-least-once delivery, acknowledge, batch responses with per-item errors, numeric statuses) and add fault switches, so every failure mode can be shown on demand. The cost is that real API quirks are untested.
- **Server-rendered UI with HTMX instead of a SPA.** Less code and no build. The pages poll every few seconds rather than using websockets, which is fine for one operator.

## Known limitations and what was left out

- **No login or roles.** "Signed in as operator" is a placeholder; the only protection on dashboard actions is the cross-site request guard. Roles are a "coming later" screen. Reason: real auth belongs to the customer's identity provider.
- **No real connectors.** The shop, eMAG and the warehouse are mocks. Their API shapes follow the real ones but are not tested against them.
- **Left out on purpose:** courier and AWB generation, returns and refunds, payments, invoices, multi-warehouse, product catalogue sync. Each is a project of its own and none changes the conflict and retry design.
- **One instance only.** Two glue processes on the same database would both claim events. Scaling is described below.
- **The shop mock sends each event once.** Real Adobe Commerce retries failed deliveries; the mock does not, and the glue does not poll the shop's orders, so an event sent while the glue is down is lost in the demo.
- **Demo secrets are in `docker-compose.yml`.** Fine for a local demo; in production they come from a secret store.
- **Mock state lives in memory** and resets on restart, which is why the reset command uses `-v`.
- **The dashboard loads HTMX and a font from public CDNs**, so the browser needs internet access.

## Testing

```sh
docker compose run --rm --build glue sh -c "ruff check . && ruff format --check . && pytest -q"
```

`--build` puts the current code in the image; drop it if the image is already up to date.

The tests start all four apps in one process and connect them with a single `httpx.AsyncClient` whose `mounts` route `http://shop`, `http://emag`, `http://warehouse` and `http://glue` to the apps directly, with no network and no ports. Each test gets a fresh SQLite file and zero retry back-off. The background loops never start: tests call the worker and the reconciler step by step, so each test reads like a demo step. The suite (14 tests) runs in under a second.

Covered:

- A duplicated shop event and a redelivery under a new event id make one order and one reservation.
- eMAG re-notifications do not allocate twice, and stop once the order is acknowledged.
- Warehouse 503, 503, 201: the order is allocated on the third attempt.
- Warehouse down: the order fails after retries (honouring `Retry-After`), is queued, and an operator retry allocates it.
- Oversell: the second order is unfulfillable, and the operator's cancel sets the eMAG order to status 0.
- eMAG rejects one SKU in a batch: the others apply, the rejected one is dirty, and the next run fixes it.
- A recount below reserved caps both channels at 0, queues each affected order once, and refuses retry with 409.
- The retry policy itself: `Retry-After` honoured, exponential back-off, 4xx returned without retrying, exhaustion raises.
- Unsigned, forged and wrong-source webhooks get 401; a signed but invalid event gets 422; dashboard actions without the HTMX header or from another origin get 403.

Not covered: the HTML pages, the assistant (it needs a live model), the background loops' timing, shipping and customer cancellations, timeouts (the in-process transport does not enforce them), and recovery after a crash. These were checked by hand in the browser.

## Observability

- **JSON logs.** Every audit row is also one JSON line on stdout with `ts`, `action`, `entity_id` and `correlation_id`. The correlation id is the inbound event id (or `run-<timestamp>` for a reconcile run, `review-<id>` for a decision), so one `grep` follows a piece of work across retries and stock pushes: `docker compose logs glue | grep emag-notify-500123-new`.
- **Audit log and order timeline.** The **Audit log** page filters by order id, SKU or correlation id. Each order's page shows its timeline, including the rows that share its correlation id.
- **`GET /metrics`** returns counts per action for the last hour and in total, and the number of open review items, as JSON.
- **`GET /health`** on all four services; compose uses them as health checks and the dashboard shows them live.
- **Stock drift** is visible on the **Stock** page: a channel figure the channel did not accept is marked "Not applied", and one that differs from the warehouse is highlighted.

**Troubleshooting "eMAG order 500123 is missing":**

1. Open `/orders/emag-500123`. If it exists, its timeline says where it stopped: `order_failed` or `unfulfillable` means it is in the **Review queue** with the reason.
2. If there is no order, filter the **Audit log** by `emag-500123`. A `review_opened` row whose reason starts with "unexpected while handling emag.notification" means the glue could not read the order from eMAG (down or rate limited). The event was marked failed; eMAG keeps re-notifying until the order is acknowledged, and the next notification retries it.
3. If there is nothing at all, the notification never arrived. Look for `signature_rejected` or `event_rejected` (wrong secret or bad payload) and check eMAG's health on the **Overview**.
4. Or ask the assistant: "What happened to emag-500123?"

## Scalability

**Where it would break first.**

- One process and SQLite: a single writer, and the inbox is polled every 0.5 s.
- eMAG rate limits: every stock change triggers a push, and a flash sale means many pushes for the same SKUs.
- The reconcile pull reads all SKUs every 10 seconds. Fine for six, not for a 20,000-product catalogue.
- Calls are sequential per order. A slow or dead warehouse holds a worker slot for the whole retry budget, several seconds per order.

**How we would measure it.** Events per second through the inbox; queue depth and the age of the oldest pending event; p95 time from event received to order allocated; retry rate per target system; the age of the oldest dirty stock row; review items opened per hour. All of these come from the audit log and inbox tables already; a load test would replay a recorded flash sale (for example the **Place 10 orders** button, scaled up) against the mocks.

**How it would scale.**

- Inbox to a real queue (or Postgres with `SELECT ... FOR UPDATE SKIP LOCKED`) and several worker processes. Handlers are already idempotent, so running them in parallel is safe.
- SQLite to Postgres. All SQL is in one file (`glue/db.py`).
- Coalesce stock pushes: collect changed SKUs for a second, then send one eMAG batch, so a flash sale becomes a few calls instead of hundreds.
- Reconcile only SKUs that changed since the last run, with a slow full sweep as the safety net.
- A circuit breaker per target system, so a dead warehouse fails fast instead of holding slots for the whole retry budget.
- A stock buffer per channel (a Rule), so the last units are not offered on both channels at once.

## Security

- **Signed webhooks.** Every inbound webhook carries `x-signature: sha256=<HMAC of the raw body>`, with a separate secret per source. Signatures are compared in constant time, an empty secret never verifies, and each source may only send its own event types (the warehouse cannot post `order.placed`). Rejections are written to the audit log as `signature_rejected`.
- **Strict validation at the edge.** Event ids, order ids, SKUs and quantities have patterns and limits. A payload that fails validation gets 422 and an `event_rejected` audit row; it never reaches the inbox.
- **Cross-site request guard.** Every state-changing dashboard request (review decisions, demo controls, assistant questions) must carry `HX-Request: true`, and its `Origin`, if present, must match the host. A cross-site form cannot set that header, and a cross-site script would need a CORS preflight the glue never approves.
- **Read-only assistant.** Its four tools only read; there is no tool that changes anything, so a question (or text hidden in order data) can at worst produce a wrong answer. Arguments are clamped and chat history is sanitised before it is sent to the model.
- **Outbound URLs** are built from validated ids and URL-encoded.

## Use of AI

<!-- Draft facts: the author will rewrite this section in their own words -->

- AI assistants were used for: research of the scenario, design discussion, implementation of most of the code under the author's direction and review, UI design, the tests, and drafts of this documentation.
- The author made the product and design decisions: the scenario, the two channels, the conflict rules, keeping a person in the loop for oversells, and what to leave out.
- The author reviewed and ran every step.
- The author chose not to rely on AI for: final design decisions, verifying behaviour (the demo was run by hand), and the wording of this section.

## Possible extensions

- **Rules engine.** Per-channel stock buffers, channel priority for the last unit, auto-cancel of unfulfillable orders under a value threshold. The screen exists as "coming later".
- **Users and roles.** Sign-in through the customer's identity provider; who may cancel an eMAG order versus only retry.
- **Triage agent.** Let the assistant suggest the action for each review item with its reasoning, still decided by a person.
- **Real connectors.** Adobe Commerce through Adobe I/O Events and the REST API, eMAG through the Marketplace API with its authentication, the warehouse through whatever it offers.
- **A real queue and Postgres**, as described under Scalability.
