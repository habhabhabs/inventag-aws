---
title: Setup Branch Protection
---

# InvenTag - Branch Protection Setup Guide

**Part of InvenTag**: Python tool to check on AWS™ cloud inventory and tagging.

> **Disclaimer**: AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is not affiliated with AWS.

## GitHub Branch Protection Rules

To enforce proper pull request workflows, set up these branch protection rules for the `main` branch:

### Option 1: Using GitHub CLI (gh)

```bash
# Install GitHub CLI if not already installed
# brew install gh (on macOS)
# Then authenticate: gh auth login

# Set up comprehensive branch protection (corrected syntax)
gh api \
  --method PUT \
  repos/habhabhabs/inventag-aws/branches/main/protection \
  --raw-field required_status_checks='{"strict":true,"contexts":[]}' \
  --field enforce_admins=true \
  --raw-field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null \
  --raw-field allow_force_pushes='false' \
  --raw-field allow_deletions='false'

# Alternative: Step-by-step approach (more reliable)
# 1. Enable basic protection first
gh api \
  --method PUT \
  repos/habhabhabs/inventag-aws/branches/main/protection \
  --raw-field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field enforce_admins=true \
  --field restrictions=null

# 2. Add status checks after workflows are set up
gh api \
  --method PATCH \
  repos/habhabhabs/inventag-aws/branches/main/protection/required_status_checks \
  --raw-field strict=true \
  --raw-field contexts='["ci/python-tests"]'
```

### Option 2: Using GitHub Web Interface

1. Go to: https://github.com/habhabhabs/inventag-aws/settings/branches
2. Click "Add rule" for branch name pattern: `main`
3. Enable these settings:

**Protect matching branches:**
- ✅ Require a pull request before merging
  - ✅ Require approvals (1 required)
  - ✅ Dismiss stale PR approvals when new commits are pushed
  - ✅ Require review from code owners
  - ✅ Require approval of the most recent reviewable push
- ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - Add status checks: `ci/python-tests`, `ci/linting`
- ✅ Require conversation resolution before merging
- ✅ Require signed commits (optional but recommended)
- ✅ Include administrators
- ✅ Restrict pushes that create files larger than 100MB
- ✅ Allow force pushes: **Never**
- ✅ Allow deletions: **No**

## What These Rules Enforce:

1. **No direct commits to main** - All changes must go through pull requests
2. **Required approvals** - At least 1 approval required before merging
3. **Stale review dismissal** - New commits dismiss old approvals
4. **Status checks** - Automated tests must pass
5. **Up-to-date branches** - PRs must be rebased/merged with latest main
6. **Code owner reviews** - Designated code owners must approve changes
7. **Admin enforcement** - Even admins must follow these rules
8. **No force pushes** - Prevents destructive changes to main branch
9. **No deletions** - Prevents accidental branch deletion

## Benefits:

- 🛡️ **Code Quality**: All changes reviewed before merging
- 🔍 **Automated Testing**: CI/CD checks prevent broken code
- 📝 **Documentation**: PR descriptions document changes
- 🔄 **Rollback Safety**: Clean git history for easy rollbacks
- 👥 **Team Collaboration**: Structured review process
- 🚫 **Prevent Accidents**: No direct pushes or force pushes to main
