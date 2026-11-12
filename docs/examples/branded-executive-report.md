---
title: "Example: branded executive Word report"
description: Produce a short, landscape Word report with your logo, colours and tag compliance summary for a leadership audience, using an InvenTag report template.
sidebar_position: 7
---

# Example: branded executive Word report

**Goal:** a short Word document for leadership with your logo and colours:
totals, services and tag compliance, without per-resource tables.

**You need:** read-only credentials and a logo as a PNG, JPEG, GIF or BMP
file. Word cannot embed SVG logos.

## Template

Put the logo next to the template, in the same folder or a subfolder:

```text
.inventag/templates/
  board-report.yaml
  brand/
    acme-logo.png
```

```yaml
# .inventag/templates/board-report.yaml
format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo        # read by screen readers
  colors:
    header_fill: "4B2E83"             # white text on this purple passes WCAG AA
  tag_policy: security-baseline
  word:
    orientation: landscape
```

## Command

```bash
./inventag.sh templates validate board-report
./inventag.sh --template board-report --create-word --account-regions us-east-1
```

## Expected output

Sample data from an offline run:

```text
OK    ~/acme-infra/.inventag/templates/board-report.yaml (report 'board-report')
Wrote bom_output/tag_compliance_20261112_132421.json
Wrote bom_output/multi_account_bom_20261112_132421.docx
Tag policy 'security-baseline': 0 of 23 resources compliant (0.0%), 23 non-compliant, 14 out of scope.
```

The document is in landscape and reads, in order:

1. **Cover:** the logo, "Cloud Estate Summary", "Quarterly review",
   "Prepared for Acme Ltd" and the date.
2. **Summary:** resources, services, accounts and regions.
3. **Resources by service:** a table with purple header rows that repeat on
   each page.
4. **Tag compliance:** the policy, the counts, the rules and the non-compliant
   resources.
5. **About this report:** how it was made, and the note that InvenTag is not
   affiliated with AWS.

If the logo is missing or is not an image Word supports, the run stops before
scanning:

```text
board-report.yaml:10: spec.logo: logo file not found: ~/acme-infra/.inventag/templates/brand/acme-logo.png
```

## Next steps

- Keep colours readable: pick a header colour with a contrast ratio of at
  least 4.5:1 against the header text.
- Add the full inventory as an Excel attachment:
  `./inventag.sh --template board-report --create-word --create-excel`.
