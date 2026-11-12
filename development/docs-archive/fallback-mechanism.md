# Fallback Resource Discovery Mechanism

## Overview

InvenTag AWS uses a sophisticated dual-tier resource discovery system to ensure comprehensive AWS resource detection. The fallback mechanism ensures no resources are missed while providing intelligent filtering to avoid noise and duplication.

## Discovery Architecture

### Primary Discovery (Service APIs)
- **Source**: Direct AWS service APIs (e.g., `ec2:describe_instances`, `s3:list_buckets`)
- **Priority**: High
- **Coverage**: Service-specific resources with full metadata
- **Tagged Status**: Both tagged and untagged resources
- **Identifier**: `discovered_via: ServiceAPI:operation_name`

### Fallback Discovery (ResourceGroupsTagging API)
- **Source**: AWS ResourceGroupsTagging API (`resourcegroupstaggingapi:get_resources`)
- **Priority**: Low (fallback only)
- **Coverage**: Only tagged resources across all services
- **Tagged Status**: Tagged resources only
- **Identifier**: `discovered_via: ResourceGroupsTaggingAPI:Fallback`

## Fallback Display Modes

### Auto Mode (Default - Recommended)
```bash
inventag-aws --fallback-display=auto
```

**Behavior**: Intelligent fallback display based on primary discovery results
- Shows fallback resources **only** when no primary resources are found for a service
- Perfect for services like AWS RoboMaker where service APIs may not return resources, but ResourceGroupsTagging API does
- Reduces noise by filtering out fallback duplicates when service APIs work properly
- **Best for debugging** - reveals gaps in primary discovery coverage

**Example Scenario**:
- EC2 service: Primary API finds 50 instances → Fallback resources hidden
- RoboMaker service: Primary API finds 0 resources → Fallback resources shown (2 simulation jobs)
- Lambda service: Primary API finds 10 functions → Fallback resources hidden

### Always Mode (Maximum Visibility)
```bash
inventag-aws --fallback-display=always
```

**Behavior**: Shows all fallback resources regardless of primary discovery results
- Maximum resource visibility for comprehensive auditing
- May show duplicate entries (same resource from both primary and fallback)
- Useful for validation and ensuring no resources are missed
- **Best for compliance audits** requiring proof of comprehensive discovery

### Never Mode (Primary Only)
```bash
inventag-aws --fallback-display=never
# OR legacy option:
inventag-aws --hide-fallback-resources
```

**Behavior**: Hides all fallback resources completely
- Only shows resources discovered via service APIs
- Cleanest output with no duplicates
- May miss resources not discoverable via service APIs
- **Best for production reports** where clean output is prioritized

## Technical Implementation

### Service Tracking
The system maintains a registry of services with successful primary discoveries:

```python
# Track services that found resources via service APIs
self.services_with_primary_resources = {"ec2", "s3", "rds", "lambda"}

# Auto mode logic for fallback
if service not in self.services_with_primary_resources:
    # Show fallback resource - primary discovery found nothing
    add_fallback_resource()
else:
    # Skip fallback resource - primary discovery was successful  
    skip_fallback_resource()
```

### Resource Deduplication
Resources are deduplicated by ARN with priority-based selection:
1. Primary resources (service APIs) take precedence
2. Fallback resources are used only when no primary equivalent exists
3. Tag data is merged from both sources for enrichment

### Debug Logging
Enable debug logging to understand fallback decisions:

```bash
inventag-aws --fallback-display=auto --verbose
```

Debug messages include:
- `Services with primary resources found: ['ec2', 's3', 'rds']`
- `Skipping fallback resource arn:aws:ec2:... - primary resources exist for service`
- `Auto mode: Fallback resources shown only for services without primary discoveries`

## Common Use Cases

### 1. Debugging Missing Resources

**Problem**: "I know there are resources but they're not showing up"

**Solution**: Use auto mode (default) with debug logging
```bash
inventag-aws --fallback-display=auto --verbose
```

This reveals:
- Which services have working primary discovery
- Which services rely on fallback discovery only
- Gaps in service API coverage

### 2. Maximum Resource Coverage

**Problem**: "I need to ensure absolutely no resources are missed"

**Solution**: Use always mode for comprehensive discovery
```bash
inventag-aws --fallback-display=always
```

**Note**: Review results for duplicates and validate against AWS console

### 3. Clean Production Reports

**Problem**: "I want clean reports without duplicate entries"

**Solution**: Use never mode for primary-only discovery
```bash
inventag-aws --fallback-display=never
```

**Trade-off**: May miss resources not discoverable via service APIs

## Resource Identification

Resources include metadata to identify their discovery source:

### Primary Resource Example
```json
{
  "service": "EC2",
  "resource_type": "Instance",
  "resource_id": "i-1234567890abcdef0",
  "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
  "discovered_via": "ServiceAPI:describe_instances",
  "priority": "primary",
  "tagged": true,
  "tags": {"Environment": "prod", "Application": "web-server"}
}
```

