import { act, fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link } from 'react-router-dom';
import { expect, it } from 'vitest';
import { useRange } from '../../lib/range';
import { Address, address, renderPage } from '../../test/render';
import { RangePicker } from './RangePicker';

function Picker() {
  const [range, setRange] = useRange();
  return <RangePicker value={range} onChange={setRange} />;
}

function renderPicker(route: string) {
  return renderPage(
    <>
      <Picker />
      <Address />
      <Link to="/?range=custom&from=2026-09-01&to=2026-09-30">September</Link>
    </>,
    { route },
  );
}

it('keeps a date typed by keyboard while the address catches up', () => {
  renderPicker('/?range=custom&from=2026-10-01&to=2026-10-22');
  const first = screen.getByLabelText('First day') as HTMLInputElement;
  let shownWhileTyping = '';

  // One act holds back the router's update, as keyboard editing does in the browser.
  act(() => {
    fireEvent.change(first, { target: { value: '2026-10-02' } });
    shownWhileTyping = first.value;
  });

  expect(shownWhileTyping).toBe('2026-10-02');
  expect(address().get('from')).toBe('2026-10-02');
});

it('the dates follow the address when it changes from outside', async () => {
  renderPicker('/?range=custom&from=2026-10-01&to=2026-10-22');

  await userEvent.click(screen.getByRole('link', { name: 'September' }));

  expect(screen.getByLabelText('First day')).toHaveValue('2026-09-01');
  expect(screen.getByLabelText('Last day')).toHaveValue('2026-09-30');
});

it('a date that makes no range waits with a message and leaves the address alone', () => {
  renderPicker('/?range=custom&from=2026-10-01&to=2026-10-22');

  fireEvent.change(screen.getByLabelText('First day'), { target: { value: '2026-10-30' } });

  const message = 'The first day must not be after the last day.';
  expect(screen.getByRole('alert')).toHaveTextContent(message);
  expect(screen.getByLabelText('First day')).toHaveValue('2026-10-30');
  expect(address().get('from')).toBe('2026-10-01');
});
