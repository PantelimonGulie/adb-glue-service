import { FlaskConical } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useDemo } from '../../api/hooks';
import styles from './SampleBanner.module.css';

export function SampleBanner() {
  const { data: demo } = useDemo();
  const { pathname } = useLocation();
  if (!demo?.sample_history) return null;
  return (
    <p className={styles.banner}>
      <FlaskConical size={16} />
      <span>
        <b>Includes sample history:</b> thirty days of made-up orders sit next to the real ones, so
        totals, charts and the activity log include them.
      </span>
      {pathname !== '/demo' && (
        <Link className={styles.link} to="/demo">
          Clear it on Demo controls
        </Link>
      )}
    </p>
  );
}
