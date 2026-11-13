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
  // Short chunks keep long pages from stalling: Chrome on desktop stops an utterance after
  // about 15 seconds. Split after sentence ends (not inside "1.1.3" or "e.g."), then cut
  // anything still long at a comma or space.
  return parts.flatMap(splitSentences).flatMap(splitLong).map((s) => s.trim()).filter(Boolean);
}

const MAX_CHUNK = 160;

function splitSentences(text: string): string[] {
  return text.split(/(?<=[.!?])\s+|(?<=[。！？])/);
}

function splitLong(text: string): string[] {
  const out: string[] = [];
  let rest = text;
  while (rest.length > MAX_CHUNK) {
    const window = rest.slice(0, MAX_CHUNK);
    let cut = Math.max(window.lastIndexOf(', '), window.lastIndexOf('; '), window.lastIndexOf('，'), window.lastIndexOf('、'));
    if (cut < MAX_CHUNK / 2) cut = window.lastIndexOf(' ');
    if (cut < MAX_CHUNK / 2) cut = MAX_CHUNK - 1;
    out.push(rest.slice(0, cut + 1));
    rest = rest.slice(cut + 1);
  }
  if (rest.trim()) out.push(rest);
  return out;
}

type State = 'idle' | 'playing' | 'paused';

export default function ReadAloud(): ReactNode {
  const {i18n} = useDocusaurusContext();
  const {pathname} = useLocation();
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<State>('idle');
  const [rateIndex, setRateIndex] = useState(0);
  const run = useRef(0); // bumped to invalidate a running queue
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  // Chrome can garbage-collect queued utterances and then never fire their events
  const queue = useRef<SpeechSynthesisUtterance[]>([]);

  const lang = SPEECH_LANG[i18n.currentLocale] ?? i18n.currentLocale;

  const stop = useCallback(() => {
    run.current += 1;
    queue.current = [];
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* speech not available */
    }
    setState('idle');
  }, []);

  useEffect(() => {
    const ok = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    setSupported(ok);
    if (!ok) return undefined;
    const synth = window.speechSynthesis;
    // Voices load asynchronously in Chrome and Firefox; getVoices() is empty until then.
    const load = () => {
      voicesRef.current = synth.getVoices();
    };
    load();
    synth.addEventListener?.('voiceschanged', load);
    // A reload or tab close must not leave the browser speaking
    const quiet = () => synth.cancel();
    window.addEventListener('pagehide', quiet);
    return () => {
      synth.removeEventListener?.('voiceschanged', load);
      window.removeEventListener('pagehide', quiet);
    };
  }, []);
  // leaving the page (or changing language) ends the reading
  useEffect(() => stop, [pathname, stop]);

  const speak = useCallback(
    (rate: number) => {
      const sentences = collectText();
      if (!sentences.length) return;
      const synth = window.speechSynthesis;
      synth.cancel();
      synth.resume(); // a cancel after pause() can leave Chrome paused for the next queue
      const id = ++run.current;
      const voices = voicesRef.current.length ? voicesRef.current : synth.getVoices();
      const voice =
        voices.find((v) => v.lang.replace('_', '-').toLowerCase() === lang.toLowerCase()) ??
        voices.find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
      sentences.forEach((text, i) => {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = lang;
        u.rate = rate;
        if (voice) u.voice = voice;
        if (i === sentences.length - 1) {
          u.onend = () => {
            if (id !== run.current) return;
            queue.current = [];
            setState('idle');
          };
        }
        u.onerror = (e) => {
          if (id === run.current && e.error !== 'interrupted' && e.error !== 'canceled') setState('idle');
        };
        queue.current.push(u);
        synth.speak(u);
      });
      setState('playing');
      // No voice or no audio output: nothing starts and no error event arrives. Do not
      // leave the controls stuck on "Pause".
      window.setTimeout(() => {
        if (id === run.current && !synth.speaking && !synth.paused) {
          run.current += 1;
          queue.current = [];
          synth.cancel();
          setState('idle');
        }
      }, 5000);
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
