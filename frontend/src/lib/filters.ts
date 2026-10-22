import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Page } from '../api/types';

type Changes = Record<string, string | null>;

// Filters live in the address, so links and the Back button keep them. Any change other than
// turning the page starts again from page 1.
export function useFilters() {
  const [params, setParams] = useSearchParams();
  const change = (changes: Changes, options?: { replace?: boolean }) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (!('page' in changes)) next.delete('page');
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      return next;
    }, options);
  const page = Number.parseInt(params.get('page') ?? '', 10);
  return { params, page: page > 0 ? page : 1, change };
}

// A page past the end (the list shrank under the reader, or an old link) starts again from page 1.
export function useBackToFirstPage(
  list: Page<unknown> | undefined,
  { page, change }: ReturnType<typeof useFilters>,
) {
  const past = page > 1 && list !== undefined && list.rows.length === 0 && list.total > 0;
  useEffect(() => {
    if (past) change({ page: null }, { replace: true });
  }, [past, change]);
}

export function oneOf<T extends string>(options: { value: T }[], value: string | null): T {
  return options.find((option) => option.value === value)?.value ?? options[0].value;
}
