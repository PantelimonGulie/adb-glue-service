import { screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { renderPage, stubApi, users } from '../../test/render';
import { Users } from './Users';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('says in plain words what each role can do', async () => {
  stubApi({ '/api/users': [users.viewer, users.operator, users.admin] });
  renderPage(<Users />, { user: users.operator });

  const operator = (await screen.findByText('(you)', { exact: false })).closest('tr')!;
  const cells = within(operator)
    .getAllByRole('cell')
    .map((cell) => cell.textContent);
  expect(cells).toEqual(['operator (you)', 'operator', 'yes', 'yes', 'yes', 'no']);
  const headers = screen.getAllByRole('columnheader').map((cell) => cell.textContent);
  expect(headers).toEqual([
    'Person',
    'Role',
    'See everything',
    'Decide reviews',
    'Ask the assistant',
    'Rules, settings, demo',
  ]);
});
