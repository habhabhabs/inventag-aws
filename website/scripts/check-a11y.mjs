#!/usr/bin/env node
/**
 * Accessibility, layout and keyboard checks for the built site, plus screenshots.
 *
 *   cd website && npm run build
 *   npm run serve:pages -- --port 4173 &   (serves build/ like GitHub Pages, under /inventag-aws/)
 *   npm run check:a11y -- [--base http://localhost:4173/inventag-aws] [--shots ../screenshots] [--quick]
 *
 * Needs Playwright with Chromium. Playwright is NOT a dependency of the site
 * (it would add ~200 MB of browsers); point NODE_PATH at an existing install,
 * e.g. `NODE_PATH=$(npm root -g) npm run check:a11y`, or `npm i -D playwright
 * && npx playwright install chromium` locally. axe-core IS a devDependency.
 *
 * Per page x theme (light, dark) x viewport (320, 390, 768, 1440):
 *   - axe-core: WCAG 2.0/2.1/2.2 A and AA rules plus best practices -> failures
 *   - text contrast >= 4.5:1 (>= 3:1 for large text) against the effective
 *     background, including syntax-highlighting tokens -> failures
 *   - no horizontal page scroll -> failure
 *   - targets: >= 24px everywhere (WCAG 2.5.8) -> failure; >= 44px on touch
 *     viewports (320, 390, 768) -> failure. Links inside sentences are exempt.
 *   - controls that are invisible until hover (opacity 0) -> failure
 *   - buttons and link pills without a >= 3:1 boundary (border or fill
 *     against what is behind them, WCAG 1.4.11) -> failure
 * Once per theme on desktop and phone:
 *   - every Tab stop shows a visible focus indicator
 *   - skip link appears on first Tab and moves focus to the content
 *   - landing copy button and code-block copy buttons work from the keyboard
 *   - theme toggle, version dropdown and the mobile menu work from the keyboard
 *   - the analytics banner is reachable, and Google Analytics is not requested
 *     before consent
 * And: no infinite animations with prefers-reduced-motion.
 * Exit code 1 if anything fails.
 */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({chromium} = require('playwright'));
} catch {
  console.error('Playwright not found. See the header of this file (NODE_PATH=$(npm root -g)).');
  process.exit(2);
}
const AXE_PATH = require.resolve('axe-core/axe.min.js');

const arg = (name, def) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
};
const BASE = arg('--base', 'http://localhost:4173/inventag-aws');
const SHOTS = arg('--shots', null);
const QUICK = process.argv.includes('--quick');

const PAGES = [
  ['landing', '/'],
  ['docs-overview', '/docs'],
  ['intro', '/docs/getting-started/introduction'],
  ['quick-start', '/docs/getting-started/quick-start'],
  ['status', '/docs/getting-started/status'],
  ['cli-guide', '/docs/user-guides/cli-user-guide'],
  ['production-safety', '/docs/user-guides/production-safety'],
  ['archived-intro', '/docs/v4.2.26/getting-started/introduction'],
  ['not-found', '/this-page-does-not-exist'],
];
const VIEWPORTS = [
  ['320', {width: 320, height: 640}, 2, true],
  ['390', {width: 390, height: 844}, 3, true],
  ['768', {width: 768, height: 1024}, 2, true],
  ['1440', {width: 1440, height: 900}, 1, false],
];
const SHOT_PAGES = new Set(['landing', 'intro', 'quick-start', 'cli-guide']);
const SHOT_VIEWPORTS = {'390': {width: 390, height: 844}, '1440': {width: 1440, height: 900}};

