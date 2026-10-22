import type { DemoButton } from './buttons';
import { CardButton } from './CardButton';
import { DemoCard } from './DemoCard';
import { useDemoRun } from './useDemoRun';

interface Props {
  title: string;
  text: string;
  buttons: DemoButton[];
  unknown?: boolean;
}

export function ActionCard({ title, text, buttons, unknown }: Props) {
  const { run, busy, result, lock } = useDemoRun();
  const note = unknown ? 'Glue could not read which faults are on right now.' : undefined;
  return (
    <DemoCard title={title} text={text} busy={busy} result={result} note={note}>
      {buttons.map(({ action, label, state }) => (
        <CardButton
          key={action}
          label={label}
          state={state}
          {...lock}
          onClick={() => run({ action })}
        />
      ))}
    </DemoCard>
  );
}
