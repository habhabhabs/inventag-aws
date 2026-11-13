#!/usr/bin/env node
/**
 * Builds the docs folder for each translated language:
 *
 *   i18n/<locale>/docusaurus-plugin-content-docs/current  (generated, git-ignored)
 *     = a copy of ../docs (English)
 *     + website/translations/<locale>/docs  laid over it
 *
 * A page that is not translated yet is therefore the English page, and its
 * relative links still resolve. Translate a page by adding it under
 * translations/<locale>/docs/ with the same path. Runs before `npm run build`
 * and `npm start`.
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const source = path.resolve(root, '../docs');
const translations = path.join(root, 'translations');
if (!fs.existsSync(translations)) process.exit(0);

for (const locale of fs.readdirSync(translations)) {
  const from = path.join(translations, locale, 'docs');
  const to = path.join(root, 'i18n', locale, 'docusaurus-plugin-content-docs', 'current');
  fs.rmSync(to, {recursive: true, force: true});
  fs.mkdirSync(to, {recursive: true});
  fs.cpSync(source, to, {recursive: true});
  if (fs.existsSync(from)) fs.cpSync(from, to, {recursive: true});
  console.log(`i18n: ${locale} docs ready (${fs.existsSync(from) ? fs.readdirSync(from, {recursive: true}).filter((f) => /\.mdx?$/.test(f)).length : 0} translated pages)`);
}
