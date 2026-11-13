#!/usr/bin/env node
/**
 * Translation coverage and structure check.
 *
 *   node scripts/check-i18n.mjs            report only
 *   node scripts/check-i18n.mjs --strict   exit 1 on structural problems
 *
 * For every language it lists the docs pages that are still English, and for
 * each translated page compares it with the English source: same number of
 * headings, code blocks, tables and links, every heading pinned to the English
 * anchor, and the same code-block contents (commands must never be translated).
 * It also compares the heading levels in order, the link targets in order,
 * the number of table rows and admonitions, the front matter keys that are not
 * text (sidebar_position, slug, id), and flags a page that is still byte-identical
 * to the English source.
 *
 * It cannot tell that a translation is stale after the English text changed
 * while the structure stayed the same. See the README or the audit report for
 * the proposed per-page source hash.
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const source = path.resolve(root, '../docs');
const strict = process.argv.includes('--strict');
const walk = (d, base = d) =>
  fs.readdirSync(d, {withFileTypes: true}).flatMap((e) =>
    e.isDirectory() ? walk(path.join(d, e.name), base) : /\.mdx?$/.test(e.name) ? [path.relative(base, path.join(d, e.name))] : [],
  );
const strip = (s) => s.replace(/<!--[\s\S]*?-->/g, '');
const facts = (s) => {
  s = strip(s);
  const fences = [...s.matchAll(/^```[^\n]*\n([\s\S]*?)^```/gm)].map((m) => m[1].trim());
  const prose = s.replace(/^```[^\n]*\n[\s\S]*?^```/gm, '');
  return {
    headings: [...prose.matchAll(/^(#{1,6}) /gm)].length,
    ids: [...prose.matchAll(/^#{2,6} .*?\{(?:#|\/\* #)([\w-]+)(?: \*\/)?\}\s*$/gm)].map((m) => m[1]),
    fences,
    tables: [...prose.matchAll(/^\|[-: |]+\|$/gm)].length,
    links: [...prose.matchAll(/\]\(([^)]+)\)/g)].map((m) => m[1].replace(/#.*$/, '')),
    levels: [...prose.matchAll(/^(#{1,6}) /gm)].map((m) => m[1].length).join(''),
    targets: [...prose.matchAll(/\]\(([^)\s]+)[^)]*\)/g)].map((m) => m[1]),
    rows: [...prose.matchAll(/^\|.*\|$/gm)].length,
    admonitions: [...prose.matchAll(/^:::\w+/gm)].length,
    meta: [...(s.match(/^---\n([\s\S]*?)\n---/) || ['', ''])[1].matchAll(/^(sidebar_position|slug|id|sidebar_class_name|hide_table_of_contents):\s*(.*)$/gm)].map((m) => `${m[1]}=${m[2]}`).join(','),
  };
};
const slug = (h) => h.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/\s/g, '-');

const english = walk(source).filter((f) => f !== 'assets/readme.md'); // excluded from the site
let problems = 0;
const locales = fs.readdirSync(path.join(root, 'translations'));
for (const loc of locales) {
  const dir = path.join(root, 'translations', loc, 'docs');
  const done = fs.existsSync(dir) ? walk(dir) : [];
  const missing = english.filter((f) => !done.includes(f));
  const orphan = done.filter((f) => !english.includes(f));
  console.log(`\n== ${loc}: ${done.length}/${english.length} pages translated, ${missing.length} still English`);
  if (orphan.length) console.log(`   translated pages with no English source: ${orphan.join(', ')}`);
  for (const f of done.filter((f) => english.includes(f))) {
    const en = fs.readFileSync(path.join(source, f), 'utf8');
    const tr = fs.readFileSync(path.join(dir, f), 'utf8');
    const a = facts(en), b = facts(tr);
    const issues = [];
    // an unquoted front-matter value containing ": " is invalid YAML and breaks the build
    for (const m of tr.split(/\n---\n/)[0].matchAll(/^(title|description): (?!["'>|])(.*: .*)$/gm)) issues.push(`front matter ${m[1]} needs quotes`);
    if (a.headings !== b.headings) issues.push(`headings ${b.headings} vs ${a.headings}`);
    if (en === tr) issues.push('identical to the English source (not translated)');
    if (a.levels !== b.levels) issues.push(`heading levels ${b.levels} vs ${a.levels}`);
    if (a.rows !== b.rows) issues.push(`table rows ${b.rows} vs ${a.rows}`);
    if (a.admonitions !== b.admonitions) issues.push(`admonitions ${b.admonitions} vs ${a.admonitions}`);
    if (a.meta !== b.meta) issues.push(`front matter differs: ${b.meta} vs ${a.meta}`);
    if (a.targets.length === b.targets.length) a.targets.forEach((t, i) => t !== b.targets[i] && issues.push(`link ${i + 1} target ${b.targets[i]} vs ${t}`));
    if (a.tables !== b.tables) issues.push(`tables ${b.tables} vs ${a.tables}`);
    if (a.links.length !== b.links.length) issues.push(`links ${b.links.length} vs ${a.links.length}`);
    if (a.fences.length !== b.fences.length) issues.push(`code blocks ${b.fences.length} vs ${a.fences.length}`);
    else a.fences.forEach((c, i) => c !== b.fences[i] && issues.push(`code block ${i + 1} differs`));
    const wantIds = [...strip(en).replace(/^```[^\n]*\n[\s\S]*?^```/gm, '').matchAll(/^#{2,6} (.*?)\s*$/gm)].map((m) => slug(m[1].replace(/\s*\{.*\}$/, '')));
    wantIds.forEach((id) => !b.ids.includes(id) && issues.push(`heading id #${id} not pinned`));
    if (issues.length) {
      problems += issues.length;
      console.log(`   ✗ ${f}: ${issues.join('; ')}`);
    }
  }
  if (missing.length) console.log('   English fallback:\n' + missing.map((f) => `     - ${f}`).join('\n'));
}
console.log(`\n${problems} structural problem(s).`);
if (strict && problems) process.exit(1);
