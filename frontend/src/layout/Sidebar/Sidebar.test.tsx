import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { overview } from '../../test/fixtures';
import { renderPage, stubApi } from '../../test/render';
import { Sidebar } from './Sidebar';

const systems = {
  shop: { ok: true, state: 'ok', latency_ms: 3 },
  emag: { ok: true, state: 'rate_limited', latency_ms: 4 },
  warehouse: { ok: false, state: 'slow', latency_ms: null },
};

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

it('says how each system is doing in plain words, with a reason on hover', async () => {
  stubApi({ '/api/overview': { ...overview, systems } });
  renderPage(<Sidebar />);

  const list = screen.getByRole('list');
  const emag = await within(list).findByText('limiting requests');
  expect(emag.closest('li')).toHaveAttribute(
    'title',
    'eMAG: limiting requests. It asks Glue to slow down, so Glue waits before it sends more.',
  );
  expect(within(list).getByText('slow')).toBeInTheDocument();
  expect(within(list).getByText('working')).toBeInTheDocument();
});

it('remembers that the menu was collapsed', async () => {
  stubApi({ '/api/overview': overview });
  const first = renderPage(<Sidebar />);

  await userEvent.click(screen.getByRole('button', { name: 'Collapse menu' }));
  first.unmount();
  renderPage(<Sidebar />);

  expect(screen.getByRole('button', { name: 'Expand menu' })).toBeInTheDocument();
});
