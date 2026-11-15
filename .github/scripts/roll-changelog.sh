#!/usr/bin/env bash
# Roll the "Unreleased" section of CHANGELOG.md into a release section.
#
#   "## [Unreleased]" + notes   ->   "## [Unreleased]" (empty)
#                                    "## [vX.Y.Z] - YYYY-MM-DD" + notes
#
# The link references at the bottom follow the same way:
#   [Unreleased]: .../compare/vPREV...HEAD  ->  .../compare/vX.Y.Z...HEAD
#   a new line  [vX.Y.Z]: .../compare/vPREV...vX.Y.Z  is added below it.
#
# Does nothing (exit 0, one log line) when the Unreleased section has no
# content, or when the file already has a section for that version, so it is
# safe to run twice. Exit 1 when the file or the "## [Unreleased]" heading is
# missing, or the arguments are wrong.
#
# Usage: roll-changelog.sh <version> <YYYY-MM-DD> [changelog-file]
#   version: X.Y.Z or vX.Y.Z. The file defaults to CHANGELOG.md.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: roll-changelog.sh <version> <YYYY-MM-DD> [changelog-file]" >&2
  exit 1
fi
version="v${1#v}"
date="$2"
file="${3:-CHANGELOG.md}"

if ! [[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "roll-changelog: '$1' is not a version like 1.2.3" >&2
  exit 1
fi
if ! [[ "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "roll-changelog: '$date' is not a date like 2026-11-15" >&2
  exit 1
fi
if [ ! -f "$file" ]; then
  echo "roll-changelog: $file not found" >&2
  exit 1
fi
if ! grep -q '^## \[Unreleased\][[:space:]]*$' "$file"; then
  echo "roll-changelog: $file has no '## [Unreleased]' heading" >&2
  exit 1
fi
if grep -q "^## \[$version\]" "$file"; then
  echo "roll-changelog: $file already has a section for $version: nothing to do"
  exit 0
fi

# 1 when the Unreleased section holds at least one non-blank line.
has_content=$(awk '
  /^## \[Unreleased\][[:space:]]*$/ { inside = 1; next }
  inside && /^## / { exit }
  inside && /[^[:space:]]/ { found = 1 }
  END { print found ? 1 : 0 }
' "$file")
if [ "$has_content" != 1 ]; then
  echo "roll-changelog: the Unreleased section of $file is empty: nothing to do"
  exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
awk -v v="$version" -v d="$date" '
  /^## \[Unreleased\][[:space:]]*$/ && !done_heading {
    print "## [Unreleased]"; print ""; print "## [" v "] - " d
    done_heading = 1; next
  }
  /^\[Unreleased\]: / && !done_link {
    url = $2
    if (match(url, /\/compare\/[^\/]+\.\.\.HEAD$/)) {
      base = substr(url, 1, RSTART - 1)
      prev = substr(url, RSTART + 9, RLENGTH - 9 - 7)
      print "[Unreleased]: " base "/compare/" v "...HEAD"
      print "[" v "]: " base "/compare/" prev "..." v
    } else {
      print
    }
    done_link = 1; next
  }
  { print }
' "$file" > "$tmp"
cat "$tmp" > "$file"
echo "roll-changelog: $file: Unreleased rolled into $version - $date"
