import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { meKey } from '../../auth/session';
import { testClient, users, withClient } from '../../test/render';
import { useConversation, type Said } from './conversation';

const asked = (content: string): Said => ({ role: 'user', content });
const saved = (name: string) => JSON.parse(sessionStorage.getItem(`glue.conversation.${name}`)!);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

it('saves nothing before it knows who is signed in', () => {
  vi.stubGlobal('fetch', () => new Promise(() => {}));
  const { result } = renderHook(useConversation, { wrapper: withClient(testClient()) });

  act(() => result.current[1]((said) => [...said, asked('hi')]));

  expect(result.current[0]).toEqual([asked('hi')]);
  expect(Object.keys(sessionStorage)).toEqual([]);
});

it("reads the new user's conversation when the user changes, and never saves the old one", async () => {
  sessionStorage.setItem('glue.conversation.admin', JSON.stringify([asked('admin asked')]));
  const client = testClient(users.operator);
  const { result } = renderHook(useConversation, { wrapper: withClient(client) });
  act(() => result.current[1]((said) => [...said, asked('operator asked')]));

  act(() => client.setQueryData(meKey, users.admin));

  await waitFor(() => expect(result.current[0]).toEqual([asked('admin asked')]));
  expect(saved('admin')).toEqual([asked('admin asked')]);
  expect(saved('operator')).toEqual([asked('operator asked')]);
});

it('still works when the browser blocks storage', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked');
  });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked');
  });
  const { result } = renderHook(useConversation, {
    wrapper: withClient(testClient(users.operator)),
  });

  act(() => result.current[1]((said) => [...said, asked('hi')]));

  expect(result.current[0]).toEqual([asked('hi')]);
});
