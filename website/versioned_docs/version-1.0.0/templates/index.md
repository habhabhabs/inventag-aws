---
title: Templates
description: Reuse report layouts, tag policies and run settings in InvenTag with small YAML templates you can list, copy, adapt and validate.
sidebar_position: 1
---

# Templates

**Who this is for:** anyone who runs InvenTag more than once and wants the
same report layout, the same tag rules or the same scan settings every time.

**What you can do after reading:** pick a built-in template, use it with
`--template`, and know when to make your own.

## What a template is

A template is a short YAML file that tells InvenTag how to do one part of a
run. There are three kinds:

| Kind | Controls | Example built-in |
|---|---|---|
| `report` | How the Excel workbook and Word document look: title, colours, columns, which sheets and sections appear | `standard-bom`, `executive-summary` |
| `tag-policy` | Which tags every resource must have, and which values are allowed | `finops-cost-allocation`, `security-baseline` |
| `config` | What to scan and what to produce: accounts, regions, output files, and which report and tag policy to use | `single-account`, `org-multi-account`, `ci-pipeline` |

InvenTag ships eight [built-in templates](./catalogue.md). You can copy any of
them into your project and [adapt it](./adapt-a-template.md).

## Use a template

Add `--template` to a normal run. You can give a name or a file path:

```bash
inventag --template executive-summary --create-word
inventag --template ./my-templates/acme-bom.yaml --create-excel
```

Repeat `--template` to combine one template of each kind:

```bash
inventag --template standard-bom --template security-baseline --create-excel
```

A few rules decide what wins when settings overlap:

1. **Flags you type win.** If a config template says `outputs: [excel]` and you
   also type `--create-word`, you get both files.
2. **A template on the command line wins over a reference inside another
   template.** `--template security-baseline` replaces the tag policy that
   `finops-cost-report` names.
3. **Without a report template, InvenTag uses `standard-bom`.**

Runs without `--template` use the original report layout.

## What a tag policy adds to your reports

When a tag policy is active, InvenTag checks every resource in scope and
adds:

- a **Tag Compliance** sheet in the workbook, one row per resource, with what
  is missing or wrong;
- a **Tag compliance** section in the Word document;
- a `tag_compliance_<timestamp>.json` file you can use in scripts or CI;
- a one-line summary in the terminal.

Sample output from an offline run with `--template finops-cost-report`
(sample data):

<!-- BEGIN EXAMPLE OUTPUT: finops-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

<!-- END EXAMPLE OUTPUT: finops-console -->

A config template can set `fail_on_tag_violations: true` to make InvenTag exit
with code 3 when something breaks the policy. The built-in `ci-pipeline`
template does this.

## Where InvenTag looks for templates

When you give a name, InvenTag checks these folders in order and uses the
first match:

1. Each folder in the `INVENTAG_TEMPLATE_PATH` environment variable (separate
   folders with `:` on Linux and macOS, `;` on Windows).
2. `.inventag/templates/` in the folder you run InvenTag from (your project).
3. `~/.config/inventag/templates/` (or `$XDG_CONFIG_HOME/inventag/templates/`).
4. The built-in templates.

So a file called `.inventag/templates/standard-bom.yaml` replaces the built-in
`standard-bom` for that project. It can still build on the original with
`extends: standard-bom`. Run `inventag templates list` to see what is
found and from where.

## Safe by design

Templates are plain data:

- InvenTag reads them with a safe YAML loader. YAML tags that create Python
  objects, such as `!!python/object`, are rejected.
- Templates cannot run code, evaluate expressions or fetch anything from the
  internet.
- File references inside a template (`extends`, `tag_policy`,
  `report_template`, `logo`) must be relative paths that stay inside the
  template's folder.
- Config templates cannot contain access keys. Use `profile_name` or
  `role_arn`.
- Values from AWS that start with `=` are written to Excel as text, so a tag
  value cannot become a spreadsheet formula.

## Next steps

- [Built-in templates](./catalogue.md): what each one produces.
- [Adapt a template](./adapt-a-template.md): copy, edit, validate, run.
- [Template reference](./reference.md): every field.
- [Examples](../examples/index.md): complete recipes that use templates.
