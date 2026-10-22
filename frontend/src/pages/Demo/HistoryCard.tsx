import { useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import controls from '../../styles/controls.module.css';
import { CardButton } from './CardButton';
import { DemoCard } from './DemoCard';
import styles from './HistoryCard.module.css';
import { useDemoRun } from './useDemoRun';

const NOTHING_TO_CLEAR = 'There is no sample history to clear';

export function HistoryCard({ loaded }: { loaded: boolean }) {
  const { run, busy, result, lock } = useDemoRun();
  const [confirming, setConfirming] = useState(false);
  const clearButton = useRef<HTMLButtonElement>(null);

  // The question replaces the button, so the button has to be back on screen before it can take
  // the focus again.
  function closeQuestion() {
    flushSync(() => {
      setConfirming(false);
    });
    clearButton.current?.focus();
  }

  function clear() {
    closeQuestion();
    run({ action: 'history-clear' });
  }

  return (
    <DemoCard
      title="Sample history"
      text="Thirty days of made-up orders, so Flow and the charts have something to show. Loading it again replaces it."
      busy={busy}
      result={result}
    >
      <CardButton
        label="Load sample history"
        state={loaded ? 'loaded' : undefined}
        {...lock}
        onClick={() => run({ action: 'history-load' })}
      />
      {confirming ? (
        <div className={styles.confirm} role="group" aria-label="Clear the sample history">
          <p className={styles.question}>Remove every sample order? Real orders stay.</p>
          <button type="button" className={controls.button} onClick={clear}>
            Yes, clear it
          </button>
          <button type="button" className={controls.button} autoFocus onClick={closeQuestion}>
            Keep it
          </button>
        </div>
      ) : (
        <CardButton
          ref={clearButton}
          label="Clear sample history"
          {...lock}
          blocked={lock.blocked || !loaded}
          title={lock.title ?? (loaded ? undefined : NOTHING_TO_CLEAR)}
          onClick={() => setConfirming(true)}
        />
      )}
    </DemoCard>
  );
}
