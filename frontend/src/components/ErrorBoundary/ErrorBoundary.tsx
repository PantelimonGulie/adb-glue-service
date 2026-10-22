import { Component, type ReactNode } from 'react';
import controls from '../../styles/controls.module.css';
import { EmptyState } from '../EmptyState/EmptyState';
import styles from './ErrorBoundary.module.css';

interface Props {
  children: ReactNode;
  resetKey?: string;
}

interface State {
  failed: boolean;
  resetKey?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true };
  }

  // A new page gets a fresh start; without this, one crash would stick to every page.
  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey === state.resetKey ? null : { failed: false, resetKey: props.resetKey };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className={styles.fallback} role="alert">
        <EmptyState title="Something went wrong on this page">
          Reload the page to try again. Orders keep moving in the background.
        </EmptyState>
        <button type="button" className={controls.button} onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    );
  }
}
