#!/usr/bin/env node
/**
 * Accessibility checks for the built site: axe-core in Chromium (Playwright)
 * at four widths, in the light and the dark theme.
 *
 *   cd website
 *   npm ci
 *   npx playwright install chromium      (once per machine)
 *   npm run build
 *   npm run check:a11y
 *
 * The script serves build/ itself (on a free local port, under the site's
 * baseUrl). It does not need `npm run serve`.
 *
 * Options:
 *   --base <url>     test an already running server instead of build/
 *   --build <dir>    serve this directory instead of build/
 *   --report <file>  JSON report path (default: a11y-report/report.json)
 *   --shots <dir>    also save a screenshot of every scan
 *   --jobs <n>       browser contexts to run in parallel (default: 4)
 *
 * Exit code: 0 = clean, 1 = at least one failure, 2 = could not run.
 *
 * What fails the run
 *   - any axe violation tagged WCAG 2.0/2.1 level A or AA
 *   - text below 4.5:1 on a gradient background (axe reports those only as
 *     "needs review"; this script takes the worst gradient stop)
 *   - the page did not render in the theme under test
 *   - horizontal page scroll (WCAG 1.4.10 Reflow). Tables and code blocks may
 *     scroll inside their own container.
 *   - a Tab stop with no visible focus indicator, off screen, or a keyboard trap
 *   - below the desktop breakpoint: the navigation menu cannot be reached,
 *     opened, used and closed with the keyboard
 *   - the search box cannot be reached and used with the keyboard
 *   - the analytics consent banner traps focus, covers the navbar, covers the
 *     end of the page, or completely covers a focused element
 *   - an animation that loops forever under prefers-reduced-motion
 *
 * What is reported but does not fail the run
 *   - axe "best-practice" rules and WCAG 2.2 AA rules (advisory)
 *   - syntax-highlighting token colours below 4.5:1
 *   - touch targets smaller than 44px at the two touch widths
 */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.resolve(HERE, '..');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Must match `baseUrl` in docusaurus.config.js. */
const BASE_PATH = '/inventag-aws';

/**
 * Infima (the Docusaurus CSS framework) switches layout at one breakpoint:
 * `@media (max-width: 996px)` is the mobile layout (hamburger menu, no docs
 * sidebar), 997px and wider is the desktop layout. The script checks at run
 * time that each width below renders the layout named here.
 */
const DESKTOP_MIN_WIDTH = 997;

const WIDTHS = [
  // WCAG 1.4.10 Reflow: content must work at 320 CSS px without sideways scroll.
  {width: 320, height: 640, touch: true},
  // Tablet, portrait. The widest common width that still gets the mobile layout.
  {width: 768, height: 1024, touch: true},
  // Small laptop or landscape tablet. The narrowest common desktop layout:
  // sidebar, content and table of contents compete for space.
  {width: 1024, height: 768, touch: false},
  // Common desktop width; content reaches its maximum line length.
  {width: 1440, height: 900, touch: false},
];

const THEMES = ['light', 'dark'];

/**
 * Pages under test. Paths are relative to the base URL. Every page except the
 * 404 must be in build/sitemap.xml, so a renamed page fails loudly here.
 */
const PAGES = [
  {id: 'home', path: '/', why: 'custom React homepage: hero, feature cards'},
  {id: 'docs-index', path: '/docs', why: 'docs landing page: sidebar, breadcrumbs, version badge'},
  {id: 'status', path: '/docs/getting-started/status', why: 'tables and code blocks'},
  {id: 'cli-user-guide', path: '/docs/user-guides/cli-user-guide', why: 'long user guide: many code blocks, deep table of contents'},
  {id: 'search', path: '/search?q=tag', why: 'search results page'},
  {id: '404', path: '/this-page-does-not-exist', why: 'not-found page', status: 404},
];

/** Pages that also get the menu, search and consent-banner state checks. */
const STATE_PAGES = ['home', 'status'];

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const ADVISORY_TAGS = ['best-practice', 'wcag22aa'];