function auditInPage(isTouch) {
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lum = ({r, g, b}) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const over = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a),
    g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a),
    a: 1,
  });
  const backgrounds = (el) => {
    const layers = [];
    let gradient = false;
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const img = cs.backgroundImage;
      if (img && img.includes('gradient')) {
        const stops = [...img.matchAll(/rgba?\([^)]+\)/g)].map((m) => parse(m[0]));
        if (stops.length) {
          gradient = true;
          layers.push({stops});
          if (stops.every((s) => s.a === 1)) break;
        }
      }
      const bg = parse(cs.backgroundColor);
      if (bg && bg.a > 0) {
        layers.push({stops: [bg]});
        if (bg.a === 1) break;
      }
    }
    let candidates = [{r: 255, g: 255, b: 255, a: 1}];
    const rootBg = parse(getComputedStyle(document.documentElement).backgroundColor);
    if (rootBg && rootBg.a === 1) candidates = [rootBg];
    for (const layer of layers.reverse()) {
      candidates = layer.stops.flatMap((s) => candidates.map((c) => over(s, c)));
    }
    return candidates;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width < 1 || r.height < 1 || cs.visibility === 'hidden' || cs.display === 'none') return false;
    if (cs.clip && cs.clip.startsWith('rect(0')) return false;
    for (let n = el; n; n = n.parentElement) if (parseFloat(getComputedStyle(n).opacity) === 0) return false;
    return true;
  };
  const rootBg = parse(getComputedStyle(document.documentElement).backgroundColor);
  const fails = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (!t.textContent.trim()) continue;
    const el = t.parentElement;
    if (!el || seen.has(el) || !visible(el)) continue;
    if (el.closest('svg, [aria-hidden="true"], noscript')) continue;
    seen.add(el);
    const cs = getComputedStyle(el);
    const fg = parse(cs.color);
    if (!fg) continue;
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const min = large ? 3 : 4.5;
    let worst = Infinity;
    for (const bg of backgrounds(el)) worst = Math.min(worst, ratio(over(fg, bg), bg));
    if (worst < min) {
      fails.push({
        text: t.textContent.trim().slice(0, 50),
        ratio: Math.round(worst * 100) / 100,
        need: large ? 3 : 4.5,
        color: cs.color,
        where: typeof el.className === 'string' ? el.className.slice(0, 60) : el.tagName,
      });
    }
  }
  const small = [];
  const hidden = [];
  for (const el of document.querySelectorAll('a[href], button, [role="button"], summary, input, select, [tabindex="0"]')) {
    if (el.closest('[aria-hidden="true"], .navbar-sidebar:not(.navbar-sidebar--show *)')) continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.matches('.sr-only, [class*="skipToContent"]')) continue;
    if (parseFloat(cs.opacity) === 0 && !el.closest('.hash-link')) {
      hidden.push(`${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30)}" is invisible until hover`);
    }
    if (el.matches('a.hash-link, pre[tabindex]')) continue;
    const inline = cs.display === 'inline' && el.closest('p, li, td, th, blockquote, .admonition, .alert, .theme-doc-version-banner, figcaption, dd');
    if (inline) continue;
    const min = isTouch ? 44 : 24;
    if (r.height < min - 0.5 || r.width < min - 0.5) {
      small.push(`${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)} (< ${min})`);
    }
  }
  // Buttons and link pills must be identifiable by their own boundary
  // (WCAG 1.4.11): a 1px+ border, or a fill, at >= 3:1 against what is behind.
  const boundary = [];
  const pills = document.querySelectorAll(
    '.button, button, [class*="cellLink"], .pagination-nav__link, .navbar__search-input, ' +
      '.navbar__item.dropdown > .navbar__link, .header-github-link, [class*="backToTopButton"]',
  );
  for (const el of pills) {
    if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
    // icon-only controls identified by their icon, and text-styled buttons
    if (el.matches('.clean-btn.menu__caret, .navbar__toggle, .navbar-sidebar__close, [class*="collapseSidebarButton"], [class*="expandButton"], .footer__button, .menu__link, .hash-link')) continue;
    // the boundary can be the control's own border or fill, or the frame of a
    // tight wrapper (e.g. the prev/next grid, the mobile "On this page" box)
    const boundaryOf = (node) => {
      const cs = getComputedStyle(node);
      const behind = backgrounds(node.parentElement)[0];
      const own = parse(cs.backgroundColor);
      const fill = own && own.a > 0 ? over(own, behind) : behind;
      let b = ratio(fill, behind);
      for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
        const w = parseFloat(cs[`border${side}Width`]);
        const c = parse(cs[`border${side}Color`]);
        if (w >= 1 && c && c.a > 0 && cs[`border${side}Style`] !== 'none') {
          b = Math.max(b, Math.min(ratio(over(c, behind), behind), 21));
        }
      }
      return b;
    };
    let best = boundaryOf(el);
    const er = el.getBoundingClientRect();
    for (let n = el.parentElement, i = 0; n && i < 2 && best < 3; n = n.parentElement, i++) {
      const nr = n.getBoundingClientRect();
      // only a wrapper that hugs the control counts (within 2px on three sides)
      const hugs = [er.left - nr.left, nr.right - er.right, er.top - nr.top].filter((d) => Math.abs(d) <= 2).length >= 2;
      if (hugs) best = Math.max(best, boundaryOf(n));
    }
    if (best < 3) {
      boundary.push(`${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30)}" boundary ${Math.round(best * 100) / 100}:1`);
    }
  }
  return {contrast: fails, small};
}

/** Facts about the element that has keyboard focus now. */
function readFocus() {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  window.__a11yIds = window.__a11yIds || new WeakMap();
  if (!window.__a11yIds.has(el)) window.__a11yIds.set(el, (window.__a11yNext = (window.__a11yNext || 0) + 1));
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const clear = (c) => c === 'transparent' || /,\s*0\)$/.test(c);
  const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2 && !clear(cs.outlineColor);
  const shadow = cs.boxShadow && cs.boxShadow !== 'none';
  const banner = document.querySelector('.consent-banner');
  let coveredByBanner = false;
  if (banner && !banner.contains(el)) {
    const b = banner.getBoundingClientRect();
    coveredByBanner = r.left >= b.left && r.right <= b.right && r.top >= b.top && r.bottom <= b.bottom;
  }
  const cls = typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : '';
  return {
    boundary,
    contrast: fails,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    small,
    hidden,
  };
}

