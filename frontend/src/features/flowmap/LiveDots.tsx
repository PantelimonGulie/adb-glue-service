import type { Route } from './layout';
import styles from './LiveDots.module.css';
import { useLiveDots } from './useLiveDots';

export function LiveDots({ paths }: { paths: Record<Route, string> }) {
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
            offsetPath: `path('${paths[dot.route]}')`,
            animationDelay: `${dot.delay}s`,
          }}
          onAnimationEnd={() => finish(dot.id)}
        />
      ))}
      {summary && <span className={styles.summary}>{summary}</span>}
    </>
  );
}
