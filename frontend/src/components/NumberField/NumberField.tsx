import { useId } from 'react';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';

interface Props {
  label: string;
  value: string | number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  title?: string;
  error?: string;
  hint?: string;
  onChange?: (value: string) => void;
}

export function NumberField({ label, value, error, hint, onChange, ...input }: Props) {
  const id = useId();
  const note = error ?? hint;
  return (
    <div className={controls.field}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="number"
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? `${id}-note` : undefined}
        readOnly={!onChange}
        onChange={(event) => onChange?.(event.target.value)}
        {...input}
      />
      {note && (
        <span id={`${id}-note`} className={error ? text.error : text.note}>
          {note}
        </span>
      )}
    </div>
  );
}
