import React, {useCallback, useEffect, useRef, useState, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import {useLocation} from '@docusaurus/router';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Icon from './Icon';

/** Browser speech voices are matched on these language tags. */
const SPEECH_LANG: Record<string, string> = {
  en: 'en-US',
  'zh-Hans': 'zh-CN',
  'zh-Hant': 'zh-TW',
  es: 'es-ES',
  fr: 'fr-FR',
};
const RATES = [1, 1.25, 1.5, 0.85];
const SKIP = 'pre, table, button, svg, .hash-link, .theme-code-block, .it-codeblock, [aria-hidden="true"]';

/** The sentences of the article, in order. Code blocks, tables and controls are not read. */
function collectText(): string[] {
  const root = document.querySelector('.theme-doc-markdown');
  if (!root) return [];
  const parts: string[] = [];
  root.querySelectorAll('h1, h2, h3, h4, p, li, blockquote > *').forEach((el) => {
    if (el.closest('pre, table')) return;
    if (el.tagName === 'P' && el.parentElement?.tagName === 'LI') return; // the <li> carries it
    const clone = el.cloneNode(true) as HTMLElement;
    clone.querySelectorAll(`${SKIP}, ul, ol`).forEach((n) => n.remove());
    const text = (clone.textContent ?? '').replace(/\s+/g, ' ').trim();
    if (text) parts.push(/[.!?。！？:：]$/.test(text) ? text : `${text}.`);
  });
  // short chunks keep long pages from stalling in some browsers
  return parts.flatMap((p) => p.match(/[^.!?。！？]+[.!?。！？]*\s*/g) ?? [p]).map((s) => s.trim()).filter(Boolean);
}

type State = 'idle' | 'playing' | 'paused';

export default function ReadAloud(): ReactNode {
  const {i18n} = useDocusaurusContext();
  const {pathname} = useLocation();
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<State>('idle');
  const [rateIndex, setRateIndex] = useState(0);
  const run = useRef(0); // bumped to invalidate a running queue

  const lang = SPEECH_LANG[i18n.currentLocale] ?? i18n.currentLocale;

  const stop = useCallback(() => {
    run.current += 1;
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* speech not available */
    }
    setState('idle');
  }, []);

  useEffect(() => {
    setSupported(typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window);
  }, []);
  // leaving the page (or changing language) ends the reading
  useEffect(() => stop, [pathname, stop]);

  const speak = useCallback(
    (rate: number) => {
      const sentences = collectText();
      if (!sentences.length) return;
      const synth = window.speechSynthesis;
      synth.cancel();
      const id = ++run.current;
      const voices = synth.getVoices();
      const voice =
        voices.find((v) => v.lang.replace('_', '-').toLowerCase() === lang.toLowerCase()) ??
        voices.find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
      sentences.forEach((text, i) => {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = lang;
        u.rate = rate;
        if (voice) u.voice = voice;
        if (i === sentences.length - 1) u.onend = () => id === run.current && setState('idle');
        u.onerror = (e) => {
          if (id === run.current && e.error !== 'interrupted' && e.error !== 'canceled') setState('idle');
        };
        synth.speak(u);
      });
      setState('playing');
    },
    [lang],
  );

  if (!supported) return null;

  const label = {
    start: translate({id: 'listen.start', message: 'Listen to this page'}),
    pause: translate({id: 'listen.pause', message: 'Pause'}),
    resume: translate({id: 'listen.resume', message: 'Resume'}),
    stop: translate({id: 'listen.stop', message: 'Stop'}),
    group: translate({id: 'listen.group', message: 'Read this page aloud'}),
    speed: translate({id: 'listen.speed', message: 'Speed {rate}×'}, {rate: String(RATES[rateIndex])}),
  };

  const togglePause = () => {
    const synth = window.speechSynthesis;
    if (state === 'playing') {
      synth.pause();
      setState('paused');
    } else {
      synth.resume();
      setState('playing');
    }
  };
  const nextRate = () => {
    const next = (rateIndex + 1) % RATES.length;
    setRateIndex(next);
    if (state !== 'idle') speak(RATES[next]); // restarts the page at the new speed
  };

  return (
    <div className="it-listen" role="group" aria-label={label.group}>
      {state === 'idle' ? (
        <button type="button" className="it-listen__btn it-listen__btn--primary" onClick={() => speak(RATES[rateIndex])}>
          <Icon name="volume" size={16} />
          {label.start}
        </button>
      ) : (
        <>
          <button type="button" className="it-listen__btn it-listen__btn--primary" onClick={togglePause}>
            <Icon name={state === 'playing' ? 'pause' : 'volume'} size={16} />
            {state === 'playing' ? label.pause : label.resume}
          </button>
          <button type="button" className="it-listen__btn" onClick={stop}>
            {label.stop}
          </button>
        </>
      )}
      <button type="button" className="it-listen__btn" onClick={nextRate}>
        {label.speed}
      </button>
    </div>
  );
}
