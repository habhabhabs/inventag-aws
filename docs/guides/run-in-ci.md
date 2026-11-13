---
title: Run InvenTag in CI/CD
description: Run InvenTag on a schedule in GitHub Actions with short-lived OIDC credentials, keep the reports as artifacts, and fail the job on tag policy violations.
sidebar_position: 7
---

# Run InvenTag in CI/CD

**Who this is for:** you want an inventory on a schedule, or a pipeline that
fails when resources are not tagged properly.

**What you can do after reading:** set up a GitHub Actions workflow that runs
InvenTag with short-lived credentials and keeps the reports.

## The pieces

1. **Credentials without stored keys.** Use OpenID Connect (OIDC): GitHub
   proves who the workflow is, and AWS gives it a temporary role session. No
   access keys live in your repository secrets.
2. **A config template** with your regions, outputs and tag policy. The
   built-in `ci-pipeline` template is a good start.
3. **An artifact** to keep `bom_output/`.

## 1. Let GitHub assume a read-only role

In AWS, add GitHub as an OIDC identity provider
(`token.actions.githubusercontent.com`) and create a role with the read-only
policy from [Set up read-only access](./read-only-access.md). Limit its trust
policy to your repository and branch. The AWS guide
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
walks through it.

## 2. Add a config template to your repository

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

Set your regions and tag policy, then commit the file.

## 3. Add the workflow

```yaml
# .github/workflows/inventory.yml
name: AWS inventory
on:
  schedule:
    - cron: "17 2 * * 1-5"   # 02:17 UTC on weekdays
  workflow_dispatch:

permissions:
  contents: read
  id-token: write            # needed for OIDC

jobs:
  inventory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          repository: habhabhabs/inventag-aws
          ref: v1.0.2            # pin a release
          path: inventag
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: pip install -r inventag/requirements.txt
      - uses: aws-actions/configure-aws-credentials@<full-commit-SHA> # pin the current release
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: python inventag/inventag_cli.py --template nightly
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

Pin each action to a full commit SHA, with the version in a comment. That
protects you if a tag is moved to malicious code. The SHAs above for
`checkout`, `setup-python` and `upload-artifact` are the ones this repository's
own workflows use. For `aws-actions/configure-aws-credentials`, look up the
SHA of its current release on its GitHub releases page: we did not verify one
for this page. Update the SHAs when you update the versions.

InvenTag runs from your repository's folder, so `.inventag/templates/nightly.yaml`
is found by name.

## What happens on a violation

With `fail_on_tag_violations: true`, InvenTag writes every report first, then
exits with code 3. The job fails, and the artifact still holds the Excel file
and `tag_compliance_<timestamp>.json` with every non-compliant resource.

Sample output of `inventag --template ci-pipeline` from an offline run
(sample data):

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

| Exit code | Meaning |
|---|---|
| 0 | Reports written, no tag violations (or no failing policy) |
| 1 | Error: invalid template, credentials, every account failed, or a failed S3 upload |
| 3 | Reports written, tag policy violations found |

## Keep it safe

- Avoid `--debug` in CI. Secrets are masked in debug logs, but the logs are
  long and still describe your accounts.
- To keep reports in S3 instead of (or as well as) artifacts, add
  `--s3-bucket` and grant `s3:PutObject` on that bucket. See
  [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).
- Keep the role read-only and scoped to the repository and branch that need
  it.
- Pin InvenTag to a release tag, not `main`.

## Next steps

- [Example: enforce a tag policy in CI](../examples/tag-policy-in-ci.md)
- [Track changes between runs](./track-changes.md)
