# Documentation Versioning Guide

This guide explains how documentation versioning is set up and managed for InvenTag AWS using Docusaurus.

## Overview

Starting from **v4.2.1**, InvenTag maintains versioned documentation to:
- Track changes across releases
- Provide stable documentation for specific versions
- Allow users to access documentation for their installed version
- Maintain backward compatibility information

## Version Structure

### Version Naming Convention
- **Current Development**: `v5.0.0-dev (Current)` - Latest unreleased features
- **Released Versions**: `v4.2.1`, `v4.3.0`, etc. - Stable release documentation

### Directory Structure
```
website/
├── docs/                          # Current (dev) documentation
├── versioned_docs/               # Versioned documentation
│   ├── version-v4.2.1/          # Documentation for v4.2.1
│   └── version-v4.3.0/          # Documentation for v4.3.0 (example)
├── versioned_sidebars/           # Version-specific navigation
│   ├── version-v4.2.1-sidebars.json
│   └── version-v4.3.0-sidebars.json
└── versions.json                 # Version configuration
```

## Creating a New Version

### Automated Method (Recommended)
Use the provided script to create new versions:

```bash
# Create a new version
./create_version.sh v4.3.0

# The script will:
# 1. Create a git tag if it doesn't exist
# 2. Generate versioned documentation
# 3. Update configuration files
# 4. Provide next steps
```

### Manual Method
If you need to create a version manually:

1. **Create Git Tag** (if not exists):
   ```bash
   git tag v4.3.0
   ```

2. **Create Documentation Version**:
   ```bash
   cd website
   npm run docusaurus -- docs:version v4.3.0
   ```

3. **Update Current Version Label**:
   Edit `website/docusaurus.config.js` and update the current version label:
   ```javascript
   versions: {
     current: {
       label: 'v5.0.0-dev (Current)', // Update this
       badge: true,
     },
   },
   ```

4. **Commit Changes**:
   ```bash
   git add .
   git commit -m "docs: create documentation version v4.3.0"
   git push origin main --tags
   ```

## Version Management

### Viewing Available Versions
```bash
# List all git tags
git tag --list --sort=-version:refname

# Check Docusaurus versions
cat website/versions.json
```

### Version Configuration
The version behavior is configured in `website/docusaurus.config.js`:

```javascript
docs: {
  // Version settings
  includeCurrentVersion: true,     // Include current dev docs
  lastVersion: 'current',          // Default to current version
  versions: {
    current: {
      label: 'v5.0.0-dev (Current)',
      badge: true,
    },
    // Versioned releases are auto-configured
  },
  disableVersioning: false,        // Enable versioning
}
```

### Navigation Bar
The version dropdown is configured in the navbar:
```javascript
navbar: {
  items: [
    {
      type: 'docsVersionDropdown',
      position: 'left',
      dropdownActiveClassDisabled: true,
    },
  ],
}
```

## Testing Versioned Documentation

### Local Development
```bash
cd website
npm start
```
- Visit the documentation site
- Use the version dropdown to switch between versions
- Verify all versions load correctly

### Build Testing
```bash
cd website
npm run build
npm run serve
```

## Version Maintenance

### Updating Older Versions
If you need to update documentation for an older version:

1. **Edit the versioned files directly**:
   ```bash
   # Edit files in versioned_docs/version-v4.2.1/
   ```

2. **Commit the changes**:
   ```bash
   git add website/versioned_docs/version-v4.2.1/
   git commit -m "docs: update v4.2.1 documentation"
   ```

### Removing Old Versions
To remove outdated versions:

1. **Delete version directories**:
   ```bash
   rm -rf website/versioned_docs/version-v4.0.0
   rm -f website/versioned_sidebars/version-v4.0.0-sidebars.json
   ```

2. **Update versions.json**:
   Remove the version from the array

3. **Commit changes**:
   ```bash
   git add .
   git commit -m "docs: remove v4.0.0 documentation version"
   ```

## Best Practices

### When to Create Versions
- **Major Releases**: Always create a version (v5.0.0)
- **Minor Releases**: Create versions for significant feature additions (v4.3.0)
- **Patch Releases**: Create versions if documentation changes significantly (v4.2.2)

### Version Timing
- Create documentation versions **after** the code release is tagged
- Ensure the documentation reflects the actual released functionality
- Test the versioned documentation before pushing

### Documentation Quality
- Review all documentation before creating a version
- Ensure examples work with the specific version
- Update any version-specific installation instructions

## Troubleshooting

### Common Issues

**Version Creation Fails**:
```bash
# Check if you're in the right directory
ls website/docusaurus.config.js

# Verify Docusaurus installation
cd website && npm list @docusaurus/core
```

**Version Dropdown Not Showing**:
- Check `docusaurus.config.js` navbar configuration
- Ensure `disableVersioning: false`
- Verify `versions.json` contains versions

**Build Errors with Versions**:
- Check for broken links in versioned docs
- Verify all referenced assets exist in versioned directories
- Review console output for specific error messages

### Getting Help
- Check [Docusaurus Versioning Documentation](https://docusaurus.io/docs/versioning)
- Review existing version structure in the repository
- Test changes locally before committing

## GitHub Actions Integration

The documentation versioning system integrates with GitHub Actions workflows for automated management:

### Automated Version Creation
Use the **Create Documentation Version** workflow for new releases:

1. **Manual Trigger**: Go to Actions → Create Documentation Version
2. **Input Version**: Enter version (e.g., `v4.3.0`)
3. **Auto-Tag Option**: Choose whether to create git tag
4. **Automated Process**: 
   - Validates version format
   - Creates versioned documentation
   - Updates configuration
   - Tests build
   - Commits and pushes changes

### Documentation Deployment
The **Documentation Deployment** workflow automatically:
- Detects versioned documentation changes
- Validates all versions during build
- Tests version dropdown functionality
- Deploys with full version support

### Workflow Triggers
- **Version Creation**: Manual trigger with version input
- **Documentation Deploy**: Automatically on docs changes
- **Path Monitoring**: Watches `create_version.sh`, `versions.json`

## Version History

| Version | Release Date | Key Changes |
|---------|--------------|-------------|
| v4.2.1  | 2024-01-30   | First versioned documentation, fallback mechanism improvements |
| Current | In Progress  | Enhanced templates, FinOps integration, GitHub Actions integration |

---

For questions about documentation versioning, please refer to the [Contributing Guide](CONTRIBUTING.md) or open an issue on GitHub.