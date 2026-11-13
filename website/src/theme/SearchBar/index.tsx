import React, {useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useHistory} from '@docusaurus/router';
import {useActivePlugin, useActiveVersion} from '@docusaurus/plugin-content-docs/client';
// The plugin's own search engine (index + worker). Only the interface is ours.
// @ts-ignore: the plugin ships JavaScript without type declarations
import {fetchIndexesByWorker, searchByWorker} from '@easyops-cn/docusaurus-search-local/dist/client/client/theme/searchByWorker';
// @ts-ignore
import {docsPluginIdForPreferredVersion} from '@easyops-cn/docusaurus-search-local/dist/client/client/utils/proxiedGenerated';
import Icon from '@site/src/components/docs/Icon';

type Hit = {
  document: {i: number; t: string; u: string; h?: string; s?: string; b?: string[]};
  type: number;
  page?: {t: string; b?: string[]};
  tokens: string[];
};

const SUGGESTED: {to: string; title: string; icon: string}[] = [
  {to: 'docs/getting-started/quick-start', title: 'Generate your first report', icon: 'rocket'},
  {to: 'docs/getting-started/installation', title: 'Install InvenTag', icon: 'download'},
  {to: 'docs/reference/cli', title: 'Command-line reference', icon: 'terminal'},
  {to: 'docs/guides/troubleshooting', title: 'Fix common problems', icon: 'help'},
];

function Marked({text, tokens}: {text: string; tokens: string[]}): ReactNode {
  const words = tokens.filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!words.length || !text) return <>{text}</>;
  const parts = text.split(new RegExp(`(${words.join('|')})`, 'ig'));
  return (
    <>
      {parts.map((p, i) =>
        i % 2 ? (
          <mark key={i} className="it-search__mark">
            {p}
          </mark>
        ) : (
          p
        ),
      )}
    </>
  );
}

function hitIcon(type: number): string {
  // Plugin enum order: 0 title, 1 heading, 2 description, 3 content, 4 keywords
  return type === 1 ? 'hash' : type === 3 || type === 2 ? 'lines' : 'file';
}

/**
 * Search as a command palette: a field in the navbar opens a centred dialog
 * with the input, results and keyboard hints. The index and ranking come from
 * @easyops-cn/docusaurus-search-local; this component only draws them.
 */
