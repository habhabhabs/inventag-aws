---
title: Run InvenTag in CI/CD
description: Run InvenTag on a schedule in GitHub Actions or GitLab CI/CD with short-lived OIDC credentials, keep the reports as artifacts, and fail the job on tag policy violations.
sidebar_position: 7
---

# Run InvenTag in CI/CD

**Who this is for:** you want an inventory on a schedule, or a pipeline that
fails when resources are not tagged properly.

**What you can do after reading:** set up a GitHub Actions workflow or a GitLab CI/CD pipeline that runs InvenTag with short-lived credentials and keeps the reports.

## The pieces

1. **Credentials without stored keys.** Use OpenID Connect (OIDC): the CI system proves who the job is, and AWS gives it a temporary role session. No
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
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly --fail-on-account-error --fail-if-empty
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

Not verified against a GitHub Actions runner: this workflow has not run on GitHub. Its YAML and its `inventag` command line are checked when the docs are built.

Pin each action to a full commit SHA, with the version in a comment. That
protects you if a tag is moved to malicious code. The four SHAs above are the commits of the tags named in the comments. Update the SHAs when you update the versions.

Not verified against GitHub: pinning to a commit SHA protects you when a tag is moved.

InvenTag runs from your repository's folder, so `.inventag/templates/nightly.yaml`
is found by name.

Without the two exit-code flags, the job succeeds even when an account could
not be scanned or nothing was found. `--fail-on-account-error` makes the job
fail with exit code 5 in the first case, and `--fail-if-empty` with exit code 6
in the second. The reports are still written, so the artifact step can keep
them.

## GitLab CI/CD {#gitlab-cicd}

This section is the GitLab twin of the GitHub Actions steps above. The config template from step 2 is the same. The examples are written for GitLab.com. A [self-managed instance](#on-a-self-managed-instance) needs a few changes.

### Let GitLab assume a read-only role {#let-gitlab-assume-a-read-only-role}

Not verified against GitLab or AWS: GitLab issuing the ID token and AWS accepting it for the role, with the trust policy conditions on `aud` and `sub`.

**Step 1: add GitLab as an OIDC identity provider in IAM.** In the IAM console, open **Identity providers > Add provider** and choose OpenID Connect ([AWS: create an OIDC identity provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)).

| Field | Value |
|---|---|
| Provider URL | `https://gitlab.com` for GitLab.com. For a self-managed instance, the address of your own instance, for example `https://gitlab.example.com`. AWS requires a URL that begins with `https://`. GitLab says the address must be publicly accessible ([GitLab: OpenID Connect in AWS](https://docs.gitlab.com/ci/cloud_services/aws/)). |
| Audience | `sts.amazonaws.com`. It must be the same text as `aud` under `id_tokens` in the pipeline. |
| Thumbprint | Nothing to enter. IAM fetches it, and AWS checks the provider's certificate against its own list of trusted root CAs first ([AWS: `create-open-id-connect-provider`](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)). |

You can add one provider per URL and AWS account. A second "add" for the same URL fails. If your account already trusts `gitlab.com`, add the audience to the existing provider.

**Step 2: create the role with a trust policy.** Create a role for this provider. The trust policy below lets one project on one branch of GitLab.com assume the role. That is the case of the scheduled examples, which run on `main`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.com:aud": "sts.amazonaws.com",
          "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main",
          "gitlab.com:project_id": "67890"
        }
      }
    }
  ]
}
```

Replace these values:

| Value | Replace with |
|---|---|
| `123456789012` | The AWS account ID that holds the identity provider and the role. The provider and the role must be in the same account. |
| `gitlab.com` (four places) | Keep it for GitLab.com. For a self-managed instance, use your instance's host name without `https://`. |
| `sts.amazonaws.com` | Keep it, unless you chose another audience in step 1 and under `id_tokens`. |
| `mygroup/myproject` | The full path of the project: group, subgroups and project. |
| `main` | The branch that the schedule runs on. |
| `67890` | The project ID. This line works on GitLab.com only. On a self-managed or Dedicated instance, AWS supports only the `sub` and `aud` claims, so delete the line there. |

