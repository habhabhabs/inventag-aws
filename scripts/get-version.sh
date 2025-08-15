#!/bin/bash
# Script to dynamically determine version based on git tags and branch
# Usage: ./scripts/get-version.sh [--format=semver|docker|branch]

set -e

# Default format
FORMAT="semver"

# Parse arguments
for arg in "$@"; do
  case $arg in
    --format=*)
      FORMAT="${arg#*=}"
      shift
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: $0 [--format=semver|docker|branch]"
      exit 1
      ;;
  esac
done

# Get the current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Check if we're on a tagged commit
if git describe --exact-match --tags HEAD >/dev/null 2>&1; then
    # We're on a tagged commit
    VERSION=$(git describe --exact-match --tags HEAD)
    VERSION_TYPE="tag"
else
    # We're not on a tagged commit, generate version based on branch and commit
    LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    COMMIT_SHORT=$(git rev-parse --short HEAD)
    
    if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
        # Main branch: use latest tag + dev suffix
        VERSION="${LATEST_TAG}-dev+${COMMIT_SHORT}"
        VERSION_TYPE="development"
    elif [[ "$BRANCH" == feature/* ]]; then
        # Feature branch: use branch name + commit
        BRANCH_CLEAN=$(echo "$BRANCH" | sed 's/feature\///' | sed 's/[^a-zA-Z0-9]/-/g')
        VERSION="${LATEST_TAG}-${BRANCH_CLEAN}+${COMMIT_SHORT}"
        VERSION_TYPE="feature"
    elif [[ "$BRANCH" == hotfix/* ]]; then
        # Hotfix branch: use branch name + commit
        BRANCH_CLEAN=$(echo "$BRANCH" | sed 's/hotfix\///' | sed 's/[^a-zA-Z0-9]/-/g')
        VERSION="${LATEST_TAG}-${BRANCH_CLEAN}+${COMMIT_SHORT}"
        VERSION_TYPE="hotfix"
    else
        # Other branches: use branch name + commit
        BRANCH_CLEAN=$(echo "$BRANCH" | sed 's/[^a-zA-Z0-9]/-/g')
        VERSION="${LATEST_TAG}-${BRANCH_CLEAN}+${COMMIT_SHORT}"
        VERSION_TYPE="branch"
    fi
fi

# Format the version according to requested format
case $FORMAT in
    semver)
        echo "$VERSION"
        ;;
    docker)
        # Docker tags can't have '+' characters
        DOCKER_VERSION=$(echo "$VERSION" | sed 's/+/-/')
        echo "$DOCKER_VERSION"
        ;;
    branch)
        echo "$BRANCH"
        ;;
    json)
        cat << EOF
{
  "version": "$VERSION",
  "version_type": "$VERSION_TYPE",
  "branch": "$BRANCH",
  "commit": "$(git rev-parse HEAD)",
  "commit_short": "$(git rev-parse --short HEAD)",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        ;;
    *)
        echo "Unknown format: $FORMAT"
        echo "Supported formats: semver, docker, branch, json"
        exit 1
        ;;
esac