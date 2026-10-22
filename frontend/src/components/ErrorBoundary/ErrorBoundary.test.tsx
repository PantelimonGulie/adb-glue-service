import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { silenceRenderErrors } from '../../test/render';
import { ErrorBoundary } from './ErrorBoundary';

function Broken(): never {
  throw new Error('render failed');
}

beforeEach(silenceRenderErrors);

afterEach(() => {
  vi.unstubAllGlobals();
});

it('shows a plain message and a reload button instead of a blank page', async () => {
  const reload = vi.fn();
  vi.stubGlobal('location', { reload });
  render(
    <ErrorBoundary>
      <Broken />
    </ErrorBoundary>,
  );

  expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong on this page');
  await userEvent.click(screen.getByRole('button', { name: 'Reload' }));
  expect(reload).toHaveBeenCalled();
});

it('recovers when the user moves to another page', () => {
  const { rerender } = render(
    <ErrorBoundary resetKey="/orders">
      <Broken />
    </ErrorBoundary>,
  );

  rerender(
    <ErrorBoundary resetKey="/stock">
      <p>Stock page</p>
    </ErrorBoundary>,
  );

  expect(screen.getByText('Stock page')).toBeInTheDocument();
});
