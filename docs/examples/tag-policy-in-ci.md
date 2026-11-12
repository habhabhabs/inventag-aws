---
title: "Example: enforce a tag policy in CI"
description: Fail a CI job with exit code 3 when AWS resources break your tag policy, while keeping the InvenTag reports as build artifacts.
sidebar_position: 4
---

# Example: enforce a tag policy in CI

**Goal:** a pipeline step that fails when resources are missing required tags
or have wrong values, and keeps the evidence.

**You need:** a CI runner with read-only AWS credentials, ideally through
OIDC. See [Run InvenTag in CI/CD](../guides/run-in-ci.md).

## Template

The built-in `ci-pipeline` config template writes Excel and a JSON file,
checks `finops-cost-allocation`, and fails on violations:

```yaml
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

```bash
./inventag.sh --template ci-pipeline
echo "exit code: $?"
```

## Expected output

Sample data from an offline run:

```text
Wrote bom_output/tag_compliance_20261112_132506.json
Wrote bom_output/multi_account_bom_20261112_132506.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
exit code: 3
```

Only the Excel file is written, because the template says `outputs: [excel]`.
The JSON file is easy to use in a later step. Its `summary` part looks like
this:

```json
{
  "checked": 23,
  "compliant": 1,
  "non_compliant": 22,
  "out_of_scope": 14,
  "percent_compliant": 4.3,
  "missing_by_key": {"CostCenter": 20, "Owner": 20, "Project": 21, "Environment": 20},
  "invalid_by_key": {"CostCenter": 1, "Owner": 0, "Project": 0, "Environment": 1}
}
```

For example, to list the first ten non-compliant resources in a GitHub Actions job summary:

```bash
python3 -c "
import json, glob
r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))
print(f\"{r['summary']['non_compliant']} non-compliant resources\")
for x in r['non_compliant_resources'][:10]:
    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))
" >> "$GITHUB_STEP_SUMMARY"
```

Sample output of that step (shortened):

```text
22 non-compliant resources
- EC2 vol-0dcf6f20398656eff missing: CostCenter, Owner, Project, Environment
- S3 acme-data-lake missing: Project
- S3 acme-reports missing:
...
```

`acme-reports` has every tag, but two values are wrong. The `invalid` list
in the JSON file and the Problems column in the workbook say which.

## Next steps

- Start in report-only mode: set `fail_on_tag_violations: false` until the
  numbers are close to zero, then switch it on.
- Use your own rules: [Check tags against a policy](../guides/check-tag-compliance.md#write-your-own-policy).
