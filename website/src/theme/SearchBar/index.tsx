import React, {useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
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

const suggested = (): {to: string; title: string; icon: string}[] => [
  {to: 'docs/getting-started/quick-start', title: translate({id: 'search.suggest.quickstart', message: 'Generate your first report'}), icon: 'rocket'},
  {to: 'docs/getting-started/installation', title: translate({id: 'search.suggest.install', message: 'Install InvenTag'}), icon: 'download'},
  {to: 'docs/reference/cli', title: translate({id: 'search.suggest.cli', message: 'Command-line reference'}), icon: 'terminal'},
  {to: 'docs/guides/troubleshooting', title: translate({id: 'search.suggest.troubleshooting', message: 'Fix common problems'}), icon: 'help'},
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
  const [indexState, setIndexState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [pending, setPending] = useState(false);
  const [slow, setSlow] = useState(false);
  const [announce, setAnnounce] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const loaded = useRef<string>('');
  const listId = useId();

  useEffect(() => {
    setMac(/Mac|iPhone|iPad/.test(navigator.platform));
  }, []);

  const setBackgroundInert = (on: boolean) => {
    const app = document.getElementById('__docusaurus');
    if (!app) return;
    if (on) app.setAttribute('inert', '');
    else app.removeAttribute('inert');
  };

  const close = useCallback((returnFocus = true) => {
    setBackgroundInert(false);
    setOpen(false);
    setQuery('');
    setHits([]);
    setActive(0);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  // Other parts of the site (the 404 page) can open the dialog with a first query
  useEffect(() => {
    const onOpen = (e: Event) => {
      setOpen(true);
      const q = (e as CustomEvent<{query?: string}>).detail?.query;
      if (q) setQuery(q);
    };
    window.addEventListener('inventag:search', onOpen);
    return () => window.removeEventListener('inventag:search', onOpen);
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

  const loadIndex = () => {
    setIndexState('loading');
    Promise.resolve(fetchIndexesByWorker(versionUrl, ''))
      .then(() => setIndexState('ready'))
      .catch(() => {
        loaded.current = '';
        setIndexState('error');
      });
  };

  // Load the index on first open, lock page scroll, focus the field.
  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    // the dialog is portalled to <body>, so the page behind can be made inert
    setBackgroundInert(true);
    if (loaded.current !== versionUrl) {
      loaded.current = versionUrl;
      loadIndex();
    }
    requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      document.body.style.overflow = '';
      setBackgroundInert(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, versionUrl]);

  useEffect(() => {
    if (!open || !query.trim()) {
      setHits([]);
      setPending(false);
      setSlow(false);
      return;
    }
    let stale = false;
    setPending(true);
    const slowTimer = setTimeout(() => !stale && setSlow(true), 150);
    const t = setTimeout(async () => {
      try {
        const result = await searchByWorker(versionUrl, '', query, 10);
        if (!stale) {
          setHits(result as Hit[]);
          setActive(0);
        }
      } catch {
        if (!stale) {
          setHits([]);
          setIndexState('error');
        }
      }
      if (!stale) {
        setPending(false);
        setSlow(false);
      }
    }, 80);
    return () => {
      stale = true;
      clearTimeout(t);
      clearTimeout(slowTimer);
    };
  }, [query, open, versionUrl, indexState === 'ready']);

  const navigate = useCallback(
    (url: string) => {
      close(false);
      history.push(url);
    },
    [close, history],
  );

  const go = useCallback(
    (hit: Hit) => {
      // The target page does not highlight terms, so no `_highlight` parameter is added.
      let url = hit.document.u;
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
    }
  };

  // Escape works from any element in the dialog; Tab stays inside it.
  const onDialogKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === 'Tab') {
      const items = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>('input, button, a[href], [tabindex]:not([tabindex="-1"])') ?? [],
      ).filter((n) => !n.hasAttribute('disabled') && n.getClientRects().length > 0);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (current === first || !dialogRef.current?.contains(current))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (current === last || !dialogRef.current?.contains(current))) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  const loading = !!query.trim() && indexState !== 'ready' && indexState !== 'error';
  const failed = indexState === 'error';
  const searching = !!query.trim() && indexState === 'ready' && pending && !count && slow;
  const empty = !!query.trim() && indexState === 'ready' && !pending && !count;
  const loadingText = translate({id: 'search.loading', message: 'Loading the search index…'});
  const searchingText = translate({id: 'search.searching', message: 'Searching…'});
  const failedText = translate({id: 'search.failed', message: 'Search could not load. Check your connection, then try again.'});
  const emptyText = translate({id: 'search.noResults', message: 'No results for “{query}”. Try fewer or different words.'}, {query});
  const countText =
    count === 1
      ? translate({id: 'search.count.one', message: '1 result'})
      : translate({id: 'search.count', message: '{count} results'}, {count});

  // One polite announcement, 500 ms after the last change (not on every keystroke)
  useEffect(() => {
    if (!open) {
      setAnnounce('');
      return undefined;
    }
    const text = failed ? failedText : loading ? loadingText : empty ? emptyText : count ? countText : '';
    const t = setTimeout(() => setAnnounce(text), 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, failed, loading, empty, count, query]);

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
            <div
              className="it-search__dialog"
              role="dialog"
              aria-modal="true"
              aria-label={translate({id: 'theme.SearchBar.label', message: 'Search documentation'})}
              ref={dialogRef}
              onKeyDown={onDialogKey}>
              <div className="it-search__bar">
                <Icon name="search" size={18} />
                <input
                  ref={inputRef}
                  className="it-search__input"
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={onInputKey}
                  placeholder={translate({id: 'theme.SearchBar.label', message: 'Search documentation'})}
                  aria-label={translate({id: 'theme.SearchBar.label', message: 'Search documentation'})}
                  role="combobox"
                  aria-expanded={count > 0}
                  aria-controls={listId}
                  aria-autocomplete="list"
                  aria-activedescendant={count ? `${listId}-${active}` : undefined}
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                />
                <button type="button" className="it-search__esc" onClick={() => close()} aria-label={translate({id: 'search.close', message: 'Close'})}>
                  <span className="it-search__esc-key" aria-hidden="true">
                    Esc
                  </span>
                  <span className="it-search__esc-word" aria-hidden="true">
                    {translate({id: 'search.close', message: 'Close'})}
                  </span>
                </button>
              </div>
              <div className="it-search__body">
                <p className="sr-only" role="status" aria-live="polite">
                  {announce}
                </p>
                {failed && (
                  <div className="it-search__empty">
                    <p>{failedText}</p>
                    <button
                      type="button"
                      className="it-retry"
                      onClick={() => {
                        loaded.current = versionUrl;
                        loadIndex();
                      }}>
                      {translate({id: 'search.retry', message: 'Try again'})}
                    </button>
                  </div>
                )}
                {!failed && (loading || searching) && <p className="it-search__empty">{loading ? loadingText : searchingText}</p>}
                <ul
                  id={listId}
                  role="listbox"
                  hidden={count === 0}
                  aria-busy={pending && count > 0 ? true : undefined}
                  aria-label={translate({id: 'search.results', message: 'Results'})}
                  className="it-search__list">
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
                {!failed && empty && <p className="it-search__empty">{emptyText}</p>}
                {(!query.trim() || (empty && !failed)) && (
                  <div className="it-search__suggest">
                    <p className="it-search__label">{translate({id: 'search.suggested', message: 'Suggested'})}</p>
                    <ul>
                      {suggested().map((s) => (
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
                  <kbd>↑</kbd> <kbd>↓</kbd> {translate({id: 'search.toMove', message: 'to move'})} <kbd>↵</kbd> {translate({id: 'search.toOpen', message: 'to open'})}
                </span>
                {query.trim() && (
                  <a
                    href={seeAll}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(seeAll);
                    }}>
                    {translate({id: 'search.seeAll', message: 'See all results'})}
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
        <span className="it-searchbtn__label">{translate({id: 'theme.SearchBar.label', message: 'Search documentation'})}</span>
        <span className="it-searchbtn__keys">
          <kbd>{mac ? '⌘' : 'Ctrl'}</kbd>
          <kbd>K</kbd>
        </span>
      </button>
      {modal}
    </div>
  );
}
