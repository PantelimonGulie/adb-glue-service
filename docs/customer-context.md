# Customer context

## The customer

A Romanian electronics reseller sells Apple products (iPhone, MacBook, iPad, AirPods, Apple Watch) through two channels:

- **Electronic Market**, its own online shop, built on Adobe Commerce.
- **eMAG Marketplace**, where it is one seller among many.

Both channels sell from one Bucharest warehouse, which has its own warehouse management system. The three systems are not connected.

## Today's manual process

- **Orders.** Staff open eMAG's seller center and the shop's admin several times a day and type each new order into the warehouse system. On eMAG they also confirm the order, or eMAG keeps showing it as new.
- **Stock.** A few times a day someone reads the warehouse's figures and types them into both channels.
- **Shipping.** When the warehouse ships, someone marks the order as shipped on the channel it came from.
- **In between,** both channels show the figure from the last copy. A product that sold out at 10:05 is still on sale on the other channel until someone notices.

## What the problem costs

- **Oversell.** The last unit sells on both channels within minutes. One customer has paid for something that does not exist. The order is cancelled, the customer is refunded, and someone handles the complaint.
- **eMAG penalties.** eMAG measures each seller's cancellation rate and penalises sellers who cancel too often. Every oversell that lands on eMAG costs more than the lost sale; enough of them put the store's standing on the marketplace at risk.
- **Missed and duplicated orders.** An order that is never typed in is never shipped, and the customer finds out first. An order typed in twice reserves stock twice and hides real availability.
- **Stale stock after a recount.** When the warehouse counts fewer units than the system thought, both channels keep selling units that are not there.
- **Staff time.** Copying orders and stock is hours a week of work that adds nothing, and it is where the mistakes above come from.

None of these figures are known yet. The first step of the engagement is to measure them from the last few months (see [Success in the first 30 days](#success-in-the-first-30-days)).

## What Glue changes

- **Orders arrive by themselves.** The shop's order events and eMAG's notifications reach Glue as they happen. Glue reserves each order at the warehouse within seconds and confirms eMAG orders, so eMAG stops showing them as new.
- **Stock follows the warehouse.** After every reservation, cancellation and recount, and every 10 seconds anyway, Glue pushes the warehouse's free figure to both channels. A channel that refused an update is corrected on the next run.
- **Duplicates and outages are handled.** A message sent twice makes one order. A warehouse that does not answer is retried, and an order it never took goes to a review queue instead of being lost.
- **People decide what costs money.** When the last unit sold on both channels, Glue reserves it for the first order, sets both channels to 0, and puts the second order in front of a person with the reason. Cancelling a paid order, and on eMAG paying for it in seller rating, stays a business decision.
- **Everything is on the record.** Every order has a timeline; every decision has a name and a time.

## What the customer must provide

- **API access to all three systems:** Adobe Commerce (an Adobe I/O Events registration for order events, and REST credentials for stock and order updates), eMAG Marketplace API credentials with the callback URL pointed at Glue, and the warehouse system's API.
- **A warehouse endpoint that accepts an idempotency key** when creating an order, or one Glue can ask "do you already have this order?" before creating it. Without one of these, a retry after a lost answer can reserve an order twice.
- **One SKU per product across all three systems,** or the mapping between them.
- **An owner for the review queue.** A named person, with a backup, who looks at the queue during business hours and decides within an agreed time. Without an owner the queue is where orders go to wait.
- **A decision on eMAG priority.** Whether to hold the last units back from eMAG (the stock buffer rule), trading some sales for a lower cancellation risk.

## Rollout

Each stage runs for about a week and moves on only when its numbers look right.

1. **Shadow mode.** Glue receives every event and reads the warehouse, but sends nothing. Each day its log of what it would have reserved and pushed is compared with what staff did by hand.
2. **Shop stock.** Glue pushes stock to the shop only. Staff stop typing shop stock and keep everything else.
3. **eMAG stock.** Glue pushes stock to eMAG too. This is where oversell risk drops, and where eMAG's real rate limits are first met.
4. **Orders.** Glue takes over orders from both channels, eMAG first because it re-sends until confirmed. Staff stop typing orders, and the review queue owner starts.

Shadow mode and the per-stage switches are not built yet; each is a flag checked before Glue calls a system. With them, going back a stage is one switch, and staff still know the manual process.

## Success in the first 30 days

Baselines are taken from the months before the rollout.

- **Oversells per week,** counted as review items with the cause "Sold on the other channel". Target: well below the baseline.
- **eMAG seller cancellation rate** for the month, from eMAG's seller center. Target: below the baseline and inside eMAG's threshold.
- **Missed orders: zero.** At month end, every order on both channels has a Glue order, and Flow shows no lost orders.
- **Time from paid to reserved:** p95 under a minute, from the Flow page.
- **Review queue:** items per day, and the oldest open item under 30 minutes in business hours.
- **Stock drift:** no channel behind the warehouse for more than 5 minutes outside known outages, from `/metrics`.
- **Staff hours** spent copying orders and stock, before and after.

## Risks

- **eMAG's real rate limits are unknown.** A flash sale could push more stock updates than eMAG accepts. Mitigation: measure in the eMAG stage, then coalesce pushes into fewer batches.
- **The warehouse API may not support idempotency.** Then Glue must look up an order before creating it, which is slower and needs testing against lost answers.
- **Adobe I/O Events signs with its own public-key scheme,** not the shared secret the demo uses. The connector must verify it properly.
- **The review queue has no owner,** and paid orders wait. Mitigation: an owner and a backup before the orders stage, and an alert on the oldest item.
- **Double processing during the switch.** If staff keep typing orders after Glue takes over, the warehouse gets them twice. Mitigation: one channel at a time, with a clear cut-over moment.
- **One instance.** While Glue is down, eMAG keeps re-sending and Adobe retries, but nothing is reserved. Mitigation: health alerts and a fast restart; more instances are on the scaling path in the README.