const hydrated = (page) => page.waitForSelector('html[data-has-hydrated="true"]', {timeout: 10000}).catch(() => {});

async function runAxe(page) {
  await page.addScriptTag({path: AXE_PATH});
  return page.evaluate(async () => {
    const r = await window.axe.run(document, {
      runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']},
      resultTypes: ['violations'],
    });
    return r.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
      count: v.nodes.length,
    }));
  });
}

const failures = [];
const warnings = [];
const fail = (s) => failures.push(s);

async function newContext(browser, {viewport, dpr = 1, mobile = false, theme, consent = 'denied', reducedMotion}) {
  const ctx = await browser.newContext({
    viewport,
    deviceScaleFactor: dpr,
    isMobile: mobile,
    hasTouch: mobile,
    colorScheme: theme,
    reducedMotion,
  });
  await ctx.addInitScript(
    ([t, c]) => {
      try {
        if (t) localStorage.setItem('theme', t);
        if (c) localStorage.setItem('inventag-analytics', c);
      } catch (e) {}
    },
    [theme, consent],
  );
  return ctx;
}

const browser = await chromium.launch();
const viewports = QUICK ? VIEWPORTS.filter(([n]) => n === '390' || n === '1440') : VIEWPORTS;

// 1. page sweep
for (const [vName, viewport, dpr, touch] of viewports) {
  for (const theme of ['light', 'dark']) {
    const ctx = await newContext(browser, {viewport, dpr, mobile: touch, theme});
    const page = await ctx.newPage();
    for (const [pName, p] of PAGES) {
      const res = await page.goto(BASE + p, {waitUntil: 'networkidle'});
      const expect404 = pName === 'not-found';
      if (!res || (res.status() >= 400 && !expect404)) {
        fail(`${pName}: HTTP ${res && res.status()}`);
        continue;
      }
      await hydrated(page);
      await page.waitForTimeout(150);
      const tag = `${pName} [${vName}, ${theme}]`;
      const r = await page.evaluate(auditInPage, touch);
      for (const f of r.contrast) fail(`${tag} contrast ${f.ratio}:1 "${f.text}" (${f.color}; ${f.where})`);
      if (r.scrollWidth > r.clientWidth) fail(`${tag} horizontal scroll: ${r.scrollWidth} > ${r.clientWidth}`);
      r.small.forEach((s) => fail(`${tag} target size: ${s}`));
      r.hidden.forEach((s) => fail(`${tag} ${s}`));
      r.boundary.forEach((s) => fail(`${tag} control ${s} (< 3:1, WCAG 1.4.11)`));
      for (const v of await runAxe(page)) {
        fail(`${tag} axe ${v.id} (${v.impact}, ${v.count}x): ${v.help} -> ${v.nodes.join(' | ')}`);
      }
    }
    await ctx.close();
  }
}

// 2. screenshots (consent already decided, so the banner does not cover content)
if (SHOTS) {
  fs.mkdirSync(SHOTS, {recursive: true});
  for (const [vName, viewport] of Object.entries(SHOT_VIEWPORTS)) {
    for (const theme of ['light', 'dark']) {
      const mobile = vName === '390';
      const ctx = await newContext(browser, {viewport, dpr: mobile ? 3 : 2, mobile, theme});
      const page = await ctx.newPage();
      for (const [pName, p] of PAGES.filter(([n]) => SHOT_PAGES.has(n))) {
        await page.goto(BASE + p, {waitUntil: 'networkidle'});
        await page.evaluate(() => document.fonts.ready);
        await page.screenshot({path: path.join(SHOTS, `${pName}-${theme}-${viewport.width}x${viewport.height}.png`)});
      }
      await ctx.close();
    }
    if (seen.has(f.id)) continue;
    seen.add(f.id);
    if (!f.sized) res.failures.push({check: 'focus-visible', detail: `focus on a hidden element: ${f.label}`});
    else if (!f.inView) res.failures.push({check: 'focus-visible', detail: `focus on an off-screen element: ${f.label}`});
    else if (!f.ring) res.failures.push({check: 'focus-visible', detail: `no focus indicator: ${f.label}`});
    if (banner && f.coveredByBanner) res.failures.push({check: 'consent-banner', detail: `banner completely covers focused ${f.label}`});
  }
  res.tabStops = stops;
  if (!stops) res.failures.push({check: 'focus-visible', detail: 'Tab never moved focus to anything'});
}

