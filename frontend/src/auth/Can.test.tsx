import { screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { renderPage, users } from '../test/render';
import { Can } from './Can';

const demoButton = (
  <Can permission="demo" fallback={<p>Only admins can use demo controls</p>}>
    <button>Stop answering</button>
  </Can>
);

it('Can hides demo for operator', () => {
  renderPage(demoButton, { user: users.operator });

  expect(screen.queryByRole('button', { name: 'Stop answering' })).toBeNull();
  expect(screen.getByText('Only admins can use demo controls')).toBeInTheDocument();
});

it('Can shows demo for admin', () => {
  renderPage(demoButton, { user: users.admin });

  expect(screen.getByRole('button', { name: 'Stop answering' })).toBeInTheDocument();
});
