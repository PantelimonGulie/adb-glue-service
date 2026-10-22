import { useSaveSettings, useSettings } from '../../api/hooks';
import { useDenied } from '../../auth/useDenied';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import { Connections } from './Connections';
import { TuningForm } from './TuningForm';

export function Settings() {
  const { data, error, isPending } = useSettings();
  const save = useSaveSettings();
  const denied = useDenied('settings');
  // The form starts again from the saved values whenever they change, from here or elsewhere.
  const saved =
    data && [data.retry_attempts, data.retry_base_seconds, data.reconcile_interval_seconds];

  return (
    <>
      <div className={page.top}>
        <h1>Settings</h1>
        <span className={page.sub}>
          {denied
            ? 'only admins can change settings'
            : 'changes apply right away and are saved in the activity log'}
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {error && (
        <section className={table.box} aria-label="Settings">
          <EmptyState title="The settings could not be loaded">{error.message}</EmptyState>
        </section>
      )}
      {data && (
        <>
          <TuningForm key={saved?.join()} settings={data} denied={denied} save={save} />
          <Connections connections={data.connections} />
        </>
      )}
    </>
  );
}
