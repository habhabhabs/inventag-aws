import React, {useEffect, useRef, useState} from 'react';
import useBrokenLinks from '@docusaurus/useBrokenLinks';
import {getChoice, setChoice} from '@site/src/clientModules/analyticsConsent';

const SETTINGS_HASH = '#analytics-settings';

// Small, plain-language consent banner. Shown until the visitor decides,
// and again when they open "Cookie settings" in the footer.
export default function Root({children}) {
  // The footer link "Cookie settings" points at #analytics-settings. The
  // banner only exists in the browser, so tell the build the anchor is real.
  useBrokenLinks().collectAnchor(SETTINGS_HASH.slice(1));

  const [open, setOpen] = useState(false);
  const [fromLink, setFromLink] = useState(false);
  const banner = useRef(null);

  useEffect(() => {
    const update = () => {
      const asked = window.location.hash === SETTINGS_HASH;
      setFromLink(asked);
      setOpen(getChoice() === null || asked);
    };
    update();
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  // While the banner is open, reserve room for it: the footer grows by the
  // banner's height and keyboard focus never scrolls a control underneath it
  // (see `html[data-consent-banner]` in custom.css).
  useEffect(() => {
    const el = banner.current;
    if (!open || !el) return undefined;
    const root = document.documentElement;
    const measure = () => {
      const gap = window.innerHeight - el.getBoundingClientRect().top;
      root.style.setProperty('--consent-banner-space', `${Math.ceil(gap) + 8}px`);
    };
    measure();
    root.setAttribute('data-consent-banner', 'open');
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (observer) observer.observe(el);
    window.addEventListener('resize', measure);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener('resize', measure);
      root.removeAttribute('data-consent-banner');
      root.style.removeProperty('--consent-banner-space');
    };
  }, [open]);

  // Opened from the footer link: move keyboard focus to the banner. On a first
  // visit the banner must not take focus away from the page.
  useEffect(() => {
    if (open && fromLink && banner.current) banner.current.focus();
  }, [open, fromLink]);

  const decide = (value) => {
    setChoice(value);
    setOpen(false);
    if (window.location.hash === SETTINGS_HASH) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    if (fromLink) {
      // Give focus back to the link that opened the banner.
      const link = document.querySelector(`a[href$="${SETTINGS_HASH}"]`);
      if (link) link.focus();
    }
    setFromLink(false);
  };

  return (
    <>
      {children}
      {open && (
        <section
          ref={banner}
          id={SETTINGS_HASH.slice(1)}
          className="consent-banner"
          aria-label="Cookie choice"
          tabIndex={-1}>
          <p>
            <strong>Cookies.</strong> This site uses essential storage only. If you allow it,
            optional analytics cookies show us which pages people read.
          </p>
          <div className="consent-banner__actions">
            <button type="button" className="button consent-banner__button" onClick={() => decide('denied')}>Essential only</button>
            <button type="button" className="button consent-banner__button" onClick={() => decide('granted')}>Allow analytics</button>
          </div>
        </section>
      )}
    </>
  );
}
