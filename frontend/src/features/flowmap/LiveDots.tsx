import styles from './LiveDots.module.css';
import { PATHS } from './layout';
import { useLiveDots } from './useLiveDots';

export function LiveDots() {
  const { dots, summary, finish } = useLiveDots();
  return (
    <>
      {dots.map((dot) => (
        <span
          key={dot.id}
          className={styles.dot}
          data-motion={dot.motion}
          style={{
            background: `var(--tone-${dot.tone}-dot)`,
            offsetPath: `path('${PATHS[dot.route]}')`,
            animationDelay: `${dot.delay}s`,
          }}
          onAnimationEnd={() => finish(dot.id)}
        />
      ))}
      {summary && <span className={styles.summary}>{summary}</span>}
    </>
  );
}
