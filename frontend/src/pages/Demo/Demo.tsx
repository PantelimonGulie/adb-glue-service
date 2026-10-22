import { useDemo } from '../../api/hooks';
import { useDenied } from '../../auth/useDenied';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import text from '../../styles/text.module.css';
import { ActionCard } from './ActionCard';
import { emagButtons, SECURITY_BUTTONS, SHOP_BUTTONS, warehouseButtons } from './buttons';
import styles from './Demo.module.css';
import { HistoryCard } from './HistoryCard';
import { RecountCard } from './RecountCard';
import { SimulationCard } from './SimulationCard';

export function Demo() {
  const { data, error, isPending } = useDemo();
  const denied = useDenied('demo');

  return (
    <>
      <div className={page.top}>
        <h1>Demo controls</h1>
        <span className={styles.sub}>break things on purpose and watch the Overview map</span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {denied && (
        <p className={text.note}>You can see the demo controls. Only admins can use them.</p>
      )}
      {error && (
        <section className={table.box} aria-label="Demo controls">
          <EmptyState title="The demo controls could not be loaded">{error.message}</EmptyState>
        </section>
      )}
      {data && (
        <div className={styles.cards}>
          <ActionCard
            title="Warehouse"
            text="Make the warehouse fail in different ways, then watch Glue retry."
            buttons={warehouseButtons(data.faults.warehouse)}
            unknown={data.faults.warehouse === null}
          />
          <RecountCard />
          <ActionCard
            title="Shop"
            text="Things the shop or its customers do."
            buttons={SHOP_BUTTONS}
          />
          <ActionCard
            title="eMAG"
            text="Things eMAG does that make syncing hard."
            buttons={emagButtons(data.faults.emag)}
            unknown={data.faults.emag === null}
          />
          <ActionCard
            title="Security"
            text="A message that did not come from our systems."
            buttons={SECURITY_BUTTONS}
          />
          <SimulationCard traffic={data.traffic} />
          <HistoryCard loaded={data.sample_history} />
        </div>
      )}
    </>
  );
}