/** Tab from the top until `test(focus)` is true. Returns the focus facts, or null. */
async function tabTo(page, test, max = 20) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  });
  for (let i = 0; i < max; i++) {
    await page.keyboard.press('Tab');
    const f = await page.evaluate(readFocus);
    if (f && test(f)) return f;
  }
  return null;
}

async function checkMobileMenu(page, pg, vp, theme) {
  const res = newResult(pg, vp, theme, 'menu-open');
  if (!(await open(page, pg, res))) return;
  const fail = (detail) => res.failures.push({check: 'mobile-menu', detail});
  const toggle = await tabTo(page, (f) => f.isToggle);
  if (!toggle) return fail('the menu button cannot be reached with Tab');
  if (!toggle.ring) fail('the menu button has no focus indicator');
  const before = await page.evaluate(() => {
    const t = document.querySelector('.navbar__toggle');
    return {name: t.getAttribute('aria-label') || t.innerText, expanded: t.getAttribute('aria-expanded')};
  });
  if (!before.name) fail('the menu button has no accessible name');
  if (before.expanded !== 'false') fail(`aria-expanded is "${before.expanded}" while the menu is closed`);
  await page.keyboard.press('Enter');
  try {
    await page.waitForFunction(() => {
      const s = document.querySelector('.navbar-sidebar');
      return s && getComputedStyle(s).visibility === 'visible' && s.getBoundingClientRect().left >= 0;
    }, null, {timeout: 3000});
  } catch {
    return fail('Enter on the menu button did not open the menu');
  }
  await page.waitForTimeout(350); // slide-in transition
  const opened = await page.evaluate(() => {
    const s = document.querySelector('.navbar-sidebar').getBoundingClientRect();
    return {
      expanded: document.querySelector('.navbar__toggle').getAttribute('aria-expanded'),
      links: [...document.querySelectorAll('.navbar-sidebar a[href]')].filter((a) => a.getBoundingClientRect().width > 0).length,
      fits: s.right <= window.innerWidth + 0.5,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  });
  if (opened.expanded !== 'true') fail(`aria-expanded is "${opened.expanded}" while the menu is open`);
  if (!opened.links) fail('the open menu shows no links');
  if (!opened.fits || opened.overflow) fail('the open menu is wider than the screen');
  await verifyTheme(page, theme, res);
  await scan(page, res);
  await shot(page, res);
  // Keyboard: opening the menu moves focus into it, and Tab stays inside it.
  const first = await page.evaluate(readFocus);
  if (!first || !first.inMenu) fail(`opening the menu left focus outside it${first ? ` (on ${first.label})` : ''}`);
  else if (!first.ring) fail(`no focus indicator in the menu: ${first.label}`);
  let inside = 0;
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    const f = await page.evaluate(readFocus);
    if (!f) continue; // focus moved to the browser's own controls and comes back
    if (!f.inMenu) {
      fail(`Tab left the open menu and went to ${f.label} behind it`);
      break;
    }
    inside++;
    if (!f.ring) fail(`no focus indicator in the menu: ${f.label}`);
    if (!f.inView || !f.sized) fail(`focus on a hidden menu item: ${f.label}`);
  }
  if (!inside) fail('Tab does not reach the items in the open menu');
  const isClosed = () => page.waitForFunction(() => !document.querySelector('.navbar-sidebar--show'), null, {timeout: 3000}).then(() => true, () => false);
  // Escape closes the menu and gives focus back to the menu button.
  await page.keyboard.press('Escape');
  if (!(await isClosed())) fail('Escape does not close the menu');
  else {
    await page.waitForTimeout(100);
    const back = await page.evaluate(readFocus);
    if (!back || !back.isToggle) fail('closing the menu does not give focus back to the menu button');
    // Open it again and close it with the close button.
    await page.keyboard.press('Enter');
    await page.waitForTimeout(450);
  }
  const close = await page.evaluate(() => {
    const c = document.querySelector('.navbar-sidebar--show .navbar-sidebar__close');
    if (c) c.focus();
    return !!c && document.activeElement === c && !!(c.getAttribute('aria-label') || c.innerText);
  });
  if (!close) return fail('the close button is missing, cannot take focus, or has no accessible name');
  await page.keyboard.press('Enter');
  if (!(await isClosed())) fail('Enter on the close button does not close the menu');
}

