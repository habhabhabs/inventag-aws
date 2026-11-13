/**
 * Swizzled (ejected) CodeBlock/Layout: every code block gets a slim header
 * with the file title or language on the left and the buttons on the right,
 * so the copy button never sits on top of the code (it used to cover the
 * end of long lines on phones).
 *
 * Blocks longer than COLLAPSE_AFTER lines (long command output, big config
 * files) start collapsed to PREVIEW_LINES with a "Show all N lines" button.
 * Without JavaScript they render in full (noscript style in docusaurus.config.ts).
 */
import React, {useId, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import clsx from 'clsx';
import {useCodeBlockContext} from '@docusaurus/theme-common/internal';
import Container from '@theme/CodeBlock/Container';
import Title from '@theme/CodeBlock/Title';
import Content from '@theme/CodeBlock/Content';
import Buttons from '@theme/CodeBlock/Buttons';
import type {Props} from '@theme/CodeBlock/Layout';
import styles from './styles.module.css';

const LANGUAGE_LABELS: Record<string, string> = {
  bash: 'Shell',
  sh: 'Shell',
  shell: 'Shell',
  zsh: 'Shell',
  console: 'Terminal',
  powershell: 'PowerShell',
  ps1: 'PowerShell',
  python: 'Python',
  py: 'Python',
  yaml: 'YAML',
  yml: 'YAML',
  json: 'JSON',
  toml: 'TOML',
  ini: 'INI',
  javascript: 'JavaScript',
  js: 'JavaScript',
  typescript: 'TypeScript',
  ts: 'TypeScript',
  groovy: 'Groovy',
  dockerfile: 'Dockerfile',
  docker: 'Dockerfile',
  markdown: 'Markdown',
  md: 'Markdown',
  diff: 'Diff',
  mermaid: 'Mermaid',
  text: 'Text',
  txt: 'Text',
};

function languageLabel(language: string | undefined): string {
  if (!language) return 'Text';
  return LANGUAGE_LABELS[language.toLowerCase()] ?? language.toUpperCase();
}

const COLLAPSE_AFTER = 30;
const PREVIEW_LINES = 18;

export default function CodeBlockLayout({className}: Props): ReactNode {
  const {metadata} = useCodeBlockContext();
  const lineCount = metadata.code.replace(/\n$/, '').split('\n').length;
  const collapsible = lineCount > COLLAPSE_AFTER;
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  return (
    <Container as="div" className={clsx(className, metadata.className)}>
      <div className={styles.header}>
        {metadata.title ? (
          <span className={styles.title}>
            <Title>{metadata.title}</Title>
          </span>
        ) : (
          <span className={styles.language}>{languageLabel(metadata.language)}</span>
        )}
        <div className={styles.actions}>
          {collapsible && (
            <button
              type="button"
              className={styles.expand}
              aria-expanded={expanded}
              aria-controls={contentId}
              onClick={() => setExpanded((v) => !v)}>
              {expanded ? translate({id: 'code.showLess', message: 'Show less'}) : translate({id: 'code.showAll', message: 'Show all {count} lines'}, {count: lineCount})}
            </button>
          )}
          <Buttons className={styles.buttons} />
        </div>
      </div>
      <div
        id={contentId}
        className={clsx(styles.content, collapsible && !expanded && 'code-collapsed')}
        style={collapsible ? ({'--preview-lines': PREVIEW_LINES} as React.CSSProperties) : undefined}>
        <Content />
      </div>
    </Container>
  );
}
