import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { Funnel } from './Funnel';

const steps = { received: 0, duplicates: 0, sent: 0, first_try: 0, after_retry: 0, failed: 0 };

it('Funnel renders zeros', () => {
  const { container } = render(<Funnel funnel={steps} period="Today" />);

  expect(screen.getAllByRole('listitem')).toHaveLength(6);
  expect(screen.getAllByText('0 · 0.0%')).toHaveLength(6);
  expect(container).not.toHaveTextContent('NaN');
});

it('shares are of every order message, duplicates included', () => {
  const counts = { received: 4, duplicates: 1, sent: 3, first_try: 2, after_retry: 1, failed: 0 };
  render(<Funnel funnel={counts} period="Today" />);

  expect(screen.getByText('Order messages received')).toBeInTheDocument();
  expect(screen.getByText('4 · 100.0%')).toBeInTheDocument();
  expect(screen.getByText('3 · 75.0%')).toBeInTheDocument();
  expect(screen.getAllByText('1 · 25.0%')).toHaveLength(2);
});
