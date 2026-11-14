---
title: Glossary
description: Plain-English meanings of the terms used in the InvenTag docs, from accounts file and ARN to tag policy and read-only guard.
sidebar_position: 6
---

# Glossary

**Who this is for:** anyone who meets an unfamiliar word in these docs.

The docs use each term below in one meaning only.

| Term | Meaning |
|---|---|
| **Accounts file** | A YAML or JSON file, passed with `--accounts-file`, that lists the AWS accounts to scan. See [Configuration files](./configuration-files.md#accounts-file). |
| **ARN** | Amazon Resource Name: the unique ID AWS gives a resource, for example `arn:aws:s3:::acme-app-logs`. |
| **AWS account** | One AWS account, identified by a 12-digit account ID such as `123456789012`. |
| **BOM** | Bill of materials: the list of resources InvenTag writes to Excel or Word. |
| **Compliant** | A resource that has every tag a tag policy requires, with allowed values. |
| **Config template** | A template with `kind: config`: which accounts and regions to scan, which files to write, and which report template and tag policy to use. |
| **Cost Explorer** | The AWS service that reports spend. InvenTag calls it to spot services with spend; AWS charges per request ([pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)). |
| **Credential chain** | The places the AWS SDK looks for credentials, such as environment variables, profiles and IAM roles. InvenTag uses the SDK's default chain. |
| **Exit code** | The number a command returns when it ends. `0` means success; InvenTag uses `1` for errors, `2` for invalid or conflicting options, `3` for tag policy violations, `4` for security group rules at or above `--risk-threshold`, `5` for an account that could not be scanned or ran out of time (with `--fail-on-account-error`) and `6` for nothing to report (with `--fail-if-empty`). If more than one applies, 5 comes first, then 6, then 3, then 4. See [Exit codes](./cli.md#exit-codes). |
| **IAM** | AWS Identity and Access Management: users, roles and the policies that say what they may do. |
| **IAM Identity Center** | The AWS service for single sign-on (SSO) to AWS accounts. |
| **IAM role** | An identity with permissions that other identities can assume for a short time. |
| **moto** | A Python library that imitates AWS on your computer. The docs' sample outputs come from runs against moto. |
| **OIDC** | OpenID Connect: lets a CI system such as GitHub Actions or GitLab CI/CD get short-lived AWS credentials without stored keys. |
| **Out of scope** | A resource that a tag policy does not check, because of its `scope` settings. |
| **Read-only guard** | The part of InvenTag that checks every AWS call before it is sent and blocks anything that is not a read. Always on. |
| **Region** | A geographic AWS location, written as a code such as `us-east-1` or `eu-west-1`. |
| **Report template** | A template with `kind: report`: the title, colours, columns, sheets and sections of the Excel and Word files. |
| **Sample data** | Output from InvenTag runs against moto, with made-up accounts and resources. Used on these pages. |
| **Snapshot** | A JSON file in `bom_output/state/` that records what one run found, so runs can be compared. |
| **Tag** | A key and value attached to an AWS resource, for example `Owner=platform`. A tag policy compares keys case-sensitively. A tag mapping matches keys case-insensitively unless `case_sensitive: true`. |
| **Tag policy** | A template with `kind: tag-policy`: the tags resources must have and the values allowed. |
| **Template** | A small YAML file that controls one part of a run: a report template, a tag policy or a config template. See [Templates](../templates/index.md). |
| **Throttling** | AWS slowing down or refusing requests because too many arrive at once. |