The `sub` claim has the form `project_path:{group}/{project}:ref_type:{type}:ref:{branch_name}` by default. A project can change that form through the projects API, and the value above then does not match ([GitLab: ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). A condition on a stable ID such as `project_id` is recommended, because a deleted project path can be created again by someone else ([AWS: IAM condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)).

A wildcard in a condition needs `StringLike`. With `StringEquals`, AWS refuses the call.

**Variant: any protected branch (GitLab.com).** Replace the `Condition` block:

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890",
    "gitlab.com:ref_protected": "true"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

Not verified against AWS: that `"true"` is the exact text AWS compares for `ref_protected`. `ref_protected` and `pipeline_source` are condition keys for GitLab.com only.

**Variant: protected tags (GitLab.com).** The same block, with `ref_type:tag:ref:*` (or `ref_type:tag:ref:v*`) in the `sub` line.

**Variant: merge request pipelines.** The token of a merge request pipeline carries the source branch, so the role must accept every branch of the project:

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

Not verified against GitLab: the exact `sub` text in a merge request pipeline.

With this variant, everyone who can push a branch to the project and open a merge request can run a job with this role, and can change the job's script in their branch. The role is read-only, so they can read what InvenTag can read. Use a separate role for this variant. Do not reuse the role of the scheduled jobs, and give it no `s3:PutObject`. See [the tag policy example](../examples/tag-policy-in-ci.md#gitlab-cicd).

**Step 3: attach the read-only policy.** Attach the policy from [Set up read-only access](./read-only-access.md): option 2, `config/defaults/iam-policy-read-only.json`, or option 1 (`ReadOnlyAccess` plus three actions).

- For the upload example, keep the statement `OptionalS3ReportUpload` and put your bucket name in place of `YOUR-REPORTS-BUCKET-NAME`. Its resource ends in `bom-reports/*`, so the key prefix must be `bom-reports/` (the default), or you change the resource. With `aws:kms`, also allow `kms:GenerateDataKey` on the key ([IAM permissions](../reference/iam-permissions.md)). See [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md). For the other examples, remove the statement.
- For the example with several accounts, the role also needs `sts:AssumeRole` on the `InvenTagReadOnly` role of each account, and each of those roles trusts this role. The policy file in the repository has no `sts:AssumeRole` statement. See [Set up read-only access](./read-only-access.md) and [Scan multiple accounts](./scan-multiple-accounts.md).

InvenTag stays read-only. Neither the role nor the pipeline makes an account compliant with anything.

#### On a self-managed instance {#on-a-self-managed-instance}

Not verified against a self-managed GitLab instance: this paragraph. The provider URL and the condition keys use the host name of your instance. AWS supports only the `sub` and `aud` claims there, so the `project_id` line goes. There is no `ref_protected` key in AWS there, so pin each branch by name. AWS must be able to reach the instance from the internet; GitLab describes a workaround for an instance that is not public and calls it advanced ([GitLab: configure a non-public GitLab instance](https://docs.gitlab.com/ci/cloud_services/aws/)). The runner must be able to run container images.

### Add the CI/CD variable {#add-the-cicd-variable}

In your GitLab project, open **Settings > CI/CD > Variables > Add variable** (Maintainer role). Use the key `AWS_ROLE_ARN` and give the ARN of the role as the value, for example `arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly`. GitLab passes the variable to the job as an environment variable ([GitLab: CI/CD variables](https://docs.gitlab.com/ci/variables/)).

- For the scheduled examples, tick **Protect variable** and protect the branch. The variable then reaches only pipelines on protected branches or tags.
- For the merge request example, do not protect the variable. A protected variable is not passed to a merge request pipeline unless the source and the target branch are both protected ([GitLab: merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). With two roles, use a second variable name in the two jobs of that example.
- GitLab makes a new variable **Masked** by default since GitLab 18.3, and a masked value must be one line of at least 8 characters with no spaces. A role ARN is not a secret. Choose **Visible** if GitLab refuses to mask the value. Not verified against GitLab: that GitLab accepts a role ARN as a masked value.
- The upload example needs two more variables, `INVENTAG_REPORTS_BUCKET` and `INVENTAG_KMS_KEY_ID`. Neither is a secret.

### Add the pipeline {#add-the-pipeline}

This job runs InvenTag every night and keeps the reports as job artifacts. It needs `.inventag/templates/nightly.yaml` from step 2. Add the file to the root of your repository as `.gitlab-ci.yml`. If the file already has `stages`, add the stage name to that list.

Not verified against a GitLab runner or a real AWS account: this pipeline has not run on GitLab. Its YAML and its `inventag` command line are checked when the docs are built. Its job ran locally with gitlab-ci-local 4.77.1 (with a stand-in for rsync) against mocked AWS, with a dummy token.

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"   # the pipeline schedule
    - if: $CI_PIPELINE_SOURCE == "web"        # "New pipeline" in the GitLab UI
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    key: pip
    paths:
      - .cache/pip
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --template nightly --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports even when the tag check fails
    paths:
      - bom_output/
    expire_in: 30 days
```

What each part does:

| Part | What it does |
|---|---|
| `stages:` and `stage:` | Declare the stage and put the job in it. A job with no `stage` goes to `test` ([GitLab: `stages`](https://docs.gitlab.com/ci/yaml/#stages)). |
| `image: python:3.12` | The job runs in this container image, in the form `<image-name>:<tag>`. InvenTag needs Python 3.11 or later, and the GitHub example uses 3.12 ([GitLab: `image`](https://docs.gitlab.com/ci/yaml/#image)). |
| `rules:` with `schedule` and `web` | The job is added only to scheduled pipelines and to pipelines started with **New pipeline** in the GitLab UI. In every other pipeline (push, merge request) no rule matches and the job is not added ([GitLab: job rules](https://docs.gitlab.com/ci/jobs/job_rules/)). |
| `timeout: 2 hours` | Stops the job after that time ([GitLab: `timeout`](https://docs.gitlab.com/ci/yaml/#timeout)). It also sets the life of the ID token: GitLab sets the token's expiry to the job's timeout if one is set, and to 5 minutes if not ([GitLab: ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). InvenTag exchanges the token more than once in a run (checked locally against mocked AWS), so always set `timeout`. GitLab-hosted runners on GitLab.com stop every job after 3 hours ([GitLab: hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)). |
| `id_tokens:` | GitLab makes an OIDC ID token (a JSON web token) for this job, with the audience in `aud`. The script reads it as `$GITLAB_OIDC_TOKEN`. It is available in the tiers Free, Premium and Ultimate, on GitLab.com, Self-Managed and Dedicated ([GitLab: `id_tokens`](https://docs.gitlab.com/ci/yaml/#id_tokens)). |
| `AWS_DEFAULT_REGION` | The region that the AWS SDK uses for the sign-in call. Set this variable: `AWS_REGION` alone is not enough, because botocore, the AWS SDK for Python, does not read it (checked locally). |
| `pip install "inventag-aws==..."` | Installs a pinned release of InvenTag. |
| The two lines with `AWS_WEB_IDENTITY_TOKEN_FILE` | Write the token to a new private file outside the project folder, and tell the AWS SDK where it is. With `AWS_ROLE_ARN` (the CI/CD variable), the SDK exchanges the token for temporary credentials by itself ([AWS: assume role credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)). No AWS CLI and no access key are needed. A file outside the project folder cannot become an artifact or a cache entry, because both take only paths inside the project folder ([GitLab: `artifacts:paths`](https://docs.gitlab.com/ci/yaml/#artifactspaths), [GitLab: caching](https://docs.gitlab.com/ci/caching/)). Checked locally against mocked AWS: the file has mode 600 and the SDK signs in with the token. |
| `PIP_CACHE_DIR` and `cache:` | Keep pip's download cache between jobs. The cache must be inside the project folder, because GitLab caches only paths there ([GitLab: caching examples](https://docs.gitlab.com/ci/caching/examples/)). Optional: the job works without these lines. |
| `inventag --template nightly --fail-on-account-error --fail-if-empty` | The same command as in the GitHub workflow. Exit code 3 when the tag policy finds violations and the template says `fail_on_tag_violations: true`, 5 when an account could not be scanned, and 6 when no resources were found. Any exit code other than 0 fails the job ([GitLab: `script`](https://docs.gitlab.com/ci/yaml/script/)). Locally (with a stand-in for rsync), the job ended with exit code 3 and the four report files were collected. |
| `artifacts:` | Uploads `bom_output/` as the job's artifacts. With `when: always`, GitLab also uploads them when the job fails; without it, only when the job succeeds. `always` does not cover a job that times out. `expire_in` says how long GitLab keeps them. GitLab keeps the artifacts of the latest pipeline of a ref regardless of `expire_in` (default project setting) ([GitLab: `artifacts:when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [GitLab: `artifacts:expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in), [GitLab: job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)). `expire_in: 30 days` matches `retention-days: 30` in the GitHub workflow. InvenTag writes the reports before it exits with code 3, 4 or 5. |
| The role ARN | Not in the YAML. It is the CI/CD variable `AWS_ROLE_ARN` from the step above. |

Two more parts of this example are not verified:

- Not verified against GitLab: `image`, `timeout`, `expire_in` and `cache` (gitlab-ci-local ignores them).
- Not verified against a GitLab pipeline schedule: the local run set the pipeline source by hand.

### Schedule it {#schedule-it}

The schedule is not in the file. Create it in GitLab: open **Build > Pipeline schedules > New schedule**, enter a cron pattern (for example `17 2 * * 1-5`) and the target branch, and save. You need the Developer role or higher. The pipeline runs with the permissions of the schedule owner ([GitLab: pipeline schedules](https://docs.gitlab.com/ci/pipelines/schedules/)). To run the job by hand, choose **New pipeline** in the GitLab UI, or **Run** on the schedule.

Not verified against GitLab: the time zone that a pipeline schedule uses for the cron pattern.

### What differs from GitHub Actions {#what-differs-from-github-actions}

The GitHub column describes only what the GitHub workflow above shows.

| Topic | GitHub Actions | GitLab CI/CD |
|---|---|---|
| File | `.github/workflows/inventory.yml` | `.gitlab-ci.yml` in the repository root |
| Schedule | `on: schedule: - cron:` inside the file | Not in the file. A pipeline schedule in the GitLab UI (**Build > Pipeline schedules**), and a `rules` line that lets the job into scheduled pipelines |
| Run by hand | `workflow_dispatch` | **New pipeline** in the UI (`$CI_PIPELINE_SOURCE == "web"`), or **Run** on the schedule |
| Ask for an OIDC token | `permissions: id-token: write` | `id_tokens:` on the job, with the audience in `aud` |
| Get AWS credentials | The action `aws-actions/configure-aws-credentials` | No action. Two script lines write the token to a file, and the AWS SDK inside InvenTag exchanges it (`AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE`) |
| Role ARN | In the YAML (`role-to-assume`) | A CI/CD variable `AWS_ROLE_ARN`, not in the YAML |
| Region | `aws-region: us-east-1` | `AWS_DEFAULT_REGION: us-east-1`. `AWS_REGION` alone is not enough |
| Identity provider in AWS | `token.actions.githubusercontent.com` | `gitlab.com`, or the host of your own instance |
| What the trust policy pins | Repository and branch | The `sub` claim: project path, ref type and ref name. On GitLab.com also the project ID |
| Token life | Not stated on this page | The job's `timeout`; 5 minutes if the job sets none. Always set `timeout` |
| Python | `actions/setup-python` with `python-version: "3.12"` | `image: python:3.12` |
| Pinning | Each action by full commit SHA | The image by minor version tag. An image digest (`<image-name>@<digest>`) is the stricter form; the examples do not use it ([GitLab: `image`](https://docs.gitlab.com/ci/yaml/#image)) |
| Keep the reports | `actions/upload-artifact` with `if: always()` and `retention-days: 30` | `artifacts:` with `when: always` and `expire_in: 30 days`. Not uploaded when the job times out. The artifact also holds `bom_output/state/` |
| Tolerate an exit code | Not shown on this page | `allow_failure: exit_codes:` on the job ([GitLab: `allow_failure:exit_codes`](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| Longest job | Not stated on this page | 3 hours on GitLab-hosted runners of GitLab.com ([GitLab: hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)) |
| Merge or pull request runs | Not shown on this page | The token names the source branch, and protected variables are passed only under GitLab's conditions. See [the tag policy example](../examples/tag-policy-in-ci.md#gitlab-cicd) |
| Job summary | `$GITHUB_STEP_SUMMARY` (on [the tag policy example](../examples/tag-policy-in-ci.md)) | Not used in these examples |

## What happens on a violation

With `fail_on_tag_violations: true`, InvenTag writes every report first, then
exits with code 3. The job fails, and the artifact still holds the Excel file
and `tag_compliance_<timestamp>.json` with every non-compliant resource.

Sample output of `inventag --template ci-pipeline` from an offline run
(sample data):

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

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | Reports written, no tag violations (or no failing policy). Also when an account failed or nothing was found, unless you pass the flags for codes 5 and 6 |
| 1 | Error: invalid template or configuration file, credentials, every account failed, a report format that could not be written, or a failed S3 upload |
| 2 | Invalid or conflicting options, for example `--accounts-file` with `--accounts-prompt`, or `--compliance-standard` (not implemented). Nothing is scanned |
| 3 | Reports written, tag policy violations found (`fail_on_tag_violations: true`) |
| 4 | Reports written, a security group rule open to the internet at or above `--risk-threshold` |
| 5 | Reports written, but an account could not be scanned or ran out of time (`--fail-on-account-error`) |
| 6 | No resources to report (`--fail-if-empty`) |

If more than one applies, 5 comes first, then 6, then 3, then 4, because the data
behind a tag or risk result is incomplete when an account is missing. Reports
are written for codes 3, 4 and 5. With code 6, a run with `--template` writes
a report that lists no resources, and a run without it writes no file.

## Keep it safe

- Avoid `--debug` in CI. Secrets are masked in debug logs, but the logs are
  long and still describe your accounts.
- To keep reports in S3 instead of (or as well as) artifacts, add
  `--s3-bucket` and grant `s3:PutObject` on that bucket. See
  [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).
- Keep the role read-only and scoped to the repository and branch that need
  it.
- In GitLab CI/CD, protect the branch that runs the pipeline, limit the role's trust policy to that branch, and keep the role ARN in a CI/CD variable. See [GitLab CI/CD](#gitlab-cicd).
- Pin InvenTag to a release (`inventag-aws==%INVENTAG_VERSION%`), not to the latest
  version. Raise the number when you choose to upgrade.

## Next steps

- [Example: enforce a tag policy in CI](../examples/tag-policy-in-ci.md)
- [Track changes between runs](./track-changes.md)
