import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it } from 'vitest';
import { renderPage, users } from '../../test/render';
import { UserMenu } from './UserMenu';

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
