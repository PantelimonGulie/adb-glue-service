import { Fragment, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useDecide } from '../../api/hooks';
import type { Decision, ReviewItem } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import styles from './Decisions.module.css';
import { cancelQuestion, choice, consequence, DECISIONS, unavailable } from './explain';

export function Decisions({ item }: { item: ReviewItem }) {
  const denied = useDenied('decide');
  const decide = useDecide();
  const [confirming, setConfirming] = useState(false);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const rows = DECISIONS.map((action) => {
    const refused = unavailable(action, item);
    return {
      action,
      label: choice(action, item),
      why: denied ?? refused,
      note: refused ?? consequence(action, item),
    };
  });
  const question = cancelQuestion(item);

  // A cancel refunds the customer, so it asks first; the other choices act at once.
  function pick(action: Decision) {
    if (action === 'cancel') setConfirming(true);
    else decide.mutate({ id: item.id, action });
  }

  // The question replaces the choices, so the button has to be back before it takes the focus.
  function keep() {
    flushSync(() => {
      setConfirming(false);
    });
    cancelButton.current?.focus();
  }

  function cancel() {
    setConfirming(false);
    decide.mutate({ id: item.id, action: 'cancel' });
  }

  return (
    <>
      {confirming ? (
        <div className={styles.confirm} role="group" aria-label={question}>
          <p className={styles.question}>
            <b>{question}</b> {consequence('cancel', item)}
          </p>
          <button type="button" className={controls.button} data-action="cancel" onClick={cancel}>
            Yes, cancel it
          </button>
          <button type="button" className={controls.button} autoFocus onClick={keep}>
            Keep the order
          </button>
        </div>
      ) : (
        <div className={styles.choices}>
          {rows.map((row) => (
            <Fragment key={row.action}>
              <button
                ref={row.action === 'cancel' ? cancelButton : undefined}
                type="button"
                className={controls.button}
                data-action={row.action}
                disabled={Boolean(row.why) || decide.isPending}
                title={row.why}
                onClick={() => pick(row.action)}
              >
                {row.label}
              </button>
              <span className={text.note}>{row.note}</span>
            </Fragment>
          ))}
        </div>
      )}
      {decide.error && (
        <p className={text.error} role="alert">
          {decide.error.message}
        </p>
      )}
    </>
  );
}
