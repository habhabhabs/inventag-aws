---
title: Release
---

# Release Management Guide

This repository uses automated semantic versioning for releases. This document explains how the release system works and how to trigger releases.

## How It Works

The release system automatically increments versions following [Semantic Versioning](https://semver.org/) principles:
- **MAJOR** version (e.g., 1.0.0 → 2.0.0): Breaking changes
- **MINOR** version (e.g., 1.0.0 → 1.1.0): New features, backwards compatible
- **PATCH** version (e.g., 1.0.0 → 1.0.1): Bug fixes, minor updates

## Version Tracking

The current version is stored in `version.json` at the repository root:
```json
{
  "version": "1.0.0",
  "release_notes": "Release 1.0.0"
}
```

## Triggering Releases

### 1. Automatic Releases (via Pull Requests)

When a Pull Request is merged to the `main` branch, a release is automatically triggered based on PR labels:

#### PR Labels for Version Control
Add one of these labels to your PR to specify the version bump:

- `release:patch` - For bug fixes and minor updates (default if no label)
- `release:minor` - For new features that are backwards compatible  
- `release:major` - For breaking changes

**Example:**
```bash
# When creating a PR, add the appropriate label:
gh pr create --title "feat: Add new export format" --label "release:minor"
```

#### Breaking Changes Detection
If your PR contains breaking changes (indicated by `!` in title or `BREAKING CHANGE` in description), you MUST add the `release:major` label, or the PR checks will fail.

### 2. Manual Releases (via GitHub Actions)

You can manually trigger a release from the GitHub Actions UI:

1. Go to **Actions** → **Automated Release** 
2. Click **Run workflow**
3. Select the version bump type: `patch`, `minor`, or `major`
4. Click **Run workflow**

### 3. Command Line Manual Release

Using GitHub CLI:
```bash
# Trigger a patch release
gh workflow run "Automated Release" --field version_bump=patch

# Trigger a minor release  
gh workflow run "Automated Release" --field version_bump=minor

# Trigger a major release
gh workflow run "Automated Release" --field version_bump=major
```

## Release Process

When a release is triggered, the system automatically:

1. **Calculates New Version**: Based on current version and bump type
2. **Updates version.json**: With the new version number
3. **Generates Release Notes**: From commit messages since last release
4. **Creates Git Tag**: In format `v1.0.0`
5. **Creates GitHub Release**: With generated notes and assets
6. **Uploads Assets**: Source code archives (.tar.gz and .zip)
7. **Runs Tests**: Validates the release works correctly

## Release Notes

Release notes are automatically generated and include:
- **What's Changed**: List of commits since last release
- **Changes by Type**: Organized by conventional commit types (feat, fix, docs, etc.)
- **Installation & Usage**: Quick start guide
- **Full Changelog**: Link to compare view

## Conventional Commit Messages

For better release notes, use conventional commit format:
```bash
feat: add new feature
fix: resolve bug
docs: update documentation  
perf: improve performance
chore: maintenance tasks
```

## Examples

### Creating a Feature PR
```bash
# Create feature branch
git checkout -b feat/new-export-format

# Make changes and commit
git commit -m "feat: add JSON export format for compliance reports"

# Create PR with minor release label
gh pr create --title "feat: add JSON export format" --label "release:minor"

# When merged to main → triggers v1.1.0 release
```

### Creating a Bug Fix PR
```bash
# Create fix branch  
git checkout -b fix/excel-formatting

# Make changes and commit
git commit -m "fix: resolve Excel cell formatting issue"

# Create PR (patch is default)
gh pr create --title "fix: resolve Excel formatting issue"

# When merged to main → triggers v1.0.1 release
```

### Creating a Breaking Change PR
```bash
# Create feature branch
git checkout -b feat/api-redesign

# Make breaking changes and commit
git commit -m "feat!: redesign CLI interface

BREAKING CHANGE: --input flag renamed to --file"

# Create PR with major release label
gh pr create --title "feat!: redesign CLI interface" --label "release:major"

# When merged to main → triggers v2.0.0 release
```

## Release Assets

Each release includes:
- **Source Code**: `inventag-aws-v1.0.0.tar.gz` and `inventag-aws-v1.0.0.zip`
- **Release Notes**: Detailed changelog and installation instructions
- **Git Tag**: `v1.0.0` for version tracking

## Monitoring Releases

- **GitHub Releases**: https://github.com/[owner]/[repo]/releases
- **Actions Logs**: Monitor release progress in GitHub Actions
- **Version File**: Check `version.json` for current version

## Troubleshooting

### Common Issues

1. **Release Not Triggered**
   - Ensure PR is merged to `main` branch
   - Check for proper PR labels
   - Verify GitHub Actions are enabled

2. **Version Calculation Errors**
   - Check `version.json` format is valid
   - Ensure semver dependency is installed

3. **Permission Errors**
   - Verify repository has proper GitHub token permissions
   - Check that Actions have `contents: write` permission

### Manual Recovery

If a release fails, you can:
1. Check the Actions logs for specific errors
2. Fix any issues and re-run the workflow
3. Manually create releases if needed using GitHub UI

## Best Practices

1. **Use Descriptive Commit Messages**: Helps generate better release notes
2. **Test Before Merging**: Ensure all tests pass
3. **Label PRs Appropriately**: Use correct version bump labels
4. **Review Breaking Changes**: Carefully consider major version bumps
5. **Monitor Releases**: Check that releases complete successfully

---

For questions or issues with the release system, please check the GitHub Actions logs or create an issue.
