#!/usr/bin/env bash
# Did the application change since the last release?
#
# The application is what goes into the published package or changes what it
# does. This file is the ONLY place that lists those paths; the release
# workflow (release.yml) releases a new version only when this prints
# application_changed=true. Documentation, the site, tests, docs tooling,
# examples and GitHub Actions code are not the application.
#
# Usage: release-needed.sh [commit]     (default HEAD; run inside the repository)
#
# Prints, one per line:
#   base_tag=<newest vX.Y.Z tag that is an ancestor of the commit; empty if none>
#   application_changed=true|false
#   path=<application path>             (one line per changed application path)
#
# One release covers every commit since the previous tag, so the whole range
# base_tag..commit is read, not only the last commit. The release job's own
# "chore: bump version to ..." commits are not counted. Without a base tag,
# every file in the commit counts as new. A shallow clone is refused (exit 2):
# the answer needs the tags and the history.
set -euo pipefail

TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'
BUMP_SUBJECT='chore: bump version to '

# Proof for each path outside inventag/ is in pyproject.toml:
#   requirements.txt  [tool.setuptools.dynamic] dependencies = file requirements.txt
#   LICENSE           license-files = ["LICENSE"]: copied into the wheel's dist-info
#   pyproject.toml, setup.py, setup.cfg, MANIFEST.in: the build configuration
is_application_path() {
  case "$1" in
    inventag/*) return 0 ;;
    pyproject.toml | setup.py | setup.cfg | MANIFEST.in) return 0 ;;
    requirements.txt | LICENSE) return 0 ;;
    *) return 1 ;;
  esac
}

git() { command git -c core.quotePath=false "$@"; }

commit="${1:-HEAD}"

if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
  echo "release-needed: shallow clone; check out with all history and tags (fetch-depth: 0)" >&2
  exit 2
fi
if ! sha=$(git rev-parse --verify --quiet "${commit}^{commit}"); then
  echo "release-needed: not a commit: $commit" >&2
  exit 2
fi

base_tag=$(git tag --merged "$sha" | { grep -E "$TAG_PATTERN" || true; } | sort -V | tail -n 1)

# Every file changed since base_tag (or every file in the commit without one).
changed_files() {
  if [ -z "$base_tag" ]; then
    git ls-tree -r --name-only "$sha"
    return
  fi
  local ids subject
  git rev-list --parents "$base_tag..$sha" | while read -r -a ids; do
    subject=$(git log -1 --format=%s "${ids[0]}")
    case "$subject" in "$BUMP_SUBJECT"*) continue ;; esac
    if [ "${#ids[@]}" -gt 2 ]; then
      # Merge commit: only what the merge itself changed; the merged
      # commits are in the range and are read one by one.
      git diff-tree -r --cc --name-only --no-commit-id "${ids[0]}"
    else
      git diff-tree -r --root --no-renames --name-only --no-commit-id "${ids[0]}"
    fi
  done
}

files=$(changed_files)
app_paths=()
while IFS= read -r path; do
  [ -n "$path" ] || continue
  if is_application_path "$path"; then
    app_paths+=("$path")
  fi
done < <(printf '%s\n' "$files" | sort -u)

echo "base_tag=$base_tag"
if [ "${#app_paths[@]}" -gt 0 ]; then
  echo "application_changed=true"
  printf 'path=%s\n' "${app_paths[@]}"
else
  echo "application_changed=false"
fi
