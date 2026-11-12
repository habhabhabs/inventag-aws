---
title: Network and security analysis
description: The current state of InvenTag's network and security-group analysis flags, and how to review VPCs and security groups with the reports today.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Network and security analysis

**Who this is for:** you want to review VPCs, subnets and security groups with
InvenTag.

**What you will know after reading:** what the analysis flags do today, and
how to get network resources into a report now.

## Current state

InvenTag has two flags for this:

- `--enable-network-analysis`: VPCs, subnets and how they are used.
- `--enable-security-analysis`: security groups and network ACLs.

On the current release, **neither flag adds anything to the Excel or Word
report.** We checked this by running both flags against mocked AWS: the
workbook had the same sheets with and without them. The analysis code exists
in `inventag/discovery/network_analyzer.py` and `security_analyzer.py`, but
its results are not written to the reports yet. This is tracked on the
[status page](../getting-started/status.md).

## What you can do today

Network resources are part of every normal scan. With the `standard-bom`
template they appear on the **VPC** sheet: VPCs, subnets, route tables,
network ACLs and security groups, each with its tags.

To see their configuration as well, add every field the AWS API returned:

```yaml
# .inventag/templates/network-review.yaml
format_version: 1
kind: report
name: network-review
description: Every field, for a network review
extends: standard-bom
spec:
  title: Network review
  excel:
    include_all_fields: true
```

```bash
./inventag.sh --template network-review --create-excel --account-regions us-east-1
```

The VPC sheet then has columns such as `raw_data.CidrBlock`,
`raw_data.IpPermissions` and `raw_data.MapPublicIpOnLaunch`. These come
straight from the AWS API, so they are detailed but not summarised.

## Next steps

- [Feature status and known limitations](../getting-started/status.md)
- [Adapt a template](../templates/adapt-a-template.md)
