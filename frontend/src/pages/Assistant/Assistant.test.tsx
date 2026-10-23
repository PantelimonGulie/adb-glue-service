import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { assistant } from '../../test/fixtures';
import { failure, lastBody, renderPage, stubApi, users } from '../../test/render';
import { Assistant } from './Assistant';

const ASK = '/api/assistant/ask';
const answer = {
  answer: 'It was reserved at 10:41.',
  tools: ['get_order', 'get_stock', 'get_order'],
  tokens: 912,
};
const downloading = {
  ...assistant,
  model: { ...assistant.model, status: 'downloading', progress: 0.34 },
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const question = () => screen.getByRole('textbox', { name: 'Question' });

it('asks the question from the address as soon as the model is ready', async () => {
  const fetch = stubApi({ '/api/assistant': assistant, [ASK]: answer });
  renderPage(<Assistant />, {
    user: users.operator,
    route: '/assistant?q=What+happened+to+emag-500124%3F',
  });

  expect(await screen.findByText('It was reserved at 10:41.')).toBeInTheDocument();
  expect(lastBody(fetch, ASK)).toEqual({ question: 'What happened to emag-500124?', history: [] });
  expect(fetch.mock.calls.filter(([path]) => path === ASK)).toHaveLength(1);
  expect(question()).toHaveValue('');
});

it('keeps the conversation when the page is left and opened again', async () => {
  stubApi({ '/api/assistant': assistant, [ASK]: answer });
  const first = renderPage(<Assistant />, { user: users.operator });
  await screen.findByText('Ready');
  await userEvent.type(question(), 'What happened to shop-1041?');
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
  await screen.findByText('It was reserved at 10:41.');
  first.unmount();

  renderPage(<Assistant />, { user: users.operator });

  expect(screen.getByText('What happened to shop-1041?')).toBeInTheDocument();
  expect(screen.getByText('It was reserved at 10:41.')).toBeInTheDocument();
});

it('asks with the conversation so far and shows what each answer looked at', async () => {
  const fetch = stubApi({ '/api/assistant': assistant, [ASK]: answer });
  renderPage(<Assistant />, { user: users.operator });
  await screen.findByText('Ready');

  await userEvent.type(question(), 'What happened to shop-1041?');
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }));

  expect(await screen.findByText('It was reserved at 10:41.')).toBeInTheDocument();
  expect(screen.getByText('Looked at: order history, stock · 912 tokens')).toBeInTheDocument();
  expect(question()).toHaveValue('');

  await userEvent.click(screen.getByRole('button', { name: 'Is the warehouse working?' }));

  await waitFor(() =>
    expect(lastBody(fetch, ASK)).toEqual({
      question: 'Is the warehouse working?',
      history: [
        { role: 'user', content: 'What happened to shop-1041?' },
        { role: 'assistant', content: 'It was reserved at 10:41.' },
      ],
    }),
  );
});

it('shows why the assistant could not answer and keeps the question', async () => {
  const spent =
    "Today's token budget is spent. It resets at midnight UTC, or an admin can raise it.";
  stubApi({ '/api/assistant': assistant, [ASK]: failure(429, spent) });
  renderPage(<Assistant />, { user: users.operator });
  await screen.findByText('Ready');

  await userEvent.type(question(), 'Which orders need a decision?');
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }));

  expect(await screen.findByRole('alert')).toHaveTextContent(spent);
  expect(question()).toHaveValue('Which orders need a decision?');
});

it('says the local model is downloading and waits for it', async () => {
  stubApi({ '/api/assistant': downloading });
  renderPage(<Assistant />, { user: users.operator });

  const notice = 'Downloading the local model, about 2 GB, one time · 34%';
  expect(await screen.findByText(new RegExp(notice))).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Is the warehouse working?' })).toBeDisabled();
});

it('a viewer sees why they cannot ask', async () => {
  stubApi({ '/api/assistant': assistant });
  renderPage(<Assistant />, { user: users.viewer });
  await screen.findByText('Ready');

  expect(question()).toBeDisabled();
  expect(question()).toHaveAttribute('placeholder', expect.stringMatching(/^Ask a question/));
  expect(
    screen.getByText('You can read this page. Only operators and admins can ask.'),
  ).toBeInTheDocument();
  const ask = screen.getByRole('button', { name: 'Ask' });
  expect(ask).toBeDisabled();
  expect(ask).toHaveAttribute('title', 'Your role (viewer) cannot do this');
});

it('shows why the assistant settings could not be loaded', async () => {
  stubApi({ '/api/assistant': failure(500, 'The database is busy') });
  renderPage(<Assistant />, { user: users.operator });

  expect(await screen.findByText('The assistant could not be loaded')).toBeInTheDocument();
  expect(screen.getByText('The database is busy')).toBeInTheDocument();
});
