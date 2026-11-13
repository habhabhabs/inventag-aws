import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import Link from '@docusaurus/Link';
import {useLocation} from '@docusaurus/router';
import {getChoice, setChoice} from '@site/src/clientModules/analyticsConsent';

const SETTINGS_HASH = '#analytics-settings';

/**
 * Cookie banner. Essentials only by default: nothing optional loads until
 * the visitor chooses "Allow analytics". "Just the essentials", the close
 * button and ignoring the banner all leave analytics off. It is a labelled
 * region, not a modal: it never traps or steals focus on page load. The
 * "Cookie preferences" button in the footer reopens it and moves focus to it.
 * Details (including the analytics provider) live on /privacy.
 */
export default function Root({children}: {children: ReactNode}): ReactNode {
  const [open, setOpen] = useState(false);
  const [focusRequest, setFocusRequest] = useState(0);
  const [choice, setChoiceState] = useState<'granted' | 'denied' | null>(null);
  const [saved, setSaved] = useState('');
  const {pathname} = useLocation();
  const regionRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  // move focus into the banner only when the visitor opened it on purpose
  useEffect(() => {
    if (open && focusRequest) regionRef.current?.focus();
  }, [open, focusRequest]);

  useEffect(() => {
    const show = (focus: boolean) => {
      setChoiceState(getChoice() as 'granted' | 'denied' | null);
      setSaved('');
      setOpen(true);
      if (focus) setFocusRequest((n) => n + 1);
    };
    if (getChoice() === null) show(false);
    if (window.location.hash === SETTINGS_HASH) show(true); // old links
    const onClick = (e: MouseEvent) => {
      const trigger = (e.target as Element | null)?.closest?.('[data-cookie-preferences]');
      if (trigger) {
        returnFocusRef.current = trigger as HTMLElement;
        show(true);
      }
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  // A link that was pressed keeps its pressed look until the next page is shown
  useEffect(() => {
    let timer: number | undefined;
    const onPress = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.('a.button, a.pagination-nav__link, a.it-card') as HTMLAnchorElement | null;
      if (!a || a.target === '_blank' || a.origin !== window.location.origin) return;
      if (a.pathname === window.location.pathname && a.hash) return; // same-page jump
      a.setAttribute('data-nav-pending', '');
      window.clearTimeout(timer);
      timer = window.setTimeout(() => document.querySelectorAll('[data-nav-pending]').forEach((n) => n.removeAttribute('data-nav-pending')), 10000);
    };
    document.addEventListener('click', onPress);
    return () => {
      document.removeEventListener('click', onPress);
      window.clearTimeout(timer);
    };
  }, []);
  useEffect(() => {
    document.querySelectorAll('[data-nav-pending]').forEach((n) => n.removeAttribute('data-nav-pending'));
  }, [pathname]);

  const decide = (value: 'granted' | 'denied') => {
    const fromFooter = choice !== null || returnFocusRef.current !== null;
    setChoice(value);
    if (fromFooter) {
      setSaved(
        value === 'granted'
          ? translate({id: 'consent.saved.on', message: 'Saved: analytics is on.'})
          : translate({id: 'consent.saved.off', message: 'Saved: analytics is off.'}),
      );
    }
    setOpen(false);
    returnFocusRef.current?.focus();
    returnFocusRef.current = null;
    if (window.location.hash === SETTINGS_HASH) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  };

  // Escape inside the banner: first visit = the close button; reopened from the footer = close, choice unchanged
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Escape') return;
    e.stopPropagation();
    if (choice === null) {
      decide('denied');
    } else {
      setOpen(false);
      returnFocusRef.current?.focus();
      returnFocusRef.current = null;
    }
  };

  const check = (
    <svg className="consent-banner__check" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
  const body =
    choice === 'denied'
      ? translate({id: 'consent.body.off', message: 'Analytics is off. Only the essential cookies are on.'})
      : choice === 'granted'
        ? translate({id: 'consent.body.on', message: 'Analytics is on. You can turn it off here.'})
        : translate({id: 'consent.body', message: 'Only the essential cookies are on: they just remember your choice. Allow one more? It helps me see which pages people find useful.'});

  return (
    <>
      {children}
      <p className="sr-only" role="status" aria-live="polite">
        {saved}
      </p>
      {open && (
        <section
          className="consent-banner"
          aria-label={translate({id: 'consent.region', message: 'Cookie preferences'})}
          tabIndex={-1}
          ref={regionRef}
          onKeyDown={onKeyDown}>
          <button
            type="button"
            className="consent-banner__close"
            aria-label={translate({id: 'consent.close', message: 'Close and keep just the essential cookies'})}
            onClick={() => decide('denied')}>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
              <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>
          <p className="consent-banner__title">{translate({id: 'consent.title', message: 'A tiny cookie confession'})}</p>
          <p>
            <span className="consent-banner__text">{body} </span>
            <Link to="/privacy">{translate({id: 'consent.link', message: 'What’s stored and why'})}</Link>.
          </p>
          <div className="consent-banner__actions">
            <button
              type="button"
              className="button consent-banner__solid"
              aria-pressed={choice === null ? undefined : choice === 'granted'}
              onClick={() => decide('granted')}>
              {choice === 'granted' && check}
              {translate({id: 'consent.allow', message: 'Allow analytics'})}
            </button>
            <button
              type="button"
              className="button button--secondary"
              aria-pressed={choice === null ? undefined : choice === 'denied'}
              onClick={() => decide('denied')}>
              {choice === 'denied' && check}
              {translate({id: 'consent.essentials', message: 'Just the essentials'})}
            </button>
          </div>
        </section>
      )}
    </>
  );
}
