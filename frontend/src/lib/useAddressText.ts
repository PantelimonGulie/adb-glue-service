import { useState } from 'react';
import { useNavigationType } from 'react-router-dom';

// The router applies address changes a render late, so an input showing the address drops keys
// typed in between. The input keeps its own text and its edits replace the address; any other
// change to the address (Back, a link, a preset) resets the text.
export function useAddressText(value: string): [string, (text: string) => void] {
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  const navigation = useNavigationType();
  if (value !== seen) {
    setSeen(value);
    if (navigation !== 'REPLACE') setText(value);
  }
  return [text, setText];
}
