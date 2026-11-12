#!/usr/bin/env node
/**
 * Accessibility and layout smoke test for the built site, plus screenshots.
 *
 *   cd website && npm run build
 *   npm run serve -- --port 4173 --no-open &   (serves build/ under /inventag-aws/)
 *   node scripts/check-a11y.mjs [--base http://localhost:4173/inventag-aws] [--shots ../screenshots]
 *
 * Needs Playwright with Chromium. It is NOT a dependency of the site; install
 * it wherever you run this (`npm i -D playwright && npx playwright install chromium`)
 * or point NODE_PATH at an existing install.
 *
 * Checks, per page x theme (light/dark) x viewport (320, 390 phone; 1440 desktop):
 *   - text contrast >= 4.5:1 against the effective background (gradients use
 *     their worst stop). Syntax-highlighting tokens are reported separately.
 *   - no horizontal page scroll
 *   - phones: interactive controls at least 44px tall/wide (links inside a
 *     sentence are exempt, as in WCAG 2.5.8)
 *   - desktop: every Tab stop on the page shows a visible focus indicator
 *   - prefers-reduced-motion: no running CSS animations
 * Exit code 1 if contrast (non-syntax), overflow, focus or motion checks fail.
 * Touch-target findings are listed as warnings.
 */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({chromium} = require('playwright'));
} catch {
  console.error('Playwright not found. See the header of this file.');
  process.exit(2);
}

const arg = (name, def) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : def;
};
const BASE = arg('--base', 'http://localhost:4173/inventag-aws');
const SHOTS = arg('--shots', null);
const PAGES = [
  ['home', '/'],
  ['docs-overview', '/docs'],
  ['intro', '/docs/getting-started/introduction'],
  ['quick-start', '/docs/getting-started/quick-start'],
  ['status', '/docs/getting-started/status'],
];
const VIEWPORTS = [
  ['phone-320', {width: 320, height: 640}, 2, true],
  ['phone', {width: 390, height: 844}, 3, true],
  ['desktop', {width: 1440, height: 900}, 1, false],
];

function auditInPage() {
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
  // Effective background(s): list of candidate opaque colours (gradient stops)
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
    const rootBg = parse(getComputedStyle(document.body).backgroundColor);
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
    let worst = Infinity;
    for (const bg of backgrounds(el)) worst = Math.min(worst, ratio(over(fg, bg), bg));
    if (worst < 4.5) {
      fails.push({
        text: t.textContent.trim().slice(0, 50),
        ratio: Math.round(worst * 100) / 100,
        color: cs.color,
        syntax: !!el.closest('.token, .prism-code, pre'),
        where: el.className && typeof el.className === 'string' ? el.className.slice(0, 60) : el.tagName,
      });
    }
  }
  // touch targets
  const small = [];
  for (const el of document.querySelectorAll('a[href], button, [role="button"], summary, input, select')) {
    if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
    const cs = getComputedStyle(el);
    const inline = cs.display === 'inline' && el.closest('p, li, td, th, blockquote, .admonition');
    if (inline) continue;
    const r = el.getBoundingClientRect();
    if (r.height < 44 || r.width < 44) {
      small.push(`${el.tagName.toLowerCase()} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  return {
    contrast: fails,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    small,
  };
}

const report = {failures: [], warnings: []};
const browser = await chromium.launch();
for (const [vName, viewport, dpr, mobile] of VIEWPORTS) {
  for (const theme of ['light', 'dark']) {
    const ctx = await browser.newContext({viewport, deviceScaleFactor: dpr, isMobile: mobile, hasTouch: mobile, colorScheme: theme});
    await ctx.addInitScript((t) => {
      try { localStorage.setItem('theme', t); } catch (e) {}
    }, theme);
    const page = await ctx.newPage();
    for (const [pName, p] of PAGES) {
      const res = await page.goto(BASE + p, {waitUntil: 'networkidle'});
      if (!res || res.status() >= 400) {
        report.failures.push(`${pName}: HTTP ${res && res.status()}`);
        continue;
      }
      await page.waitForTimeout(300);
      const r = await page.evaluate(auditInPage);
      const tag = `${pName} [${vName}, ${theme}]`;
      for (const f of r.contrast) {
        const line = `${tag} contrast ${f.ratio}:1 "${f.text}" (${f.color}; ${f.where})`;
        (f.syntax ? report.warnings : report.failures).push((f.syntax ? 'syntax ' : '') + line);
      }
      if (r.scrollWidth > r.clientWidth) report.failures.push(`${tag} horizontal scroll: ${r.scrollWidth} > ${r.clientWidth}`);
      if (mobile) r.small.forEach((s) => report.warnings.push(`${tag} touch target < 44px: ${s}`));
      if (SHOTS && vName !== 'phone-320' && ['home', 'intro', 'quick-start'].includes(pName)) {
        fs.mkdirSync(SHOTS, {recursive: true});
        await page.screenshot({path: path.join(SHOTS, `${pName}-${vName}-${theme}.png`)});
      }
    }
    await ctx.close();
  }
}

// keyboard focus visibility (desktop, both themes, homepage + one doc page)
for (const theme of ['light', 'dark']) {
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, colorScheme: theme});
  await ctx.addInitScript((t) => { try { localStorage.setItem('theme', t); } catch (e) {} }, theme);
  const page = await ctx.newPage();
  for (const p of ['/', '/docs/getting-started/quick-start']) {
    await page.goto(BASE + p, {waitUntil: 'networkidle'});
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('Tab');
      const f = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const cs = getComputedStyle(el);
        const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) || (cs.boxShadow && cs.boxShadow !== 'none');
        return {ring, label: `${el.tagName.toLowerCase()} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`};
      });
      if (f && !f.ring) report.failures.push(`focus not visible [${theme}] ${p}: ${f.label}`);
    }
  }
  await ctx.close();
}

// reduced motion
{
  const ctx = await browser.newContext({reducedMotion: 'reduce'});
  const page = await ctx.newPage();
  for (const [pName, p] of PAGES) {
    await page.goto(BASE + p, {waitUntil: 'networkidle'});
    const running = await page.evaluate(() =>
      document.getAnimations().filter((a) => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length);
    if (running) report.failures.push(`${pName}: ${running} infinite animation(s) running with prefers-reduced-motion`);
  }
  await ctx.close();
}
await browser.close();

const uniq = (a) => [...new Set(a)];
console.log(`Warnings (${uniq(report.warnings).length}):`);
uniq(report.warnings).slice(0, 60).forEach((w) => console.log('  ' + w));
console.log(`\nFailures (${uniq(report.failures).length}):`);
uniq(report.failures).forEach((f) => console.log('  ' + f));
process.exit(report.failures.length ? 1 : 0);
