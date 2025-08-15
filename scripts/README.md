# Documentation Transformation Pipeline

This directory contains scripts for the comprehensive CI/CD transformation pipeline that handles GitHub → Docusaurus format differences with validation and fallback strategies.

## Scripts Overview

### 🔄 `transform-docs.js`
**Main transformation pipeline script**

Handles intelligent content processing with:
- **Link Format Conversion**: Converts GitHub markdown links to Docusaurus routing
- **Frontmatter Enhancement**: Adds or improves frontmatter for Docusaurus features
- **Asset Path Normalization**: Ensures assets work in both GitHub and Docusaurus
- **Content Cleanup**: Fixes common markdown formatting issues

**Features:**
- ✅ Comprehensive logging with detailed transformation tracking
- ✅ Automatic backup creation before any modifications
- ✅ Validation of transformed content integrity
- ✅ Fallback strategy for transformation failures
- ✅ Dry-run mode for testing transformations
- ✅ Configurable transformation priorities

**Usage:**
```bash
# Run transformations
node scripts/transform-docs.js

# Dry run (no changes made)
DRY_RUN=true node scripts/transform-docs.js

# Verbose output
VERBOSE=true node scripts/transform-docs.js
```

### ✅ `validate-docs.js`
**Documentation validation and quality assurance**

Comprehensive validation including:
- **Link Validation**: Checks internal and external links
- **Image Validation**: Verifies image files exist and have alt text
- **Frontmatter Validation**: Ensures proper YAML frontmatter structure
- **Content Structure**: Validates heading hierarchy and markdown structure
- **Docusaurus Config**: Validates configuration files

**Features:**
- ✅ Dual-platform compatibility checking (GitHub + Docusaurus)
- ✅ Detailed error reporting with file locations
- ✅ Configurable strictness levels
- ✅ Performance metrics and statistics
- ✅ Comprehensive validation report generation

**Usage:**
```bash
# Run validation
node scripts/validate-docs.js

# Strict mode (fail on warnings)
node scripts/validate-docs.js --strict

# Verbose output
VERBOSE=true node scripts/validate-docs.js
```

### ✅ `validate-docs-migration.js`
**Migration-friendly documentation validation**

A simplified, tolerant validator designed specifically for documentation migration scenarios:
- **Critical Error Detection**: Only fails on issues that would break the build
- **Migration Tolerance**: Treats expected migration issues as warnings, not errors
- **Smart Link Checking**: Recognizes and ignores expected broken links to external files
- **Placeholder Awareness**: Handles placeholder images and assets gracefully
- **Clear Reporting**: Distinguishes between critical errors and expected migration warnings

**Features:**
- ✅ Migration-aware validation logic
- ✅ Tolerant of common migration issues
- ✅ Clear distinction between critical errors and warnings
- ✅ Optimized for CI/CD pipeline integration
- ✅ Focused on build-breaking issues only

**Usage:**
```bash
# Run migration-friendly validation
node scripts/validate-docs-migration.js

# Verbose output to see all warnings
node scripts/validate-docs-migration.js --verbose
```

### 📊 `monitor-docs.js`
**Health monitoring and metrics collection**

Provides comprehensive monitoring including:
- **Health Checks**: Validates documentation system health
- **Performance Metrics**: Tracks build times, file sizes, and transformation stats
- **Content Analysis**: Analyzes documentation structure and content
- **Build Monitoring**: Monitors build success/failure rates

**Features:**
- ✅ Real-time health status reporting
- ✅ Comprehensive metrics collection
- ✅ Performance trend analysis
- ✅ Automated alerting for issues
- ✅ Historical data tracking

**Usage:**
```bash
# Run health monitoring
node scripts/monitor-docs.js

# Verbose monitoring
VERBOSE=true node scripts/monitor-docs.js
```

## NPM Scripts

For convenience, the following npm scripts are available in the root `package.json`:

```bash
# Transformation
npm run docs:transform              # Run transformations
npm run docs:transform:dry          # Dry run mode

# Validation
npm run docs:validate               # Full validation (strict)
npm run docs:validate:strict        # Strict mode validation
npm run docs:validate:migration     # Migration-friendly validation

# Monitoring
npm run docs:monitor                # Health monitoring

# Full Pipeline
npm run docs:pipeline               # Transform → Validate → Build
npm run docs:pipeline:safe          # Dry run → Validate → Report
```

