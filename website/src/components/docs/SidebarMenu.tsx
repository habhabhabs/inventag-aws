import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import Link from '@docusaurus/Link';
import type {PropSidebarItem, PropSidebarItemLink, PropSidebarItemCategory} from '@docusaurus/plugin-content-docs';
import Icon from '@site/src/components/docs/Icon';

/**
 * Two-level docs menu shared by the phone drawer and the desktop sidebar:
 * "Get started" pages as icon rows, other sections as rows that open their
 * own page list, with a back button.
 */

const SECTION_ICON: Record<string, string> = {
  'nav-cat-start': 'rocket',
  'nav-cat-guides': 'book',
  'nav-cat-templates': 'layers',
  'nav-cat-examples': 'terminal',
  'nav-cat-reference': 'file',
  'nav-cat-security': 'shield',
  'nav-cat-contrib': 'code',
};

function pageIcon(item: PropSidebarItemLink): string {
  const h = item.href;
  if (/introduction/.test(h)) return 'info';
  if (/installation/.test(h)) return 'download';
  if (/quick-start/.test(h)) return 'terminal';
  if (/status/.test(h)) return 'check';
  return 'book';
}

function hasActive(item: PropSidebarItem, path: string): boolean {
  if (item.type === 'link') return item.href === path;
  if (item.type === 'category') return item.href === path || item.items.some((i) => hasActive(i, path));
  return false;
}

function Row({item, path, onGo, icon}: {item: PropSidebarItemLink; path: string; onGo: () => void; icon?: string}): ReactNode {
  const active = item.href === path;
  return (
    <li>
      <Link
        to={item.href}
        className={`it-mnav__row${active ? ' is-active' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={onGo}>
        {icon && <Icon name={icon} size={18} />}
        <span>{item.label}</span>
      </Link>
    </li>
  );
}

/** One folder in the page tree: a toggle with its own indented, guided children. */
function Branch({item, path, onGo}: {item: PropSidebarItemCategory; path: string; onGo: () => void}): ReactNode {
  const [open, setOpen] = useState(hasActive(item, path) || !item.collapsed);
  return (
    <li className="it-tree__branch">
      <button type="button" className="it-tree__toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name="chevron-right" size={14} />
        <span>{item.label}</span>
      </button>
      {open && (
        <ul className="it-tree__list">
          {item.href && (
            <Row item={{type: 'link', href: item.href, label: translate({id: 'menu.sectionOverview', message: '{label} overview'}, {label: item.label})}} path={path} onGo={onGo} />
          )}
          <Pages items={item.items} path={path} onGo={onGo} />
        </ul>
      )}
    </li>
  );
}

function Pages({items, path, onGo}: {items: readonly PropSidebarItem[]; path: string; onGo: () => void}): ReactNode {
  return (
    <>
      {items.map((item, i) => {
        if (item.type === 'link') return <Row key={item.href} item={item} path={path} onGo={onGo} />;
        if (item.type === 'category') return <Branch key={`${item.label}-${i}`} item={item} path={path} onGo={onGo} />;
        return null;
      })}
    </>
  );
}

export default function SidebarMenu({sidebar, path, onGo}: {sidebar: readonly PropSidebarItem[]; path: string; onGo?: () => void}): ReactNode {
  const close = () => onGo?.();
  const categories = sidebar.filter((i): i is PropSidebarItemCategory => i.type === 'category');
  const start = categories.find((c) => c.className?.includes('nav-cat-start'));
  const rest = categories.filter((c) => c !== start);
  const links = sidebar.filter((i): i is PropSidebarItemLink => i.type === 'link');
  const initial = rest.find((c) => hasActive(c, path))?.label ?? null;
  const [open, setOpen] = useState<string | null>(initial);
  const current = rest.find((c) => c.label === open);
  const rootRef = useRef<HTMLDivElement>(null);
  // Set only by a press on a section row or on Back, so focus moves for the
  // reader's own action and not on mount or on a route change.
  const focusNext = useRef<{kind: 'back'} | {kind: 'row'; label: string} | null>(null);
  const openSection = (label: string) => {
    focusNext.current = {kind: 'back'};
    setOpen(label);
  };
  const back = () => {
    if (current) focusNext.current = {kind: 'row', label: current.label};
    setOpen(null);
  };
  useEffect(() => {
    const want = focusNext.current;
    if (!want) return;
    focusNext.current = null;
    const root = rootRef.current;
    if (!root) return;
    if (want.kind === 'back') root.querySelector<HTMLElement>('.it-mnav__back')?.focus();
    else {
      const rows = Array.from(root.querySelectorAll<HTMLElement>('[data-section]'));
      rows.find((r) => r.dataset.section === want.label)?.focus();
    }
  }, [open]);

  if (current) {
    return (
      <div className="it-mnav" ref={rootRef}>
        <button
          type="button"
          className="it-mnav__back"
          aria-label={translate({id: 'menu.backToSections', message: '{section}: back to all sections'}, {section: current.label})}
          onClick={back}>
          <Icon name="chevron-left" size={18} />
          <span>{current.label}</span>
        </button>
        <ul className="it-mnav__list it-tree__list it-tree__list--root">
          {current.href && (
            <Row item={{type: 'link', href: current.href, label: translate({id: 'menu.sectionOverview', message: '{label} overview'}, {label: current.label})}} path={path} onGo={close} />
          )}
          <Pages items={current.items} path={path} onGo={close} />
        </ul>
      </div>
    );
  }

  return (
    <div className="it-mnav" ref={rootRef}>
      <p className="it-mnav__label">{start?.label ?? translate({id: 'menu.getStarted', message: 'Get started'})}</p>
      <ul className="it-mnav__list">
        {links.map((l) => (
          <Row key={l.href} item={{...l, label: translate({id: 'menu.overview', message: 'Overview'})}} path={path} onGo={close} icon="book" />
        ))}
        {start?.items
          .filter((i): i is PropSidebarItemLink => i.type === 'link')
          .map((l) => (
            <Row key={l.href} item={l} path={path} onGo={close} icon={pageIcon(l)} />
          ))}
      </ul>
      <p className="it-mnav__label">{translate({id: 'menu.documentation', message: 'Documentation'})}</p>
      <ul className="it-mnav__list">
        {rest.map((c) => (
          <li key={c.label}>
            <button
              type="button"
              className={`it-mnav__row it-mnav__row--section${hasActive(c, path) ? ' is-current' : ''}`}
              data-section={c.label}
              onClick={() => openSection(c.label)}>
              <Icon name={SECTION_ICON[(c.className ?? '').split(' ').find((n) => n in SECTION_ICON) ?? ''] ?? 'file'} size={18} />
              <span>{c.label}</span>
              <Icon name="chevron-right" size={16} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
