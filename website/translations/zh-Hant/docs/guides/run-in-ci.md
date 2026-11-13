---
title: 在 CI/CD 中執行 InvenTag
description: 在 GitHub Actions 中定時執行 InvenTag，使用短期的 OIDC 憑證，把報告儲存為構件，並在標籤策略違規時讓作業失敗。
sidebar_position: 7
---

# 在 CI/CD 中執行 InvenTag

**適合誰閱讀：** 你想定時生成清單，或者希望在資源標籤不規範時讓流水線失敗。

**讀完後你可以：** 搭建一個 GitHub Actions 工作流，用短期憑證執行 InvenTag 並儲存報告。

## 組成部分 {#the-pieces}

1. **不儲存金鑰的憑證。** 使用 OpenID Connect（OIDC）：GitHub 證明工作流的身份，
   AWS 為它提供一個臨時的角色會話。你的儲存庫機密中不儲存任何存取金鑰。
2. **一個設定範本**，包含你的區域、輸出和標籤策略。內建的 `ci-pipeline` 範本是個不錯的起點。
3. **一個構件**，用來儲存 `bom_output/`。

## 1. 讓 GitHub 擔任唯讀角色 {#1-let-github-assume-a-read-only-role}

在 AWS 中，把 GitHub 新增為 OIDC 身份提供商（`token.actions.githubusercontent.com`），
並建立一個角色，附加[設定唯讀存取](./read-only-access.md)中的唯讀策略。
把它的信任策略限制在你的儲存庫和分支上。AWS 的指南
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
有詳細講解。

## 2. 把設定範本新增到你的儲存庫 {#2-add-a-config-template-to-your-repository}

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

設定你的區域和標籤策略，然後提交該檔案。

## 3. 新增工作流 {#3-add-the-workflow}

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
      - uses: aws-actions/configure-aws-credentials@<full-commit-SHA> # pin the current release
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

請把每個 action 固定到完整的提交 SHA，並在註釋中註明版本。這樣即使某個標籤被移到惡意程式碼上，
你也能得到保護。上面 `checkout`、`setup-python` 和 `upload-artifact` 的 SHA，
是本儲存庫自己的工作流所使用的。對於 `aws-actions/configure-aws-credentials`，
請到它的 GitHub 發佈頁面查詢目前發佈版本的 SHA：我們沒有為本頁驗證過任何一個。
更新版本時，請同時更新 SHA。

InvenTag 從你儲存庫的資料夾執行，因此 `.inventag/templates/nightly.yaml` 可以按名稱找到。

## 發生違規時會怎樣 {#what-happens-on-a-violation}

設定了 `fail_on_tag_violations: true` 時，InvenTag 會先寫出所有報告，然後以結束代碼 3 退出。
作業會失敗，而構件中仍然儲存著 Excel 檔案和 `tag_compliance_<timestamp>.json`，
後者包含每個不合規的資源。

下面是離線執行 `inventag --template ci-pipeline` 的範例輸出（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
$ echo $?
3
```

| 結束代碼 | 含義 |
|---|---|
| 0 | 報告已寫出，沒有標籤違規（或沒有會導致失敗的策略） |
| 1 | 錯誤：範本無效、憑證問題、所有帳戶都失敗，或 S3 上傳失敗 |
| 3 | 報告已寫出，發現標籤策略違規 |

## 保持安全 {#keep-it-safe}

- 在 CI 中避免使用 `--debug`。除錯日誌中的機密會被遮蔽，但日誌很長，仍然會描述你的帳戶。
- 如果想把報告儲存在 S3 中（代替構件，或與構件並用），請新增 `--s3-bucket`，
  並授予對該儲存貯體的 `s3:PutObject` 權限。參見
  [定時把報告上傳到 S3](../examples/scheduled-s3-upload.md)。
- 保持角色唯讀，並把它限定在需要它的儲存庫和分支。
- 把 InvenTag 固定到某個發佈版本（`inventag-aws==%INVENTAG_VERSION%`），而不是最新版本。想升級時再自己提高版本號。

## 下一步 {#next-steps}

- [範例：在 CI 中強制執行標籤策略](../examples/tag-policy-in-ci.md)
- [跟蹤兩次執行之間的變化](./track-changes.md)