## CI/CD Integration

The transformation pipeline is fully integrated into the GitHub Actions workflow (`.github/workflows/docs-deploy.yml`) with:

### 🔄 Transformation Phase
1. **Pre-transformation Validation**: Validates source documentation structure
2. **Intelligent Transformation**: Applies necessary format conversions
3. **Post-transformation Validation**: Ensures transformation integrity
4. **Backup Management**: Creates and manages file backups

### ✅ Validation Phase
1. **Content Validation**: Validates all markdown files and links
2. **Configuration Validation**: Checks Docusaurus and sidebar configs
3. **Cross-platform Testing**: Ensures compatibility with both GitHub and Docusaurus
4. **Quality Assurance**: Runs comprehensive quality checks

### 🏗️ Build Phase with Fallback
1. **Primary Build Attempt**: Standard Docusaurus build process
2. **Fallback Strategy**: Automatic recovery from transformation issues
3. **Build Validation**: Validates build output and structure
4. **Performance Monitoring**: Tracks build performance metrics

### 📊 Monitoring Phase
1. **Health Assessment**: Comprehensive system health evaluation
2. **Metrics Collection**: Gathers performance and usage metrics
3. **Log Aggregation**: Centralizes all pipeline logs
4. **Artifact Upload**: Preserves logs and metrics for analysis

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VERBOSE` | Enable verbose logging | `false` |
| `DRY_RUN` | Run transformations without making changes | `false` |
| `STRICT` | Fail on warnings during validation | `false` |

### File Structure

```
scripts/
├── README.md                 # This documentation
├── transform-docs.js         # Main transformation pipeline
├── validate-docs.js          # Validation and quality assurance
└── monitor-docs.js           # Health monitoring and metrics

.docs-logs/                   # Generated monitoring logs
├── docs-metrics.json         # Performance and transformation metrics
└── docs-health.json          # Health check results

.docs-backup/                 # Automatic backups (created during transformation)
└── [mirrored docs structure] # Backup copies of original files
```

## Transformation Types

### 1. Link Format Conversion
**Problem**: GitHub uses `.md` extensions in links, Docusaurus uses clean URLs
**Solution**: Automatically converts `[text](file.md)` to `[text](file)`

**Example:**
```markdown
# Before transformation
[User Guide](../user-guides/cli-guide.md)

# After transformation  
[User Guide](../user-guides/cli-guide)
```

### 2. Frontmatter Enhancement
**Problem**: GitHub ignores frontmatter, Docusaurus requires it for navigation
**Solution**: Adds minimal, GitHub-compatible frontmatter

**Example:**
```markdown
# Before transformation
# My Documentation Page

# After transformation
---
title: My Documentation Page
---

# My Documentation Page
```

### 3. Asset Path Normalization
**Problem**: Different base paths between GitHub and Docusaurus
**Solution**: Normalizes asset paths to work in both contexts

**Example:**
```markdown
# Before transformation
![Screenshot](./assets/screenshot.png)

