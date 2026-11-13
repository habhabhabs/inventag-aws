---
title: Security
description: How to report a vulnerability in InvenTag, which Python versions to use, how dependencies are checked, and what to do after a supply-chain incident.
sidebar_position: 1
---

# Security

**Who this is for:** security reviewers, and anyone running InvenTag against
production accounts.

**What you will know after reading:** how to report a problem, how InvenTag's
dependencies are checked, and how to limit the damage if something goes
wrong.

## Report a vulnerability

Please don't put exploit details in a public issue.

This repository does not have a `SECURITY.md` file or GitHub private
vulnerability reporting set up yet (checked November 2026). Until it does,
open an [issue](https://github.com/habhabhabs/inventag-aws/issues) titled
"Security contact request", with no technical details, and ask the
maintainer for a private channel.

## What InvenTag does with your accounts

- **It only reads.** A read-only guard checks every AWS call before it is
  sent. It blocks anything that is not a read, and reads that return secrets
  or data, such as `secretsmanager:GetSecretValue`, `s3:GetObject`,
  `cloudformation:GetTemplate` or `ec2:GetLaunchTemplateData`. It also blocks
  allowed operations when a parameter asks for a secret (API keys with
  `includeValue`, `ec2:DescribeInstanceAttribute` for `userData`), and it
  checks presigned URLs and database auth tokens, which are signed without a
  call to AWS. It is always on.
- **Sign-in still works.** The guard lets the AWS SDK exchange an IAM Identity
  Center (SSO), web-identity or `aws login` token for credentials. It allows
  only these four unsigned calls: `sso:GetRoleCredentials`,
  `sso-oidc:CreateToken`, `sts:AssumeRoleWithWebIdentity` and
  `signin:CreateOAuth2Token`. A signed client that makes the same call is
  blocked.
- **It masks secret values in allowed answers.** Values of fields that often
  hold secrets, such as Lambda environment variables, EC2 user data or
  CloudFormation parameter values, become `***REDACTED***` in reports,
  snapshots and logs. The names stay. See
  [Feature status](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).
- **It sends no usage data.** InvenTag has no telemetry. The command-line tool
  only talks to AWS. The optional CI helper in the Python library can post to
  Slack, Microsoft Teams or a Prometheus Pushgateway, but only to addresses
  you configure yourself.
- **Its files are private.** Reports, snapshots and logs are created readable
  by your user only.
- **Its logs hide secrets.** Session tokens, keys, request signatures and the
  masked values above are hidden, even with `--debug`.

You can check what a run did with `--audit-output audit.json`, and what the
guard allows with `--validate-operations`:

<!-- BEGIN EXAMPLE OUTPUT: validate-operations -->

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: validate-operations -->

## Use a supported Python version

Use Python 3.11 or later. Python 3.10 and older no longer receive security
fixes: 3.10 reached end of life in October 2026
([Python release status](https://devguide.python.org/versions/)).

## How dependencies are checked

| What | How, on the current `main` branch |
|---|---|
| Python dependencies | Listed in `requirements.txt` with minimum versions (`>=`), not exact pins. Each security floor names the advisory it avoids. A fresh install gets the newest matching releases. |
| Development tools | Listed in `requirements-dev.txt` with exact pins (`==`) for the test and lint tools, plus minimum versions for their dependencies. |
| Website | Locked in `website/package-lock.json`. |
| Dependency check in CI | The CI workflow runs `pip-audit -r requirements.txt` and fails on a finding. It runs Bandit and `npm audit` too, but does not fail on their findings. |
| Scheduled scan | A separate workflow runs on pushes to `main` and `develop`, on pull requests to `main` and weekly (Sundays, 02:00 UTC). It runs Bandit, Safety, pip-audit, `npm audit` and detect-secrets. Findings are reported but do not fail that workflow. |
| Software bill of materials | The documentation build generates SBOM files for the Python and website dependencies. |

To check your own installation:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

The template feature adds no new dependencies. It uses PyYAML, openpyxl and
python-docx, which InvenTag already needs.

## Reduce the impact if something goes wrong

InvenTag reads your AWS accounts, so the credentials you give it matter more
than the tool itself.

- **Read-only, least privilege.** Give InvenTag only read permissions:
  [Set up read-only access](../guides/read-only-access.md).
- **Short-lived credentials.** Use IAM Identity Center or an assumed role,
  not access keys on disk or in CI secrets. In GitHub Actions, use OIDC.
- **Keep logs private.** Secrets are masked in logs, but logs still describe
  your accounts.
- **Pin what you run.** Check out a release tag of InvenTag, and pin GitHub
  Actions to commit SHAs.

## After a supply-chain incident

If a dependency, a CI action or the machine that runs InvenTag may have been
compromised:

1. **Revoke and rotate** the credentials InvenTag used: delete access keys,
   revoke active role sessions, and sign out of SSO sessions.
2. **Check AWS CloudTrail** for calls from that identity that InvenTag would
   not make, especially anything that is not `List`, `Describe` or `Get`.
3. **Check the IAM policy is still read-only** and remove anything extra.
4. **Rebuild the environment** from a clean virtual environment:
   `pip install -r requirements.txt`, then run `pip-audit`.
5. **Treat old reports as sensitive.** They list your resources and tags.

## Templates are data, not code

Templates are read with a safe YAML loader, cannot run code or fetch URLs, can
only reference files inside their own folder, and cannot hold access keys.
Details: [Templates](../templates/index.md#safe-by-design).
