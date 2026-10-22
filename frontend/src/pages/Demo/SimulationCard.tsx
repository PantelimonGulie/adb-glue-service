import type { Demo } from '../../api/types';
import { Segmented } from '../../components/Segmented/Segmented';
import { trafficButton } from './buttons';
import { CardButton } from './CardButton';
import { DemoCard } from './DemoCard';
import styles from './SimulationCard.module.css';
import { useDemoRun } from './useDemoRun';

const SPEEDS: { value: Demo['traffic']['speed']; label: string }[] = [
  { value: 'slow', label: 'Slow' },
  { value: 'normal', label: 'Normal' },
  { value: 'fast', label: 'Fast' },
];

export function SimulationCard({ traffic }: { traffic: Demo['traffic'] }) {
  const { run, busy, result, lock } = useDemoRun();
  const pause = trafficButton(traffic.running);
  return (
    <DemoCard
      title="Simulation"
      text="How fast new orders arrive. Slow lets you follow each dot; fast shows high volume."
      busy={busy}
      result={result}
    >
      <span className={styles.speed} title={lock.title}>
        <Segmented
          label="Speed"
          options={SPEEDS}
          value={traffic.speed}
          disabled={lock.disabled}
          onChange={(speed) => run({ action: `speed-${speed}` })}
        />
      </span>
      <CardButton label={pause.label} {...lock} onClick={() => run({ action: pause.action })} />
      <CardButton label="Turn every fault off" {...lock} onClick={() => run({ action: 'reset' })} />
    </DemoCard>
  );
}
