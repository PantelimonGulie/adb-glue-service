import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { analytics, overview, stock } from '../../test/fixtures';
import { renderPage, stubApi } from '../../test/render';
import { Flow } from './Flow';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('clicking a box on the map shows that part and the export follows the range', async () => {
  stubApi({ '/api/analytics': analytics, '/api/overview': overview, '/api/stock': stock });
  renderPage(<Flow />, { route: '/flow?range=today' });

  expect(await screen.findByRole('heading', { name: 'Glue' })).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Bucharest warehouse/ }));

  expect(screen.getByRole('heading', { name: 'Bucharest warehouse' })).toBeInTheDocument();
  expect(screen.getByText('about 14 minutes')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    '/api/analytics.csv?range=today',
  );
});
