import { useAddressText } from '../../lib/useAddressText';
import controls from '../../styles/controls.module.css';
import styles from './SearchBox.module.css';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function SearchBox({ value, onChange }: Props) {
  const [text, setText] = useAddressText(value);
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
