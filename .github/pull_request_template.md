# Pull Request

## Summary
<!-- Provide a brief summary of your changes -->

## Type of Change
<!-- Mark with an "x" all that apply -->
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🎨 Code style/formatting changes
- [ ] ♻️ Refactoring (no functional changes)
- [ ] ⚡ Performance improvements
- [ ] 🔧 Build/CI changes
- [ ] 🧪 Test changes

## Related Issues
<!-- Link to related issues -->
Closes #<!-- issue number -->
Related to #<!-- issue number -->

## Changes Made
<!-- Describe the changes in detail -->
- 
- 
- 

## Testing
<!-- Describe how you tested your changes -->
### Test Environment
- [ ] Local testing completed
- [ ] AWS account testing completed
- [ ] CI/CD pipeline tests passing
- [ ] Documentation examples verified

### Test Commands
<!-- Include the commands you used to test -->
```bash
# Example test commands
inventag --create-excel --regions us-east-1
python -m pytest tests/
```

### Test Results
<!-- Summarize test results -->
- ✅ All tests passing
- ✅ No regression detected
- ✅ Performance within acceptable range

## AWS Services Affected
<!-- List AWS services impacted by your changes -->
- [ ] EC2
- [ ] S3
- [ ] RDS
- [ ] Lambda
- [ ] IAM
- [ ] CloudFront
- [ ] Route53
- [ ] Other: <!-- specify -->

## Breaking Changes
<!-- If this is a breaking change, describe the impact and migration path -->
None / N/A

**Migration required:**
- 

## Documentation
<!-- Documentation changes -->
- [ ] Code comments added/updated
- [ ] README updated
- [ ] Documentation site updated
- [ ] Examples added/updated
- [ ] No documentation changes needed

## Screenshots
<!-- Add screenshots if applicable, especially for CLI output changes -->

## Checklist
<!-- Mark with an "x" all that apply -->
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] New and existing unit tests pass locally with my changes
- [ ] I have tested with a real AWS account
- [ ] I have removed any hardcoded credentials, account IDs, or sensitive data

## Additional Notes
<!-- Any additional information for reviewers -->

## Performance Impact
<!-- If applicable, describe performance implications -->
- [ ] No performance impact
- [ ] Performance improvement
- [ ] Performance regression (explain why acceptable)
- [ ] Performance impact unknown

**Benchmarks:**
<!-- Include performance numbers if relevant -->
- Discovery speed: X resources/second
- Memory usage: X MB
- API calls: X per resource