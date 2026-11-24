# InvenTag policy findings

Snapshot `s1.json`, evaluated on 2026-11-20.

| Rows | Fail | Waived | Not evaluated | Pass |
| --- | --- | --- | --- | --- |
| 10 | 2 | 0 | 1 | 3 |

## EC2-002 (low)

File policies/ex09.yaml: fail 1, waived 1, not evaluated 0, pass 0, out of scope 0.

| Result | Account | Region | Resource | Detail |
| --- | --- | --- | --- | --- |
| fail | 111111111111 | us-east-1 | arn:aws:ec2:us-east-1:111111111111:instance/web\]\[31m(http://x)\|&lt;b&gt;\]\]&gt;&amp;"' line2 | EC2-002: condition not met: raw\_data.Password |
| waived | 111111111111 | us-east-1 | arn:aws:ec2:us-east-1:111111111111:instance/i-0w | EC2-002: condition not met: tag:Owner waived: legacy, expires 2027-01-01 |

## EC2-003 (low)

File policies/ex10.yaml: fail 0, waived 0, not evaluated 1, pass 0, out of scope 0.

| Result | Account | Region | Resource | Detail |
| --- | --- | --- | --- | --- |
| not\_evaluated | 111111111111 | us-east-1 | arn:aws:ec2:us-east-1:111111111111:instance/i-0n | EC2-003: not evaluated (tags\_not\_read) |

## Units not read

| Policy | Account | Service | Region | Outcome |
| --- | --- | --- | --- | --- |
| EC2-002 | 111111111111 | EC2 | eu-west-1 | access\_denied |

## Unused waivers

| Policy | Resource | Expires | Why | File |
| --- | --- | --- | --- | --- |
| EC2-002 | arn:x | 2027-01-01 | no match | waivers.yaml |
| EC2-002 | arn:y | 2026-12-31 | superseded | waivers.yaml |

Exit code 8: something was not evaluated and --fail-on-not-evaluated is set.
