#!/usr/bin/env node
/**
 * Assemble the site the way `docusaurus build` (all locales) lays it out, from
 * one build per locale, so a machine that cannot hold all five builds in memory
 * can still check the real paths (L-04):
 *
 *   build/                 the English build (base /inventag-aws/)
 *   build/<locale>/        the build of that locale (base /inventag-aws/<locale>/)
 *
 *   node scripts/assemble-locales.mjs --en DIR --locale fr=DIR [--locale es=DIR] --out DIR
 *
 * `docusaurus build --locale fr --out-dir X` writes the French site at the root
 * of X with links under /inventag-aws/fr/. Served from X, those pages are at the
 * wrong address (the single-locale build problem). Copied to <out>/fr/ they are
 * where the real build puts them. Before copying, each input is checked:
 *   - English: <html lang="en"> and links under /inventag-aws/ only;
 *   - a locale: its <html lang> is that locale and its page links begin with
 *     /inventag-aws/<locale>/ (a build made without that base path is refused).
 * Exit 0 on success, 1 on a refused input, 2 on a usage error.
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

export const BASE = '/inventag-aws/';
export const LOCALES = ['zh-Hans', 'zh-Hant', 'es', 'fr'];

/** Problems with a locale build folder (an empty list means it can be assembled). */
export function inspectBuild(dir, locale) {
  const problems = [];
  const index = path.join(dir, 'index.html');
  if (!fs.existsSync(index)) return [`${dir}: no index.html`];
  const html = fs.readFileSync(index, 'utf8');
  const lang = html.match(/<html\b[^>]*\slang=["']?([\w-]+)/i)?.[1];
  const wantLang = locale === 'en' ? 'en' : locale;
  if (!lang || !(lang === wantLang || lang.startsWith(`${wantLang}-`))) {
    problems.push(`${index}: <html lang="${lang}"> but this is the ${locale} build`);
  }
  const prefix = locale === 'en' ? BASE : `${BASE}${locale}/`;
  if (!html.includes(prefix)) {
    problems.push(`${index}: no link or asset under ${prefix}; was it built with --locale ${locale}?`);
  }
  if (locale === 'en') {
    for (const other of LOCALES) {
      if (fs.existsSync(path.join(dir, other, 'index.html'))) {
        problems.push(`${dir}: already holds /${other}/; give the English build only`);
      }
    }
  }
  return problems;
}

export function assemble({en, locales, out}) {
  const problems = inspectBuild(en, 'en');
  for (const [locale, dir] of Object.entries(locales)) {
    if (!LOCALES.includes(locale)) problems.push(`unknown locale ${locale}`);
    else problems.push(...inspectBuild(dir, locale));
  }
  if (problems.length) return {problems, copied: []};
  fs.rmSync(out, {recursive: true, force: true});
  fs.cpSync(en, out, {recursive: true});
  for (const [locale, dir] of Object.entries(locales)) {
    fs.cpSync(dir, path.join(out, locale), {recursive: true});
  }
  return {problems: [], copied: ['en', ...Object.keys(locales)]};
}

function parseArgs(argv) {
  const args = {locales: {}};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--en') args.en = path.resolve(argv[++i]);
    else if (argv[i] === '--out') args.out = path.resolve(argv[++i]);
    else if (argv[i] === '--locale') {
      const [locale, dir] = (argv[++i] ?? '').split('=');
      if (!locale || !dir) return null;
      args.locales[locale] = path.resolve(dir);
    } else return null;
  }
  return args.en && args.out && Object.keys(args.locales).length ? args : null;
}

if (process.argv[1] && path.resolve(process.argv[1]) === url.fileURLToPath(import.meta.url)) {
  const args = parseArgs(process.argv.slice(2));
  if (!args) {
    console.error('usage: assemble-locales.mjs --en DIR --locale <locale>=DIR [...] --out DIR');
    process.exit(2);
  }
  const {problems, copied} = assemble(args);
  if (problems.length) {
    problems.forEach((p) => console.error(`refused: ${p}`));
    process.exit(1);
  }
  console.log(`assembled ${copied.join(', ')} into ${args.out}`);
}
