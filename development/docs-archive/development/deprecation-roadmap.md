# Deprecation Roadmap

## Overview

This document tracks deprecated features, legacy resources, and planned deprecations in InvenTag AWS. It provides migration guidance and timelines for removal.

## Currently Deprecated Features

### CLI Arguments

#### `--hide-fallback-resources`
- **Status**: Deprecated in v1.1.0
- **Replacement**: `--fallback-display=never`
- **Migration**: Replace usage with the new `--fallback-display` option
- **Planned Removal**: v2.0.0 (Q2 2025)
- **Reason**: More flexible fallback display modes introduced

```bash
# Old (deprecated)
inventag-aws --hide-fallback-resources

# New (recommended)
inventag-aws --fallback-display=never
```

### Configuration Properties

#### `hide_fallback_resources` (Boolean)
- **Status**: Deprecated in v1.1.0
- **Replacement**: `fallback_display_mode` (String: "auto"|"always"|"never")
- **Migration**: Update configuration files and code
- **Planned Removal**: v2.0.0 (Q2 2025)
- **Backward Compatibility**: Maintained - will automatically convert to new format

```python
# Old (deprecated)
hide_fallback_resources: bool = True

# New (recommended)
fallback_display_mode: str = "never"
```

```json
// Old configuration (deprecated but supported)
{
  "hide_fallback_resources": true
}

// New configuration (recommended)
{
  "fallback_display_mode": "never"
}
```

## Legacy Resources Under Review

### Discovery System Components

#### Legacy Script Interfaces
- **Location**: `scripts/aws_resource_inventory.py`
- **Status**: Maintained for backward compatibility
- **Replacement**: Unified CLI (`inventag-aws`)
- **Migration Timeline**: Evaluation ongoing
- **Notes**: Still widely used in existing integrations

#### Standalone Discovery Scripts
- **Location**: `development/debugging/` directory
- **Status**: Development and debugging tools
- **Future**: Will be consolidated or marked as examples
- **Timeline**: TBD based on usage patterns

### Configuration Formats

#### Legacy JSON Configuration Schema v1
- **Status**: Supported but not recommended for new implementations
- **Replacement**: Enhanced JSON/YAML configuration schema v2
- **Migration**: Automatic upgrade path available
- **Notes**: Most existing configurations use v1 format

#### Environment Variable Configuration
- **Status**: Limited support
- **Enhancement**: More comprehensive environment variable support planned
- **Timeline**: Enhancement in v1.2.0

## Planned Deprecations (Future Releases)

### v1.2.0 Deprecations (Q1 2025)

#### Legacy Service Discovery Patterns
- **Target**: Older service discovery patterns that don't follow AWS API standards
- **Replacement**: Standardized service discovery framework
- **Impact**: Internal refactoring, minimal user impact

#### Legacy Tag Processing
- **Target**: Old tag processing logic with limited validation
- **Replacement**: Enhanced tag validation and normalization
- **Migration**: Automatic for most cases

### v1.3.0 Deprecations (Q2 2025)

#### Legacy Report Formats
- **Target**: Older Excel and CSV report formats
- **Replacement**: Enhanced report templates with better formatting
- **Migration**: Template upgrade utility planned

#### Legacy Credential Handling
- **Target**: Simplified credential handling for edge cases
- **Replacement**: Enhanced multi-account credential management
- **Impact**: Improved security and flexibility

### v2.0.0 Breaking Changes (Q3 2025)

#### Configuration Schema Breaking Changes
- **Change**: Removal of deprecated configuration properties
- **Impact**: Configuration files will require updates
- **Migration**: Automated migration tool provided

#### API Interface Changes
- **Change**: Cleanup of deprecated parameters in Python API
- **Impact**: Code using deprecated parameters will need updates
- **Migration**: Clear migration guide and examples provided

## Migration Strategy

### Immediate Actions (Now)

1. **Update CLI Usage**: Replace `--hide-fallback-resources` with `--fallback-display`
2. **Configuration Audit**: Review and update configuration files
3. **Script Updates**: Begin migration from standalone scripts to unified CLI

### Short Term (Q1 2025)

1. **Configuration Migration**: Update to v2 configuration schema
2. **Integration Testing**: Validate all integrations work with new parameters
3. **Documentation Updates**: Ensure all documentation uses new syntax

