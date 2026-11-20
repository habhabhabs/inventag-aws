#!/usr/bin/env bash
# Lay out the Homebrew tap repository (habhabhabs/homebrew-inventag) in an empty
# directory and make one local commit (plan 3.4, work order B4).
#
#   init_tap.sh <directory> [--formula <rendered inventag.rb>]
#
# The directory must be empty or not exist. It gets README.md, a copy of
# LICENSE, .github/workflows/ci.yml and Formula/. Formula/ holds .gitkeep until
# the first release writes inventag.rb (scripts/packaging/render_formula.py);
# --formula adds an already rendered file. The unrendered template is never
# copied.
#
# This script makes no network call. It does not run gh and does not push. It
# prints the two commands that the owner runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TAP_SRC="$ROOT/packaging/homebrew-tap"
REPO="habhabhabs/homebrew-inventag"
URL="https://github.com/$REPO.git"

die() { echo "init_tap.sh: $*" >&2; exit 2; }
usage() { echo "usage: init_tap.sh <empty-directory> [--formula <rendered inventag.rb>]" >&2; exit 2; }

target=""
formula=""
while [ $# -gt 0 ]; do
  case "$1" in
    --formula) [ $# -ge 2 ] || usage; formula="$2"; shift 2 ;;
    -*) usage ;;
    *) [ -z "$target" ] || usage; target="$1"; shift ;;
  esac
done
[ -n "$target" ] || usage

if [ -n "$formula" ]; then
  [ -f "$formula" ] || die "the formula file $formula does not exist"
  if grep -q '{{' "$formula"; then
    die "$formula is still a template (it holds {{...}}); render it with render_formula.py first"
  fi
fi

if [ -e "$target" ] && [ ! -d "$target" ]; then
  die "$target is not a directory"
fi
if [ -d "$target" ]; then
  abs="$(cd "$target" && pwd -P)"
  case "$abs/" in
    "$ROOT"/*) die "$target is inside the InvenTag source tree; use a directory outside it" ;;
  esac
  if [ -n "$(ls -A "$target")" ]; then
    die "$target is not empty; use a new or empty directory"
  fi
fi
# The commit is made in a new repository, which reads only the global settings
# and the environment, so the check runs outside any repository too.
probe="$(mktemp -d)"
if ! git -C "$probe" -c user.useConfigOnly=true var GIT_AUTHOR_IDENT >/dev/null 2>&1 \
   || ! git -C "$probe" -c user.useConfigOnly=true var GIT_COMMITTER_IDENT >/dev/null 2>&1; then
  rmdir "$probe"
  die "git has no name and email for the commit; run: git config --global user.name \"Your Name\" and git config --global user.email you@example.com"
fi
rmdir "$probe"

mkdir -p "$target"
target="$(cd "$target" && pwd -P)"

cp "$TAP_SRC/README.md" "$target/README.md"
cp "$ROOT/LICENSE" "$target/LICENSE"
mkdir -p "$target/.github/workflows" "$target/Formula"
cp "$TAP_SRC/.github/workflows/ci.yml" "$target/.github/workflows/ci.yml"
if [ -n "$formula" ]; then
  cp "$formula" "$target/Formula/inventag.rb"
else
  : > "$target/Formula/.gitkeep"
fi

git -C "$target" init -q
git -C "$target" symbolic-ref HEAD refs/heads/main
git -C "$target" remote add origin "$URL"
git -C "$target" add -A
git -C "$target" commit -q -m "Create the InvenTag tap"

q="$(printf '%q' "$target")"
echo "The tap is laid out in $target (one local commit on the branch main; nothing was pushed)."
echo "Two commands are yours to run, in this order:"
echo
printf '  gh repo create %s --public\n' "$REPO"
printf '  git -C %s push -u origin main\n' "$q"
echo
echo "Then the release workflow needs the secret HOMEBREW_TAP_TOKEN and the variable HOMEBREW_TAP_REPO (see the B4 report)."
