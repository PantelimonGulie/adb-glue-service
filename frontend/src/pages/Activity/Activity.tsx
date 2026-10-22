import { useActivity } from '../../api/hooks';
import type { ActivityKind } from '../../api/types';
import { ActivityTable } from '../../components/ActivityTable/ActivityTable';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Pager } from '../../components/Pager/Pager';
import { RangePicker } from '../../components/RangePicker/RangePicker';
import { Segmented } from '../../components/Segmented/Segmented';
import { Tag } from '../../components/Tag/Tag';
import { oneOf, useBackToFirstPage, useFilters } from '../../lib/filters';
import { formatWindow } from '../../lib/format';
import { useProductName } from '../../lib/products';
import { useRange } from '../../lib/range';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import { Chip } from './Chip';

const KINDS: { value: ActivityKind; label: string }[] = [
  { value: 'all', label: 'Everything' },
  { value: 'orders', label: 'Orders' },
  { value: 'retries', label: 'Retries' },
  { value: 'problems', label: 'Problems' },
  { value: 'duplicates', label: 'Duplicates' },
  { value: 'stock', label: 'Stock' },
  { value: 'decisions', label: 'Decisions' },
];

const isTime = (value: string | null): value is string =>
  value !== null && !Number.isNaN(Date.parse(value));

export function Activity() {
  const [range, setRange] = useRange();
  const filters = useFilters();
  const { params, change } = filters;
  const kind = oneOf(KINDS, params.get('kind'));
  const entity = params.get('entity') ?? '';
  const since = params.get('since');
  const until = params.get('until');
  // A chart bar links here with its exact time window, which replaces the range.
  const exact = isTime(since) && isTime(until) ? { since, until } : null;
  const { data, error, isPending, isPlaceholderData } = useActivity({
    ...(exact ?? { range }),
    kind,
    entity: entity || undefined,
    page: filters.page,
  });
  useBackToFirstPage(data, filters);
  const loading = isPending || isPlaceholderData;
  const productName = useProductName();
  const rows = data?.rows ?? [];

  return (
    <>
      <div className={page.top}>
        <h1>Activity log</h1>
        <span className={page.sub}>
          everything Glue did, newest first · hover a label for its meaning
        </span>
        <span role="status">{loading && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {exact ? (
        <div className={page.toolbar}>
          <Chip
            clearLabel="Show the whole range"
            onClear={() => change({ since: null, until: null })}
          >
            Showing {formatWindow(exact.since, exact.until)}
          </Chip>
        </div>
      ) : (
        <RangePicker value={range} onChange={setRange} />
      )}
      <div className={page.toolbar}>
        <Segmented
          label="What to show"
          options={KINDS}
          value={kind}
          onChange={(value) => change({ kind: value === 'all' ? null : value })}
        />
        {entity && (
          <Chip clearLabel="Show every order and product" onClear={() => change({ entity: null })}>
            Only {entity}
          </Chip>
        )}
      </div>
      {(error || data) && (
        <section className={table.box} aria-label="Activity">
          {error && (
            <EmptyState title="The activity log could not be loaded">{error.message}</EmptyState>
          )}
          {data && data.total === 0 && (
            <EmptyState title="Nothing happened here">
              Try a longer time range or show everything.
            </EmptyState>
          )}
          {rows.length > 0 && <ActivityTable rows={rows} productName={productName} />}
          {data && data.total > 0 && (
            <Pager
              page={data.page}
              perPage={data.per_page}
              total={data.total}
              onPage={(next) => change({ page: String(next) })}
            />
          )}
        </section>
      )}
    </>
  );
}
