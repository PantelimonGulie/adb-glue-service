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

**A clean demo.** Because the mocks forget and Glue remembers, start a demo from a fresh Glue database: `docker compose down`, then `docker volume rm glueservice_glue-data` (Compose prefixes the project folder's name; `docker volume ls` shows it). Never use `docker compose down -v`: it also deletes `ollama-models`, and the model downloads again.

## Read this first

The sync core is six files. Read them in this order:

1. [`glue/inbox.py`](glue/inbox.py): verifies the signature, validates the payload, saves the event, answers 202. No other work happens in the request.
2. [`glue/worker.py`](glue/worker.py): claims pending events, takes a per-order lock, runs the handler, turns any unexpected error into a failed event and a review item.
3. [`glue/router.py`](glue/router.py): the only code that changes an order's status. Places, imports from eMAG, cancels, ships.
4. [`glue/retry.py`](glue/retry.py): the one retry policy every outbound call goes through; each retry is logged in plain words.
5. [`glue/reconciler.py`](glue/reconciler.py): reads the warehouse's stock and pushes it to both channels; a refused push leaves a dirty flag that the next run clears. A recount below reserved sends only the newest orders the shelf cannot cover to review.
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

Compose starts demo traffic (`DEMO_TRAFFIC: slow`): a random order on the shop or eMAG every 5 seconds, a shipment every sixth tick, and a restock when a product has fewer than 3 free. The restock is a warehouse recount marked "demo restock", so **Activity log** shows it as "Shelf count changed". Traffic never restocks a product someone counted by hand in the last 10 minutes, so the recount steps below hold. The mock pages reload every 4 seconds, except while you type in a field, have changed one, or wait for a form you sent.

Every time and date on the dashboard is Bucharest time (see [Architecture](#architecture)).

1. **Watch it run.** **Overview** on **Live · 15 min** shows the flow map: each dot is one real event from the audit log, moving from a channel through Glue to the Bucharest warehouse. The map's nodes and the sidebar show each system's state: working, slow, limiting requests or not answering. The counters, **Waiting for you** and **Latest activity** sit around it. Click any order on **Orders** for its timeline: the inbound event, retries, the reservation, the stock pushes it caused and any decision. Ctrl+K (Cmd+K on a Mac) opens a command palette that finds orders and pages.
2. **Pause for the scripted steps.** On **Demo controls**, Simulation card, click **Pause new orders** so each step below is easy to follow.
3. **A shop order.** On the shop (:8001) buy an iPhone 16 128GB. On the dashboard, **Orders** shows it **Reserved**, and **Stock** shows the same lower figure for the warehouse, the shop and eMAG.
4. **An eMAG order.** On the marketplace (:8002), buy AirPods Pro 3 in the Offers table. The order row starts at "1 · New" and moves to "2 · In progress" once Glue has read the order, reserved it and acknowledged it. The marketplace's API activity log shows the callback to Glue, `order/read` and `order/acknowledge`.
5. **Duplicates.** Shop card, **Send the same order twice**: the shop re-sends its last event with the same event id. **Activity log** shows "Duplicate ignored" and no second order appears.
6. **Warehouse outage.** Warehouse card, **Stop answering**, then buy anything on the shop. **Activity log** shows "Retrying" lines that wait the 2 seconds the warehouse asks for in `Retry-After`, then "Failed, needs you". The warehouse terminal (:8003) shows the outage banner and the refused order in its outbox. **Review queue** groups the order under "Warehouse outage". Click **Bring the warehouse back**, then **Retry all** on that group: the order is reserved. (With the auto-retry rule on, under **Rules**, Glue retries by itself when the warehouse answers again.)
7. **Oversell.** On **Stock**, note how many MacBook Air M4 are reserved, then use the **Warehouse recount** card to set the shelf to that number plus one, so exactly one unit is free. eMAG card, **Ignore stock updates**: eMAG now keeps showing its old figure. Buy the MacBook Air M4 on the shop. eMAG still shows 1, so buy it there too. The warehouse refuses the second order; it lands in **Review queue** under "Sold out", and the card names the shop order that got the last unit. Click **Cancel on eMAG**, then **Yes, cancel it**: the marketplace shows the order as "0 · Cancelled by seller". Click **Apply stock updates again**.
8. **eMAG rate limit and a missed ship notice.** eMAG card, **Ask Glue to slow down**: eMAG answers every API call with 429 and `Retry-After: 1`, and the sidebar shows eMAG as "limiting requests". On the warehouse terminal, click **Ship** on the eMAG order from step 4. Glue marks it shipped, cannot tell eMAG, and opens a review item that says so. **Stock** marks eMAG's figures as refused for the same reason. Click **Stop asking to slow down**, then **Retry** on the item: the marketplace shows "4 · Finalized", and the next reconcile run (every 10 seconds) clears the stock flags.
9. **Partial batch rejection.** eMAG card, **Refuse updates for MacBook Air M4**. On the next reconcile run the batch applies every other product and only MacBook Air M4 is flagged on **Stock**; the marketplace's Offers table shows "rejected: validation error" for it. **Accept updates for MacBook Air M4 again** clears it on the next run.
10. **Recount below reserved.** With at least two iPhone 16 128GB reserved, use **Warehouse recount** (or the warehouse terminal) to set the shelf to one fewer than are reserved. Both channels drop to 0, and only the newest reserved order appears under "Shelf count too low": the shelf is short by one. Retry is not offered: the order still holds its reservation, so a person decides whether to cancel it. Recount the shelf back up and Glue closes the item itself ("Closed as no longer needed").
11. **A forged message.** Security card, **Send a message with a fake signature**: Glue answers 401, and **Activity log** shows "Fake message blocked".
12. **History and analytics.** **Sample history** card, **Load sample history**: 30 days of generated orders from a fixed seed, about 300 a day. Open **Flow** on **This month**: the funnel from received to reserved, p50 and p95 time to reserve, orders with problems per day, a panel per system (including "Orders lost"), a breakdown by product and **Export CSV**. A banner says sample data is included until **Clear sample history** (it asks you to confirm) removes it; real orders stay.
13. **Assistant and triage.** Once the model is ready, ask the **Assistant** "Which orders need a decision?". It answers from a block of live facts and five read-only lookups, and the page lists the lookups it used. On a review card, **Suggest an action** asks the model for a triage suggestion; it is shown on the card and never acts.

Click **Resume new orders** when done.

## Architecture

Four services from one image: three mocks and Glue. Glue is one FastAPI process with one SQLite file. It serves the webhooks, a JSON API under `/api`, and the built React dashboard.

- **Inbox.** Webhooks from the shop and the warehouse, and notifications from eMAG, are verified, validated, saved and answered 202. Nothing is processed in the request, so nothing is lost if processing fails.
- **Worker.** Claims pending events, at most 10 at a time, one task each. Events for the same order run one at a time.
- **Router.** The only writer of order status.
- **Reconciler.** Pulls the warehouse's stock and pushes the sellable figure to both channels: at startup, every 10 seconds, after every reservation or cancellation, and on every stock event.
- **Review queue.** The orders Glue would not decide alone, with retry, cancel and dismiss.
- **Audit log.** One row per thing that happened, with a correlation id, mirrored as one JSON log line.
- **Business timezone.** `BUSINESS_TIMEZONE` (default `Europe/Bucharest`) says where a day starts. Today, Last 7 days, This month and custom ranges, and the Flow page's day buckets, are cut at midnight in that zone, so the day the clocks go back has 25 hours. Glue stores and returns UTC; `/api/me` names the zone, and the dashboard shows every time and date in it, whatever the browser's own zone.

**Crash safety.** Four patterns keep an order right wherever Glue stops. A transactional inbox saves each event with its audit row before the 202. Processing is at least once, and every hop is idempotent, which together give effectively once. Each local step is atomic: a state change, its audit row and its review item commit in one SQLite transaction. Steps across the three systems cannot share a transaction, so they run saga style: each is idempotent and retried, and what still fails goes to a person in the review queue, whose **Cancel** compensates it on the channel. What is saved, and what happens on restart, for each place Glue can stop is in the [crash table](docs/architecture.md#crash-safety).

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
- **Jinja2** for the three mock systems: server-rendered pages with plain HTML forms, fonts vendored in `common/static/fonts/` with their licences. Their only script, `common/static/refresh.js`, reloads the page every 4 seconds.
- **Ollama with `qwen2.5:3b`**, called through the **openai** SDK (Ollama's OpenAI-compatible endpoint). Free, local, no key, nothing leaves the machine.
- **Docker Compose** with a multi-stage `Dockerfile` (Node builds the dashboard, the Python image serves it). The same first run on any machine.
- **pytest, pytest-asyncio, ruff** for the backend; **Vitest, Testing Library, ESLint, tsc** for the dashboard.

**Not used, and why:**

- **A message broker (Kafka, RabbitMQ, SQS).** The inbox table already works as a durable queue (claim, process, mark done or failed) for one reseller's volume. Handlers are idempotent, so a broker can replace the table without touching them.
- **Postgres.** One file and no service is enough for one instance. All SQL is in `glue/db.py`, so the move is contained.
- **An ORM or Alembic.** About sixty queries in one file, and three migration steps. The ordered list is the whole mechanism.
- **Celery or a task framework.** Four asyncio loops in one process.
- **WebSockets or server-sent events.** The dashboard polls every 2 seconds; the live map asks only for rows after a cursor. Fine for a handful of operators.
- **A component library, Tailwind or Redux.** CSS Modules and tokens keep the bundle small and the styles local; TanStack Query already holds the server state.
- **An agent framework.** The assistant is one tool loop of about forty lines over five read-only functions.
- **A hosted model by default.** A reviewer should not need a key. The usage limits exist for when it points at a paid model.

## Assumptions

1. **Adobe Commerce events** are delivered at least once, not necessarily in order, and may be duplicated, as Adobe's event documentation states. Each carries an event id (`x-adobe-event-id` here). A redelivery may come under a new id, so Glue also deduplicates by order id.
2. **eMAG notifications** carry only the order id and type; the full order is read with `order/read`. eMAG re-sends a new-order notification until the seller calls `order/acknowledge`. Statuses are numeric (0 cancelled, 1 new, 2 in progress, 3 prepared, 4 finalized). Stock goes in batches through `product_offer/save`, and a batch can fail for one item while the rest apply. The mock follows public copies of the Marketplace API v4 documentation, which may be out of date; real rate limits are unverified, so Glue honours `Retry-After` on 429.
3. **The warehouse owns stock.** Its figure (`on_hand − reserved`) is the truth; the channels show only what Glue last told them. Its order endpoint is atomic and accepts an `Idempotency-Key`.
4. **First to reach the warehouse wins.** Neither channel is preferred. Holding units back from one channel is a rule (off by default), not part of the conflict logic.
5. **Payments are out of scope.** The customer has paid when an order reaches Glue; cancelling means the channel refunds them. Glue never sees payment data.
6. **One warehouse, one currency, and one order line per mock checkout.** The models and the warehouse accept several lines.
7. **Signing.** Each source signs with a shared-secret HMAC. Adobe I/O Events uses its own public-key scheme, and whether real eMAG callbacks can be signed is unverified. Because Glue pulls every eMAG order through the authenticated API and acts on the status it reads back, a forged eMAG notification could at most trigger a read: a cancel notice for an order eMAG still shows open is logged as ignored (`cancel_ignored`) and changes nothing.
8. **SKUs are the same everywhere.** The shop's SKU, eMAG's `part_number` and the warehouse's code are one value. A real rollout needs a mapping table.

## Trade-offs

- **SQLite and one process instead of a queue and a worker pool.** The inbox survives restarts and is all one reseller needs. The cost is one writer and no horizontal scaling; the path is under [Scalability](#scalability).
- **Pull stock from the warehouse instead of trusting events alone.** Every run pushes every SKU it covers, even when nothing seems to have changed. That costs calls but heals any drift: a missed event, a restarted channel, a refused update. Events make it fast; the periodic pull makes it correct.
- **First come, first served across channels.** Simple, explainable and fair. It does not protect eMAG's seller rating; the stock buffer rule does, at the cost of selling less, so it is a switch for the business, not the default.
- **A person decides oversells.** Cancelling a paid order is a business decision: stock may arrive tomorrow, the customer may take a different model. Glue does the safe part (reserve nothing it cannot fill, cap both channels at 0) and queues the rest with the reason.
- **Per-order serialisation instead of a global lock.** Events and decisions for one order run one at a time; different orders run in parallel. At scale this becomes workers partitioned by order id.
- **Decisions run inside the HTTP request.** Simple, and the operator sees the outcome at once. The cost is that a retry against a slow warehouse holds the request; the `acting` state makes a cut-off decision safe, but not fast.
- **No distributed transaction across the three systems: idempotency and compensation instead.** The shop, eMAG and the Bucharest warehouse are separate systems behind HTTP APIs, and none of them offers a two-phase commit. Holding one transaction across them would also let one slow system stall the others. So each call is idempotent and retried, its result is saved locally in one transaction with its audit row, and what cannot be completed goes to review, where a cancel undoes it on the channel. The cost is a short window in which the systems disagree, such as a reservation Glue has not recorded yet; the crash-point test shows that each such window heals.
- **Triage: the policy is in code, the model explains it.** The 3B local model follows a rule that names one choice but not a conditional one, so `glue/ai/triage_prompt.py` decides the recommendation and the model writes the reason. It is testable, and the model cannot steer the outcome.
- **No RAG:** orders, stock and the audit log are live, structured data, so the assistant's tools query them directly, which is more accurate than searching embeddings.
- **Polling instead of push to the browser.** Two-second polling with a cursor is simple and survives proxies; push would matter only with many operators.
- **Mocks instead of real sandboxes.** The mocks copy the behaviour that matters for the logic (at-least-once delivery, acknowledge, per-item batch results, numeric statuses) and add fault switches, so every failure can be shown on demand. Real API quirks stay untested.

## Known limitations

- **One instance only.** The per-order locks, the reconcile lock and the "warehouse is down" flag live in process memory. A second process on the same file would not share them.
- **Decisions run inside the request.** **Retry all** with a slow warehouse can take longer than a browser waits. Moving decisions onto the worker is the fix.
- **In-memory state.** `warehouse_down` and `last_reconcile_ok_at` reset on restart, so an outage that ended while Glue was stopped is not seen as a recovery and auto-retry does not fire for it; **Retry all** covers it. A rate limit that Glue's own calls met is remembered for 30 seconds in memory too. Demo traffic is in-memory state as well: restarting the `glue` container turns it back on as `DEMO_TRAFFIC` says, even after **Pause new orders**.
- **Shutdown does not wait for in-flight event handlers.** The loops are cancelled and awaited, but an event a handler was working on stays `processing` and goes back to `pending` on the next start. Handlers are idempotent, so it is handled once.
- **The mocks keep state in memory; Glue persists.** A restarted or rebuilt mock comes back with seed stock and no orders, while Glue keeps every order it saw. Glue's reservations then drift from the warehouse's: orders show **Reserved** that the warehouse no longer holds and will never ship. A real warehouse system is durable. For a clean demo, start from a fresh `glue-data` volume, as under [Quickstart](#quickstart), and never delete `ollama-models`.
- **Glue knows what a channel accepted, not what it shows.** A channel that accepts a figure and does not apply it, like eMAG's **Ignore stock updates** fault, looks in step on **Stock** and to the assistant. Reading eMAG's offers back during reconcile would close this.
- **"Orders in" and the Flow funnel can differ.** Orders in counts order rows by when they came in; the funnel counts order messages in the window. An eMAG notice whose order Glue could not read (eMAG down, or the order gone) is in the funnel but has no order row. Their reserved counts can also differ at a range's end, for an order that came in during the range and was reserved after it.
- **A short shelf count comes back if closed early.** Closing a "Shelf count too low" item without changes while the shelf is still short opens it again on the next stock check. Cancelling the order, or a count that covers it, ends it.
- **The shop mock sends each event once,** and Glue does not poll the shop. An event sent while Glue is down is lost in the demo. Real Adobe Commerce retries delivery.
- **No retention.** `events_inbox` and `audit_log` grow forever. See [Operability](#operability).
- **Analytics read the audit log on every request.** Fine for months of one reseller; at scale it needs pre-aggregated buckets, and an index on `review_queue.order_id` for the lost-orders count. "Longest outage" is an estimate from retry rows, because nothing is logged when the warehouse comes back.
- **Demo sign-in.** Three fixed users with passwords from the environment, no password hashing, no sign-in rate limit, no `Secure` cookie flag (it runs on plain HTTP locally). Real sign-in belongs to the customer's identity provider; the roles and per-route checks would stay.
- **Demo secrets are in `docker-compose.yml`.** In production they come from a secret store, and webhook secrets need rotation with an overlap window, which is not built.
- **No real connectors.** API shapes follow the public documentation but are not tested against sandboxes.
- **A 3B local model is often vague and sometimes wrong.** The assistant runs at temperature 0 with live facts. In the last measured runs, "What failed in the last hour?", "Is the warehouse working?" and "Why is the MacBook different on eMAG?" (with nothing out of step) were right every time. "Which orders need a decision?" named the right order, but for an item stored before reasons were plain words it repeated the raw "404 Not Found" text; the review lookup now sends the item's plain cause and what it means, never its stored reason text, and a test pins that. In an earlier round, when eMAG refused a MacBook update, the figures were right in 8 of 8 answers but the reason ("eMAG refused the update") was given in only 2 and wrong in 1. Answers can still vary between runs, because the facts carry the time to the second. Triage reasons are sensible but wordy; the choice itself comes from code.
- **Left out on purpose:** courier and AWB, returns and refunds, payments, invoices, several warehouses, catalogue sync. None changes the conflict and retry design.
- **Small leftovers.** Uvicorn's own access lines are plain text next to the JSON audit lines. `glue/context.py` imports the demo `Traffic` dataclass, so the core depends on one demo type.

## Testing

```sh
# Backend, in the same image Compose runs: lint, format check, 238 tests in about 13 seconds
docker compose run --rm --no-deps --build glue sh -c "ruff check . && ruff format --check . && pytest -q"

# Dashboard, with Node 24 as in the Dockerfile: lint, typecheck, 222 tests in 44 files
cd frontend && npm ci && npm run lint && npm run typecheck && npm test
```

`--build` puts the current code in the image; drop it if the image is up to date. `--no-deps` leaves a running demo alone: the tests start their own in-process apps, so the mock containers are not recreated and keep their stock. Without Docker, with Python 3.12 or newer: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -q`.

**How the backend tests run.** [`tests/conftest.py`](tests/conftest.py) starts all four apps in one process and connects them with one `httpx.AsyncClient` whose mounts route `http://shop`, `http://emag`, `http://warehouse` and `http://glue` to the apps directly: no network, no ports. Each test gets a fresh SQLite file, zero back-off, a stub Ollama and a session signed in as `operator`. The background loops do not start; tests drive the worker and the reconciler step by step, so each test reads like a demo step and asserts end state (one reservation, eMAG status 4, which items are open), not call counts.

**What they prove**, one failure mode each:

- **Duplicates.** A repeated shop event, a redelivery under a new event id, and eMAG re-notifications each make one order and one reservation; an event id from one sender cannot hide another sender's event.
- **Retries.** Warehouse 503, 503, 201 reserves on the third try; `Retry-After` is honoured as seconds or an HTTP date, capped at 30 seconds, and ignored when unreadable; 4xx answers are not retried; a retried eMAG read or acknowledge, warehouse cancel, ship notice or channel cancel each leaves a retry row in the activity log.
- **Partial failures.** A ship notice the channel missed is retried from review; an acknowledge that fails after the reservation heals on eMAG's next notification; a failed event sent again goes back to the queue; items whose order reached a good state by another path close themselves.
- **Concurrency.** Two cancels for one order in one batch cancel it once; an operator cancel racing a customer cancel cancels it once; the production worker loop refills a slot as soon as one frees.
- **Crash recovery.** An event claimed when Glue stopped is handled once after a restart; a decision cut short is reopened or closed depending on where the order got to; a database from before versioning, or from before `received_at`, upgrades in place; and the crash-point test below.
- **Conflicts.** The oversell is queued, names the order that got the last unit, and the operator's cancel sets the eMAG order to 0; a shelf short by two flags the two newest orders, and a count that covers them closes their items; a two-product order keeps its item while only one product is short; a rejected SKU in an eMAG batch is flagged and fixed on the next run.
- **Security.** Unsigned, forged, wrong-source and replayed-under-a-new-id webhooks get 401; a shop order without lines gets 422 and an eMAG order without products is never reserved; an eMAG cancel notice changes nothing while eMAG shows the order open, and a new-order notice reserves nothing once eMAG shows it cancelled; an empty secret verifies nothing; a session cookie with a superscript digit in its expiry is refused instead of crashing; dashboard writes without `X-Glue-Request` or from another origin get 403; each role gets 403 on what it may not do.
- **Business days.** Today starts at midnight in Bucharest, an order at 00:30 local counts for that day, and the day the clocks go back has 25 hourly buckets.
- **Console, AI and demo.** Filters, paging without gaps when orders arrive in the same millisecond, the events cursor, analytics (including lost orders, and Overview, Flow and Orders agreeing on one day), system states (including a rate limit only Glue's own calls meet), settings, rules, the model download, budgets, an assistant prompt that carries live facts and tools that answer in product names, triage that hands the model the facts, never acts, drops sentences that name internal tools and refuses a missing or decided item before asking the model, and demo restocks that leave a hand-counted product alone.

**The crash-point test.** [`tests/test_crash_points.py`](tests/test_crash_points.py) runs 11 flows: a shop order reserved, refused with 409, or failed in an outage; a cancel; a shipment; an eMAG order; a retry from review; an eMAG order Glue cannot read; a cancel of a failed order; a cancel from review that fails; and a short recount. It counts each flow's database writes, then reruns the flow on fresh systems once per write and stops Glue just before it: 132 crash points in about 6 seconds. After each restart it checks that the warehouse holds exactly Glue's allocated orders, that every order ends as in the run without a crash, that every failed order has one open item, that every state change has its audit row once, and that every event ends done or failed with an item. Before the fixes this test led to, 31 of the 132 points failed. How it stops and restarts Glue is under [Crash safety](docs/architecture.md#crash-safety).

**A mutation check.** Each of these bugs, planted one at a time, makes the backend suite fail: inbox dedupe off, order-id dedupe off, no `Idempotency-Key`, `Retry-After` ignored, `Retry-After` uncapped, 4xx retried, no per-order lock, `processing` not reset at start, cut-off decisions not settled at start, stale items not settled, event id left out of the signature, an empty secret accepted, dirty flag never set, negative stock pushed, a cancel that does not release stock, ship notices not retryable, eMAG never acknowledged, CSRF header not checked.

The dashboard tests (Vitest, Testing Library, jsdom) cover each page's states, the API client, the events cursor, the flow map's dot mapping and layout, and the formatting helpers.

**Not covered by automated tests:** the assistant against the real model, timeouts (the in-process transport does not enforce them), the background loops' timing, and the mock pages' reload (a test checks only that every mock serves the script). These were checked by hand in a browser.

## Observability

- **JSON logs.** Every audit row is also one JSON line on stdout with `ts`, `level`, `action`, `entity_type`, `entity_id`, `correlation_id` and the details. Retries, failures and review items carry the raw technical error (`HTTP 503`, `ReadTimeout: …`) in an `error` field; the dashboard shows only the plain reason, and an unexpected error tells the operator the detail is in this log. The correlation id is the inbound event id (`run-<time>` for a reconcile run, `review-<id>` for a decision), so one `grep` follows a piece of work across retries and stock pushes: `docker compose logs glue | grep emag-notify-500123-new`.
- **Audit log and timelines.** **Activity log** filters by kind, by order id, SKU or correlation id, and by time. Each order's page shows its timeline, including the rows that share its correlation id.
- **System states.** The sidebar, the live map and Settings show each system as `ok`, `slow`, `rate_limited` or `down` ("working", "slow", "limiting requests", "not answering"). A health check sets the state; a 429 that Glue's own calls met in the last 30 seconds marks a system `rate_limited` even when its health check passes, as eMAG's does.
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
2. If there is no order, search **Activity log** for `emag-500123`. A "Sent to review" row with a reason such as "eMAG no longer knows this order" or "eMAG is not answering (tried 5 times)" means Glue could not read the order from eMAG; the service log line has the raw error. eMAG keeps re-notifying until the order is acknowledged, and the next notification retries it.
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
- **Read-only AI.** The assistant's five tools only read, with arguments clamped; only the last 12 turns of history go back, each trimmed. Triage gets facts assembled in code, with text from other systems collapsed to one short line. Its suggestion is kept only if it is an action the item allows and the reason does not name a different order; sentences that name internal tools or fields are dropped, and if none is left there is no suggestion. Neither can change anything.
- **Outbound calls** are built from validated ids and URL-encoded. SQL is parameterised; the only SQL built from strings uses column names and filters written in `glue/db.py`, never request input.

## Operability

- **Migrations.** `glue/db.py` keeps an ordered list of steps; `PRAGMA user_version` records how many a database has had. On start, each missing step runs in its own transaction together with its version bump. The first step is `glue/schema.sql`, frozen as every existing database already has it; later changes are new steps, never edits to that file. The second step re-keyed the inbox on `(source, event_id)`. The third added `orders.received_at`, filled from each order's last update, with an index; the Orders range filters by it, and paging sorts by `received_at` then order id. An existing `glue-data` volume upgrades in place; `tests/test_restart.py` covers a database from before versioning and one from before `received_at`.
- **Recovery on start.** Events left `processing` go back to `pending`. Review items left `acting` are reopened if their action is still possible, or closed if the order has moved on or a newer item holds the same failure.
- **Shutdown.** The background loops are cancelled and awaited before the database closes.
- **Configuration is split in two.** Environment variables hold what is fixed per deployment: system URLs, webhook secrets, the database path, the HTTP timeout, worker concurrency, the model, sign-in passwords, demo traffic, the business timezone (an unknown zone stops the start). The `settings` table holds what an admin tunes live on **Settings**: retry attempts, back-off base, the reconcile interval, and the assistant's effort and token limits. Those are bounded, audited as `settings_changed` and survive restarts; until an admin saves one, the environment or built-in default applies.
- **Backups (not built).** The database is one WAL-mode file in a volume. Production would run `sqlite3 glue.db ".backup …"` on a schedule, or stream it to object storage with Litestream.
- **Retention (not built).** A nightly job would delete `done` inbox events older than about 7 days. The audit log is the record, so it would be archived rather than deleted.

## Use of AI

I built this with an AI coding assistant (Claude Code) and used it heavily. This is the split.

**Delegated to AI.** Most of the implementation: the sync core, the React dashboard and the mock UIs, written task by task from plans and clickable mockups I approved. Also the test drafts, the load probe, the first drafts of these docs and the slides. Every change went through a separate AI review pass before it was accepted, and a final independent review and a browser QA pass covered the whole branch.

**Decided by me.** The scenario (one Bucharest warehouse, the shop and eMAG); that the first order to reach the warehouse wins; that a person decides oversells; that triage is policy in code and the model only explains it; the look of every screen, approved as mockups before any UI code; what to leave out; and the order of work: the sync core first, then the operator console, then the demo layer.

**How it was checked.** 238 backend and 222 dashboard tests; a mutation check of 18 planted bugs that the suite must catch; a load probe; a run from a fresh clone with only Docker installed; and browser walkthroughs of every screen at six widths for each role.

**What review caught.** Three partial-failure gaps in the core (a ship notice nobody retried, a crash in the middle of a review decision, review items left open after the problem healed), a hard-coded "Orders lost: 0", a recount that flooded the review queue, and a worker loop capped at 20 orders per second that only the load probe exposed. Each is fixed and has a test.

## Possible extensions

- **More rules.** Channel priority for the last unit, auto-cancel of unfulfillable orders under a value threshold, a per-SKU stop-selling threshold. The two existing rules show the shape: a row in `rules`, one function applied in the reconciler or the review flow, every effect audited.
- **Decisions on the worker.** Queue the operator's decision as an event so the request returns at once and the outcome shows on the card.
- **Real sign-in.** The customer's identity provider instead of the demo users, and finer permissions (who may cancel on eMAG versus only retry).
- **Triage that learns.** Compare suggestions with the decisions people took and surface the disagreements; a stronger model could be given the open choice.
- **Real connectors.** Adobe Commerce through Adobe I/O Events and the REST API, eMAG through the Marketplace API with its authentication, the warehouse through whatever it offers.
- **A real queue and Postgres,** as under [Scalability](#scalability).
