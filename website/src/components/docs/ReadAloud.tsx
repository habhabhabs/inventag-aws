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

type State = 'idle' | 'starting' | 'playing' | 'paused';

export default function ReadAloud(): ReactNode {
  const {i18n} = useDocusaurusContext();
  const {pathname} = useLocation();
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<State>('idle');
  const [rateIndex, setRateIndex] = useState(0);
  const [note, setNote] = useState(''); // visible message after a failure
  const [announce, setAnnounce] = useState(''); // live region
  const run = useRef(0); // bumped to invalidate a running queue
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  // Chrome can garbage-collect queued utterances and then never fire their events
  const queue = useRef<SpeechSynthesisUtterance[]>([]);
  const sentencesRef = useRef<string[]>([]);
  const indexRef = useRef(0); // sentence being read, kept for Pause and for speed changes
  const groupRef = useRef<HTMLDivElement>(null);
  const noteTimer = useRef<number | undefined>(undefined);
  const focusIdle = useRef(false);

  const lang = SPEECH_LANG[i18n.currentLocale] ?? i18n.currentLocale;

  const cancelQueue = useCallback(() => {
    run.current += 1;
    queue.current = [];
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* speech not available */
    }
  }, []);

  const stop = useCallback(() => {
    cancelQueue();
    setState('idle');
  }, [cancelQueue]);

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
  useEffect(() => {
    setNote('');
    setAnnounce('');
    return stop;
  }, [pathname, stop]);

  // Focus the Listen button after Stop, and after an end or failure when the focus was on a
  // control that has just disappeared (it would otherwise drop to <body>).
  useEffect(() => {
    if (state === 'idle' && focusIdle.current) {
      focusIdle.current = false;
      groupRef.current?.querySelector<HTMLElement>('.it-listen__btn')?.focus();
    }
  }, [state]);
  const focusLostOrInside = () => {
    const el = document.activeElement;
    return !el || el === document.body || !!groupRef.current?.contains(el);
  };

  const fail = useCallback(
    (id: number, hasVoice: boolean, voicesLoaded: boolean) => {
      if (id !== run.current) return;
      if (focusLostOrInside()) focusIdle.current = true;
      cancelQueue();
      setState('idle');
      const msg =
        voicesLoaded && !hasVoice
          ? translate({id: 'listen.noVoice', message: 'No voice for this language on this device.'})
          : translate({id: 'listen.failed', message: 'Reading could not start on this device.'});
      setNote(msg);
      setAnnounce(msg);
      window.clearTimeout(noteTimer.current);
      noteTimer.current = window.setTimeout(() => setNote(''), 6000);
    },
    [cancelQueue],
  );

  const speak = useCallback(
    (rate: number, from = 0, resuming = false) => {
      const all = from === 0 && !resuming ? collectText() : sentencesRef.current;
      if (!all.length) return;
      sentencesRef.current = all;
      const synth = window.speechSynthesis;
      synth.cancel();
      synth.resume(); // a cancel after pause() can leave Chrome paused for the next queue
      queue.current = [];
      const id = ++run.current;
      const voices = voicesRef.current.length ? voicesRef.current : synth.getVoices();
      const voice =
        voices.find((v) => v.lang.replace('_', '-').toLowerCase() === lang.toLowerCase()) ??
        voices.find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
      const voicesLoaded = voices.length > 0;
      let started = false;
      setNote('');
      if (!resuming) setState('starting');
      all.slice(from).forEach((text, k) => {
        const index = from + k;
        const u = new SpeechSynthesisUtterance(text);
        u.lang = lang;
        u.rate = rate;
        if (voice) u.voice = voice;
        u.onstart = () => {
          if (id !== run.current) return;
          indexRef.current = index;
          if (!started) {
            started = true;
            setState('playing');
            if (!resuming) setAnnounce(translate({id: 'listen.status.started', message: 'Reading started.'}));
          }
        };
        if (index === all.length - 1) {
          u.onend = () => {
            if (id !== run.current) return;
            if (focusLostOrInside()) focusIdle.current = true;
            queue.current = [];
            setState('idle');
            setAnnounce(translate({id: 'listen.status.finished', message: 'Reading finished.'}));
          };
        }
        u.onerror = (e) => {
          if (id === run.current && e.error !== 'interrupted' && e.error !== 'canceled') fail(id, !!voice, voicesLoaded);
        };
        queue.current.push(u);
        synth.speak(u);
      });
      // No voice or no audio output: nothing starts, and often no error event arrives.
      window.setTimeout(() => {
        if (id === run.current && !started) fail(id, !!voice, voicesLoaded);
      }, 5000);
    },
    [lang, fail],
  );

  if (!supported) return null;

  const label = {
    start: translate({id: 'listen.start', message: 'Listen to this page'}),
    short: translate({id: 'listen.short', message: 'Listen'}),
    starting: translate({id: 'listen.starting', message: 'Starting…'}),
    pause: translate({id: 'listen.pause', message: 'Pause'}),
    resume: translate({id: 'listen.resume', message: 'Resume'}),
    stop: translate({id: 'listen.stop', message: 'Stop'}),
    group: translate({id: 'listen.group', message: 'Read this page aloud'}),
    speed: translate({id: 'listen.speed', message: 'Speed {rate}×'}, {rate: String(RATES[rateIndex])}),
    speedLabel: translate({id: 'listen.speedLabel', message: 'Reading speed {rate}×. Press to change.'}, {rate: String(RATES[rateIndex])}),
  };

  // Pause is cancel-and-remember: speechSynthesis.pause() does not pause on every browser
  // (notably Chrome on Android) and can leave the queue stuck.
  const togglePause = () => {
    if (state === 'playing') {
      cancelQueue();
      setState('paused');
      setAnnounce(translate({id: 'listen.status.paused', message: 'Paused.'}));
    } else {
      speak(RATES[rateIndex], indexRef.current, true);
      setState('playing');
      setAnnounce('');
    }
  };
  const onStop = () => {
    focusIdle.current = true;
    stop();
    setAnnounce('');
  };
  const nextRate = () => {
    const next = (rateIndex + 1) % RATES.length;
    setRateIndex(next);
    // keeps the place: the current sentence starts again at the new speed
    if (state === 'playing') speak(RATES[next], indexRef.current, true);
  };

  const idle = state === 'idle';
  const starting = state === 'starting';
  return (
    <div ref={groupRef} className={`it-listen${idle || starting ? ' it-listen--idle' : ''}`} role="group" aria-label={label.group}>
      {idle || starting ? (
        <button
          type="button"
          className="it-listen__btn it-listen__btn--idle"
          aria-label={starting ? label.starting : label.start}
          aria-busy={starting ? true : undefined}
          title={label.start}
          onClick={() => !starting && speak(RATES[rateIndex])}>
          <Icon name="volume" size={16} />
          {starting ? label.starting : label.short}
        </button>
      ) : (
        <>
          <button type="button" className="it-listen__btn it-listen__btn--primary" onClick={togglePause}>
            <Icon name={state === 'playing' ? 'pause' : 'volume'} size={16} />
            {state === 'playing' ? label.pause : label.resume}
          </button>
          <button type="button" className="it-listen__btn" onClick={onStop}>
            {label.stop}
          </button>
          <button type="button" className="it-listen__btn" aria-label={label.speedLabel} onClick={nextRate}>
            {label.speed}
          </button>
        </>
      )}
      {note && <span className="it-listen__note">{note}</span>}
      <span className="sr-only" role="status" aria-live="polite">
        {announce}
      </span>
    </div>
  );
}
