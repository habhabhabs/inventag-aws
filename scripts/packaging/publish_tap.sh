#!/usr/bin/env bash
# Push a rendered Homebrew formula to the tap (architect plan homebrew-publish,
# section 2; work order B4c). Called by the publish-tap job of
# .github/workflows/package.yml after a real tag release.
#
#   publish_tap.sh --formula <rendered inventag.rb> --version X.Y.Z --repo <owner>/homebrew-<name>
#   publish_tap.sh --manual-steps --version X.Y.Z --repo <owner>/homebrew-<name>
#
# The first form clones the tap's main, writes Formula/inventag.rb and pushes
# one commit "inventag X.Y.Z" by Alex <alex.ng@ollion.com>, with no trailer.
# - The same file is already there: nothing is pushed, exit 0 ("already published").
# - The tap holds a higher version: nothing is pushed, exit 1 (a re-run of an
#   older tag must not take the tap back).
# - The push is refused (main moved): fetch main and do the write once more
#   on top of it (the version check runs again), push once more, then fail.
# The second form prints the steps to publish by hand, with the version filled in.
#
# The token: HOMEBREW_TAP_TOKEN in the environment. git reads it through
# GIT_ASKPASS (this script, answering from the environment). It is never put in
# a URL, an argument or a file, and the script never traces. The remote is
# PUBLISH_TAP_BASE_URL/<repo>.git; the default base is https://github.com. The
# tests use a file:// base with local bare repositories, which need no token.
#
# Exit codes: 0 published or already published; 1 the tap refused or holds a
# higher version; 2 a bad input.
set -euo pipefail

# The askpass answer. git calls GIT_ASKPASS with one prompt argument.
if [ "${PUBLISH_TAP_ASKPASS:-}" = 1 ]; then
  case "${1:-}" in
    Username*) printf '%s\n' "x-access-token" ;;
    *) printf '%s\n' "${HOMEBREW_TAP_TOKEN:-}" ;;
  esac
  exit 0
fi

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/$(basename "${BASH_SOURCE[0]}")"
SOURCE_REPO="habhabhabs/inventag-aws"
NAME="Alex"
EMAIL="alex.ng@ollion.com"

die() { echo "publish_tap.sh: $1" >&2; exit "${2:-2}"; }
usage() {
  echo "usage: publish_tap.sh --formula <file> --version X.Y.Z --repo <owner>/homebrew-<name>" >&2
  echo "       publish_tap.sh --manual-steps --version X.Y.Z --repo <owner>/homebrew-<name>" >&2
  exit 2
}

formula=""
version=""
repo=""
manual=0
while [ $# -gt 0 ]; do
  case "$1" in
    --formula) [ $# -ge 2 ] || usage; formula="$2"; shift 2 ;;
    --version) [ $# -ge 2 ] || usage; version="$2"; shift 2 ;;
    --repo) [ $# -ge 2 ] || usage; repo="$2"; shift 2 ;;
    --manual-steps) manual=1; shift ;;
    *) usage ;;
  esac
done

version_rx='^[0-9]+\.[0-9]+\.[0-9]+$'
repo_rx='^[A-Za-z0-9_.-]+/homebrew-[A-Za-z0-9_.-]+$'
[[ "$version" =~ $version_rx ]] || die "the version '$version' is not of the form X.Y.Z"
[[ "$repo" =~ $repo_rx ]] || die "the tap repository '$repo' is not of the form owner/homebrew-name"
case "$repo" in *..*) die "the tap repository '$repo' is not of the form owner/homebrew-name" ;; esac

if [ "$manual" = 1 ]; then
  cat <<EOF
The tap was not updated. Publish inventag $version by hand (architect plan
homebrew-publish, section 1), on a computer with git, gh (signed in) and python3:

cd "\$(mktemp -d)"
git clone --depth 1 --branch v$version https://github.com/$SOURCE_REPO.git src
gh release download v$version --repo $SOURCE_REPO --pattern SHA256SUMS
python3 src/scripts/packaging/render_formula.py --version $version --sums SHA256SUMS --output inventag.rb
grep -c '{{' inventag.rb            # must print 0
git clone https://github.com/$repo.git tap && cd tap
git switch -c inventag-$version
cp ../inventag.rb Formula/inventag.rb && git rm -q --ignore-unmatch Formula/.gitkeep
git add Formula/inventag.rb && git commit -m "inventag $version" && git push -u origin inventag-$version
gh run watch --repo $repo     # "Tap checks": both jobs green
git switch main && git merge --ff-only inventag-$version && git push && git push origin --delete inventag-$version
brew install habhabhabs/inventag/inventag && inventag --version && inventag selftest
EOF
  exit 0
fi

[ -n "$formula" ] || usage
[ -f "$formula" ] || die "the formula file $formula does not exist"
if grep -q '{{' "$formula"; then
  die "$formula still holds a {{...}} placeholder; render it with render_formula.py first"
