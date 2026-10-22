import { Fragment, type ReactNode } from 'react';
import type { SystemName } from '../../api/types';
import styles from './MapNodes.module.css';
import { NODES, type Part } from './layout';
import type { MapView } from './model';

interface Props {
  view: MapView;
  selected?: Part;
  onSelect?: (part: Part) => void;
}

const SYSTEMS: SystemName[] = ['shop', 'emag', 'warehouse'];

interface NodeProps extends Omit<Props, 'view'> {
  part: Part;
  bad?: boolean;
  children: ReactNode;
}

function Node({ part, bad, children, selected, onSelect }: NodeProps) {
  const { left, top, width, height } = NODES[part];
  const shared = {
    className: styles.node,
    style: { left, top, width, minHeight: height },
    'data-part': part,
    'data-bad': bad,
  };
  if (!onSelect) return <div {...shared}>{children}</div>;
  return (
    <button
      type="button"
      {...shared}
      aria-pressed={selected === part}
      onClick={() => onSelect(part)}
    >
      {children}
    </button>
  );
}

export function MapNodes({ view, selected, onSelect }: Props) {
  const { glue } = view;
  return (
    <>
      {SYSTEMS.map((part) => (
        <Node
          key={part}
          part={part}
          bad={view.status[part].bad}
          selected={selected}
          onSelect={onSelect}
        >
          <span className={styles.kicker}>{NODES[part].kicker}</span>
          <span className={styles.title}>{NODES[part].title}</span>
          <span className={styles.status}>{view.status[part].text}</span>
        </Node>
      ))}
      <Node part="glue" selected={selected} onSelect={onSelect}>
        <span className={styles.top}>
          <span className={styles.kicker}>{NODES.glue.kicker}</span>
          <span className={styles.reserved}>{glue.reserved}</span>
        </span>
        <span className={styles.counts}>
          {glue.rows.map((row) => (
            <Fragment key={row.label}>
              <span>{row.label}</span>
              <span className={styles.count} data-tone={row.tone}>
                {row.value}
              </span>
            </Fragment>
          ))}
        </span>
        <span className={styles.kicker}>{view.stockCheck}</span>
      </Node>
    </>
  );
}
