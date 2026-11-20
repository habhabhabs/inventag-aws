#!/usr/bin/env bash
# Check that an install left the lxml extension modules as the release archive
# has them (Decision 2, condition 2: lxml's modules stay separate, unmodified
# files; Homebrew may relink or re-sign files in its keg).
#
#   check_lxml.sh <release archive .tar.gz> <installed root>
#
# The installed root is the folder that holds the archive's top-level content,
# for Homebrew $(brew --prefix inventag)/libexec. Every lxml/*.so of the archive
# must be at the same place under the root with the same sha256, and the root
# must hold no other lxml/*.so. Output, one line each: "ok <path>",
# "DIFFERENT <path>", "MISSING <path>", "EXTRA <path>". Exit 0 when all are ok,
# 1 on any other line or when the archive has no lxml/*.so (a check that finds
# nothing proves nothing), 2 on wrong usage. No network.
set -euo pipefail

usage() { echo "usage: check_lxml.sh <archive.tar.gz> <installed root>" >&2; exit 2; }
[ $# -eq 2 ] || usage
archive="$1"
root="$2"
[ -f "$archive" ] || { echo "check_lxml.sh: $archive is not a file" >&2; exit 2; }
[ -d "$root" ] || { echo "check_lxml.sh: $root is not a folder" >&2; exit 2; }

if command -v sha256sum >/dev/null 2>&1; then
  sha() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
  sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
  echo "check_lxml.sh: neither sha256sum nor shasum is installed" >&2
  exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -xzf "$archive" -C "$work" --strip-components=1

# Paths are relative and sorted; a name with a newline is not expected.
(cd "$work" && find . -type f -path '*/lxml/*' -name '*.so' | sed 's|^\./||' | LC_ALL=C sort) > "$work.expected"
(cd "$root" && find . -type f -path '*/lxml/*' -name '*.so' | sed 's|^\./||' | LC_ALL=C sort) > "$work.found"
trap 'rm -rf "$work" "$work.expected" "$work.found"' EXIT

if [ ! -s "$work.expected" ]; then
  echo "check_lxml.sh: the archive has no lxml *.so file, so nothing can be compared" >&2
  echo "no lxml modules in the archive"
  exit 1
fi

status=0
while IFS= read -r rel; do
  if [ ! -f "$root/$rel" ]; then
    echo "MISSING $rel"; status=1
  elif [ "$(sha "$work/$rel")" = "$(sha "$root/$rel")" ]; then
    echo "ok $rel"
  else
    echo "DIFFERENT $rel"; status=1
  fi
done < "$work.expected"
while IFS= read -r rel; do
  echo "EXTRA $rel"; status=1
done < <(LC_ALL=C comm -13 "$work.expected" "$work.found")
exit "$status"
