import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import clsx from 'clsx';
import {IconCopy, IconDone} from './Icons';
import styles from './landing.module.css';

type Line = {cmd: string; note?: string};

/**
 * Terminal-style command list with a real, keyboard-operable copy button.
 * The copied text is the commands only (no "$ " prompts, no notes).
 */
export default function CommandSnippet({
  title,
  lines,
  footnote,
}: {
  title: string;
  lines: Line[];
  footnote?: ReactNode;
}): ReactNode {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');
  const timer = useRef<number | undefined>(undefined);
  const codeRef = useRef<HTMLElement>(null);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    window.clearTimeout(timer.current);
    const text = lines.map((l) => l.cmd).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setStatus('copied');
      timer.current = window.setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('failed');
      // select the commands so the reader can copy them by hand
      if (codeRef.current) {
        const range = document.createRange();
        range.selectNodeContents(codeRef.current);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
      timer.current = window.setTimeout(() => setStatus('idle'), 4000);
    }
  };

  return (
    <figure className={styles.terminal} aria-labelledby="terminal-title">
      <div className={styles.terminalBar}>
        <figcaption id="terminal-title" className={styles.terminalTitle}>
          {title}
        </figcaption>
        <button
          type="button"
          className={clsx(styles.copyButton, status === 'copied' && styles.copyButtonDone, status === 'failed' && styles.copyButtonFailed)}
          onClick={copy}
          aria-label={status === 'copied' ? translate({id: 'code.commandsCopied', message: 'Commands copied'}) : translate({id: 'code.copyAll', message: 'Copy all {count} commands'}, {count: lines.length})}>
          {status === 'copied' ? <IconDone /> : <IconCopy />}
          <span className={styles.copyLabels} aria-hidden="true">
            <span data-on={status === 'idle' ? '' : undefined}>{translate({id: 'code.copy', message: 'Copy'})}</span>
            <span data-on={status === 'copied' ? '' : undefined}>{translate({id: 'code.copied', message: 'Copied'})}</span>
            <span data-on={status === 'failed' ? '' : undefined}>{translate({id: 'code.notCopied', message: 'Not copied'})}</span>
          </span>
        </button>
        <span className="sr-only" role="status" aria-live="polite">
          {status === 'copied'
            ? translate({id: 'code.copiedClipboard', message: 'Copied to clipboard'})
            : status === 'failed'
              ? translate({id: 'code.copyFailedCommands', message: 'Copy failed. Select the commands instead.'})
              : ''}
        </span>
      </div>
      <pre className={styles.terminalBody} tabIndex={0}>
        <code ref={codeRef}>
          {lines.map((l) => (
            <span key={l.cmd} className={styles.terminalLine}>
              <span className={styles.prompt} aria-hidden="true">
                ${' '}
              </span>
              {l.cmd}
              {l.note && <span className={styles.terminalNote}>{`  # ${l.note}`}</span>}
              {'\n'}
            </span>
          ))}
        </code>
      </pre>
      {footnote && <div className={styles.terminalFoot}>{footnote}</div>}
    </figure>
  );
}
