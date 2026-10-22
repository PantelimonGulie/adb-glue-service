import { useRules } from '../../api/hooks';
import { useDenied } from '../../auth/useDenied';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import text from '../../styles/text.module.css';
import { BufferRule } from './BufferRule';
import { RetryRule } from './RetryRule';
import styles from './Rules.module.css';

export function Rules() {
  const { data, error, isPending } = useRules();
  const denied = useDenied('rules');

  return (
    <>
      <div className={page.top}>
        <h1>Rules</h1>
        <span className={page.sub}>
          automations that act without a person · each action is saved as &quot;Rule applied&quot;
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {denied && <p className={text.note}>You can see the rules. Only admins can change them.</p>}
      {error && (
        <section className={table.box} aria-label="Rules">
          <EmptyState title="The rules could not be loaded">{error.message}</EmptyState>
        </section>
      )}
      <div className={styles.rules}>
        {data?.map((rule) =>
          rule.name === 'stock-buffer' ? (
            // A save from anywhere changes the rule; the form starts again from what was saved.
            <BufferRule key={`${rule.name} ${rule.updated_at}`} rule={rule} />
          ) : (
            <RetryRule key={rule.name} rule={rule} />
          ),
        )}
      </div>
    </>
  );
}
