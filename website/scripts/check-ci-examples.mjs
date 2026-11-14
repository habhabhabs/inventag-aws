#!/usr/bin/env node
/**
 * CI example check: runs scripts/docs/check_ci_examples.py from the repo root.
 *
 *   node scripts/check-ci-examples.mjs [--docs <dir>] [--list]
 *
 * Why Python: the checker parses YAML and reads InvenTag's own argument parser.
 * PyYAML is in requirements.txt; the website package has no YAML parser of its
 * own. Set PYTHON to choose the interpreter (default: python3, then python).
 * Needs `pip install -r requirements.txt` first.
 *
 * Translated pages: `npm run check:i18n` already compares every code block with
 * the English page byte for byte, so this script reads docs/ only.
 */
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import url from 'node:url';

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '../..');
const script = path.join(root, 'scripts/docs/check_ci_examples.py');
const candidates = process.env.PYTHON ? [process.env.PYTHON] : ['python3', 'python'];
for (const py of candidates) {
  const r = spawnSync(py, [script, ...process.argv.slice(2)], {stdio: 'inherit', cwd: root});
  if (r.error && r.error.code === 'ENOENT') continue;
  process.exit(r.status ?? 1);
}
console.error('check-ci-examples: no Python interpreter found (set PYTHON).');
process.exit(1);
