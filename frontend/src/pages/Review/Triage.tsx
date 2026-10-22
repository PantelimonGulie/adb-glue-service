import { useAssistant, useTriage } from '../../api/hooks';
import type { ReviewItem } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { modelState } from '../../lib/model';
import controls from '../../styles/controls.module.css';
import { suggested } from './explain';
import styles from './Triage.module.css';

export function Triage({ item }: { item: ReviewItem }) {
  const denied = useDenied('ask');
  const triage = useTriage();
  const { data: assistant } = useAssistant();
  const notice = assistant && modelState(assistant.model).notice;
  const blocked = denied ?? notice;

  if (item.suggestion) {
    return (
      <div className={styles.suggestion}>
        <span className={styles.kicker}>Triage agent · a suggestion, it does not act</span>
        <p>
          <b>{suggested(item.suggestion.action, item)}.</b> {item.suggestion.reason}
        </p>
      </div>
    );
  }
  if (item.status === 'decided') return null;
  return (
    <div className={styles.ask}>
      <button
        type="button"
        className={controls.button}
        disabled={Boolean(blocked) || triage.isPending}
        title={blocked}
        onClick={() => triage.mutate(item.id)}
      >
        Ask the triage agent
      </button>
      {triage.isPending && (
        <span className={styles.note}>Thinking… a local model can take a minute.</span>
      )}
      {notice && <span className={styles.note}>{notice}</span>}
      {triage.error && (
        <span className={styles.error} role="alert">
          {triage.error.message}
        </span>
      )}
    </div>
  );
}
