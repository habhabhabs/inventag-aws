import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import Link from '@docusaurus/Link';
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
  const regionRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  // move focus into the banner only when the visitor opened it on purpose
  useEffect(() => {
    if (open && focusRequest) regionRef.current?.focus();
  }, [open, focusRequest]);

  useEffect(() => {
    const show = (focus: boolean) => {
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

  const decide = (value: 'granted' | 'denied') => {
    setChoice(value);
    setOpen(false);
    returnFocusRef.current?.focus();
    returnFocusRef.current = null;
    if (window.location.hash === SETTINGS_HASH) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  };

  return (
    <>
      {children}
      {open && (
        <section className="consent-banner" aria-label="Cookie preferences" tabIndex={-1} ref={regionRef}>
          <button
            type="button"
            className="consent-banner__close"
            aria-label="Close and keep just the essential cookies"
            onClick={() => decide('denied')}>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
              <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>
          <p className="consent-banner__title">A tiny cookie confession</p>
          <p>
            Only the essential cookies are on: they just remember your choice. Allow one more? It helps
            me see which pages people find useful. <Link to="/privacy">What&rsquo;s stored and why</Link>.
          </p>
          <div className="consent-banner__actions">
            <button type="button" className="button consent-banner__solid" onClick={() => decide('granted')}>
              Allow analytics
            </button>
            <button type="button" className="button button--secondary" onClick={() => decide('denied')}>
              Just the essentials
            </button>
          </div>
        </section>
      )}
    </>
  );
}