fi
archive="inventag-$version-darwin-arm64.tar.gz"
grep -qF "$archive" "$formula" || die "$formula does not name $archive: it is not the formula of $version"

base="${PUBLISH_TAP_BASE_URL:-https://github.com}"
case "$base" in
  https://*)
    [ -n "${HOMEBREW_TAP_TOKEN:-}" ] || die "HOMEBREW_TAP_TOKEN is empty: the repository secret is missing or was not passed to this workflow"
    ;;
  file://*) ;;
  *) die "PUBLISH_TAP_BASE_URL must start with https:// or file://" ;;
esac
url="$base/$repo.git"

work="$(mktemp -d "${TMPDIR:-/tmp}/publish-tap.XXXXXX")"
trap 'rm -rf "$work"' EXIT
clone="$work/tap"

# Every git call: no credential helper of the runner, the token only through
# the askpass answer, no prompt, no hooks, no signing, our identity.
tapgit() {
  GIT_ASKPASS="$SELF" PUBLISH_TAP_ASKPASS=1 GIT_TERMINAL_PROMPT=0 \
  GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL" \
  GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL" \
    git -c credential.helper= -c core.hooksPath=/dev/null -c commit.gpgsign=false "$@"
}

# The version in a formula: the one in its macOS archive name.
version_of() {
  sed -n 's/.*inventag-\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)-darwin-arm64\.tar\.gz.*/\1/p' "$1" | head -n 1
}

# Prints -1, 0 or 1 for a <, =, > b (numbers, not text).
compare() {
  local a1 a2 a3 b1 b2 b3 i
  IFS=. read -r a1 a2 a3 <<<"$1"
  IFS=. read -r b1 b2 b3 <<<"$2"
  local a=("$a1" "$a2" "$a3") b=("$b1" "$b2" "$b3")
  for i in 0 1 2; do
    if ((10#${a[$i]} > 10#${b[$i]})); then echo 1; return; fi
    if ((10#${a[$i]} < 10#${b[$i]})); then echo -1; return; fi
  done
  echo 0
}

# Writes the formula on the checked-out main and commits it.
# Returns 0 committed, 10 already published; exits 1 on a higher version.
write_formula() {
  local dest="$clone/Formula/inventag.rb" old
  if [ -f "$dest" ]; then
    old="$(version_of "$dest")"
    [ -n "$old" ] || die "cannot read the version of Formula/inventag.rb in $repo; check it by hand" 1
    if [ "$(compare "$old" "$version")" = 1 ]; then
      die "Formula/inventag.rb in $repo holds $old, which is higher than $version; nothing was pushed" 1
    fi
    if cmp -s "$formula" "$dest"; then
      return 10
    fi
  fi
  # The caller runs this as `write_formula || status=$?`, which turns set -e
  # off in here: every step is checked, and the first failure stops the write.
  if ! { mkdir -p "$clone/Formula" &&
    cp "$formula" "$dest" &&
    cmp -s "$formula" "$dest" &&
    tapgit -C "$clone" rm -q --ignore-unmatch Formula/.gitkeep &&
    tapgit -C "$clone" add Formula/inventag.rb &&
    tapgit -C "$clone" commit -q -m "inventag $version"; }; then
    die "could not write and commit Formula/inventag.rb in the clone of $repo; nothing was pushed" 1
  fi
}

if ! tapgit clone -q --no-tags --single-branch --branch main "$url" "$clone" 2>"$work/clone.err"; then
  sed 's/^/  /' "$work/clone.err" >&2
  die "could not clone the main branch of $repo" 1
fi

finish() {
  local sha
  sha="$(git -C "$clone" rev-parse HEAD)"
  echo "Published inventag $version to $repo: $base/$repo/commit/$sha"
  echo "Look at the tap's checks (\"Tap checks\") for that commit: $base/$repo/actions"
  exit 0
}

already() {
  echo "Formula/inventag.rb in $repo already holds this file for $version: already published. Nothing was pushed."
  exit 0
}

status=0
write_formula || status=$?
[ "$status" = 10 ] && already
[ "$status" = 0 ] || exit "$status"

if tapgit -C "$clone" push -q origin HEAD:refs/heads/main; then
  finish
fi

echo "The push to $repo was refused. Fetching main and trying once more." >&2
tapgit -C "$clone" fetch -q --no-tags origin main
tapgit -C "$clone" reset -q --hard FETCH_HEAD
status=0
write_formula || status=$?
[ "$status" = 10 ] && already
[ "$status" = 0 ] || exit "$status"
if tapgit -C "$clone" push -q origin HEAD:refs/heads/main; then
  finish
fi
die "inventag $version was not pushed to $repo: the push was refused twice" 1
