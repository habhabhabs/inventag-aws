#!/usr/bin/env bash
# Is the "## [Unreleased]" section of CHANGELOG.md empty?
#
# release.yml runs this on the push of its own "chore: bump version to" commit
# (job "Changelog rolled"): right after a release the notes must sit under the
# new version heading, not under Unreleased (register rows C-09 and P-16). The
# check reports; it does not stop or undo the release.
#
# Usage: check-unreleased-empty.sh [changelog-file]   (default CHANGELOG.md)
# Exit: 0 empty; 1 not empty (the first lines are printed with a GitHub
#       "::error::" line); 2 no file or no "## [Unreleased]" heading.
set -euo pipefail

file="${1:-CHANGELOG.md}"

if [ ! -f "$file" ]; then
  echo "::error::check-unreleased-empty: $file not found"
  exit 2
fi
if ! grep -q '^## \[Unreleased\][[:space:]]*$' "$file"; then
  echo "::error::check-unreleased-empty: $file has no '## [Unreleased]' heading"
  exit 2
fi

# The non-blank lines between "## [Unreleased]" and the next "## " heading,
# each with its line number.
content=$(awk '
  /^## \[Unreleased\][[:space:]]*$/ { inside = 1; next }
  inside && /^## / { exit }
  inside && /[^[:space:]]/ { print NR ": " $0 }
' "$file")

if [ -z "$content" ]; then
  echo "check-unreleased-empty: the Unreleased section of $file is empty"
  exit 0
fi

count=$(printf '%s\n' "$content" | wc -l | tr -d ' ')
echo "::error::The Unreleased section of $file is not empty after a release ($count lines). Move them under the released version's heading in a commit marked [skip release]; see the release runbook."
printf '%s\n' "$content" | head -n 10
exit 1
