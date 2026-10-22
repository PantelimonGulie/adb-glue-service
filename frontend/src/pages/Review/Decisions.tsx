import { Fragment } from 'react';
import { useDecide } from '../../api/hooks';
import type { ReviewItem } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import styles from './Decisions.module.css';
import { choice, consequence, DECISIONS, unavailable } from './explain';

export function Decisions({ item }: { item: ReviewItem }) {
  const denied = useDenied('decide');
  const decide = useDecide();
  const rows = DECISIONS.map((action) => {
    const refused = unavailable(action, item);
    return {
      action,
      label: choice(action, item),
      why: denied ?? refused,
      note: refused ?? consequence(action, item),
    };
  });

  return (
    <>
      <div className={styles.choices}>
        {rows.map((row) => (
          <Fragment key={row.action}>
            <button
              type="button"
              className={controls.button}
              data-action={row.action}
              disabled={Boolean(row.why) || decide.isPending}
              title={row.why}
              onClick={() => decide.mutate({ id: item.id, action: row.action })}
            >
              {row.label}
            </button>
            <span className={text.note}>{row.note}</span>
          </Fragment>
        ))}
      </div>
      {decide.error && (
        <p className={text.error} role="alert">
          {decide.error.message}
        </p>
      )}
    </>
  );
}
