/**
 * Swizzled (ejected) CopyButton: a visible "Copy" label next to the icon,
 * and a polite live region so screen readers hear "Copied" after a click.
 */
import React, {useCallback, useEffect, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import clsx from 'clsx';
import {useCodeBlockContext} from '@docusaurus/theme-common/internal';
import Button from '@theme/CodeBlock/Buttons/Button';
import IconCopy from '@theme/Icon/Copy';
import IconSuccess from '@theme/Icon/Success';
import type {Props} from '@theme/CodeBlock/Buttons/CopyButton';
import styles from './styles.module.css';

async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const {default: copy} = await import('copy-text-to-clipboard');
  if (!copy(text)) throw new Error('copy failed');
}

export default function CopyButton({className}: Props): ReactNode {
  const {
    metadata: {code},
  } = useCodeBlockContext();
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');
  const timer = useRef<number | undefined>(undefined);

  const onClick = useCallback((e: React.MouseEvent<HTMLElement>) => {
    const button = e.currentTarget;
    window.clearTimeout(timer.current);
    copyToClipboard(code)
      .then(() => {
        setStatus('copied');
        timer.current = window.setTimeout(() => setStatus('idle'), 2000);
      })
      .catch(() => {
        setStatus('failed');
        // select the code so the reader can copy it by hand
        const block = button.closest('.theme-code-block')?.querySelector('pre code');
        if (block) {
          const range = document.createRange();
          range.selectNodeContents(block);
          const sel = window.getSelection();
          sel?.removeAllRanges();
          sel?.addRange(range);
        }
        timer.current = window.setTimeout(() => setStatus('idle'), 4000);
      });
  }, [code]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <>
      <Button
        aria-label={status === 'copied' ? translate({id: 'code.copied', message: 'Copied'}) : translate({id: 'code.copyAria', message: 'Copy code to clipboard'})}
        className={clsx(className, styles.copyButton, status === 'copied' && styles.copied, status === 'failed' && styles.failed)}
        onClick={onClick}>
        {status === 'copied' ? (
          <IconSuccess aria-hidden="true" className={styles.icon} />
        ) : (
          <IconCopy aria-hidden="true" className={styles.icon} />
        )}
        <span className={styles.labels} aria-hidden="true">
          <span data-on={status === 'idle' ? '' : undefined}>{translate({id: 'code.copy', message: 'Copy'})}</span>
          <span data-on={status === 'copied' ? '' : undefined}>{translate({id: 'code.copied', message: 'Copied'})}</span>
          <span data-on={status === 'failed' ? '' : undefined}>{translate({id: 'code.notCopied', message: 'Not copied'})}</span>
        </span>
      </Button>
      <span className="sr-only" role="status" aria-live="polite">
        {status === 'copied' ? translate({id: 'code.copiedClipboard', message: 'Copied to clipboard'}) : status === 'failed' ? translate({id: 'code.copyFailed', message: 'Copy failed. Select the text instead.'}) : ''}
      </span>
    </>
  );
}
