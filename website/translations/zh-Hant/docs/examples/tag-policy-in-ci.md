---
title: "範例：在 CI 中強制執行標籤策略"
description: 當 AWS 資源違反你的標籤策略時，讓 CI 作業以結束代碼 3 失敗，同時把 InvenTag 報告保留為建置產物。
sidebar_position: 4
---

# 範例：在 CI 中強制執行標籤策略

**目標：** 一個流水線步驟，在資源缺少必需標籤或標籤值錯誤時失敗，並保留證據。

**你需要：** 一個帶有隻讀 AWS 憑證的 CI 執行器，最好透過 OIDC（OpenID Connect）獲取。
參見[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md)。

## 範本 {#template}

內建的 `ci-pipeline` 設定範本會寫出 Excel 和一個 JSON 檔案，檢查 `finops-cost-allocation`，
並在出現違規時失敗：

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

## 輸出 {#output}

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
3
```

因為範本寫了 `outputs: [excel]`，所以只會寫出 Excel 檔案和 JSON 檔案：

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

要在 GitHub Actions 作業摘要中列出前十個不合規的資源：

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

`acme-reports` 擁有所有標籤，但有兩個值是錯誤的。JSON 檔案中的 `invalid` 列表和工作簿中的 Problems 欄會說明具體是哪兩個。

## 下一步 {#next-steps}

- 先從僅報告模式開始：在數字接近零之前，把 `fail_on_tag_violations` 設為 `false`，然後再開啟它。
- 不要讓不完整的執行被當作透過：有帳戶無法掃描時，`--fail-on-account-error` 以結束代碼 5 結束；沒有找到任何資源時，`--fail-if-empty` 以結束代碼 6 結束。兩者都優先於結束代碼 3。
- 使用你自己的規則：[對照策略檢查標籤](../guides/check-tag-compliance.md#write-your-own-policy)。
