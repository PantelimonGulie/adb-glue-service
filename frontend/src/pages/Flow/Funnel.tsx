import type { Analytics } from '../../api/types';
import { Panel } from '../../components/Panel/Panel';
import { formatNumber } from '../../lib/format';
import styles from './Funnel.module.css';

type Steps = Analytics['funnel'];

const STEPS: { key: keyof Steps; label: string; hint: string }[] = [
  {
    key: 'received',
    label: 'Order messages received',
    hint: 'every order message from both channels, duplicates included',
  },
  { key: 'duplicates', label: 'Duplicates ignored', hint: 'same message twice, handled once' },
  { key: 'sent', label: 'Sent to warehouse', hint: 'unique orders Glue passed on' },
  { key: 'first_try', label: 'Reserved on first try', hint: 'warehouse accepted straight away' },
  { key: 'after_retry', label: 'Reserved after retry', hint: 'needed one or more retries' },
  { key: 'failed', label: 'Failed, sent to review', hint: 'every try failed; a person decides' },
];

function rows(funnel: Steps) {
  return STEPS.map((step) => {
    const count = funnel[step.key];
    const share = funnel.received ? (count / funnel.received) * 100 : 0;
    return { ...step, width: `${share}%`, text: `${formatNumber(count)} · ${share.toFixed(1)}%` };
  });
}

export function Funnel({ funnel, period }: { funnel: Steps; period: string }) {
  return (
    <Panel title="What happened to every order" note={period}>
      <ol className={styles.steps}>
        {rows(funnel).map((row) => (
          <li key={row.key} className={styles.step} title={row.hint}>
            <span>{row.label}</span>
            <span className={styles.track}>
              <i className={styles.bar} data-step={row.key} style={{ width: row.width }} />
            </span>
            <span className={styles.count}>{row.text}</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
