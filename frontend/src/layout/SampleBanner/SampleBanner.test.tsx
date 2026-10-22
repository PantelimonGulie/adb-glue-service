import { screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { demo } from '../../test/fixtures';
import { renderPage, stubApi, users } from '../../test/render';
import { SampleBanner } from './SampleBanner';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('says the dashboard includes sample history and where to clear it', async () => {
  stubApi({ '/api/demo': { ...demo, sample_history: true } });
  renderPage(<SampleBanner />, { user: users.viewer, route: '/orders' });

  expect(await screen.findByText(/Includes sample history/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Clear it on Demo controls' })).toHaveAttribute(
    'href',
    '/demo',
  );
});