async function checkSearch(page, pg, vp, theme) {
  const res = newResult(pg, vp, theme, 'search-open');
  if (!(await open(page, pg, res))) return;
  const fail = (detail) => res.failures.push({check: 'search', detail});
  const indexReady = () => page.waitForSelector('.navbar__search-input[role="combobox"]', {timeout: 10000}).then(() => true, () => false);
  const box = await tabTo(page, (f) => f.isSearch, 30);
  if (!box) return fail('the search box cannot be reached with Tab');
  if (!box.ring) fail('the search box has no focus indicator');
  // The search index loads on first focus (slowed down for this page, see
  // runCombo). Move on before it arrives: focus must stay where the user put it.
  await page.keyboard.press('Tab');
  const moved = await page.evaluate(readFocus);
  if (!(await indexReady())) return fail('the search index did not load');
  await page.waitForTimeout(150);
  const now = await page.evaluate(readFocus);
  if (moved && !moved.isSearch && now && now.isSearch) fail(`focus jumped back to the search box from ${moved.label} when the search index loaded`);
  await page.keyboard.press('Shift+Tab');
  const backIn = await page.evaluate(readFocus);
  if (!backIn || !backIn.isSearch) return fail('Shift+Tab does not go back to the search box');
  await page.keyboard.type('tag', {delay: 30});
  try {
    await page.waitForFunction(() => document.querySelectorAll('.navbar__search [role="option"]').length > 0, null, {timeout: 8000});
  } catch {
    return fail('typing in the search box showed no suggestions');
  }
  await page.waitForTimeout(250);
  const box2 = await page.evaluate(() => {
    const list = document.querySelector('.navbar__search [role="listbox"]').getBoundingClientRect();
    const input = document.querySelector('.navbar__search-input').getBoundingClientRect();
    return {
      left: Math.round(list.left), right: Math.round(list.right), vw: document.documentElement.clientWidth,
      inputWidth: Math.round(input.width),
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  });
  if (box2.left < 0 || box2.right > box2.vw) fail(`the suggestion list runs off the screen (${box2.left}px to ${box2.right}px of ${box2.vw}px)`);
  if (box2.overflow) fail('the open suggestion list makes the page scroll sideways');
  if (box2.inputWidth < 120) fail(`the search box is only ${box2.inputWidth}px wide while typing`);
  await verifyTheme(page, theme, res);
  await scan(page, res);
  await shot(page, res);
  // keyboard: arrow down selects a suggestion, Escape closes the list
  await page.keyboard.press('ArrowDown');
  const active = await page.evaluate(() => {
    const i = document.querySelector('.navbar__search-input');
    const id = i.getAttribute('aria-activedescendant');
    return !!(id && document.getElementById(id));
  });
  if (!active) fail('arrow keys do not select a suggestion');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const closed = await page.evaluate(() => {
    const l = document.querySelector('.navbar__search [role="listbox"]');
    return !l || getComputedStyle(l).display === 'none';
  });
  if (!closed) fail('Escape does not close the suggestion list');
  // A query with no results: the "no results" message is scanned as well.
  await page.focus('.navbar__search-input');
  await page.keyboard.press('Control+A');
  await page.keyboard.type('zzqxv', {delay: 30});
  try {
    await page.waitForFunction(() => {
      const l = document.querySelector('.navbar__search [role="listbox"]');
      return l && getComputedStyle(l).display !== 'none' && !l.querySelector('[role="option"][id]') && l.innerText.trim().length > 0;
    }, null, {timeout: 8000});
  } catch {
    return fail('a query with no results shows no message');
  }
  const empty = await runAxe(page);
  const mark = (v) => ({...v, help: `${v.help} [no-results state]`});
  res.wcag.push(...empty.wcag.map(mark));
  res.advisory.push(...empty.advisory.map(mark));
}

async function checkConsentBanner(page, pg, vp, theme) {
  const res = newResult(pg, vp, theme, 'consent-banner');
  if (!(await open(page, pg, res))) return;
  const fail = (detail) => res.failures.push({check: 'consent-banner', detail});
  try {
    await page.waitForSelector('.consent-banner', {state: 'visible', timeout: 3000});
  } catch {
    res.warnings.push({check: 'consent-banner', detail: 'no consent banner on a first visit; checks skipped'});
    return;
  }
  await verifyTheme(page, theme, res);
  await scan(page, res);
  await shot(page, res);
  const m = await page.evaluate(async () => {
    const b = document.querySelector('.consent-banner');
    const r = b.getBoundingClientRect();
    const nav = document.querySelector('.navbar').getBoundingClientRect();
    const out = {
      height: Math.round(r.height), share: r.height / window.innerHeight,
      offscreen: r.left < 0 || r.right > window.innerWidth || r.top < 0 || r.bottom > window.innerHeight,
      coversNavbar: r.top < nav.bottom,
      stoleFocus: b.contains(document.activeElement),
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
    // Is the end of the page readable when scrolled all the way down?
    window.scrollTo(0, document.documentElement.scrollHeight);
    await new Promise((ok) => setTimeout(ok, 200));
    const b2 = b.getBoundingClientRect();
    const last = [...document.querySelectorAll('footer a, footer .footer__copyright')].filter((e) => e.getBoundingClientRect().height > 0).pop();
    if (last) {
      const range = document.createRange();
      range.selectNodeContents(last);
      const lr = range.getBoundingClientRect();
      out.endHidden = lr.bottom > b2.top && lr.right > b2.left && lr.left < b2.right;
      out.endDetail = `last footer text ends at ${Math.round(lr.bottom)}px, banner starts at ${Math.round(b2.top)}px`;
    }
    window.scrollTo(0, 0);
    return out;
  });
  res.banner = m;
  if (m.offscreen) fail('the banner does not fit on the screen');
  if (m.overflow) fail('the banner makes the page scroll sideways');
  if (m.coversNavbar) fail('the banner covers the navbar');
  if (m.share > 0.5) fail(`the banner covers ${Math.round(m.share * 100)}% of the screen height`);
  if (m.stoleFocus) fail('the banner takes keyboard focus on page load');
  if (m.endHidden) fail(`the banner hides the end of the page (${m.endDetail})`);
  // Tab through the page with the banner open: nothing fully covered, no trap.
  await tabWalk(page, res, TAB_STOPS, {banner: true});
  // Focus must be able to leave the banner in both directions.
  for (const key of ['Tab', 'Shift+Tab']) {
    await page.evaluate((k) => {
      const btns = document.querySelectorAll('.consent-banner button');
      btns[k === 'Tab' ? btns.length - 1 : 0].focus();
    }, key);
    const start = await page.evaluate(readFocus);
    if (!start || !start.inBanner) fail(`the banner buttons cannot take focus (focus is on ${start ? start.label : 'nothing'}; banner ${(await page.$('.consent-banner')) ? 'present' : 'gone'})`);
    else if (!start.ring) fail(`no focus indicator on banner button ${start.label}`);
    await page.keyboard.press(key);
    const f = await page.evaluate(readFocus);
    if (f && f.inBanner) fail(`${key} from the ${key === 'Tab' ? 'last' : 'first'} banner button stays in the banner (focus trap)`);
  }
  // Keyboard can dismiss it, and the choice is stored.
  await page.evaluate(() => {
    // "Essential only" is the first button.
    document.querySelectorAll('.consent-banner button')[0].focus();
  });
  await page.keyboard.press('Enter');
  await page.waitForTimeout(150);
  const after = await page.evaluate(() => ({gone: !document.querySelector('.consent-banner'), choice: localStorage.getItem('inventag-analytics')}));
  if (!after.gone) fail('Enter on "Essential only" does not close the banner');
  if (after.choice !== 'denied') fail(`"Essential only" stored "${after.choice}" instead of "denied"`);
}

async function checkPage(page, pg, vp, theme) {
  const res = newResult(pg, vp, theme, 'default');
  if (!(await open(page, pg, res))) return;
  await verifyTheme(page, theme, res);
  const layout = await page.evaluate(readLayout);
  res.layout = layout;
  const wantMobile = vp.width < DESKTOP_MIN_WIDTH;
  if (layout.mobileLayout !== wantMobile) {
    res.failures.push({check: 'breakpoint', detail: `expected the ${wantMobile ? 'mobile' : 'desktop'} layout at ${vp.width}px`});
  }
  if (layout.scrollWidth > layout.clientWidth) {
    res.failures.push({
      check: 'reflow',
      detail: `page scrolls sideways: ${layout.scrollWidth}px content in a ${layout.clientWidth}px viewport` +
        (layout.offenders.length ? `; caused by ${layout.offenders.join(', ')}` : ''),
    });
  }
  const c = await scan(page, res);
  if (vp.touch) for (const s of c.small) res.warnings.push({check: 'touch-target', detail: `smaller than 44px: ${s}`});
  await shot(page, res);
  await tabWalk(page, res, TAB_STOPS);
}

async function runCombo(browser, vp, theme) {
  const contextOptions = {
    viewport: {width: vp.width, height: vp.height},
    isMobile: vp.touch,
    hasTouch: vp.touch,
    colorScheme: theme,
  };
  const prepare = async (ctx) => {
    // Nothing leaves the machine: fonts, analytics and other third parties are blocked.
    await ctx.route((url) => url.origin !== ORIGIN, (route) => route.abort());
  };
  // 1. Pages, menu and search: consent already answered, so the banner is closed.
  const ctx = await browser.newContext(contextOptions);
  await prepare(ctx);
  // Docusaurus reads the `theme` key from localStorage before first paint and
  // sets <html data-theme>. Setting the key is what the theme switch does.
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      localStorage.setItem('inventag-analytics', 'denied');
    } catch (e) { /* ignore */ }
  }, theme);
  const page = await ctx.newPage();
  for (const pg of PAGES) await checkPage(page, pg, vp, theme);
  for (const pg of PAGES.filter((p) => STATE_PAGES.includes(p.id))) {
    if (vp.width < DESKTOP_MIN_WIDTH) await checkMobileMenu(page, pg, vp, theme);
  }
  await page.close();
  // Search: a fresh page per check, with a slow search index, so the check
  // can leave the search box before the index arrives.
  for (const pg of PAGES.filter((p) => STATE_PAGES.includes(p.id))) {
    const sp = await ctx.newPage();
    await sp.route(/search-index[^/]*\.json/, async (route) => {
      await new Promise((ok) => setTimeout(ok, 600));
      await route.continue();
    });
    await checkSearch(sp, pg, vp, theme);
    await sp.close();
  }
}

