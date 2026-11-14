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
```

## Output

<!-- BEGIN EXAMPLE OUTPUT: ci-console -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="Output"
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
22 non-compliant resources
- ATHENA primary missing: CostCenter, Owner, Project, Environment
- DYNAMODB acme-orders missing: CostCenter, Project
- EC2 i-855a01aabe3d29d3a missing: CostCenter, Project
- EC2 snap-3585ce88e25ef1196 missing: CostCenter, Owner, Project, Environment
- EC2 vol-680d0e08d01dd52e7 missing: CostCenter, Owner, Project, Environment
- EC2 vol-57d5df4cfc9884b48 missing: CostCenter, Owner, Project, Environment
- EVENTS default missing: CostCenter, Owner, Project, Environment
- IAM acme-orders-api-role missing: CostCenter, Owner, Project, Environment
- LAMBDA acme-orders-api missing: CostCenter, Project
- S3 acme-data-lake missing: Project
```

<!-- END EXAMPLE OUTPUT: ci-summary-output -->

`acme-reports` has every tag, but two values are wrong. The `invalid` list
in the JSON file and the Problems column in the workbook say which.

## GitLab CI/CD

The same check can run as a GitLab CI/CD job in merge request pipelines. **The check reads AWS as it is now. It does not read the changes in the merge request.**

Set up the role and the CI/CD variable first: see [Run InvenTag in CI/CD](../guides/run-in-ci.md#gitlab-cicd). The merge request jobs need a second role, as the third point below explains.

Not verified against a GitLab runner or a real AWS account: this pipeline has not run on GitLab. Its YAML and its `inventag` command line are checked when the docs are built. Its job ran locally with gitlab-ci-local 4.77.1 (with a stand-in for rsync) against mocked AWS, with a dummy token.

```yaml
# .gitlab-ci.yml
stages:
  - check

tag-policy:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour                             # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # Exit code 3 (tag policy violations) fails this job.
    # Exit code 5 (an account could not be scanned) and 6 (no resources found) fail it too.
    - inventag --template ci-pipeline --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports when the job fails
    paths:
      - bom_output/
    expire_in: 1 week

security-groups:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour
  allow_failure:
    exit_codes: 4                             # warn only; delete these two lines to block on exit code 4
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --create-excel --enable-security-analysis --risk-threshold HIGH --fail-on-account-error --fail-if-empty
  artifacts:
    when: always
    paths:
      - bom_output/
    expire_in: 1 week
```

### What each exit code does

What GitLab does with each InvenTag exit code in this file:

| Exit code | Job `tag-policy` | Job `security-groups` |
|---|---|---|
| 0 | passes | passes |
| 3 (tag policy violations) | **fails**, as the GitHub Actions example does | does not occur (this command has no tag policy) |
| 4 (security group rule at or above `HIGH`) | does not occur (no `--risk-threshold`) | "allowed to fail": the job shows a warning, the pipeline goes on and counts as passed ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| 5 (an account could not be scanned; `--fail-on-account-error`), 6 (no resources found; `--fail-if-empty`) | fails | fails: the code is not in `exit_codes`, so `allow_failure` is false for it |
| 1, 2 | fails | fails |

### What each part does

The lines that every GitLab example shares (`image`, `timeout`, `id_tokens`, the two token lines and `artifacts`) are in the table of [Run InvenTag in CI/CD](../guides/run-in-ci.md#gitlab-cicd). This table has the parts of this example:

| Part | What it does |
|---|---|
| `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"` | The job runs in merge request pipelines only ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). |
| `inventag --template ci-pipeline --fail-on-account-error --fail-if-empty` | The command of this page plus the two opt-in flags. Exit codes 5 and 6 win over 3 (the order is 5, 6, 3, 4), so a run with an account that could not be scanned, or with no resources, is never shown as "no violations". A failed service call inside an account that was reached does not give 5. In the local run, this job ended as failed with exit code 3 and its report files were collected. |
| `allow_failure: exit_codes: 4` | Only exit code 4 is tolerated. With any other non-zero code the job fails as usual. To block the merge request on code 4, delete the two lines. To start the `tag-policy` job in warning mode, give it `allow_failure:` with `exit_codes: 3` in the same way, or keep `fail_on_tag_violations: false`, as "Next steps" says ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)). In the local run, `security-groups` ended with a warning and exit code 4. |
| `inventag --create-excel --enable-security-analysis --risk-threshold HIGH ...` | Exit code 4 when a security group rule is at or above `HIGH`. `--risk-threshold` needs `--enable-security-analysis`, otherwise the exit code is 2. There is no `--template` here, because `--enable-security-analysis` adds nothing with `--template` (see the [CLI reference](../reference/cli.md)). This job scans every enabled region. |

What is not verified:

- Not verified against GitLab or AWS: GitLab issuing the ID token and AWS accepting it for the role, with the trust policy conditions on `aud` and `sub`.
- Not verified against GitLab: `image`, `timeout`, `expire_in` and `cache` (gitlab-ci-local ignores them).
- Not verified against GitLab: how a failed job or a job that is allowed to fail affects later jobs, the pipeline status and the merge request.

### Three things to know

1. **The check reads AWS as it is now. It does not read the changes in the merge request.** The commands give InvenTag nothing from the repository except its template files. Each job scans the account once, so a merge request pipeline makes two scans. By default each run also uses Cost Explorer, and AWS charges for each Cost Explorer request; `--no-billing-validation` stops those calls (see the [CLI reference](../reference/cli.md)).
2. **A failed job blocks the merge only if the project requires it.** Turn on **Settings > Merge requests > Merge checks > Pipelines must succeed**. You need the Maintainer or Owner role ([GitLab](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)).
3. **In a merge request pipeline the ID token names the source branch, not `main`** ([GitLab](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). A role whose trust policy allows only `ref:main` refuses these jobs. Create a second read-only role for them, without the upload statement (`s3:PutObject`). The trust policy for this case is in [Run InvenTag in CI/CD](../guides/run-in-ci.md#gitlab-cicd). Everyone who can push a branch to the project and open a merge request can run a job with this role, and can change the job's script in their branch. The role is read-only, so they can read what InvenTag can read. Do not reuse the role of your scheduled jobs.
   - A protected CI/CD variable is passed to a merge request pipeline only if the source branch and the target branch are both protected, both are in the same project, and the user may merge to the target branch. It is never passed from a fork ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). So do not protect `AWS_ROLE_ARN` for these jobs.
   - The example reads `AWS_ROLE_ARN`, which is right for a project that has only these merge request jobs. A project that also runs scheduled jobs with the first role needs a second variable name for the second role. This example does not show how to map it.

## Next steps

- Start in report-only mode: set `fail_on_tag_violations: false` until the
  numbers are close to zero, then switch it on.
- Do not let an incomplete run pass as clean: `--fail-on-account-error` exits
  with code 5 when an account could not be scanned, and `--fail-if-empty` exits
  with code 6 when no resources were found. Both win over code 3.
- Use your own rules: [Check tags against a policy](../guides/check-tag-compliance.md#write-your-own-policy).
