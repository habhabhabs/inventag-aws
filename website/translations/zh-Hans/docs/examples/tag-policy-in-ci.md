---
title: "示例：在 CI 中强制执行标签策略"
description: 当 AWS 资源违反你的标签策略时，让 CI 作业以退出码 3 失败，同时把 InvenTag 报告保留为构建产物。
sidebar_position: 4
---

# 示例：在 CI 中强制执行标签策略

**目标：** 一个流水线步骤，在资源缺少必需标签或标签值错误时失败，并保留证据。

**你需要：** 一个带有只读 AWS 凭证的 CI 运行器，最好通过 OIDC（OpenID Connect）获取。
参见[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md)。

## 模板 {#template}

内置的 `ci-pipeline` 配置模板会写出 Excel 和一个 JSON 文件，检查 `finops-cost-allocation`，
并在出现违规时失败：

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

## 命令 {#command}

```bash title="Terminal"
inventag --template ci-pipeline
echo $?
```

## 输出 {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
$ echo $?
3
```

因为模板写了 `outputs: [excel]`，所以只会写出 Excel 文件和 JSON 文件：

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

要在 GitHub Actions 作业摘要中列出前十个不合规的资源：

```bash title="Workflow step"
python3 -c "
import json, glob
r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))
print(f\"{r['summary']['non_compliant']} non-compliant resources\")
for x in r['non_compliant_resources'][:10]:
    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))
" >> "$GITHUB_STEP_SUMMARY"
```

```text title="Job summary"
21 non-compliant resources
- DYNAMODB acme-orders missing: CostCenter, Project
- EC2 i-855a01aabe3d29d3a missing: CostCenter, Project
- EC2 snap-3585ce88e25ef1196 missing: CostCenter, Owner, Project, Environment
- EC2 vol-680d0e08d01dd52e7 missing: CostCenter, Owner, Project, Environment
- EC2 vol-57d5df4cfc9884b48 missing: CostCenter, Owner, Project, Environment
- EVENTS default missing: CostCenter, Owner, Project, Environment
- IAM acme-orders-api-role missing: CostCenter, Owner, Project, Environment
- LAMBDA acme-orders-api missing: CostCenter, Project
- S3 acme-data-lake missing: Project
- S3 acme-reports missing:
```

`acme-reports` 拥有所有标签，但有两个值是错误的。JSON 文件中的 `invalid` 列表和工作簿中的 Problems 列会说明具体是哪两个。

## 下一步 {#next-steps}

- 先从仅报告模式开始：在数字接近零之前，把 `fail_on_tag_violations` 设为 `false`，然后再打开它。
- 使用你自己的规则：[对照策略检查标签](../guides/check-tag-compliance.md#write-your-own-policy)。