### Medium Term (Q2 2025)

1. **Code Cleanup**: Remove deprecated parameter handling
2. **API Stabilization**: Finalize v2.0 API interfaces
3. **Migration Tools**: Complete automated migration utilities

### Long Term (Q3+ 2025)

1. **Legacy Removal**: Remove deprecated features completely
2. **Performance Optimization**: Optimize code without backward compatibility overhead
3. **New Features**: Implement features that require breaking changes

## Backward Compatibility Policy

### Support Levels

#### Full Support
- Current features actively maintained and enhanced
- Bug fixes and security updates provided
- Full documentation and support

#### Deprecated - Maintained
- Features marked deprecated but still functional
- Security updates provided
- Bug fixes for critical issues only
- Migration guidance available

#### Legacy - Limited Support
- Old features kept for compatibility
- Security updates only
- No bug fixes for non-critical issues
- Removal planned

#### Removed
- Features no longer available
- Migration required

### Deprecation Timeline

1. **Announcement**: Feature marked deprecated, migration path provided
2. **Warning Period**: 2-3 releases with deprecation warnings
3. **Legacy Period**: 1-2 releases with limited support
4. **Removal**: Feature removed in major version release

## Communication Strategy

### Deprecation Announcements

#### Documentation Updates
- Deprecation notices in relevant documentation
- Migration guides and examples
- Updated CLI help text

#### Code Warnings
- Deprecation warnings in logs when deprecated features used
- Clear guidance on replacement features
- Version information for removal timeline

#### Release Notes
- Detailed deprecation information in release notes
- Migration instructions and breaking changes
- Examples of updated usage patterns

### Support Channels

#### Documentation
- Comprehensive migration guides
- Code examples and best practices
- FAQ for common migration issues

#### Community Support
- GitHub issues for migration questions
- Discussion forums for best practices
- Community contributions welcomed

## Implementation Status

### Completed Deprecations
- ✅ `--hide-fallback-resources` CLI argument deprecated
- ✅ `hide_fallback_resources` configuration property deprecated
- ✅ Migration path to `--fallback-display` implemented
- ✅ Backward compatibility maintained

### In Progress
- 🔄 Documentation updates for new fallback display options
- 🔄 Enhanced configuration validation
- 🔄 Migration utility development

### Planned
- ⏳ Legacy script consolidation evaluation
- ⏳ Configuration schema v2 development
- ⏳ API interface stabilization for v2.0

## Migration Examples

### CLI Migration

```bash
# Before (deprecated)
inventag-aws --hide-fallback-resources --regions us-east-1

# After (recommended)
inventag-aws --fallback-display=never --regions us-east-1

# Or better (smart default)
inventag-aws --fallback-display=auto --regions us-east-1
```

### Configuration Migration

```yaml
# Before (deprecated but supported)
accounts:
  - account_id: "123456789012"
    regions: ["us-east-1"]
    hide_fallback_resources: true

# After (recommended)
accounts:
  - account_id: "123456789012" 
    regions: ["us-east-1"]
    fallback_display_mode: "never"

# Or better (smart default)
accounts:
  - account_id: "123456789012"
    regions: ["us-east-1"] 
    fallback_display_mode: "auto"
```

### Code Migration

```python
# Before (deprecated but supported)
inventory = AWSResourceInventory(
    regions=['us-east-1'],
    hide_fallback_resources=True
)

# After (recommended)
inventory = AWSResourceInventory(
    regions=['us-east-1'],
    fallback_display_mode='never'
)

# Or better (smart default)
inventory = AWSResourceInventory(
    regions=['us-east-1'],
    fallback_display_mode='auto'
)
```

## Testing Deprecated Features

### Automated Testing
- Deprecated features included in regression tests
- Migration path validation in CI/CD
- Backward compatibility verification

### Manual Testing
- Regular testing of deprecated features
- Migration scenario validation
- User experience testing

## Feedback and Questions

### Reporting Issues
- Use GitHub issues for deprecation-related problems
- Provide clear migration requirements
- Include current usage patterns

### Feature Requests
- New feature requests should avoid deprecated patterns
- Migration assistance requests welcomed
- Community input valued for deprecation timelines

---

**Note**: This document is updated with each release. Check the latest version for current deprecation status and timelines.

**Last Updated**: 2025-08-08
**Next Review**: 2025-09-01