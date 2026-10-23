import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Brand } from '../../components/Brand/Brand';
import { useSignIn } from '../session';
import styles from './SignIn.module.css';

// Only paths inside the dashboard: "//host" and "/\host" would send the user to another site.
function safeNext(next: string | null): string {
  if (!next?.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/';
  return next.startsWith('/sign-in') ? '/' : next;
}

export function SignIn() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const signIn = useSignIn();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const ended = params.get('ended') === '1';

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = safeNext(params.get('next'));
    signIn.mutate({ username, password }, { onSuccess: () => navigate(next, { replace: true }) });
  }

  return (
    <main className={styles.page}>
      <form className={styles.card} onSubmit={submit}>
        <Brand />
        <div className={styles.heading}>
          <h1>Sign in</h1>
          <p className={styles.note}>Follow orders from the shop and eMAG to the warehouse.</p>
        </div>
        {ended && (
          <p className={styles.ended} role="status">
            Your session ended. Sign in again.
          </p>
        )}
        <label className={styles.field}>
          User name
          <input
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label className={styles.field}>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {signIn.error && (
          <p className={styles.error} role="alert">
            {signIn.error.message}
          </p>
        )}
        <button className={styles.submit} disabled={signIn.isPending}>
          Sign in
        </button>
        <p className={styles.note}>
          Demo users: viewer, operator and admin. Unless it was changed, each password is the same as
          the user name.
        </p>
      </form>
    </main>
  );
}
