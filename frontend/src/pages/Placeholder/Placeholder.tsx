import styles from './Placeholder.module.css';

export function Placeholder({ title }: { title: string }) {
  return (
    <div className={styles.top}>
      <h1>{title}</h1>
    </div>
  );
}
