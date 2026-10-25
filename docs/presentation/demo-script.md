# Demo script (5 minutes)

A presenter's cheat sheet for the live part of the interview. Each step has the clicks, the words to say, and what to do if it goes wrong. Button names are the ones on screen.

## The day before

- `docker compose up --build -d` on the branch you will present. The first run needs internet: pip and npm for the image, the `ollama/ollama` image, and the local model (qwen2.5:3b, about 2 GB, downloaded once into the `ollama-models` volume). After that everything works offline, fonts included.
- Open **Assistant** and wait until the model panel says **Ready**. Ask it one question so the model is warm.
- Do a full dry run from a clean start, the six steps below, then a clean start again. A clean start is `docker compose down`, then `docker volume rm glueservice_glue-data` (Compose prefixes the folder name; `docker volume ls` shows it), then `docker compose up -d`. Never `docker compose down -v`: it also deletes `ollama-models`, and the model downloads again. The mocks forget on restart and Glue remembers, which is why the clean start removes Glue's volume.
- Run the checks once so you can show them green if asked:
  - `docker compose run --rm --no-deps --build glue sh -c "ruff check . && ruff format --check . && pytest -q"` (227 tests, about 8 s; `--no-deps` leaves a running demo alone)
  - `cd frontend && npm ci && npm run lint && npm run typecheck && npm test` (222 tests)
- Optional, for the Flow page: **Demo controls**, **Load sample history** (30 days of made-up orders, labelled as sample everywhere). Clear it after the demo with **Clear sample history** if you want clean numbers.

## 15 minutes before

```sh
docker compose up -d     # image and model already in place
docker compose ps        # shop, emag, warehouse and glue "healthy"
```

Open four browser tabs in this order and leave them open:

1. `localhost:8000` Glue dashboard. Sign in as `admin` (password `admin` unless `.env` changes it). Stay on **Overview**.
2. `localhost:8001` Electronic Market (the shop)
3. `localhost:8002` eMAG Marketplace (the seller center mock)
4. `localhost:8003` Bucharest warehouse

Zoom the browser to 110 to 125% so the panel can read it. In **Demo controls**, click **Turn every fault off** once. New orders arrive on their own every 5 seconds (`DEMO_TRAFFIC: slow`), with a shipment every sixth tick and a restock when a product runs low; that is what moves the live map. The mock pages reload every 4 seconds, except while you type in a field. Every time on the dashboard is Bucharest time.

Order ids are numbers the mocks make from the clock (for example `shop-254879695`), so they differ every run. Read them off the screen; the script does not assume any.

## The six steps

### 1. Live map (30 s)

- **Show:** **Overview**. Dots move from the shop and eMAG boxes into Glue and on to the Bucharest warehouse. The counters tick up.
- **Say:** "Every dot is a real event. Orders come in from both channels, Glue reserves each one at the warehouse, and pushes the warehouse's figure back to both channels after every change."
- **Click:** **Stock**: every product shows its free figure, the last figure Glue sent the shop and eMAG, and state **sent to both**.

### 2. Duplicate (30 s)

- **Click:** **Demo controls**, Shop card, **Send the same order twice**.
- **Click:** **Activity log**, tab **Duplicates**: a **Duplicate ignored** row. **Orders** still has the order once.
- **Say:** "The shop sent the same event id again. It is dropped at the inbox. A redelivery under a new id would be caught one layer down, by the order id, and the warehouse's Idempotency-Key is the third layer."

### 3. Outage (75 s)

- **Click:** **Demo controls**, Warehouse card, **Stop answering**. Go back to **Overview**: the sidebar and the map show the warehouse as **not answering**, and new orders start retrying.
- **Say:** "The warehouse now answers 503 with Retry-After 2. Glue waits exactly that, five attempts, then gives up on that order and puts it in front of a person. Nothing is lost."
- **Click:** **Review queue** after about 10 s: the **Warehouse outage** group fills up. **Retry all** waits, greyed out, while the warehouse is still not answering. Only the warehouse not answering counts as an outage.
- **Click:** **Demo controls**, **Bring the warehouse back**. **Review queue**, **Retry all N**: the cards move to **Decided** and the orders are reserved.
- Optional: open one of those orders from **Orders** to show its history in plain words: received, four retries 2 s apart ("the Bucharest warehouse is not answering"), failed, sent to review, the decision, reserved.
- If asked: the auto-retry rule (**Rules**, off by default) would have retried the outage items by itself once the warehouse answered; it touches outage items only.

### 4. Oversell (75 s), the main point of the demo

