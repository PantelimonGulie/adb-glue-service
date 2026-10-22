interface Bounds {
  min: number;
  max: number;
  whole?: boolean;
}

// What was typed into a number field, or undefined when it is empty or out of bounds.
export function numberIn(text: string, { min, max, whole = false }: Bounds): number | undefined {
  const value = Number(text);
  const fits = value >= min && value <= max && (!whole || Number.isInteger(value));
  return text.trim() !== '' && fits ? value : undefined;
}
