import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { renderPage, users } from '../../test/render';
import { UserMenu } from './UserMenu';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

async function openMenu() {
  renderPage(<UserMenu me={users.operator} />);
  const trigger = screen.getByRole('button', { name: 'operator · operator' });
  await userEvent.click(trigger);
  return trigger;
}

it('opens a menu the button points to and focuses its first item', async () => {
  const trigger = await openMenu();

  expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('menu')).toHaveAttribute('id', trigger.getAttribute('aria-controls'));
  expect(screen.getByRole('menuitem', { name: 'Sign in as another user' })).toHaveFocus();
});

it('returns focus to its button when Escape closes it', async () => {
  const trigger = await openMenu();
  screen.getByRole('menuitem', { name: 'Sign out' }).focus();

  await userEvent.keyboard('{Escape}');

  expect(screen.queryByRole('menu')).toBeNull();
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(trigger).toHaveFocus();
});

it('moves between items with the arrow keys', async () => {
  await openMenu();

  await userEvent.keyboard('{ArrowDown}');
  expect(screen.getByRole('menuitem', { name: 'Sign out' })).toHaveFocus();
  await userEvent.keyboard('{ArrowDown}');
  expect(screen.getByRole('menuitem', { name: 'Sign in as another user' })).toHaveFocus();
});

it('signing out forgets every saved assistant conversation, so the next person cannot read it', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
  sessionStorage.setItem('glue.conversation.operator', '[{"role":"user","content":"hi"}]');
  sessionStorage.setItem('glue.other', 'kept');
  await openMenu();

  await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));

  await waitFor(() => expect(location.assign).toHaveBeenCalledWith('/sign-in'));
  expect(sessionStorage.getItem('glue.conversation.operator')).toBeNull();
  expect(sessionStorage.getItem('glue.other')).toBe('kept');
});

it('still signs out when the browser blocks storage', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  vi.stubGlobal('location', { pathname: '/', search: '', assign: vi.fn() });
  sessionStorage.setItem('glue.conversation.operator', '[]');
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
    throw new Error('blocked');
  });
  await openMenu();

  await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));

  await waitFor(() => expect(location.assign).toHaveBeenCalledWith('/sign-in'));
});
