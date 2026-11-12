import React, {useEffect, useState} from 'react';
import {getChoice, setChoice} from '@site/src/clientModules/analyticsConsent';

// Small, plain-language consent banner. Shown until the visitor decides,
// and again when they open "Analytics settings" in the footer.
export default function Root({children}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const update = () => setOpen(getChoice() === null || window.location.hash === '#analytics-settings');
    update();
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const decide = (value) => {
    setChoice(value);
    setOpen(false);
    if (window.location.hash === '#analytics-settings') {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  };
  return (
    <>
      {children}
      {open && (
        <section className="consent-banner" aria-label="Analytics choice">
          <p>
            <strong>Count this visit?</strong> If you allow it, this site uses Google Analytics
            (cookies) to see which pages people read. Nothing is loaded unless you say yes.
          </p>
          <div className="consent-banner__actions">
            <button type="button" className="button button--primary" onClick={() => decide('granted')}>Allow</button>
            <button type="button" className="button button--secondary" onClick={() => decide('denied')}>No thanks</button>
          </div>
        </section>
      )}
    </>
  );
}
