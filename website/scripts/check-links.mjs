#!/usr/bin/env node
/**
 * Link check for the built site (no dependencies).
 *
 *   cd website && npm run build && npm run check:links
 *
 * Fails (exit 1) on:
 *   - internal links/images in the homepage or the *current* docs that do not
 *     resolve to a built file, or point at a missing #anchor
 *   - external target="_blank" links without rel="noopener"
 * Reports but does not fail on:
 *   - broken links inside archived versions (/docs/vX.Y.Z/...), which are
 *     snapshots and are not edited
 *   - <img> without width/height (layout shift risk)
 *
 * File resolution mimics GitHub Pages: /a/b -> a/b, a/b.html, a/b/index.html.
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const here = path.dirname(url.fileURLToPath(import.meta.url));
const BUILD = path.resolve(here, '..', 'build');
const BASE = '/inventag-aws/';
const ARCHIVED = /^\/inventag-aws\/docs\/v\d+\.\d+\.\d+(\/|$)/;

if (!fs.existsSync(BUILD)) {
  console.error('No build/ directory. Run `npm run build` first.');
  process.exit(2);
}

function walk(dir) {
  return fs.readdirSync(dir, {withFileTypes: true}).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : p.endsWith('.html') ? [p] : [];
  });
}

function resolveFile(pathname) {
  const rel = decodeURIComponent(pathname.slice(BASE.length));
  for (const c of [rel, `${rel}.html`, path.join(rel, 'index.html')]) {
    const f = path.join(BUILD, c);
    if (fs.existsSync(f) && fs.statSync(f).isFile()) return f;
  }
  return null;
}

const idCache = new Map();
function ids(file) {
  if (!idCache.has(file)) {
    const html = fs.readFileSync(file, 'utf8');
    idCache.set(file, new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])));
  }
  return idCache.get(file);
}

const errors = [];
const archived = [];
const warnings = [];
let checked = 0;

for (const file of walk(BUILD)) {
  const pagePath = BASE + path.relative(BUILD, file).replace(/\\/g, '/').replace(/(index)?\.html$/, '');
  const isArchived = ARCHIVED.test(pagePath);
  const html = fs.readFileSync(file, 'utf8');

  for (const m of html.matchAll(/<a\b[^>]*>/g)) {
    const tag = m[0];
    // rel=noopener matters for cross-origin targets (tab-nabbing); same-origin
    // file downloads that Docusaurus opens in a new tab are fine without it
    const external = /href="https?:\/\//.test(tag);
    if (external && /target="_blank"/.test(tag) && !/rel="[^"]*noopener/.test(tag)) {
      errors.push(`${pagePath}: target=_blank without rel=noopener: ${tag.slice(0, 120)}`);
    }
  }

  for (const m of html.matchAll(/<(a|img|link)\b[^>]*?\s(href|src)="([^"]+)"/g)) {
    const [, el, , raw] = m;
    if (el === 'link' && !/rel="(icon|apple-touch-icon|canonical|alternate)"/.test(m[0])) continue;
    if (/^(https?:|mailto:|data:|javascript:|#$)/.test(raw)) continue;
    let target;
    try {
      target = new URL(raw, `https://example.test${pagePath}`);
    } catch {
      continue;
    }
    if (!target.pathname.startsWith(BASE)) continue;
    checked++;
    const f = resolveFile(target.pathname.replace(/\/$/, '') || BASE);
    let problem = null;
    if (!f) problem = 'missing page/file';
    else if (target.hash && f.endsWith('.html') && !ids(f).has(decodeURIComponent(target.hash.slice(1)))) {
      problem = `missing anchor ${target.hash}`;
    }
    if (problem) (isArchived ? archived : errors).push(`${pagePath} -> ${raw} (${problem})`);
  }

  if (!isArchived) {
    for (const m of html.matchAll(/<img\b[^>]*>/g)) {
      if (!/\swidth=/.test(m[0]) || !/\sheight=/.test(m[0])) {
        warnings.push(`${pagePath}: <img> without width/height: ${m[0].slice(0, 100)}`);
      }
    }
  }
}

const uniq = (a) => [...new Set(a)];
console.log(`Checked ${checked} internal links/images in ${BUILD}`);
if (uniq(warnings).length) {
  console.log(`\nWarnings (${uniq(warnings).length}):`);
  uniq(warnings).slice(0, 30).forEach((w) => console.log('  ' + w));
}
if (archived.length) {
  console.log(`\nBroken links in archived versions (not failing the check): ${uniq(archived).length}`);
}
if (errors.length) {
  console.log(`\nErrors (${uniq(errors).length}):`);
  uniq(errors).forEach((e) => console.log('  ' + e));
  process.exit(1);
}
console.log('\nOK: no broken links in the homepage or current docs.');