/**
 * Accepted violations. Keep this empty: fix the site instead.
 * If an entry is ever needed, every field is required and `reason` must say
 * why the violation cannot be fixed in this repository:
 *   {rule: 'axe-rule-id', selector: 'css selector of the node', reason: '...'}
 */
const ALLOWLIST = [];

const TAB_STOPS = 25;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const arg = (name, def) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
};
const die = (msg) => {
  console.error(msg);
  process.exit(2);
};

for (const a of ALLOWLIST) {
  if (!a.rule || !a.selector || !a.reason || a.reason.trim().length < 20) {
    die(`ALLOWLIST entry ${JSON.stringify(a)} needs rule, selector and a written reason.`);
  }
}

let chromium;
try {
  ({chromium} = require('playwright'));
} catch {
  die('Playwright not found. Run `npm ci` in website/, then `npx playwright install chromium`.');
}
let axeSource;
try {
  axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
} catch {
  die('axe-core not found. Run `npm ci` in website/.');
}

const BUILD = path.resolve(SITE, arg('--build', 'build'));
const REPORT = path.resolve(SITE, arg('--report', 'a11y-report/report.json'));
const SHOTS = arg('--shots', null);
const JOBS = Math.max(1, parseInt(arg('--jobs', '4'), 10) || 4);
let BASE = arg('--base', null);

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
  '.xml': 'application/xml', '.txt': 'text/plain', '.woff2': 'font/woff2', '.webp': 'image/webp',
  '.yaml': 'text/yaml', '.jpg': 'image/jpeg',
};

/** Static server for build/, with GitHub Pages behaviour (x -> x.html, 404.html). */
function serveBuild() {
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const send = (status, file) => {
      res.writeHead(status, {'content-type': MIME[path.extname(file)] || 'application/octet-stream'});
      fs.createReadStream(file).pipe(res);
    };
    if (p === BASE_PATH || p.startsWith(BASE_PATH + '/')) {
      const rel = p.slice(BASE_PATH.length).replace(/^\/+|\/+$/g, '');
      for (const c of [rel, rel + '.html', path.join(rel, 'index.html')]) {
        const file = path.join(BUILD, c);
        if (file.startsWith(BUILD) && fs.existsSync(file) && fs.statSync(file).isFile()) return send(200, file);
      }
    }
    return send(404, path.join(BUILD, '404.html'));
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

let server = null;
if (!BASE) {
  if (!fs.existsSync(path.join(BUILD, 'index.html'))) die(`${BUILD} not found. Run \`npm run build\` first.`);
  const sitemap = fs.readFileSync(path.join(BUILD, 'sitemap.xml'), 'utf8');
  const locs = new Set([...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => new URL(m[1]).pathname.replace(/\/$/, '')));
  for (const pg of PAGES) {
    if (pg.status === 404) continue;
    const want = (BASE_PATH + pg.path.split('?')[0]).replace(/\/$/, '');
    if (!locs.has(want)) die(`Page "${pg.id}" (${want}) is not in sitemap.xml. Update PAGES in ${path.basename(import.meta.url)}.`);
  }
  server = await serveBuild();
  BASE = `http://127.0.0.1:${server.address().port}${BASE_PATH}`;
}
const ORIGIN = new URL(BASE).origin;

// ---------------------------------------------------------------------------
// In-page helpers (run inside the browser)
// ---------------------------------------------------------------------------

/** Theme actually rendered: the attribute Docusaurus sets, and the real page background. */
function readTheme() {
  const rgba = (c) => {
    const p = c.match(/[\d.]+/g).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const lum = ({r, g, b}) => 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  // Page background: <html>, else <body>, else the browser's white canvas.
  let background = 'rgb(255, 255, 255)';
  for (const el of [document.body, document.documentElement]) {
    const c = getComputedStyle(el).backgroundColor;
    if (rgba(c).a === 1) background = c;
  }
  const text = getComputedStyle(document.body).color;
  return {
    attr: document.documentElement.getAttribute('data-theme'),
    stored: localStorage.getItem('theme'),
    background,
    text,
    backgroundLuminance: lum(rgba(background)),
    textLuminance: lum(rgba(text)),
  };
}

/** Layout facts: page overflow, the elements that cause it, and which layout is active. */
function readLayout() {
  const vw = document.documentElement.clientWidth;
  const scrolls = (el) => {
    for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
      const o = getComputedStyle(n).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true;
    }
    return false;
  };
  const offenders = [];
  if (document.documentElement.scrollWidth > vw) {
    for (const el of document.body.querySelectorAll('*')) {
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed' || cs.visibility === 'hidden' || cs.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > vw + 0.5 && !scrolls(el)) {
        const cls = typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
        offenders.push(`${el.tagName.toLowerCase()}${cls} (right edge ${Math.round(r.right)}px)`);
        if (offenders.length >= 5) break;
      }
    }
  }
  const toggle = document.querySelector('.navbar__toggle');
  return {
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: vw,
    offenders,
    mobileLayout: !!toggle && getComputedStyle(toggle).display !== 'none' && toggle.getBoundingClientRect().width > 0,
  };
}

