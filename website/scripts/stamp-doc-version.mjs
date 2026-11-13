#!/usr/bin/env node
/**
 * Stamps one archived docs snapshot with its own version number.
 *
 *   node scripts/stamp-doc-version.mjs <snapshot-dir> <version> [--check]
 *   node scripts/stamp-doc-version.mjs versioned_docs/version-1.1.0 1.1.0
 *
 * The docs at a release tag were not always updated for that release, so a
 * snapshot can say "This page describes InvenTag v1.0.2" in the 1.1.2 docs.
 * This script rewrites the places where a page names a version of InvenTag as
 * "this" version, and nothing else. Each pattern below was reviewed by hand;
 * version numbers that are historical facts (changelog text, "since 1.0.1",
 * Python, action and dependency versions) are not matched on purpose.
 *
 * Every replacement is printed. --check changes nothing and exits 1 when a
 * replacement would be made. Running it twice changes nothing the second time.
 *
 * sync-doc-versions.sh runs it right after a snapshot is created.
 */
import fs from 'node:fs';
import path from 'node:path';

const SEMVER = String.raw`\d+\.\d+\.\d+`;

// [description, regex]. The regex has three groups: (before)(version)(after);
// only the middle group is replaced.
const PATTERNS = [
  // getting-started/status.md, front matter description
  ['status description', new RegExp(String.raw`(Which InvenTag features work in v)(${SEMVER})(,)`, 'g')],
  // getting-started/status.md, first paragraph
  ['status sentence', new RegExp(String.raw`(This page describes InvenTag v)(${SEMVER})(\.)`, 'g')],
  // getting-started/status.md, flags table ("Accepted. We did not re-test them for v1.0.0.")
  ['status re-test note', new RegExp(String.raw`(We did not re-test them for v)(${SEMVER})(\.)`, 'g')],
  // getting-started/installation.md and guides/run-in-ci.md: pinned install
  ['pinned pip install', new RegExp(String.raw`(inventag-aws==)(${SEMVER})(\b)`, 'g')],
  // getting-started/installation.md: install from a source checkout of this release
  ['git checkout of the release', new RegExp(String.raw`(git checkout v)(${SEMVER})(\b)`, 'g')],
  // guides/run-in-ci.md: actions/checkout of the InvenTag repository at a release
  ['CI ref pin', new RegExp(String.raw`(ref: v)(${SEMVER})(\s+# pin a release)`, 'g')],
  // reference/cli.md ("matches `inventag --help` on v5.0.0", a retired number)
  ['cli --help sentence', new RegExp(String.raw`(matches \`inventag --help\` on v)(${SEMVER})(\.)`, 'g')],
];

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) walk(full, out);
    else if (/\.mdx?$/.test(name)) out.push(full);
  }
  return out;
}

const args = process.argv.slice(2);
const check = args.includes('--check');
const [dir, version] = args.filter((a) => a !== '--check');
if (!dir || !version || !new RegExp(`^${SEMVER}$`).test(version) || !fs.existsSync(dir)) {
  console.error('usage: stamp-doc-version.mjs <snapshot-dir> <X.Y.Z> [--check]');
  process.exit(2);
}

let count = 0;
for (const file of walk(dir).sort()) {
  const original = fs.readFileSync(file, 'utf8');
  const lines = original.split('\n');
  let changed = false;
  lines.forEach((line, i) => {
    let next = line;
    for (const [what, re] of PATTERNS) {
      next = next.replace(re, (m, before, found, after) => {
        if (found === version) return m;
        count++;
        changed = true;
        console.log(`${path.relative(dir, file)}:${i + 1}: ${what}: ${found} -> ${version}`);
        return `${before}${version}${after}`;
      });
    }
    lines[i] = next;
  });
  if (changed && !check) fs.writeFileSync(file, lines.join('\n'));
}

const label = `${dir} (v${version})`;
if (check) {
  console.log(count ? `${label}: ${count} replacement(s) needed` : `${label}: stamped, nothing to change`);
  process.exit(count ? 1 : 0);
}
console.log(`${label}: ${count} replacement(s)`);
