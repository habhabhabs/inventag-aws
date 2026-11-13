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
import path from 'node:path';

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
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const img = cs.backgroundImage;
      if (img && img.includes('gradient')) {
        const stops = [...img.matchAll(/rgba?\([^)]+\)/g)].map((m) => parse(m[0]));
        layers.push({stops});
        if (stops.every((s) => s.a === 1)) break;
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
  const fails = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (!t.textContent.trim()) continue;
    const el = t.parentElement;
    if (!el || seen.has(el) || !visible(el)) continue;
    if (el.closest('svg, [aria-hidden="true"], .sr-only, noscript')) continue;
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
    await page.goto(BASE + '/docs/getting-started/installation', {waitUntil: 'networkidle'});
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
}

// 5. reduced motion
{
  const ctx = await newContext(browser, {viewport: {width: 1440, height: 900}, theme: 'light', reducedMotion: 'reduce'});
  const page = await ctx.newPage();
  for (const [pName, p] of PAGES) {
    await page.goto(BASE + p, {waitUntil: 'networkidle'});
    const running = await page.evaluate(() =>
      document.getAnimations().filter((a) => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length);
    if (running) fail(`${pName}: ${running} infinite animation(s) running with prefers-reduced-motion`);
  }
  await ctx.close();
}
await browser.close();

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