/**
 * Text contrast with gradient backgrounds resolved to their worst stop, and
 * touch-target sizes. axe-core cannot judge text on a gradient and files it
 * under "incomplete"; this covers that gap.
 */
function auditContrastAndTargets() {
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
  const layersOf = (el) => {
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
    return {layers, gradient};
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
    const {layers, gradient} = layersOf(el);
    if (!gradient) continue; // plain backgrounds are axe's job
    let candidates = [rootBg && rootBg.a === 1 ? rootBg : {r: 255, g: 255, b: 255, a: 1}];
    for (const layer of layers.reverse()) candidates = layer.stops.flatMap((s) => candidates.map((c) => over(s, c)));
    let worst = Infinity;
    for (const bg of candidates) worst = Math.min(worst, ratio(over(fg, bg), bg));
    const size = parseFloat(cs.fontSize);
    const large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
    if (worst < (large ? 3 : 4.5)) {
      fails.push({
        text: t.textContent.trim().slice(0, 50),
        ratio: Math.round(worst * 100) / 100,
        need: large ? 3 : 4.5,
        color: cs.color,
        syntax: !!el.closest('.token, .prism-code, pre'),
        where: el.className && typeof el.className === 'string' ? el.className.slice(0, 60) : el.tagName.toLowerCase(),
      });
    }
  }
  const small = [];
  for (const el of document.querySelectorAll('a[href], button, [role="button"], summary, input, select')) {
    if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'inline' && el.closest('p, li, td, th, blockquote, .admonition')) continue;
    const r = el.getBoundingClientRect();
    if (r.height < 44 || r.width < 44) {
      small.push(`${el.tagName.toLowerCase()} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
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
    id: window.__a11yIds.get(el),
    label: `${el.tagName.toLowerCase()}${cls} "${(el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().replace(/\s+/g, ' ').slice(0, 30)}"`,
    ring: !!(outline || shadow),
    sized: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden',
    inView: r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth,
    coveredByBanner,
    inBanner: !!(banner && banner.contains(el)),
    inMenu: !!el.closest('.navbar-sidebar'),
    isToggle: el.matches('.navbar__toggle'),
    isMenuClose: el.matches('.navbar-sidebar__close'),
    isSearch: el.matches('.navbar__search-input'),
  };
}

// ---------------------------------------------------------------------------
// Checks
// ---------------------------------------------------------------------------

const results = []; // one entry per page x width x theme x state
const startedAt = Date.now();

function allowlisted(rule, node) {
  return ALLOWLIST.some((a) => a.rule === rule && node.target.join(' ').includes(a.selector));
}

async function runAxe(page) {
  await page.evaluate(axeSource);
  const raw = await page.evaluate(
    (tags) => window.axe.run(document, {runOnly: {type: 'tag', values: tags}, resultTypes: ['violations', 'incomplete']}),
    [...WCAG_TAGS, ...ADVISORY_TAGS],
  );
  const slim = (v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    helpUrl: v.helpUrl,
    tags: v.tags.filter((t) => /^wcag|best-practice/.test(t)),
    nodes: v.nodes
      .filter((n) => !allowlisted(v.id, n))
      .map((n) => ({
        target: n.target.join(' '),
        html: n.html.replace(/\s+/g, ' ').slice(0, 220),
        summary: (n.failureSummary || '').replace(/\s+/g, ' ').slice(0, 400),
      })),
  });
  const violations = raw.violations.map(slim).filter((v) => v.nodes.length);
  const isWcag = (v) => v.tags.some((t) => WCAG_TAGS.includes(t));
  return {
    wcag: violations.filter(isWcag),
    advisory: violations.filter((v) => !isWcag(v)),
    // "Needs review": axe could not decide. Kept in the report with axe's reason.
    incomplete: raw.incomplete.map((v) => {
      const reasons = {};
      for (const n of v.nodes) {
        const key = [...n.any, ...n.all, ...n.none].map((c) => c.data && c.data.messageKey).find(Boolean) || 'unspecified';
        reasons[key] = (reasons[key] || 0) + 1;
      }
      return {id: v.id, nodes: v.nodes.length, reasons};
    }),
  };
}

function newResult(pg, vp, theme, state) {
  const r = {page: pg.id, url: pg.path, width: vp.width, theme, state, wcag: [], advisory: [], incomplete: [], failures: [], warnings: []};
  results.push(r);
  return r;
}

async function settle(page) {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => document.documentElement.hasAttribute('data-theme') && document.fonts.status === 'loaded');
  await page.waitForTimeout(250);
}

async function open(page, pg, res) {
  const response = await page.goto(BASE + pg.path, {waitUntil: 'load'});
  const want = pg.status || 200;
  if (!response || response.status() !== want) {
    res.failures.push({check: 'http', detail: `expected HTTP ${want}, got ${response && response.status()}`});
    return false;
  }
  await settle(page);
  return true;
}

async function verifyTheme(page, theme, res) {
  const t = await page.evaluate(readTheme);
  res.rendered = t;
  // The attribute alone is not proof: the colours on screen must match it.
  const dark = t.backgroundLuminance < 0.1 && t.textLuminance > 0.5;
  const light = t.backgroundLuminance > 0.8 && t.textLuminance < 0.1;
  const ok = t.attr === theme && (theme === 'dark' ? dark : light);
  if (!ok) res.failures.push({check: 'theme', detail: `asked for ${theme}; got data-theme="${t.attr}", background ${t.background}, text ${t.text}`});
  return ok;
}

async function shot(page, res) {
  if (!SHOTS) return;
  fs.mkdirSync(SHOTS, {recursive: true});
  const state = res.state === 'default' ? '' : `-${res.state}`;
  await page.screenshot({path: path.join(SHOTS, `${res.page}-${res.width}-${res.theme}${state}.png`)});
}

async function scan(page, res) {
  const a = await runAxe(page);
  res.wcag = a.wcag;
  res.advisory = a.advisory;
  res.incomplete = a.incomplete;
  const c = await page.evaluate(auditContrastAndTargets);
  for (const f of c.contrast) {
    const detail = `${f.ratio}:1 (needs ${f.need}:1) "${f.text}" ${f.color} on gradient; ${f.where}`;
    if (f.syntax) res.warnings.push({check: 'syntax-contrast', detail});
    else res.failures.push({check: 'gradient-contrast', detail});
  }
  return c;
}

/** Press Tab `count` times from the top of the page; check every stop. */
async function tabWalk(page, res, count, {banner = false} = {}) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  });
  let last = null;
  let repeats = 0;
  let stops = 0;
  const seen = new Set();
  for (let i = 0; i < count; i++) {
    await page.keyboard.press('Tab');
    const f = await page.evaluate(readFocus);
    if (!f) continue;
    // First focus on the search box starts loading the search index. Wait for
    // it, so the load cannot finish at a random point later in the walk.
    if (f.isSearch) await page.waitForSelector('.navbar__search-input[role="combobox"]', {timeout: 10000}).catch(() => {});
    stops++;
    repeats = last === f.id ? repeats + 1 : 0;
    last = f.id;
    if (repeats >= 2) {
      res.failures.push({check: 'keyboard-trap', detail: `focus stuck on ${f.label}`});
      break;
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

async function checkReducedMotion(browser) {
  const ctx = await browser.newContext({reducedMotion: 'reduce', viewport: {width: 1440, height: 900}});
  await ctx.route((url) => url.origin !== ORIGIN, (route) => route.abort());
  const page = await ctx.newPage();
  for (const pg of PAGES) {
    const res = newResult(pg, {width: 1440}, 'light', 'reduced-motion');
    if (!(await open(page, pg, res))) continue;
    const running = await page.evaluate(() =>
      document.getAnimations().filter((a) => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length);
    if (running) res.failures.push({check: 'reduced-motion', detail: `${running} looping animation(s) run with prefers-reduced-motion: reduce`});
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

const browser = await chromium.launch();
const combos = WIDTHS.flatMap((vp) => THEMES.map((theme) => ({vp, theme})));
let crashed = null;
try {
  const queue = [...combos];
  await Promise.all(
    Array.from({length: Math.min(JOBS, queue.length)}, async () => {
      for (let c = queue.shift(); c; c = queue.shift()) await runCombo(browser, c.vp, c.theme);
    }),
  );
  await checkReducedMotion(browser);
} catch (e) {
  crashed = e;
} finally {
  await browser.close();
  if (server) server.close();
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

const order = (r) => PAGES.findIndex((p) => p.id === r.page) * 1e6 + r.width * 10 + (r.theme === 'dark' ? 1 : 0);
results.sort((a, b) => order(a) - order(b) || a.state.localeCompare(b.state));
const nodes = (list) => list.reduce((n, v) => n + v.nodes.length, 0);
const where = (r) => `${r.page} @ ${r.width}px ${r.theme}${r.state === 'default' ? '' : ` [${r.state}]`}`;

const totals = {
  scans: results.filter((r) => r.state !== 'reduced-motion').length,
  pageScans: results.filter((r) => r.state === 'default').length,
  wcagViolations: results.reduce((n, r) => n + r.wcag.length, 0),
  wcagNodes: results.reduce((n, r) => n + nodes(r.wcag), 0),
  checkFailures: results.reduce((n, r) => n + r.failures.length, 0),
  advisoryViolations: results.reduce((n, r) => n + r.advisory.length, 0),
  advisoryNodes: results.reduce((n, r) => n + nodes(r.advisory), 0),
  warnings: results.reduce((n, r) => n + r.warnings.length, 0),
  needsReview: results.reduce((n, r) => n + r.incomplete.reduce((k, i) => k + i.nodes, 0), 0),
};
const seconds = Math.round((Date.now() - startedAt) / 100) / 10;
const failed = !!crashed || totals.wcagViolations > 0 || totals.checkFailures > 0;

fs.mkdirSync(path.dirname(REPORT), {recursive: true});
fs.writeFileSync(REPORT, JSON.stringify({
  generated: new Date().toISOString(),
  base: BASE,
  seconds,
  passed: !failed,
  crashed: crashed ? String(crashed.stack || crashed) : null,
  config: {widths: WIDTHS, themes: THEMES, pages: PAGES, statePages: STATE_PAGES, wcagTags: WCAG_TAGS, advisoryTags: ADVISORY_TAGS, allowlist: ALLOWLIST, desktopMinWidth: DESKTOP_MIN_WIDTH},
  totals,
  results,
}, null, 2));

const line = '-'.repeat(78);
console.log(`Accessibility check: ${PAGES.length} pages x ${WIDTHS.length} widths x ${THEMES.length} themes = ${totals.pageScans} page scans,`);
console.log(`plus ${totals.scans - totals.pageScans} state scans (menu open, search open, consent banner). ${seconds}s.`);
console.log(`Rules: ${WCAG_TAGS.join(', ')} (fail); ${ADVISORY_TAGS.join(', ')} (advisory).\n`);

// Matrix: WCAG violations + failed checks per page x width x theme (all states added up)
const cols = WIDTHS.flatMap((vp) => THEMES.map((t) => ({width: vp.width, theme: t})));
console.log('Failures per page x width x theme (WCAG A/AA nodes + failed checks; "." = none)');
console.log('page'.padEnd(16) + cols.map((c) => `${c.width}${c.theme[0].toUpperCase()}`.padStart(7)).join(''));
for (const pg of PAGES) {
  const cells = cols.map((c) => {
    const rs = results.filter((r) => r.page === pg.id && r.width === c.width && r.theme === c.theme && r.state !== 'reduced-motion');
    const n = rs.reduce((s, r) => s + nodes(r.wcag) + r.failures.length, 0);
    return (n ? String(n) : '.').padStart(7);
  });
  console.log(pg.id.padEnd(16) + cells.join(''));
}
console.log('(L = light, D = dark)\n');

const bad = results.filter((r) => r.wcag.length || r.failures.length);
if (bad.length) {
  console.log(line + '\nFAILURES\n' + line);
  for (const r of bad) {
    console.log(`\n${where(r)}`);
    for (const v of r.wcag) {
      console.log(`  [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node${v.nodes.length > 1 ? 's' : ''}; ${v.tags.filter((t) => WCAG_TAGS.includes(t)).join(', ')})`);
      for (const n of v.nodes.slice(0, 4)) {
        console.log(`      ${n.target}`);
        console.log(`        ${n.summary.replace(/^Fix (any|all) of the following: /, '')}`);
      }
      if (v.nodes.length > 4) console.log(`      ... ${v.nodes.length - 4} more in the JSON report`);
    }
    for (const f of r.failures) console.log(`  [check] ${f.check}: ${f.detail}`);
  }
  console.log('');
}

// Advisory rules and warnings: one line per rule, with how many scans hit it
const group = (pick) => {
  const m = new Map();
  for (const r of results) for (const item of pick(r)) {
    const g = m.get(item.key) || {...item, scans: new Set(), count: 0, examples: new Set()};
    g.scans.add(where(r));
    g.count += item.n;
    if (g.examples.size < 3) g.examples.add(item.example);
    m.set(item.key, g);
  }
  return [...m.values()].sort((a, b) => b.count - a.count);
};
const advisory = group((r) => r.advisory.map((v) => ({key: v.id, label: `${v.id}: ${v.help} [${v.tags.filter((t) => ADVISORY_TAGS.includes(t)).join(', ')}]`, n: v.nodes.length, example: v.nodes[0].target})));
console.log(line + `\nADVISORY (does not fail the run): ${advisory.length} rule(s), ${totals.advisoryNodes} node(s)\n` + line);
for (const g of advisory) {
  console.log(`  ${g.label}`);
  console.log(`      ${g.count} node(s) in ${g.scans.size} scan(s); e.g. ${[...g.examples].join(' | ')}`);
}
const warnings = group((r) => r.warnings.map((w) => ({key: w.check + '|' + w.detail, label: `${w.check}: ${w.detail}`, n: 1, example: ''})));
console.log(`\nWARNINGS (does not fail the run): ${warnings.length} distinct`);
for (const g of warnings.slice(0, 15)) console.log(`  ${g.label}  (${g.scans.size} scan(s))`);
if (warnings.length > 15) console.log(`  ... ${warnings.length - 15} more in the JSON report`);

console.log('\n' + line);
console.log(`WCAG 2.1 A/AA violations: ${totals.wcagViolations} (${totals.wcagNodes} nodes)   failed checks: ${totals.checkFailures}`);
console.log(`axe "needs review" items (not failures; listed per scan in the report): ${totals.needsReview}`);
console.log(`Report: ${path.relative(process.cwd(), REPORT)}`);
if (crashed) {
  console.error('\nThe run stopped early:\n' + (crashed.stack || crashed));
  process.exit(2);
}
console.log(failed ? 'RESULT: FAIL' : 'RESULT: PASS');
process.exit(failed ? 1 : 0);
