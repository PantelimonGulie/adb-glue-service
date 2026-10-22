import { Fragment, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAsk } from '../../api/hooks';
import type { Assistant, Turn } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { modelState } from '../../lib/model';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import styles from './Chat.module.css';
import { lookedAt } from './lookedAt';

type Said = Turn & { meta?: string };

const GREETING =
  'Ask me about orders, stock or failures. I only read the activity log and the order history. I cannot change anything.';
const QUESTIONS = [
  'What failed in the last hour?',
  'Which orders need a decision?',
  'Why is the MacBook different on eMAG?',
  'Is the warehouse working?',
];
const PLACEHOLDER = 'Ask a question, e.g. what happened to shop-1042?';
// The API reads only the latest 12 turns, so sending more is wasted.
const HISTORY_TURNS = 12;

export function Chat({ model }: { model?: Assistant['model'] }) {
  const [params] = useSearchParams();
  const [question, setQuestion] = useState(params.get('q') ?? '');
  const [said, setSaid] = useState<Said[]>([]);
  const ask = useAsk();
  const denied = useDenied('ask');
  const notice = model && modelState(model).notice;
  const blocked = denied ?? notice;
  const busy = Boolean(blocked) || ask.isPending;

  function send(asked: string) {
    const history = said.slice(-HISTORY_TURNS).map(({ role, content }) => ({ role, content }));
    setSaid([...said, { role: 'user', content: asked }]);
    setQuestion('');
    ask.mutate(
      { question: asked, history },
      {
        onSuccess: ({ answer, tools, tokens }) => {
          const meta = lookedAt(tools, tokens);
          setSaid((current) => [...current, { role: 'assistant', content: answer, meta }]);
        },
        // The question goes back in the box, so it can be asked again once the cause is fixed.
        onError: () => {
          setSaid(said);
          setQuestion(asked);
        },
      },
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const asked = question.trim();
    if (asked) send(asked);
  }

  return (
    <section className={styles.chat} aria-label="Conversation">
      {notice && <p className={styles.notice}>{notice}</p>}
      <div className={styles.log} role="log">
        <p className={styles.bubble} data-role="assistant">
          {GREETING}
        </p>
        {said.map((turn, index) => (
          <Fragment key={index}>
            <p className={styles.bubble} data-role={turn.role}>
              {turn.content}
            </p>
            {turn.meta && <span className={styles.meta}>{turn.meta}</span>}
          </Fragment>
        ))}
        {ask.isPending && (
          <p className={styles.bubble} data-role="assistant" role="status">
            Thinking… a local model can take a minute.
          </p>
        )}
      </div>
      <div className={styles.quick}>
        {QUESTIONS.map((quick) => (
          <button
            key={quick}
            type="button"
            className={controls.button}
            disabled={busy}
            title={blocked}
            onClick={() => send(quick)}
          >
            {quick}
          </button>
        ))}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <input
          className={controls.input}
          aria-label="Question"
          value={question}
          maxLength={1000}
          placeholder={denied ?? PLACEHOLDER}
          disabled={Boolean(denied)}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" className={controls.button} disabled={busy} title={blocked}>
          Ask
        </button>
      </form>
      {ask.error && (
        <p className={`${text.error} ${styles.error}`} role="alert">
          {ask.error.message}
        </p>
      )}
    </section>
  );
}
