import { Fragment, useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAsk } from '../../api/hooks';
import type { Assistant } from '../../api/types';
import { useDenied } from '../../auth/useDenied';
import { modelState } from '../../lib/model';
import controls from '../../styles/controls.module.css';
import text from '../../styles/text.module.css';
import styles from './Chat.module.css';
import { useConversation, type Said } from './conversation';
import { lookedAt } from './lookedAt';

const GREETING =
  'Ask me about orders, stock or failures. I only read the activity log and the order history. I cannot change anything.';
const QUESTIONS = [
  'What failed in the last hour?',
  'Which orders need a decision?',
  'Why is the MacBook different on eMAG?',
  'Is the warehouse working?',
];
const PLACEHOLDER = 'Ask a question, e.g. which orders failed today?';
const VIEWER_NOTE = 'You can read this page. Only operators and admins can ask.';
// The API reads only the latest 12 turns, so sending more is wasted.
const HISTORY_TURNS = 12;

export function Chat({ model }: { model?: Assistant['model'] }) {
  const [params, setParams] = useSearchParams();
  const linked = params.get('q');
  const [question, setQuestion] = useState(linked ?? '');
  const [said, setSaid] = useConversation();
  const ask = useAsk();
  const denied = useDenied('ask');
  const notice = model && modelState(model).notice;
  const blocked = denied ?? notice;
  const busy = Boolean(blocked) || ask.isPending;
  // "Ask the assistant about this order" links here with the question; it is asked once the
  // model can answer, and leaves the address so Back or a reload does not ask it again.
  const askLinked = Boolean(linked) && model !== undefined && !blocked;

  // The question joins the conversation with its answer; until then it shows as pending.
  function send(asked: string) {
    const history = said.slice(-HISTORY_TURNS).map(({ role, content }) => ({ role, content }));
    ask.mutate(
      { question: asked, history },
      {
        onSuccess: ({ answer, tools, tokens }) => {
          const meta = lookedAt(tools, tokens);
          const turns: Said[] = [
            { role: 'user', content: asked },
            { role: 'assistant', content: answer, meta },
          ];
          setSaid((current) => [...current, ...turns]);
          setQuestion((current) => (current === asked ? '' : current));
        },
        // The question goes back in the box, so it can be asked again once the cause is fixed.
        onError: () => setQuestion(asked),
      },
    );
  }

  useEffect(() => {
    if (askLinked && linked) {
      setParams({}, { replace: true });
      send(linked);
    }
    // send changes every render; askLinked turns true once, when the model can answer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askLinked]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const asked = question.trim();
    if (!asked) return;
    setQuestion('');
    send(asked);
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
          <>
            <p className={styles.bubble} data-role="user">
              {ask.variables.question}
            </p>
            <p className={styles.bubble} data-role="assistant" role="status">
              Thinking… a local model can take a minute.
            </p>
          </>
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
      {denied && <p className={`${text.note} ${styles.denied}`}>{VIEWER_NOTE}</p>}
      <form className={styles.form} onSubmit={submit}>
        <input
          className={controls.input}
          aria-label="Question"
          value={question}
          maxLength={1000}
          placeholder={PLACEHOLDER}
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