# After transformation
![Screenshot](assets/screenshot.png)
```

### 4. Content Cleanup
**Problem**: Inconsistent markdown formatting
**Solution**: Standardizes formatting and structure

**Features:**
- Removes excessive empty lines
- Ensures proper file endings
- Standardizes heading structure
- Cleans up whitespace

## Fallback Strategies

### 1. Transformation Failures
- **Automatic Backup Restoration**: Restores original files from backup
- **Selective Transformation**: Skips problematic files and continues
- **Error Isolation**: Prevents single file errors from breaking entire pipeline
- **Comprehensive Logging**: Detailed error reporting for debugging

### 2. Build Failures
- **Backup-based Recovery**: Uses backup files for build retry
- **Configuration Fallback**: Falls back to minimal configuration
- **Partial Build Support**: Builds available content even with some failures
- **Manual Override**: Allows manual intervention in CI/CD pipeline

### 3. Validation Failures
- **Warning vs Error Classification**: Distinguishes between critical and non-critical issues
- **Graceful Degradation**: Continues with warnings in non-production environments
- **Detailed Reporting**: Provides actionable feedback for fixing issues
- **Automated Retry**: Retries validation after automatic fixes

## Monitoring and Alerting

### Health Checks
- ✅ **Documentation Structure**: Validates directory structure and file organization
- ✅ **Configuration Integrity**: Checks Docusaurus and sidebar configurations
- ✅ **Dependency Status**: Validates Node.js dependencies and versions
- ✅ **Build Output**: Verifies build artifacts and structure
- ✅ **Content Quality**: Assesses documentation content quality and completeness

### Performance Metrics
- 📊 **Build Performance**: Tracks build times and resource usage
- 📊 **Transformation Efficiency**: Monitors transformation speed and success rates
- 📊 **Content Growth**: Tracks documentation size and complexity over time
- 📊 **Error Rates**: Monitors failure rates and common issues
- 📊 **User Experience**: Tracks page load times and accessibility metrics

### Alerting
- 🚨 **Build Failures**: Immediate notification of build failures
- 🚨 **Validation Errors**: Alerts for critical validation failures
- 🚨 **Performance Degradation**: Notifications for performance issues
- 🚨 **Health Check Failures**: Alerts for system health problems

## Troubleshooting

### Common Issues

#### Transformation Failures
```bash
# Check transformation logs
cat transform.log

# Run in dry-run mode to test
DRY_RUN=true VERBOSE=true node scripts/transform-docs.js

# Restore from backup if needed
cp -r .docs-backup/* docs/
```

#### Validation Errors
```bash
# Run migration-friendly validation (recommended during migration)
node scripts/validate-docs-migration.js --verbose

# Run full validation with detailed output
VERBOSE=true node scripts/validate-docs.js

# Check specific file issues
node scripts/validate-docs.js --verbose | grep "filename.md"
```

#### Build Issues
```bash
# Check build logs in CI/CD
# Look for fallback strategy activation
# Verify backup restoration

# Local debugging
cd website
npm run build
```

### Debug Mode

Enable comprehensive debugging:
```bash
# Enable all debugging options
export VERBOSE=true
export DRY_RUN=true  # For testing transformations

# Run full pipeline
node scripts/transform-docs.js
node scripts/validate-docs.js
node scripts/monitor-docs.js
```

## Development

### Adding New Transformations

1. **Register Transformation** in `transform-docs.js`:
```javascript
transformations.push({
  name: 'my-transformation',
  fn: (content, filePath) => {
    // Transformation logic
    return { content: transformedContent, hasChanges: true };
  },
  priority: 5  // Higher priority runs first
});
```

2. **Add Validation** in `validate-docs.js`:
```javascript
// Add validation logic for your transformation
validateMyTransformation(content, filePath) {
  // Validation logic
}
```

3. **Update Monitoring** in `monitor-docs.js`:
```javascript
// Add metrics for your transformation
this.metrics.transformation.myTransformationCount = 0;
```

### Testing

```bash
# Test transformations without changes
DRY_RUN=true node scripts/transform-docs.js

# Test validation
node scripts/validate-docs.js --verbose

# Test monitoring
node scripts/monitor-docs.js
```

## Best Practices

### 1. Single Source of Truth
- Keep documentation in root-level `docs/` directory
- Use GitHub-compatible frontmatter that doesn't interfere with GitHub rendering
- Ensure all transformations preserve content integrity

### 2. Dual Compatibility
- Test all changes on both GitHub and Docusaurus
- Use relative paths that work in both contexts
- Maintain consistent file naming and structure

### 3. Robust Error Handling
- Always create backups before transformations
- Implement comprehensive validation
- Use fallback strategies for critical failures
- Provide detailed error reporting

### 4. Performance Optimization
- Use efficient file processing algorithms
- Implement caching where appropriate
- Monitor and optimize build times
- Track performance metrics over time

### 5. Maintainability
- Keep transformations simple and focused
- Document all transformation logic
- Use consistent coding patterns
- Implement comprehensive testing

---

This transformation pipeline ensures reliable, automated documentation deployment while maintaining the flexibility to handle various GitHub → Docusaurus format differences with comprehensive validation and fallback strategies.