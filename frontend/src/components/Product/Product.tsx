import styles from './Product.module.css';

export function Product({ name, sku }: { name: string; sku: string }) {
  return (
    <span className={styles.product}>
      {name}
      {name !== sku && <small className={styles.code}>{sku}</small>}
    </span>
  );
}
