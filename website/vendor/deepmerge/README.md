# deepmerge 4.3.1, patched

Why this exists: `deepmerge` (MIT, https://github.com/TehShrike/deepmerge) is
pulled in by `@docusaurus/preset-classic` → `@docusaurus/plugin-svgr` →
`@svgr/webpack` → `@svgr/plugin-svgo`. Every published version up to and
including 4.3.1 (the latest on npm as of 12 Nov 2026) is affected by
**CVE-2026-93753 / GHSA-gcqx-w48m-w2h4**: an object with an own `__proto__`
key (for example from `JSON.parse`) passed as the merge *target* replaces the
prototype of the merged result (reproduced locally against 4.3.1). There is no
fixed release upstream (tracking issue: TehShrike/deepmerge#273).

`website/package.json` installs this copy and points every `deepmerge` in the
tree at it:

```json
"devDependencies": { "deepmerge": "file:vendor/deepmerge" },
"overrides": { "deepmerge": "$deepmerge" }
```

(A bare `file:` path inside `overrides` is resolved relative to the package
that depends on it and produces a broken link, hence the `$deepmerge`
reference.) The version is labelled `4.3.2-inventag.1`: "after 4.3.1, our
patch", so it is not mistaken for the vulnerable upstream 4.3.1.

What changed compared to `deepmerge@4.3.1/dist/cjs.js`: only `mergeObject()`.
Keys `__proto__`, `constructor` and `prototype` are skipped, and each key is
written with `Object.defineProperty` instead of assignment. Everything else is
byte-for-byte the upstream build. `test.cjs` checks the fix and the normal
merge behaviour (`node vendor/deepmerge/test.cjs`).

Exposure on this site was low even before the patch: SVGO only merges its own
build-time configuration, never visitor input, and the site is static.

**Remove this override** as soon as `npm view deepmerge version` shows a fixed
release (or `@svgr/plugin-svgo` drops the dependency): delete the
`overrides.deepmerge` entry and this folder, then run `npm install` and
`npm audit`.
