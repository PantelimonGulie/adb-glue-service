import { useOverview, useReview } from '../../api/hooks';
import type { Cause } from '../../api/types';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Segmented } from '../../components/Segmented/Segmented';
import { Tag } from '../../components/Tag/Tag';
import { oneOf, useFilters } from '../../lib/filters';
import { formatNumber } from '../../lib/format';
import { cause } from '../../lib/labels';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import text from '../../styles/text.module.css';
import cards from './cards.module.css';
import { ReviewCard } from './ReviewCard';
import { ReviewGroup } from './ReviewGroup';

type Show = 'open' | Cause | 'decided';

const CAUSES: Cause[] = ['outage', 'soldout', 'recount', 'other'];
const FIRST = 3;
const DECIDED_SHOWN = 20;

export function Review() {
  const { params, change } = useFilters();
  const { data: overview } = useOverview({ range: 'live' });
  const waiting = overview ? ` (${formatNumber(overview.open_reviews)})` : '';
  const options: { value: Show; label: string }[] = [
    { value: 'open', label: `All open${waiting}` },
    ...CAUSES.map((name) => ({ value: name, label: cause(name).label })),
    { value: 'decided', label: 'Decided' },
  ];
  const show = oneOf(options, params.get('show'));
  const decided = show === 'decided';
  const { data, error, isPending } = useReview({ status: decided ? 'decided' : 'open' });
  const items = data?.items ?? [];
  const groups = (decided ? [] : (data?.groups ?? []))
    .filter((group) => show === 'open' || group.cause === show)
    .map((group) => {
      const all = items.filter((item) => item.cause === group.cause);
      return { ...group, items: show === 'open' ? all.slice(0, FIRST) : all };
    });
  const latest = decided ? items.slice(0, DECIDED_SHOWN) : [];
  const empty = data !== undefined && (decided ? latest : groups).length === 0;
  const emptyTitle = decided ? 'Nothing decided yet' : 'Nothing is waiting for a decision';

  return (
    <>
      <div className={page.top}>
        <h1>Review queue</h1>
        <span className={page.sub}>
          orders Glue will not decide alone · grouped by cause · every decision is saved
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      <div className={page.toolbar}>
        <Segmented
          label="What to show"
          options={options}
          value={show}
          onChange={(value) => change({ show: value === 'open' ? null : value })}
        />
      </div>
      {(error || empty) && (
        <section className={table.box} aria-label="Review queue">
          {error && (
            <EmptyState title="The review queue could not be loaded">{error.message}</EmptyState>
          )}
          {empty && <EmptyState title={emptyTitle} />}
        </section>
      )}
      {groups.map((group) => (
        <ReviewGroup
          key={group.cause}
          name={group.cause}
          count={group.count}
          items={group.items}
          onShowAll={() => change({ show: group.cause })}
        />
      ))}
      {latest.length > 0 && (
        <div className={cards.cards}>
          {latest.map((item) => (
            <ReviewCard key={item.id} item={item} />
          ))}
        </div>
      )}
      {decided && items.length > latest.length && (
        <p className={text.note}>Showing the latest {DECIDED_SHOWN} decisions.</p>
      )}
    </>
  );
}
