import { Workflow } from 'lucide-react';
import styles from './Brand.module.css';

export function Brand() {
  return (
    <span className={styles.brand}>
      <Workflow size={22} />
      <span className={styles.name}>glue</span>
      <span className={styles.chip}>demo · local</span>
    </span>
  );
}