### Fallback Resource Example  
```json
{
  "service": "ROBOMAKER",
  "resource_type": "SimulationJob", 
  "resource_id": "sim-1234567890abcdef0",
  "arn": "arn:aws:robomaker:us-east-1:123456789012:simulation-job/sim-1234567890abcdef0",
  "discovered_via": "ResourceGroupsTaggingAPI:Fallback",
  "priority": "fallback",
  "tagged": true,
  "tags": {"Project": "robotics-dev", "Team": "ai-research"}
}
```

## Performance Considerations

### Auto Mode (Recommended)
- **Pros**: Optimal balance of coverage and performance
- **Cons**: Requires both discovery methods to run
- **Performance**: Medium (both APIs called, smart filtering)

### Always Mode
- **Pros**: Maximum coverage, useful for audits
- **Cons**: More processing, potential duplicates in output
- **Performance**: Slower (both APIs + deduplication)

### Never Mode  
- **Pros**: Fastest execution, cleanest output
- **Cons**: May miss resources not discoverable via service APIs
- **Performance**: Fastest (service APIs only)

## Migration from Legacy Option

The `--hide-fallback-resources` flag is deprecated but still supported:

```bash
# Legacy (deprecated)
inventag-aws --hide-fallback-resources

# New equivalent  
inventag-aws --fallback-display=never
```

**Migration Path**:
1. Replace `--hide-fallback-resources` with `--fallback-display=never`
2. Consider upgrading to `--fallback-display=auto` for better resource coverage
3. Test with `--fallback-display=always` if comprehensive discovery is critical

## Best Practices

### For Development and Debugging
```bash
# Recommended: Smart fallback with detailed logging
inventag-aws --fallback-display=auto --verbose
```

### For Production Reports
```bash
# Clean output, primary resources only
inventag-aws --fallback-display=never
```

### For Compliance Audits
```bash  
# Maximum resource coverage with verification
inventag-aws --fallback-display=always --enable-security-analysis
```

### For Cost Analysis
```bash
# Smart fallback ensures all billable resources are captured
inventag-aws --fallback-display=auto --enable-cost-analysis
```

## Troubleshooting

### Issue: Resources Missing from Reports

**Diagnosis Steps**:
1. Run with auto mode and debug logging: `--fallback-display=auto --verbose`
2. Check if service appears in "Services with primary resources found"
3. If service missing from list, fallback resources should be shown
4. Compare with always mode: `--fallback-display=always`

### Issue: Duplicate Resources in Output

**Likely Cause**: Using `--fallback-display=always`
**Solution**: Switch to auto mode: `--fallback-display=auto`

### Issue: Specific Service Resources Not Found

**Example**: AWS RoboMaker simulation jobs not appearing

**Diagnosis**:
```bash
# Check if RoboMaker has primary resources
inventag-aws --services=robomaker --fallback-display=auto --verbose

# Force show fallback resources
inventag-aws --services=robomaker --fallback-display=always
```

**Common Services Relying on Fallback**: AppStream, RoboMaker, WorkSpaces, IoT devices

## AWS Service Coverage

### Services with Comprehensive Primary API Coverage
- **EC2**: Instances, volumes, security groups, VPCs
- **S3**: Buckets with location and metadata
- **RDS**: Instances, clusters, snapshots
- **Lambda**: Functions with configurations

### Services Often Requiring Fallback Discovery
- **AWS RoboMaker**: Simulation jobs, applications
- **AWS AppStream**: Fleets, stacks, images  
- **AWS WorkSpaces**: Workspaces, directories
- **IoT Core**: Things, certificates, policies

### Services with Limited API Discoverability
Services that may only be discoverable through ResourceGroupsTagging API due to:
- Regional API limitations
- Permission requirements
- Service API design constraints

## Configuration Examples

### Multi-Account Configuration
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "role_arn": "arn:aws:iam::123456789012:role/InvenTagRole",
      "regions": ["us-east-1", "us-west-2"],
      "fallback_display": "auto"
    }
  ],
  "settings": {
    "fallback_display_mode": "auto",
    "max_concurrent_accounts": 5
  }
}
```

### Service-Specific Discovery
```bash
# Discover only RoboMaker with intelligent fallback
inventag-aws --services=robomaker --fallback-display=auto

# Discover compute services with maximum coverage
inventag-aws --services=ec2,lambda,ecs --fallback-display=always
```

## API Reference

### CLI Arguments
- `--fallback-display={auto|always|never}`: Control fallback resource display
- `--hide-fallback-resources`: Legacy flag (deprecated, equivalent to `never`)

### Configuration Properties
```python
fallback_display_mode: str = "auto"  # "auto", "always", "never"
```

### Resource Metadata Fields
- `discovered_via`: Source of discovery (ServiceAPI:operation or ResourceGroupsTaggingAPI:Fallback)
- `priority`: Resource priority (primary or fallback)
- `tagged`: Boolean indicating if resource has tags

## Conclusion

The intelligent fallback mechanism ensures comprehensive AWS resource discovery while maintaining clean, actionable output. The auto mode provides the optimal balance for most use cases, automatically adapting to the discovery capabilities of each AWS service.

For debugging and maximum visibility, the fallback mechanism provides transparency into which resources come from which discovery method, enabling users to make informed decisions about their AWS resource inventory strategy.