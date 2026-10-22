import { useState } from 'react';
import { useNavigationType } from 'react-router-dom';
import controls from '../../styles/controls.module.css';
import styles from './SearchBox.module.css';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

// The router applies address changes a render late, so an input showing the address drops keys
// typed in between. Typing replaces the address; any other change (Back, a link) resets the text.
export function SearchBox({ value, onChange }: Props) {
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  const navigation = useNavigationType();
  if (value !== seen) {
    setSeen(value);
    if (navigation !== 'REPLACE') setText(value);
  }

  return (
    <input
      type="search"
      className={`${controls.input} ${styles.search}`}
      aria-label="Search order or product"
      placeholder="Search order or product"
      maxLength={64}
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onChange(event.target.value);
      }}
    />
  );
}