export default function SearchBar(): ReactNode {
  const {
    siteConfig: {baseUrl},
  } = useDocusaurusContext();
  const history = useHistory();
  const activePlugin = useActivePlugin();
  const activeVersion = useActiveVersion(activePlugin?.pluginId ?? docsPluginIdForPreferredVersion);
  const versionUrl = activeVersion && !activeVersion.isLast ? `${activeVersion.path}/` : baseUrl;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<Hit[]>([]);
  const [active, setActive] = useState(0);
  const [mac, setMac] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const loaded = useRef<string>('');
  const listId = useId();

  useEffect(() => {
    setMac(/Mac|iPhone|iPad/.test(navigator.platform));
  }, []);

  const close = useCallback((returnFocus = true) => {
    setOpen(false);
    setQuery('');
    setHits([]);
    setActive(0);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  // Global shortcut: Ctrl or Cmd + K, and "/" outside text fields.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Load the index on first open, lock page scroll, focus the field.
  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    if (loaded.current !== versionUrl) {
      loaded.current = versionUrl;
      fetchIndexesByWorker(versionUrl, '');
    }
    requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      document.body.style.overflow = '';
    };
  }, [open, versionUrl]);

  useEffect(() => {
    if (!open || !query.trim()) {
      setHits([]);
      return;
    }
    let stale = false;
    const t = setTimeout(async () => {
      const result = await searchByWorker(versionUrl, '', query, 10);
      if (!stale) {
        setHits(result as Hit[]);
        setActive(0);
      }
    }, 80);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [query, open, versionUrl]);

  const navigate = useCallback(
    (url: string) => {
      close(false);
      history.push(url);
    },
    [close, history],
  );

  const go = useCallback(
    (hit: Hit) => {
      let url = hit.document.u;
      if (hit.tokens.length) {
        const params = new URLSearchParams();
        hit.tokens.forEach((tok) => params.append('_highlight', tok));
        url += `?${params.toString()}`;
      }
      if (hit.document.h) url += hit.document.h;
      navigate(url);
    },
    [navigate],
  );

  const seeAll = useMemo(() => `${baseUrl}search/?q=${encodeURIComponent(query)}`, [baseUrl, query]);
  const count = hits.length;

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' && count) {
      e.preventDefault();
      setActive((a) => (a + 1) % count);
    } else if (e.key === 'ArrowUp' && count) {
      e.preventDefault();
      setActive((a) => (a - 1 + count) % count);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (hits[active]) go(hits[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  };

  useEffect(() => {
    document.getElementById(`${listId}-${active}`)?.scrollIntoView({block: 'nearest'});
  }, [active, listId]);

  const modal =
    open && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="it-search"
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) close();
            }}>
            <div className="it-search__dialog" role="dialog" aria-modal="true" aria-label="Search documentation">
              <div className="it-search__bar">
                <Icon name="search" size={18} />
                <input
                  ref={inputRef}
                  className="it-search__input"
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={onInputKey}
                  placeholder="Search documentation"
                  aria-label="Search documentation"
                  role="combobox"
                  aria-expanded={count > 0}
                  aria-controls={listId}
                  aria-autocomplete="list"
                  aria-activedescendant={count ? `${listId}-${active}` : undefined}
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                />
                <button type="button" className="it-search__esc" onClick={() => close()}>
                  Esc
                </button>
              </div>
              <div className="it-search__body">
                {count > 0 && (
                  <ul id={listId} role="listbox" aria-label="Results" className="it-search__list">
                    {hits.map((h, i) => {
                      const path = (h.page ? [...(h.page.b ?? []), h.page.t] : (h.document.b ?? [])).join(' › ');
                      return (
                        <li
                          key={`${h.document.i}-${i}`}
                          id={`${listId}-${i}`}
                          role="option"
                          aria-selected={i === active}
                          className={`it-search__hit${i === active ? ' is-active' : ''}`}
                          onMouseMove={() => setActive(i)}
                          onClick={() => go(h)}>
                          <span className="it-search__hit-icon">
                            <Icon name={hitIcon(h.type)} size={16} />
                          </span>
                          <span className="it-search__hit-text">
                            <span className="it-search__hit-title">
                              <Marked text={h.document.t} tokens={h.tokens} />
                            </span>
                            {path && <span className="it-search__hit-path">{path}</span>}
                          </span>
                          <span className="it-search__hit-go" aria-hidden="true">
                            <Icon name="enter" size={16} />
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {!count && query.trim() && (
                  <p className="it-search__empty">
                    No results for <strong>“{query}”</strong>. Try fewer or different words.
                  </p>
                )}
                {!query.trim() && (
                  <div className="it-search__suggest">
                    <p className="it-search__label">Suggested</p>
                    <ul>
                      {SUGGESTED.map((s) => (
                        <li key={s.to}>
                          <a
                            href={`${baseUrl}${s.to}`}
                            className="it-search__hit"
                            onClick={(e) => {
                              e.preventDefault();
                              navigate(`${baseUrl}${s.to}`);
                            }}>
                            <span className="it-search__hit-icon">
                              <Icon name={s.icon} size={16} />
                            </span>
                            <span className="it-search__hit-text">
                              <span className="it-search__hit-title">{s.title}</span>
                            </span>
                            <span className="it-search__hit-go" aria-hidden="true">
                              <Icon name="arrow" size={16} />
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="it-search__foot">
                <span>
                  <kbd>↑</kbd> <kbd>↓</kbd> to move <kbd>↵</kbd> to open
                </span>
                {query.trim() && (
                  <a
                    href={seeAll}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(seeAll);
                    }}>
                    See all results
                  </a>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="navbar__search it-searchwrap">
      <button
        ref={triggerRef}
        type="button"
        className="it-searchbtn"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}>
        <Icon name="search" size={16} />
        <span className="it-searchbtn__label">Search documentation</span>
        <span className="it-searchbtn__keys">
          <kbd>{mac ? '⌘' : 'Ctrl'}</kbd>
          <kbd>K</kbd>
        </span>
      </button>
      {modal}
    </div>
  );
}
