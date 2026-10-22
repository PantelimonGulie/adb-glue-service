import { useUsers } from '../../api/hooks';
import type { Permission } from '../../api/types';
import { useMe } from '../../auth/session';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Tag } from '../../components/Tag/Tag';
import page from '../../styles/page.module.css';
import table from '../../styles/table.module.css';
import styles from './Users.module.css';

const ABILITIES: { label: string; needs: Permission[] }[] = [
  { label: 'See everything', needs: ['view'] },
  { label: 'Decide reviews', needs: ['decide'] },
  { label: 'Ask the assistant', needs: ['ask'] },
  { label: 'Rules, settings, demo', needs: ['rules', 'settings', 'demo'] },
];

export function Users() {
  const { data, error, isPending } = useUsers();
  const { data: me } = useMe();
  const rows = (data ?? []).map((user) => ({
    ...user,
    you: user.name === me?.name,
    can: ABILITIES.map(({ needs }) => needs.every((name) => user.permissions.includes(name))),
  }));

  return (
    <>
      <div className={page.top}>
        <h1>Users and roles</h1>
        <span className={page.sub}>
          sign in as another user from the menu at the top right to try each role
        </span>
        <span role="status">{isPending && <Tag tone="grey">Loading…</Tag>}</span>
      </div>
      {(error || data) && (
        <section className={table.box} aria-label="Users and roles">
          {error && <EmptyState title="The users could not be loaded">{error.message}</EmptyState>}
          {data && (
            <div className={table.scroll}>
              <table className={table.table}>
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Role</th>
                    {ABILITIES.map(({ label }) => (
                      <th key={label}>{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((user) => (
                    <tr key={user.name}>
                      <td>
                        <b>{user.name}</b>
                        {user.you && <span className={styles.you}> (you)</span>}
                      </td>
                      <td className={table.number}>{user.role}</td>
                      {user.can.map((yes, index) => (
                        <td key={ABILITIES[index].label} data-yes={yes} className={styles.answer}>
                          {yes ? 'yes' : 'no'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}