- **Click:** **Demo controls**, Simulation card, **Pause new orders** (so random orders do not take the last unit).
- **Click:** **Stock**, note how many MacBook Air M4 are reserved. **Demo controls**, **Warehouse recount** card: product MacBook Air M4, units on the shelf = that number plus 1, **Save the count**. Free is now 1, and both channels show 1 within a second. (The warehouse terminal at :8003 has the same recount field.) Demo traffic never restocks a product counted by hand in the last 10 minutes.
- **Click:** dashboard, **Demo controls**, eMAG card, **Ignore stock updates**.
- **Say:** "This makes eMAG ignore stock updates, so the race is repeatable. In real life it is a few seconds of lag."
- **Click:** shop tab (:8001), **Buy now** on MacBook Air M4. Marketplace tab (:8002): MBA-M4 still shows 1. **Buy** it there.
- **Click:** **Review queue**, tab **Sold out**: "An eMAG customer ordered 1 × MacBook Air M4, but the last unit went to shop-… first." **Got the unit** names the shop order that won.
- **Say:** "First to reach the warehouse wins. Glue does not cancel a paid order on its own: on eMAG that counts against the seller's rating. It shows the facts and what each button does, and a person decides."
- **Click:** **Cancel on eMAG**, then **Yes, cancel it**. Marketplace tab: that order shows status **0 · Cancelled by seller**, and the **Seller cancellation rate** tile goes up: that is the cost the person weighed. **Activity log**, tab **Decisions**: the decision under `admin`.
- **Click:** **Demo controls**, **Apply stock updates again**, then **Resume new orders**.

### 5. Partial batch (40 s)

- **Click:** **Demo controls**, eMAG card, **Refuse updates for MacBook Air M4**.
- **Click:** **Stock**, wait for the next run (at most 10 s): the MacBook row says **eMAG refused**; every other product is still **sent to both**. The marketplace's Offers table shows "rejected: validation error" for it.
- **Say:** "eMAG's batch API answers per item. One refused product does not block the rest, the row is marked dirty, and the next run pushes everything again."
- **Click:** **Accept updates for MacBook Air M4 again**. Within 10 s the row is back to **sent to both**.

### 6. Timeline and assistant (30 s)

- **Click:** **Orders**, the eMAG order you cancelled in step 4: its history shows it received from eMAG, sold out at the warehouse, sent to review, confirmed to eMAG, the decision and the cancel.
- **Click:** **Ask the assistant about this order** (or **Assistant** and ask "What happened to emag-…?").
- **Say:** "A local model through Ollama, answering from live facts and five lookups that only read. It cannot change anything; at worst it gives a wrong answer." On a review card, **Suggest an action** asks the same model for a triage suggestion: the rule is in code, the model writes the reason, and it never acts.

Close with: "Every line you saw is also a JSON log line with the same correlation id, and /metrics shows how old the oldest waiting event, dirty row and review item are."

## If something goes wrong live

| Problem | What to do |
|---|---|
| A fault is still on and the next step behaves oddly | **Demo controls**, **Turn every fault off**. |
| State is messy | Clean start: `docker compose down`, `docker volume rm glueservice_glue-data`, `docker compose up -d`. About 20 s until all four are healthy. Never `down -v` (it deletes the model). |
| Step 4: the last MacBook sold to random traffic first | You forgot **Pause new orders**. Recount again (reserved + 1) and repeat. |
| Step 4: the card is under "Shelf count too low", not "Sold out" | The recount went below reserved. Recount to reserved + 1; Glue closes that item by itself once the count covers the order. |
| Step 4: eMAG refuses the purchase, or it is reserved with no review item | **Ignore stock updates** was off (eMAG already showed 0), or the recount left more than 1 free. Check **Stock**, recount, repeat. |
| Step 3 takes longer than expected | It waits for the real retry budget (about 8 s per order). Talk over it: explain Retry-After while the rows appear. |
| Step 5 flag does not clear | Wait for the 10 s reconcile; it runs on a timer. **Update channels now** on **Stock** forces a run. |
| Assistant says the model is downloading or offline | Say so plainly: the page shows the one-time download (about 2 GB) and its progress. Show `glue/ai/assistant.py` (five read-only tools) and `glue/ai/triage_prompt.py` (the rule in code) instead. |
| A page shows stale numbers | Auto-refresh may be off (top right). Turn it on, or click **Refresh**. |
| Port already in use | Another stack is running: `docker compose down`, or stop whatever holds ports 8000 to 8003. |
| Docker Desktop is not running | Start it before the interview and check `docker compose ps`. |

## Backup material

- Diagrams for deep dives: `docs/presentation/diagrams/` (component map, the architecture overview, both order sequences, stock reconcile, the oversell, order states, review item states). The `.mmd` files are the sources.
- Code to open if asked: `glue/router.py` (order states), `glue/retry.py` (the policy), `glue/reconciler.py` (stock and dirty flags), `glue/review.py` and `glue/settle.py` (the queue, crash-safe decisions, auto-resolve), `glue/inbox.py` (signatures and source binding), `glue/worker.py` (per-order lock), `tests/conftest.py` (all four apps in one process).