// 3. keyboard and behaviour
for (const theme of ['light', 'dark']) {
  // desktop
  {
    const ctx = await newContext(browser, {viewport: {width: 1440, height: 900}, theme});
    await ctx.grantPermissions(['clipboard-read', 'clipboard-write']);
    const page = await ctx.newPage();
    for (const p of ['/', '/docs/getting-started/quick-start']) {
      await page.goto(BASE + p, {waitUntil: 'networkidle'});
      for (let i = 0; i < 40; i++) {
        await page.keyboard.press('Tab');
        const f = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const cs = getComputedStyle(el);
          const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) || (cs.boxShadow && cs.boxShadow !== 'none');
          return {ring, label: `${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30)}"`};
        });
        if (f && !f.ring) fail(`focus not visible [${theme}] ${p}: ${f.label}`);
      }
    }
    // skip link
    await page.goto(BASE + '/docs/getting-started/quick-start', {waitUntil: 'networkidle'});
    await page.keyboard.press('Tab');
    const skip = await page.evaluate(() => {
      const el = document.activeElement;
      const r = el.getBoundingClientRect();
      return {text: el.textContent.trim(), visible: r.width > 1 && r.top >= 0 && r.top < 100};
    });
    if (!/skip/i.test(skip.text) || !skip.visible) fail(`skip link not first or not visible [${theme}]: "${skip.text}"`);
    await page.keyboard.press('Enter');
    await page.keyboard.press('Tab');
    const afterSkip = await page.evaluate(() => !!document.activeElement.closest('main, [id="__docusaurus_skipToContent_fallback"]'));
    if (!afterSkip) fail(`skip link does not move focus into the content [${theme}]`);
    // landing copy button
    await page.goto(BASE + '/', {waitUntil: 'networkidle'});
    await hydrated(page);
    const copyBtn = page.getByRole('button', {name: /copy all/i});
    await copyBtn.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
    const status = await page.locator('[role="status"]').first().textContent();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    if (!/copied/i.test(status || '')) fail(`landing copy button: no "Copied" status [${theme}]`);
    if (!clip.startsWith('git clone https://github.com/habhabhabs/inventag-aws.git') || clip.includes('$ ')) {
      fail(`landing copy button copied the wrong text [${theme}]: ${JSON.stringify(clip.slice(0, 60))}`);
    }
    // code block copy button
    await page.goto(BASE + '/docs/getting-started/quick-start', {waitUntil: 'networkidle'});
    await hydrated(page);
    const codeCopy = page.getByRole('button', {name: 'Copy code to clipboard'}).first();
    await codeCopy.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
    const clip2 = await page.evaluate(() => navigator.clipboard.readText());
    if (!clip2.includes('git clone')) fail(`code block copy button did not copy the block [${theme}]`);
    // theme toggle: Docusaurus 3.10 cycles system -> light -> dark, so check
    // that the button's state (its label) changes, not only data-theme
    await hydrated(page);
    const toggle = page.locator('[class*="colorModeToggle"] button');
    const before = await toggle.getAttribute('aria-label');
    await toggle.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    const after = await toggle.getAttribute('aria-label');
    if (before === after) fail(`theme toggle does not respond to Enter [${theme}]`);
    // version dropdown
    await page.reload({waitUntil: 'networkidle'});
    await hydrated(page);
    const dd = page.locator('.navbar__item.dropdown > .navbar__link').first();
    await dd.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    await page.keyboard.press('Tab');
    const inMenu = await page.evaluate(() => !!document.activeElement.closest('.dropdown__menu'));
    if (!inMenu) fail(`version dropdown: Tab after Enter does not reach the menu [${theme}]`);
    await ctx.close();
  }
  // phone: mobile menu
  {
    const ctx = await newContext(browser, {viewport: {width: 390, height: 844}, dpr: 3, mobile: true, theme});
    const page = await ctx.newPage();
    await page.goto(BASE + '/docs/getting-started/quick-start', {waitUntil: 'networkidle'});
    await hydrated(page);
    const toggle = page.getByRole('button', {name: /toggle navigation bar/i});
    await toggle.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(400);
    const open = await page.evaluate(() => document.querySelector('.navbar-sidebar--show') !== null);
    if (!open) fail(`mobile menu does not open from the keyboard [${theme}]`);
    const links = await page.locator('.navbar-sidebar .menu__link').count();
    if (links < 5) fail(`mobile menu has only ${links} links [${theme}]`);
    await page.keyboard.press('Escape');
    await ctx.close();
  }
}

