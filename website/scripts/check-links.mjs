#!/usr/bin/env node
/**
 * Link check for the built site (no dependencies).
 *
 *   cd website && npm run build && npm run check:links
 *
 * Fails (exit 1) on:
 *   - internal links/images/icons in the homepage or the *current* docs that
 *     do not resolve to a built file, or point at a missing #anchor
 *   - external target="_blank" links without rel="noopener"
 *   - pages without a favicon, canonical URL, description or og:image, or
 *     with other than exactly one <h1>
 *   - the checker itself seeing suspiciously few links (parser gone blind)
 * Reports but does not fail on:
 *   - broken links inside archived versions (/docs/vX.Y.Z/...), which are
 *     snapshots and are not edited
 *   - <img> without width/height in current pages (layout-shift risk; most
 *     come from Markdown images in docs/)
 *
 * File resolution mimics GitHub Pages: /a/b -> a/b, a/b.html, a/b/index.html.
 *
 * The same check runs at the end of every `npm run build` (postBuild hook in
 * docusaurus.config.ts), so a broken link in the current docs fails the build
 * while archived versions only warn.
 *
 * The production HTML is minified and attribute quotes are often dropped
 * (href=/inventag-aws/docs), so attributes are parsed properly below rather
 * than matched with href="...".
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const here = path.dirname(url.fileURLToPath(import.meta.url));
const OTHER_LOCALE = /^\/inventag-aws\/(zh-Hans|zh-Hant|es|fr)(\/|$)/;
const BASE = '/inventag-aws/';
const ARCHIVED = /^\/inventag-aws\/docs\/v\d+\.\d+\.\d+(\/|$)/;
// Pages that are not content (no h1/meta requirements)
const NON_CONTENT = /^\/inventag-aws\/(404|search)$/;

function walk(dir) {
  return fs.readdirSync(dir, {withFileTypes: true}).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : p.endsWith('.html') ? [p] : [];
  });
}

function resolveFile(build, pathname) {
  const rel = decodeURIComponent(pathname.slice(BASE.length));
  for (const c of [rel, `${rel}.html`, path.join(rel, 'index.html')]) {
    const f = path.join(build, c);
    if (fs.existsSync(f) && fs.statSync(f).isFile()) return f;
  }
  return null;
}

/** Attributes of one start tag: double-, single- and unquoted values. */
export function attrs(tag) {
  const out = {};
  const body = tag.replace(/^<[a-z][a-z0-9-]*/i, '').replace(/\/?>$/, '');
  for (const m of body.matchAll(/([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g)) {
    out[m[1].toLowerCase()] = m[2] ?? m[3] ?? m[4] ?? '';
  }
  return out;
}

function tags(html, name) {
  return [...html.matchAll(new RegExp(`<${name}\\b[^>]*>`, 'gi'))].map((m) => ({raw: m[0], at: attrs(m[0])}));
}

const idCache = new Map();
function ids(file) {
  if (!idCache.has(file)) {
    const html = fs.readFileSync(file, 'utf8');
    const set = new Set();
    for (const m of html.matchAll(/<[a-z][a-z0-9-]*\b[^>]*>/gi)) {
      const a = attrs(m[0]);
      if (a.id) set.add(a.id);
    }
    idCache.set(file, set);
  }
  return idCache.get(file);
}

export function checkLinks(build) {
  const errors = [];
  const archived = [];
  const warnings = [];
  let checked = 0;
  let pages = 0;

  for (const file of walk(build)) {
    const pagePath = BASE + path.relative(build, file).replace(/\\/g, '/').replace(/(index)?\.html$/, '');
    const cleanPath = pagePath.replace(/\/$/, '') || BASE;
    // other-language copies are checked but only warn, like archived versions
    const isArchived = ARCHIVED.test(pagePath) || OTHER_LOCALE.test(pagePath);
    const html = fs.readFileSync(file, 'utf8');
    // static/docs/index.html is a hand-written redirect stub, not a Docusaurus page
    const isStub = /http-equiv=["']?refresh/i.test(html);
    if (!isStub) pages++;

    for (const {raw, at} of tags(html, 'a')) {
      // rel=noopener matters for cross-origin targets (tab-nabbing)
      if (/^https?:\/\//.test(at.href || '') && at.target === '_blank' && !/\bnoopener\b/.test(at.rel || '')) {
        errors.push(`${pagePath}: target=_blank without rel=noopener: ${raw.slice(0, 120)}`);
      }
    }

    const refs = [
      ...tags(html, 'a').map((t) => ['a', t.at.href]),
      ...tags(html, 'img').map((t) => ['img', t.at.src]),
      ...tags(html, 'link')
        .filter((t) => /^(icon|apple-touch-icon|canonical|alternate|manifest|preload)$/.test(t.at.rel || ''))
        .map((t) => ['link', t.at.href]),
      ...tags(html, 'meta')
        .filter((t) => /^(og:image|twitter:image)$/.test(t.at.property || t.at.name || ''))
        .map((t) => ['meta', t.at.content]),
    ];
    for (const [, ref] of refs) {
      if (!ref || /^(mailto:|data:|javascript:|#$)/.test(ref)) continue;
      let target;
      try {
        target = new URL(ref, `https://habhabhabs.github.io${pagePath}`);
      } catch {
        continue;
      }
      if (target.host !== 'habhabhabs.github.io' || !target.pathname.startsWith(BASE)) continue;
      // the English build runs before the other languages exist: links to them cannot resolve yet
      const loc = target.pathname.match(OTHER_LOCALE);
      if (loc && !fs.existsSync(path.join(build, loc[1]))) continue;
      checked++;
      const f = resolveFile(build, target.pathname.replace(/\/$/, '') || BASE);
      let problem = null;
      if (!f) problem = 'missing page/file';
      else if (target.hash && f.endsWith('.html') && !ids(f).has(decodeURIComponent(target.hash.slice(1)))) {
        problem = `missing anchor ${target.hash}`;
      }
      if (problem) (isArchived ? archived : errors).push(`${pagePath} -> ${ref} (${problem})`);
    }

    if (!isArchived && !isStub) {
      for (const {raw, at} of tags(html, 'img')) {
        if (at.width === undefined || at.height === undefined) {
          warnings.push(`${pagePath}: <img> without width/height: ${raw.slice(0, 100)}`);
        }
      }
      if (!NON_CONTENT.test(cleanPath)) {
        const h1 = (html.match(/<h1\b/gi) || []).length;
        if (h1 !== 1) errors.push(`${pagePath}: ${h1} <h1> elements (expected exactly 1)`);
        const meta = tags(html, 'meta');
        const has = (key, val) => meta.some((t) => (t.at.name || t.at.property) === key && (!val || val.test(t.at.content || '')));
        if (!has('description', /\S{3}/)) errors.push(`${pagePath}: no meta description`);
        if (!has('og:image', /^https:\/\/habhabhabs\.github\.io\/inventag-aws\/img\/social-card\.png$/)) {
          errors.push(`${pagePath}: og:image missing or not the absolute social-card URL`);
        }
        const links = tags(html, 'link');
        if (!links.some((t) => t.at.rel === 'canonical' && t.at.href?.startsWith('https://habhabhabs.github.io/inventag-aws/'))) {
          errors.push(`${pagePath}: no canonical URL`);
        }
        if (!links.some((t) => t.at.rel === 'icon' && t.at.type === 'image/svg+xml')) errors.push(`${pagePath}: no SVG favicon link`);
        if (!/<html\b[^>]*\slang=["']?en/i.test(html)) errors.push(`${pagePath}: <html> without lang="en"`);
      }
    }
  }

  // Guard against the checker going blind (as it did once when the minifier
  // stopped quoting attributes): every page has navbar and footer links.
  if (pages && checked < pages * 5) {
    errors.push(`Link checker saw only ${checked} internal links in ${pages} pages: is the HTML parser broken?`);
  }
  const uniq = (a) => [...new Set(a)];
  return {checked, pages, errors: uniq(errors), archived: uniq(archived), warnings: uniq(warnings)};
}

export function printReport({checked, pages, errors, archived, warnings}, buildDir) {
  console.log(`Checked ${checked} internal links/images/icons in ${pages} pages (${buildDir})`);
  if (warnings.length) {
    console.log(`\nWarnings (${warnings.length}):`);
    warnings.slice(0, 30).forEach((w) => console.log('  ' + w));
  }
  if (archived.length) {
    console.log(`\nBroken links in archived versions (not failing the check): ${archived.length}`);
  }
  if (errors.length) {
    console.log(`\nErrors (${errors.length}):`);
    errors.forEach((e) => console.log('  ' + e));
  } else {
    console.log('\nOK: no broken links, and every current page has one h1, a description, a canonical URL, og:image and favicons.');
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === url.fileURLToPath(import.meta.url)) {
  const build = path.resolve(here, '..', 'build');
  if (!fs.existsSync(build)) {
    console.error('No build/ directory. Run `npm run build` first.');
    process.exit(2);
  }
  const result = checkLinks(build);
  printReport(result, build);
  process.exit(result.errors.length ? 1 : 0);
}
