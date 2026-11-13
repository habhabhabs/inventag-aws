#!/usr/bin/env bash
# Reconcile the archived documentation versions with the release tags.
#
#   - every release tag vX.Y.Z that is on main's history and carries the docs/
#     folder gets a snapshot in website/versioned_docs/version-X.Y.Z
#   - the version in version.json is the current docs (docs/), so it is not archived
#   - each new snapshot is stamped with its own version (scripts/stamp-doc-version.mjs)
#   - versions.json is rebuilt from the snapshots that exist, newest first
#
# Tags that cannot be archived (not on main's history, or no docs/ in them) are
# listed at the end so they can be fixed by hand. Safe to run repeatedly.
#
# Usage: sync-doc-versions.sh [tag-pattern]   (run from the repository root)
#
# Local runs in a shallow clone (no network, tags fetched at depth 1) can set
#   SYNC_DOCS_OFFLINE=1        do not fetch or unshallow
#   SYNC_DOCS_SKIP_ANCESTRY=1  do not test that the tag is on main's history
#                              (git merge-base cannot answer in a shallow clone)
# Neither is set in CI, where both checks run as usual.
set -euo pipefail

PATTERN="${1:-^v1\.[0-9]+\.[0-9]+$}"
MIN_PAGES=5                                   # a tag with fewer docs pages is not a docs release
CURRENT="$(jq -r .version version.json)"
cd website

if [ "${SYNC_DOCS_OFFLINE:-0}" != 1 ]; then
  git rev-parse --is-shallow-repository | grep -q true && git fetch --unshallow --tags -q || true
  git fetch --tags -q 2>/dev/null || true
fi
rm -rf i18n/*/docusaurus-plugin-content-docs/current   # generated copies must not leak into snapshots
mkdir -p versioned_docs versioned_sidebars

# versions.json = the snapshots on disk, newest first. Written before archiving too:
# docs:version loads the site config, which fails when versions.json lists a
# snapshot that is not on disk (for example one deleted to be archived again).
write_versions_json() {
  find versioned_docs -mindepth 1 -maxdepth 1 -type d -name 'version-*' -printf '%f\n' \
    | sed 's/^version-//' | sort -rV | jq -R . | jq -s . > versions.json
}
write_versions_json

# If archiving stops half-way, put the current docs and sidebars back.
restore_current_docs() {
  git reset -q HEAD -- ../docs sidebars.ts sidebars.js
  rm -rf ../docs
  git checkout -- ../docs sidebars.ts sidebars.js
}
trap 'echo "sync-doc-versions: failed, restoring docs/"; restore_current_docs' ERR

archived=(); skipped=(); present=(); dropped=()
for tag in $(git tag -l | grep -E "$PATTERN" | sort -V); do
  v="${tag#v}"
  [ "$v" = "$CURRENT" ] && continue
  if [ "${SYNC_DOCS_SKIP_ANCESTRY:-0}" != 1 ] && ! git merge-base --is-ancestor "$tag" HEAD; then
    skipped+=("$tag (not on main's history: $(git log -1 --format=%ad --date=short "$tag"))"); continue
  fi
  pages=$(git ls-tree -r --name-only "$tag" -- ../docs | grep -cE '\.mdx?$' || true)
  if [ "$pages" -lt "$MIN_PAGES" ]; then
    skipped+=("$tag (only $pages docs pages)"); continue
  fi
  if [ -d "versioned_docs/version-$v" ] && [ -n "$(find "versioned_docs/version-$v" -name '*.md*' -print -quit)" ] \
     && [ -f "versioned_sidebars/version-$v-sidebars.json" ]; then
    present+=("$v"); continue
  fi
  echo "Archiving $tag ($pages pages)"
  rm -rf "versioned_docs/version-$v" "versioned_sidebars/version-$v-sidebars.json"
  cp versions.json /tmp/versions.before.json
  rm -rf ../docs                                         # start empty: index.md vs index.mdx must not both land in a snapshot
  git checkout "$tag" -- ../docs
  # Some tags carry a page twice, as X.md and X.mdx (v1.1.1 has docs/index.md and
  # docs/index.mdx). Docusaurus refuses two docs with one id, so keep the .mdx.
  while IFS= read -r mdx; do
    if [ -f "${mdx%.mdx}.md" ]; then
      rm -f "${mdx%.mdx}.md"
      dropped+=("$tag: ${mdx#../}, dropped the duplicate .md")
    fi
  done < <(find ../docs -name '*.mdx')
  for sb in sidebars.ts sidebars.js; do git cat-file -e "$tag:website/$sb" 2>/dev/null && git checkout "$tag" -- "$sb"; done
  npm run docusaurus -- docs:version "$v"
  restore_current_docs                                   # unstage the old tag's files, put the current docs back
  [ -d "versioned_docs/version-$v" ] && [ -f "versioned_sidebars/version-$v-sidebars.json" ] \
    || { echo "snapshot of $tag was not created"; exit 1; }
  # The docs at a tag can still name an older release ("This page describes
  # InvenTag v1.0.2" in the 1.1.2 docs): make the snapshot name its own version.
  node scripts/stamp-doc-version.mjs "versioned_docs/version-$v" "$v"
  # Sidebar and version-label strings for the translated sites: start from the
  # current docs' strings (current.json) so the category labels stay translated.
  for cur in i18n/*/docusaurus-plugin-content-docs/current.json; do
    out="${cur%current.json}version-$v.json"
    [ -f "$out" ] || jq --arg v "$v" \
      '{"version.label": {message: "v\($v)", description: "The label for version \($v)"}} + .' "$cur" > "$out"
  done
  archived+=("$v")
done

trap - ERR
write_versions_json
for f in versioned_sidebars/version-*-sidebars.json; do
  v="${f#versioned_sidebars/version-}"; v="${v%-sidebars.json}"
  [ -d "versioned_docs/version-$v" ] || { echo "removing orphan sidebar $f"; rm -f "$f"; }
done

echo
echo "Current docs:  v$CURRENT (docs/)"
echo "Archived now:  ${archived[*]:-none}"
echo "Already there: ${present[*]:-none}"
echo "versions.json: $(jq -c . versions.json)"
if [ "${#dropped[@]}" -gt 0 ]; then
  echo "Duplicate pages in tags:"; printf '  - %s\n' "${dropped[@]}"
fi
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "Skipped tags:"; printf '  - %s\n' "${skipped[@]}"
fi