// 4. analytics: banner shows on first visit, no Google request before consent
{
  const ctx = await newContext(browser, {viewport: {width: 1440, height: 900}, theme: 'light', consent: null});
  const page = await ctx.newPage();
  const ga = [];
  page.on('request', (r) => /googletagmanager|google-analytics/.test(r.url()) && ga.push(r.url()));
  await page.goto(BASE + '/', {waitUntil: 'networkidle'});
  const banner = await page.locator('.consent-banner').count();
  if (!banner) fail('analytics banner not shown on first visit');
  for (const r of [await page.evaluate(auditInPage, false)]) r.boundary.forEach((b) => fail(`banner control ${b}`));
  for (const v of await runAxe(page)) fail(`landing with banner: axe ${v.id}: ${v.help} -> ${v.nodes.join(' | ')}`);
  await page.goto(BASE + '/docs/getting-started/quick-start', {waitUntil: 'networkidle'});
  if (ga.length) fail(`Google Analytics requested before consent: ${ga[0]}`);
  await page.getByRole('button', {name: 'Just the essentials'}).click();
  await page.goto(BASE + '/docs', {waitUntil: 'networkidle'});
  if (ga.length) fail('Google Analytics requested after "Just the essentials"');
  await page.getByRole('button', {name: 'Cookie preferences'}).click();
  await page.waitForTimeout(100);
  const focused = await page.evaluate(() => !!document.activeElement.closest('.consent-banner'));
  if (!focused) fail('"Cookie preferences" does not move focus to the banner');
  const named = await page.evaluate(() => /google|analytics 4/i.test(document.querySelector('.consent-banner')?.textContent || ''));
  if (named) fail('cookie banner names the analytics vendor (keep that on /privacy)');
  // allow, then withdraw: GA loads once, then cookies are cleared
  await page.getByRole('button', {name: 'Allow analytics'}).click();
  await page.waitForTimeout(800);
  if (!ga.length) fail('Google Analytics not loaded after "Allow analytics"');
  await page.context().addCookies([{name: '_ga', value: 'GA1.1.test', domain: new URL(page.url()).hostname, path: '/'}]);
  await page.getByRole('button', {name: 'Cookie preferences'}).click();
  await page.getByRole('button', {name: 'Just the essentials'}).click();
  const left = (await page.context().cookies()).filter((c) => c.name === '_ga' || c.name.startsWith('_ga_'));
  if (left.length) fail(`_ga cookies left after withdrawing consent: ${left.map((c) => c.name).join(', ')}`);
  // the close button counts as essentials only
  await page.evaluate(() => localStorage.removeItem('inventag-analytics'));
  await page.reload({waitUntil: 'networkidle'});
  await page.getByRole('button', {name: /close and keep just the essential/i}).click();
  const stored = await page.evaluate(() => localStorage.getItem('inventag-analytics'));
  if (stored !== 'denied') fail(`closing the banner stored "${stored}", expected "denied"`);
  await ctx.close();
  // 2. First visit: no stored consent choice, so the banner is open.
  const first = await browser.newContext(contextOptions);
  await prepare(first);
  await first.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      if (!sessionStorage.getItem('a11y-first')) {
        localStorage.removeItem('inventag-analytics');
        sessionStorage.setItem('a11y-first', '1');
      }
    } catch (e) { /* ignore */ }
  }, theme);
  for (const pg of PAGES.filter((p) => STATE_PAGES.includes(p.id))) {
    const p2 = await first.newPage();
    await checkConsentBanner(p2, pg, vp, theme);
    await p2.close();
  }
  await first.close();
}

// 5. reduced motion
{
  const ctx = await newContext(browser, {viewport: {width: 1440, height: 900}, theme: 'light', reducedMotion: 'reduce'});
  const page = await ctx.newPage();
  for (const pg of PAGES) {
    const res = newResult(pg, {width: 1440}, 'light', 'reduced-motion');
    if (!(await open(page, pg, res))) continue;
    const running = await page.evaluate(() =>
      document.getAnimations().filter((a) => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length);
    if (running) fail(`${pName}: ${running} infinite animation(s) running with prefers-reduced-motion`);
  }
  await ctx.close();
}

const uniq = (a) => [...new Set(a)];
if (warnings.length) {
  console.log(`Warnings (${uniq(warnings).length}):`);
  uniq(warnings).slice(0, 60).forEach((w) => console.log('  ' + w));
}
console.log(`Pages: ${PAGES.length}, viewports: ${viewports.map((v) => v[0]).join('/')}, themes: light/dark`);
console.log(`\nFailures (${uniq(failures).length}):`);
uniq(failures).forEach((f) => console.log('  ' + f));
if (!failures.length) console.log('  none');
process.exit(failures.length ? 1 : 0);
