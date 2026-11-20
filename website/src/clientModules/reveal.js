/**
 * Scroll reveal for the landing page and the 404 page (design: audit
 * site-v2-phase1.md, Revision 2, and the architect's rulings). Docs pages have
 * no marks, so nothing happens there.
 *
 * Contract
 * - The hidden state exists only when the head script set `data-it-motion` on
 *   <html> (no reduced motion, IntersectionObserver present) AND this module
 *   added `.is-pending` to an element. Without JavaScript nothing is hidden.
 * - Only elements below the viewport at setup wait. Anything in view is never
 *   hidden. Each element is shown once.
 * - Opacity and an 8 px rise only (src/css/motion.css): no layout shift.
 * - Shown at once, with no transition: on keyboard focus inside the element,
 *   after an in-page jump, during a fast scroll (more than a screen in one
 *   step, or faster than 2.5 screens a second), before printing, and when the
 *   reader switches on reduced motion.
 * - Stagger: one 40 ms step per row inside a group, at most three steps.
 * - Reads (geometry) happen in one pass before writes (classes).
 * - Client-side navigation: Docusaurus calls onRouteDidUpdate after every
 *   render of a new route, also the first; the observer is set up again.
 */
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

const MAX_STEP = 2;
const FAST = 2.5; // screens per second
let io = null;
let jumpUntil = 0;
let lastY = 0;
let lastT = 0;
let wired = false;

const root = () => document.documentElement;
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const enabled = () => root().hasAttribute('data-it-motion') && 'IntersectionObserver' in window && !reduced();

function targets() {
  document.querySelectorAll('[data-reveal-group]').forEach((g) => {
    for (const c of g.children) if (!c.hasAttribute('data-reveal')) c.setAttribute('data-reveal', '');
  });
  return Array.from(document.querySelectorAll('[data-reveal]'));
}

function done(el) {
  el.classList.add('is-done');
  el.style.removeProperty('--it-reveal-i');
}

function instant(el) {
  if (io) io.unobserve(el);
  if (!el.classList.contains('is-pending')) return;
  // .is-done has no transition, so removing .is-pending in the same frame shows it at once
  el.classList.add('is-done');
  el.classList.remove('is-pending');
}

function show(el, step) {
  if (io) io.unobserve(el);
  if (!el.classList.contains('is-pending')) return;
  el.style.setProperty('--it-reveal-i', String(step));
  el.classList.remove('is-pending');
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    el.removeEventListener('transitionend', onEnd);
    done(el);
  };
  const onEnd = (e) => {
    if (e.target === el && e.propertyName === 'opacity') finish();
  };
  el.addEventListener('transitionend', onEnd);
  window.setTimeout(finish, 1000); // a transition that never ends must not stay
}

function revealAll() {
  document.querySelectorAll('[data-reveal].is-pending').forEach(instant);
}

function instantInView() {
  const h = window.innerHeight;
  const waiting = Array.from(document.querySelectorAll('[data-reveal].is-pending'));
  const inView = waiting.filter((el) => {
    const r = el.getBoundingClientRect();
    return r.top < h && r.bottom > 0;
  });
  inView.forEach(instant);
}

function onHit(entries) {
  const hits = entries.filter((e) => e.isIntersecting);
  if (!hits.length) return;
  if (performance.now() < jumpUntil) {
    hits.forEach((e) => instant(e.target));
    return;
  }
  hits.sort((a, b) => (a.target.compareDocumentPosition(b.target) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  const rows = new Map();
  for (const e of hits) {
    const group = e.target.parentElement;
    const top = Math.round(e.boundingClientRect.top);
    let row = rows.get(group);
    if (!row || Math.abs(top - row.top) > 8) row = {i: row ? row.i + 1 : 0, top};
    rows.set(group, row);
    show(e.target, Math.min(row.i, MAX_STEP));
  }
}

function setup() {
  if (io) io.disconnect();
  io = null;
  const els = targets();
  if (!els.length) return;
  if (!enabled()) {
    revealAll();
    return;
  }
  io = new IntersectionObserver(onHit, {rootMargin: '0px 0px 10% 0px', threshold: 0});
  const h = window.innerHeight;
  // one read pass, then one write pass
  const below = els.map((el) => !el.classList.contains('is-done') && el.getBoundingClientRect().top >= h);
  els.forEach((el, i) => {
    if (el.classList.contains('is-done') || el.classList.contains('is-pending')) return;
    if (!below[i]) {
      el.classList.add('is-done');
      return;
    }
    el.classList.add('is-pending');
    io.observe(el);
  });
  lastY = window.scrollY;
  lastT = performance.now();
}

function markJump() {
  jumpUntil = performance.now() + 600;
  // after the browser has moved: everything now in view, bottom strip included
  requestAnimationFrame(() => requestAnimationFrame(instantInView));
}

function wire() {
  if (wired) return;
  wired = true;
  document.addEventListener('focusin', (e) => {
    const el = e.target instanceof Element ? e.target.closest('[data-reveal].is-pending') : null;
    if (el) instant(el);
  });
  window.addEventListener('hashchange', markJump);
  document.addEventListener('click', (e) => {
    const a = e.target instanceof Element ? e.target.closest('a[href*="#"]') : null;
    if (a && a.pathname === window.location.pathname) markJump();
  });
  window.addEventListener(
    'scroll',
    () => {
      if (!io) return;
      const now = performance.now();
      const y = window.scrollY;
      const dt = now - lastT;
      const dy = Math.abs(y - lastY);
      const h = window.innerHeight;
      if (dy > h || (dt > 0 && dt < 200 && (dy / dt) * 1000 > FAST * h)) {
        jumpUntil = now + 300;
        instantInView();
      }
      lastY = y;
      lastT = now;
    },
    {passive: true},
  );
  window.addEventListener('beforeprint', revealAll);
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  const onChange = () => {
    if (!mq.matches) return;
    root().removeAttribute('data-it-motion');
    if (io) io.disconnect();
    io = null;
    revealAll();
  };
  if (mq.addEventListener) mq.addEventListener('change', onChange);
  else if (mq.addListener) mq.addListener(onChange);
}

export function onRouteDidUpdate() {
  if (!ExecutionEnvironment.canUseDOM) return;
  wire();
  // the new page is in the DOM; wait one frame for its layout
  requestAnimationFrame(setup);
}
