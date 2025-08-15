# Repository Configuration for Automated Releases

This document provides instructions for configuring your GitHub repository to allow the automated release workflow to push version updates back to the main branch.

## 🚀 Quick Setup

### Step 1: Repository Settings
1. Go to your repository on GitHub
2. Click on **Settings** tab
3. Navigate to **Actions** → **General**

### Step 2: Configure Actions Permissions
Under **Actions permissions**, ensure the following are enabled:
- ✅ **Allow all actions and reusable workflows**
- ✅ **Allow actions created by GitHub**
- ✅ **Allow actions by Marketplace verified creators**

### Step 3: Configure Workflow Permissions
Under **Workflow permissions**, select:
- ✅ **Read and write permissions**
- ✅ **Allow GitHub Actions to create and approve pull requests**

### Step 4: Configure Branch Protection (If Main is Protected)

If your main branch has protection rules:

1. Go to **Settings** → **Branches**
2. Find your main branch protection rule
3. Click **Edit**
4. Under **Restrict pushes that create files**, ensure:
   - ✅ **Do not restrict pushes that create files** (or)
   - ✅ Add `github-actions[bot]` to the allowed list

5. Under **Allow force pushes**, you can leave this **disabled**
6. Under **Do not allow bypassing the above settings**, ensure:
   - ✅ **Include administrators** is checked if you want consistent enforcement

### Step 5: Alternative - Add GitHub Actions as Exception

If you want to keep strict branch protection:

1. In branch protection settings
2. Under **Restrict pushes that create files**:
   - Add `github-actions[bot]` to the exceptions
3. Under **Allow specified actors to bypass required pull requests**:
   - Add `github-actions[bot]`

## 🔧 Advanced Configuration

### Option 1: Use Personal Access Token (PAT)

For maximum control, you can use a Personal Access Token:

1. Create a fine-grained PAT with repository access
2. Grant permissions:
   - Contents: Write
   - Metadata: Read
   - Pull requests: Write
   - Actions: Write
3. Add as repository secret named `RELEASE_TOKEN`
4. Update workflow to use `${{ secrets.RELEASE_TOKEN }}` instead of `${{ secrets.GITHUB_TOKEN }}`

### Option 2: Use GitHub App

For enterprise environments:

1. Create a GitHub App with appropriate permissions
2. Install the app on your repository
3. Use the app's credentials in the workflow

## ✅ Verification

After configuration, test the setup:

1. Create a test PR with the label `release:patch`
2. Merge the PR to main
3. Verify the workflow:
   - ✅ Updates `version.json`
   - ✅ Commits changes to main
   - ✅ Creates git tag
   - ✅ Creates GitHub release

## 🚨 Troubleshooting

### Common Issues

**Error: "Remote rejected (protected branch hook declined)"**
- Solution: Add `github-actions[bot]` to branch protection exceptions

**Error: "Permission denied (push to protected branch)"**
- Solution: Enable "Read and write permissions" in Actions settings

**Error: "Resource not accessible by integration"**
- Solution: Verify workflow permissions include "contents: write"

### Debug Steps

1. Check workflow permissions in `.github/workflows/release.yml`:
   ```yaml
   permissions:
     contents: write
     issues: write
     pull-requests: write
     actions: write
   ```

2. Verify repository Actions settings:
   - Actions permissions: Enabled
   - Workflow permissions: Read and write

3. Check branch protection settings:
   - GitHub Actions bot has appropriate exceptions
   - Force push restrictions don't block version commits

## 📋 Required Labels

The workflow recognizes these PR labels for version bumping:
- `release:major` - Major version bump (e.g., 1.0.0 → 2.0.0)
- `release:minor` - Minor version bump (e.g., 1.0.0 → 1.1.0)  
- `release:patch` - Patch version bump (e.g., 1.0.0 → 1.0.1)

Without labels, PRs merged to main default to patch releases.

## 🛡️ Security Considerations

1. **Principle of Least Privilege**: Only grant minimum required permissions
2. **Token Rotation**: If using PAT, rotate regularly
3. **Audit Logs**: Monitor Actions usage in repository settings
4. **Branch Protection**: Keep main branch protection for human pushes
5. **Review Process**: Require PR reviews for all changes except automated version bumps

## 📚 Additional Resources

- [GitHub Actions Permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)
- [Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [Fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

---

✅ **Once configured, every PR merge to main will automatically:**
- Update `version.json` with new version and release notes
- Commit changes back to main branch  
- Create and push git tag
- Generate comprehensive GitHub release with assets