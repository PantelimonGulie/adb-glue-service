import { useAssistant } from '../../api/hooks';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import styles from './Assistant.module.css';
import { Chat } from './Chat';
import { ModelPanel } from './ModelPanel';

export function Assistant() {
  const { data, error, isPending } = useAssistant();

  return (
    <>
      <div className={page.top}>
        <h1>Assistant</h1>
        <span className={page.sub}>
          read-only · answers from the activity log and order history · cannot change anything
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {error && (
        <section className={table.box} aria-label="Assistant">
          <EmptyState title="The assistant could not be loaded">{error.message}</EmptyState>
        </section>
      )}
      <div className={styles.columns}>
        <div className={styles.chat}>
          <Chat model={data?.model} />
        </div>
        {data && (
          <div className={styles.side}>
            <ModelPanel assistant={data} />
          </div>
        )}
      </div>
    </>
  );
}
