import { useStock } from '../api/hooks';
import type { ProductName } from './activity';

// Product names come with the stock list; an unknown code is shown as it is.
export function useProductName(): ProductName {
  const { data: stock } = useStock();
  const names = new Map(stock?.rows.map((row) => [row.sku, row.product]));
  return (sku) => names.get(sku) ?? sku;
}
