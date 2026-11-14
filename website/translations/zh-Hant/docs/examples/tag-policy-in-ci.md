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

## GitLab CI/CD {#gitlab-cicd}

同樣的檢查可以作為 GitLab CI/CD 作業，在合併請求流水線中執行。**該檢查讀取的是 AWS 目前的狀態，不會讀取合併請求中的更改。**

請先設定角色和 CI/CD 變數：參見[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)。合併請求作業需要第二個角色，見下面的第三點。

未針對 GitLab Runner 或真實的 AWS 帳戶驗證：此流水線尚未在 GitLab 上執行。它的 YAML 和 `inventag` 命令列會在建置文件時檢查。它的作業已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）、模擬的 AWS 和一個虛擬權杖執行過。

```yaml
# .gitlab-ci.yml
stages:
  - check

tag-policy:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour                             # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # Exit code 3 (tag policy violations) fails this job.
    # Exit code 5 (an account could not be scanned) and 6 (no resources found) fail it too.
    - inventag --template ci-pipeline --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports when the job fails
    paths:
      - bom_output/
    expire_in: 1 week

security-groups:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour
  allow_failure:
    exit_codes: 4                             # warn only; delete these two lines to block on exit code 4
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --create-excel --enable-security-analysis --risk-threshold HIGH --fail-on-account-error --fail-if-empty
  artifacts:
    when: always
    paths:
      - bom_output/
    expire_in: 1 week
```

### 每個結束代碼的結果 {#what-each-exit-code-does}

此檔案中，GitLab 對 InvenTag 每個結束代碼的處理：

| 結束代碼 | 作業 `tag-policy` | 作業 `security-groups` |
|---|---|---|
| 0 | 透過 | 透過 |
| 3（標籤策略違規） | **失敗**，與 GitHub Actions 範例一致 | 不會出現（此命令沒有標籤策略） |
| 4（有安全組規則達到或超過 `HIGH`） | 不會出現（沒有 `--risk-threshold`） | 「允許失敗」：作業顯示警告，流水線繼續執行，並算作透過（[GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)） |
| 5（有帳戶無法掃描；`--fail-on-account-error`）、6（沒有找到資源；`--fail-if-empty`） | 失敗 | 失敗：該結束代碼不在 `exit_codes` 中，所以對它而言 `allow_failure` 為 false |
| 1、2 | 失敗 | 失敗 |

### 各部分的作用 {#what-each-part-does}

所有 GitLab 範例共用的行（`image`、`timeout`、`id_tokens`、兩行權杖命令和 `artifacts`）見[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中的表格。下表列出本範例特有的部分：

| 部分 | 作用 |
|---|---|
| `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"` | 作業只在合併請求流水線中執行（[GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。 |
| `inventag --template ci-pipeline --fail-on-account-error --fail-if-empty` | 本頁的命令，加上兩個需要主動開啟的選項。結束代碼 5 和 6 優先於 3（順序為 5、6、3、4），所以有帳戶無法掃描、或沒有找到資源的執行，絕不會顯示為「無違規」。已連線帳戶內某次服務呼叫失敗不會給出 5。在本地執行中，此作業以結束代碼 3 失敗，其報告檔案已被收集。 |
| `allow_failure: exit_codes: 4` | 只容許結束代碼 4。其他任何非零結束代碼，作業照常失敗。若要讓結束代碼 4 也阻止合併請求，刪除這兩行。若要讓 `tag-policy` 作業以警告模式啟動，用同樣的方式給它加上 `allow_failure:` 和 `exit_codes: 3`，或者像「下一步」所說，保持 `fail_on_tag_violations: false`（[GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)）。在本地執行中，`security-groups` 以警告和結束代碼 4 結束。 |
| `inventag --create-excel --enable-security-analysis --risk-threshold HIGH ...` | 有安全組規則達到或超過 `HIGH` 時結束代碼為 4。`--risk-threshold` 需要 `--enable-security-analysis`，否則結束代碼為 2。這裡沒有 `--template`，因為 `--enable-security-analysis` 與 `--template` 一起使用時不會增加任何內容（見 [CLI 參考](../reference/cli.md)）。此作業會掃描每個已啟用的區域。 |

尚未驗證的內容：

- 未針對 GitLab 或 AWS 驗證：GitLab 簽發 ID 權杖，以及 AWS 據此接受該角色，包括對 `aud` 和 `sub` 的信任策略條件。
- 未針對 GitLab 驗證：`image`、`timeout`、`expire_in` 和 `cache`（gitlab-ci-local 會忽略它們）。
- 未針對 GitLab 驗證：失敗的作業或允許失敗的作業如何影響後續作業、流水線狀態和合並請求。

### 需要了解的三點 {#three-things-to-know}

1. **該檢查讀取的是 AWS 目前的狀態，不會讀取合併請求中的更改。** 這些命令除了範本檔案之外，不會把儲存庫中的任何內容交給 InvenTag。每個作業對帳戶掃描一次，所以一次合併請求流水線會掃描兩次。預設情況下，每次執行還會使用 Cost Explorer，AWS 對每次 Cost Explorer 請求收費；`--no-billing-validation` 會停止這些呼叫（見 [CLI 參考](../reference/cli.md)）。
2. **只有專案要求時，失敗的作業才會阻止合併。** 請開啟 **Settings > Merge requests > Merge checks > Pipelines must succeed**。你需要 Maintainer 或 Owner 角色（[GitLab](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)）。
3. **在合併請求流水線中，ID 權杖指明的是源分支，而不是 `main`**（[GitLab](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。信任策略只允許 `ref:main` 的角色會拒絕這些作業。請為它們建立第二個唯讀角色，不帶上傳語句（`s3:PutObject`）。這種情況的信任策略見[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)。任何能向專案推送分支並建立合併請求的人，都可以用這個角色執行作業，還可以在自己的分支中修改作業的指令碼。該角色是隻讀的，所以他們能讀取 InvenTag 能讀取的內容。不要複用定時作業所用的角色。
   - 受保護的 CI/CD 變數只有在源分支和目標分支都受保護、兩者在同一個專案中、並且該使用者可以合併到目標分支時，才會傳給合併請求流水線。來自復刻（fork）的流水線永遠得不到它（[GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。因此，不要為這些作業保護 `AWS_ROLE_ARN`。
   - 範例讀取的是 `AWS_ROLE_ARN`，這適用於只有這些合併請求作業的專案。如果專案還用第一個角色執行定時作業，第二個角色需要另一個變數名。本範例沒有演示如何對應。

## 下一步 {#next-steps}

- 先從僅報告模式開始：在數字接近零之前，把 `fail_on_tag_violations` 設為 `false`，然後再開啟它。
- 不要讓不完整的執行被當作透過：有帳戶無法掃描時，`--fail-on-account-error` 以結束代碼 5 結束；沒有找到任何資源時，`--fail-if-empty` 以結束代碼 6 結束。兩者都優先於結束代碼 3。
- 使用你自己的規則：[對照策略檢查標籤](../guides/check-tag-compliance.md#write-your-own-policy)。
