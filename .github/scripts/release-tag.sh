#!/usr/bin/env bash
# Tag the release commit and push the tag, with a bounded retry.
#
# Called by the "Create Git Tag" step of release.yml with the commit that the
# step "Commit and push version.json changes" pushed to main (its `sha` output),
# never with whatever HEAD happens to be.
#
# Why a retry: in the v1.2.2 release (run 44499441432) the push of the tag, one
# step after the push of the bump commit, was refused with
#   ! [remote rejected] v1.2.2 -> v1.2.2 (missing necessary objects)
# git gives that answer when the server advertises a branch at the commit (so
# the client sends no objects with the tag) and then cannot read that commit.
# tests/unit/test_release_tag.py makes the same answer with a local bare
# repository. Not verified against GitHub: that the server's view of a commit
# pushed seconds before is the cause, and that a later attempt succeeds.
#
# Steps:
#   1. If the remote already has the tag on <sha>: done (exit 0). On another
#      commit: exit 1, nothing is changed.
#   2. Create the local lightweight tag on <sha> (an existing local tag must
#      already point at <sha>).
#   3. Push refs/tags/<tag> up to RELEASE_TAG_ATTEMPTS times (default 5),
#      waiting RELEASE_TAG_DELAY seconds times the attempt number in between
#      (default 5: 5 + 10 + 15 + 20 = 50 s at most).
#   4. After each attempt read the tag back with git ls-remote. Success means
#      the remote tag points at <sha>, whatever git push said.
#   5. On failure: a GitHub "::error::" line that names the manual recovery
#      (tag and release by hand, then a run with publish_existing_tag), exit 1.
#
# Usage: release-tag.sh <tag vX.Y.Z> <commit sha> [remote]   (remote: origin)
# Exit: 0 tag on the remote at <sha>; 1 not pushed or on another commit;
#       2 wrong arguments.
set -euo pipefail

git() { command git -c core.quotePath=false "$@"; }

log() { printf 'release-tag: %s\n' "$*"; }

# The commit that refs/tags/<tag> names on the remote (peeled for an annotated
# tag), or nothing when the remote has no such tag or cannot be read.
remote_tag_sha() {
  local remote="$1" tag="$2" out
  out=$(git ls-remote --tags "$remote" "refs/tags/$tag" "refs/tags/$tag^{}" 2>/dev/null) || return 0
  printf '%s\n' "$out" | awk -v t="refs/tags/$tag" '
    $2 == t "^{}" { p = $1 } $2 == t { l = $1 }
    END { print (p != "" ? p : l) }'
}

recovery_message() {
  local tag="$1" sha="$2"
  printf '%s\n' \
    "::error::Tag $tag was not pushed to commit $sha. The bump commit is on main, but there is no tag, no GitHub release and no PyPI upload. Recovery: on the GitHub releases page create the release $tag with target $sha (this creates the tag), then run Automated Release by hand with publish_existing_tag=$tag. See the release runbook, section \"The tag push failed\"."
}

push_tag_with_retry() {
  local tag="$1" sha="$2" remote="${3:-origin}"
  local attempts="${RELEASE_TAG_ATTEMPTS:-5}" delay="${RELEASE_TAG_DELAY:-5}"
  local existing local_sha attempt

  if ! [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "release-tag: '$tag' is not a tag like v1.2.3" >&2
    return 2
  fi
  if ! [[ "$sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "release-tag: '$sha' is not a full commit id" >&2
    return 2
  fi
  if ! [[ "$attempts" =~ ^[1-9][0-9]?$ ]] || ! [[ "$delay" =~ ^[0-9]+$ ]]; then
    echo "release-tag: RELEASE_TAG_ATTEMPTS must be 1 to 99 and RELEASE_TAG_DELAY a whole number" >&2
    return 2
  fi
  if [ "$(git cat-file -t "$sha" 2>/dev/null || true)" != commit ]; then
    echo "release-tag: $sha is not a commit in this repository" >&2
    return 2
  fi

  existing=$(remote_tag_sha "$remote" "$tag")
  if [ "$existing" = "$sha" ]; then
    log "$remote already has $tag on $sha: nothing to push"
    return 0
  fi
  if [ -n "$existing" ]; then
    echo "::error::$remote already has $tag on $existing, not on $sha. Nothing was changed. Check which commit $tag should name before you release by hand."
    return 1
  fi

  if local_sha=$(git rev-parse --verify --quiet "refs/tags/$tag^{commit}"); then
    if [ "$local_sha" != "$sha" ]; then
      echo "::error::The local tag $tag points at $local_sha, not at $sha. Nothing was pushed."
      return 1
    fi
  else
    git tag "$tag" "$sha"
  fi
  log "tag $tag on $sha (remote main: $(git ls-remote "$remote" refs/heads/main 2>/dev/null | cut -f1 || true))"

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if git push "$remote" "refs/tags/$tag:refs/tags/$tag"; then
      log "attempt $attempt of $attempts: push accepted"
    else
      log "attempt $attempt of $attempts: push refused"
    fi
    existing=$(remote_tag_sha "$remote" "$tag")
    if [ "$existing" = "$sha" ]; then
      log "verified with git ls-remote: $remote has $tag on $sha"
      return 0
    fi
    if [ -n "$existing" ]; then
      echo "::error::$remote now has $tag on $existing, not on $sha. Stopped."
      return 1
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      log "the remote has no $tag yet; next attempt in $((delay * attempt)) s"
      sleep "$((delay * attempt))"
    fi
  done

  recovery_message "$tag" "$sha"
  return 1
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: release-tag.sh <tag vX.Y.Z> <commit sha> [remote]" >&2
    exit 2
  fi
  push_tag_with_retry "$@"
fi
