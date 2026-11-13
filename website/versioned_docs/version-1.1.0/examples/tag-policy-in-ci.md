---
title: "Example: enforce a tag policy in CI"
description: Fail a CI job with exit code 3 when AWS resources break your tag policy, while keeping the InvenTag reports as build artifacts.
sidebar_position: 4
---

# Example: enforce a tag policy in CI

**Goal:** a pipeline step that fails when resources are missing required tags
or have wrong values, and keeps the evidence.

**You need:** a CI runner with read-only AWS credentials, ideally through
OIDC (OpenID Connect). See [Run InvenTag in CI/CD](../guides/run-in-ci.md).

## Template

The built-in `ci-pipeline` config template writes Excel and a JSON file,
checks `finops-cost-allocation`, and fails on violations:

```yaml title="ci-pipeline (built-in)"
format_version: 1
kind: config
name: ci-pipeline
description: Excel report plus tag-compliance JSON; exits with code 3 on tag policy violations.
spec:
  regions: [us-east-1]
  outputs: [excel]
  output_directory: bom_output
  report_template: standard-bom
  tag_policy: finops-cost-allocation
  fail_on_tag_violations: true
  parallel_processing: false
```

## Command

```bash title="Terminal"
inventag --template ci-pipeline
echo $?
```

## Output

<!-- BEGIN EXAMPLE OUTPUT: ci-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
$ echo $?
3
```

<!-- END EXAMPLE OUTPUT: ci-console -->

Only the Excel file and the JSON file are written, because the template says
`outputs: [excel]`:

<!-- BEGIN EXAMPLE OUTPUT: ci-files -->

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

<!-- END EXAMPLE OUTPUT: ci-files -->

To list the first ten non-compliant resources in a GitHub Actions job
summary:

```bash title="Workflow step"
python3 -c "
import json, glob
r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))
print(f\"{r['summary']['non_compliant']} non-compliant resources\")
for x in r['non_compliant_resources'][:10]:
    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))
" >> "$GITHUB_STEP_SUMMARY"
```

<!-- BEGIN EXAMPLE OUTPUT: ci-summary-output -->

```text title="Job summary"
21 non-compliant resources
- DYNAMODB acme-orders missing: CostCenter, Project
- EC2 i-855a01aabe3d29d3a missing: CostCenter, Project
- EC2 snap-3585ce88e25ef1196 missing: CostCenter, Owner, Project, Environment
- EC2 vol-680d0e08d01dd52e7 missing: CostCenter, Owner, Project, Environment
- EC2 vol-57d5df4cfc9884b48 missing: CostCenter, Owner, Project, Environment
- EVENTS default missing: CostCenter, Owner, Project, Environment
- IAM acme-orders-api-role missing: CostCenter, Owner, Project, Environment
- LAMBDA acme-orders-api missing: CostCenter, Project
- S3 acme-data-lake missing: Project
- S3 acme-reports missing:
```

<!-- END EXAMPLE OUTPUT: ci-summary-output -->

`acme-reports` has every tag, but two values are wrong. The `invalid` list
in the JSON file and the Problems column in the workbook say which.

## Next steps

- Start in report-only mode: set `fail_on_tag_violations: false` until the
  numbers are close to zero, then switch it on.
- Use your own rules: [Check tags against a policy](../guides/check-tag-compliance.md#write-your-own-policy).
