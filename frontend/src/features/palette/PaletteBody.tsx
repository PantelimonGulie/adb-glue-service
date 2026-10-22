import { Command } from 'cmdk';
import { useState } from 'react';
import { useStock } from '../../api/hooks';
import { MAIN, PLATFORM } from '../../lib/pages';
import styles from './CommandPalette.module.css';
import { OrderResults } from './OrderResults';
import { useDebounced } from './useDebounced';

const PAGES = [...MAIN, ...PLATFORM];
// Orders are searched once typing pauses and the text could name one, not on every key.
const SEARCH_AFTER_MS = 250;
const SHORTEST_ORDER_SEARCH = 2;

const matches = (text: string, query: string) => text.toLowerCase().includes(query.toLowerCase());

export function PaletteBody({ onOpen }: { onOpen: (to: string) => void }) {
  const [search, setSearch] = useState('');
  const query = search.trim();
  const settled = useDebounced(query, SEARCH_AFTER_MS);
  const { data: stock } = useStock();
  const pages = PAGES.filter((page) => matches(page.label, query));
  const products = (stock?.rows ?? []).filter((row) => matches(`${row.product} ${row.sku}`, query));
  const searchOrders = settled.length >= SHORTEST_ORDER_SEARCH;

  return (
    <>
      <Command.Input
        className={styles.input}
        value={search}
        onValueChange={setSearch}
        maxLength={64}
        placeholder="Type an order number, a product or a page"
      />
      <Command.List className={styles.list} label="Results">
        {pages.map((page) => (
          <Command.Item key={page.to} value={`page ${page.to}`} onSelect={() => onOpen(page.to)}>
            <page.icon size={16} strokeWidth={1.8} />
            {page.label}
            <span className={styles.kind}>page</span>
          </Command.Item>
        ))}
        {products.map((row) => (
          <Command.Item
            key={row.sku}
            value={`product ${row.sku}`}
            onSelect={() => onOpen('/stock')}
          >
            {row.product} · stock
            <span className={styles.kind}>product</span>
          </Command.Item>
        ))}
        {searchOrders ? (
          <OrderResults q={settled} onOpen={onOpen} />
        ) : (
          <Command.Empty>Nothing found.</Command.Empty>
        )}
      </Command.List>
      <p className={styles.keys}>↑ ↓ to move · Enter to open · Esc to close</p>
    </>
  );
}
