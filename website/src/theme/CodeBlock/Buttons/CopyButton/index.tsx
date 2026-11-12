/**
 * Swizzled (ejected) CopyButton: a visible "Copy" label next to the icon,
 * and a polite live region so screen readers hear "Copied" after a click.
 */
import React, {useCallback, useEffect, useRef, useState, type ReactNode} from 'react';
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

  const onClick = useCallback(() => {
    window.clearTimeout(timer.current);
    copyToClipboard(code)
      .then(() => setStatus('copied'))
      .catch(() => setStatus('failed'))
      .finally(() => {
        timer.current = window.setTimeout(() => setStatus('idle'), 2000);
      });
  }, [code]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <>
      <Button
        aria-label={status === 'copied' ? 'Copied' : 'Copy code to clipboard'}
        className={clsx(className, styles.copyButton, status === 'copied' && styles.copied)}
        onClick={onClick}>
        {status === 'copied' ? (
          <IconSuccess aria-hidden="true" className={styles.icon} />
        ) : (
          <IconCopy aria-hidden="true" className={styles.icon} />
        )}
        <span aria-hidden="true">{status === 'copied' ? 'Copied' : 'Copy'}</span>
      </Button>
      <span className="sr-only" role="status" aria-live="polite">
        {status === 'copied' ? 'Copied to clipboard' : status === 'failed' ? 'Copy failed. Select the text instead.' : ''}
      </span>
    </>
  );
}
