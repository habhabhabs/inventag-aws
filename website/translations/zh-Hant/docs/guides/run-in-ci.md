---
title: 在 CI/CD 中執行 InvenTag
description: 在 GitHub Actions 或 GitLab CI/CD 中定時執行 InvenTag，使用短期的 OIDC 憑證，把報告儲存為構件，並在標籤策略違規時讓作業失敗。
sidebar_position: 7
---

# 在 CI/CD 中執行 InvenTag

**適合誰閱讀：** 你想定時生成清單，或者希望在資源標籤不規範時讓流水線失敗。

**讀完後你可以：** 搭建一個 GitHub Actions 工作流或 GitLab CI/CD 流水線，用短期憑證執行 InvenTag 並儲存報告。

## 組成部分 {#the-pieces}

1. **不儲存金鑰的憑證。** 使用 OpenID Connect（OIDC）：CI 系統證明作業的身份，
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
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly --fail-on-account-error --fail-if-empty
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

請把每個 action 固定到完整的提交 SHA，並在註釋中註明版本。這樣即使某個標籤被移到惡意程式碼上，
你也能得到保護。上面四個 SHA 是註釋中所標版本的標籤所對應的提交。
更新版本時，請同時更新 SHA。

InvenTag 從你儲存庫的資料夾執行，因此 `.inventag/templates/nightly.yaml` 可以按名稱找到。

不加這兩個結束代碼引數時，即使有帳戶無法掃描或什麼都沒找到，作業也會成功。`--fail-on-account-error` 會讓前一種情況以結束代碼 5 使作業失敗，
`--fail-if-empty` 會讓後一種情況以結束代碼 6 使作業失敗。報告仍會寫出，所以上傳構件的步驟可以保留它們。

## GitLab CI/CD {#gitlab-cicd}

本節是上面 GitHub Actions 步驟在 GitLab 上的對應做法。第 2 步的設定範本是同一個。範例按 GitLab.com 編寫。[自託管例項](#on-a-self-managed-instance)需要做幾處修改。

### 讓 GitLab 擔任唯讀角色 {#let-gitlab-assume-a-read-only-role}

未針對 GitLab 或 AWS 驗證：GitLab 簽發 ID 權杖，以及 AWS 為該角色接受它，包括信任策略中對 `aud` 和 `sub` 的條件。

**第 1 步：把 GitLab 新增為 IAM 中的 OIDC 身份提供商。** 在 IAM 控制檯中開啟 **Identity providers > Add provider**，選擇 OpenID Connect（[AWS：建立 OIDC 身份提供商](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)）。

| 欄位 | 值 |
|---|---|
| 提供商 URL | GitLab.com 用 `https://gitlab.com`。自託管例項用你自己例項的地址，例如 `https://gitlab.example.com`。AWS 要求 URL 以 `https://` 開頭。GitLab 說明該地址必須可公開存取（[GitLab：OpenID Connect in AWS](https://docs.gitlab.com/ci/cloud_services/aws/)）。 |
| 受眾 | `sts.amazonaws.com`。它必須與流水線中 `id_tokens` 下的 `aud` 文字相同。 |
| 指紋 | 無需填寫。IAM 會自行獲取，並且 AWS 會先對照自己的受信任根 CA 列表檢查提供商的證書（[AWS：`create-open-id-connect-provider`](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)）。 |

每個 URL 在每個 AWS 帳戶中只能新增一個提供商。對同一個 URL 再次新增會失敗。如果你的帳戶已經信任 `gitlab.com`，就把該受眾新增到現有的提供商中。

**第 2 步：用信任策略建立角色。** 為這個提供商建立一個角色。下面的信任策略允許 GitLab.com 上的一個專案、一個分支擔任該角色。這是定時範例的情形，它們在 `main` 上執行。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.com:aud": "sts.amazonaws.com",
          "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main",
          "gitlab.com:project_id": "67890"
        }
      }
    }
  ]
}
```

替換這些值：

| 值 | 替換為 |
|---|---|
| `123456789012` | 儲存身份提供商和角色的 AWS 帳戶 ID。提供商和角色必須在同一個帳戶中。 |
| `gitlab.com`（四處） | GitLab.com 保持不變。自託管例項則使用你例項的主機名，不帶 `https://`。 |
| `sts.amazonaws.com` | 保持不變，除非你在第 1 步和 `id_tokens` 下選了別的受眾。 |
| `mygroup/myproject` | 專案的完整路徑：組、子組和專案。 |
| `main` | 定時流水線執行所在的分支。 |
| `67890` | 專案 ID。這一行只在 GitLab.com 上有效。在自託管或 Dedicated 例項上，AWS 只支援 `sub` 和 `aud` 宣告，所以在那裡要刪除這一行。 |

`sub` 宣告預設的形式是 `project_path:{group}/{project}:ref_type:{type}:ref:{branch_name}`。專案可以透過 projects API 改變這個形式，改變後上面的值就不再匹配（[GitLab：ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。建議使用針對穩定 ID（如 `project_id`）的條件，因為已刪除的專案路徑可能被別人重新建立（[AWS：IAM 條件鍵](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)）。

條件中使用萬用字元需要 `StringLike`。如果用 `StringEquals`，AWS 會拒絕該呼叫。

**變體：任意受保護的分支（GitLab.com）。** 替換 `Condition` 塊：

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890",
    "gitlab.com:ref_protected": "true"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

未針對 AWS 驗證：`"true"` 是否正是 AWS 為 `ref_protected` 比較的文字。`ref_protected` 和 `pipeline_source` 只是 GitLab.com 的條件鍵。

**變體：受保護的標籤（GitLab.com）。** 同一個塊，把 `sub` 行中的 `ref_type:branch:ref:*` 部分換成 `ref_type:tag:ref:*`（或 `ref_type:tag:ref:v*`）。

**變體：合併請求流水線。** 合併請求流水線的權杖帶的是源分支，所以角色必須接受專案的每一個分支：

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

未針對 GitLab 驗證：合併請求流水線中 `sub` 的確切文字。

使用這個變體時，任何能向專案推送分支並建立合併請求的人，都能用這個角色執行作業，還能在自己的分支裡修改作業的指令碼。該角色是隻讀的，所以他們能讀到 InvenTag 能讀到的內容。為這個變體單獨建立一個角色。不要複用定時作業的角色，也不要給它 `s3:PutObject`。參見[標籤策略範例](../examples/tag-policy-in-ci.md#gitlab-cicd)。

**第 3 步：附加唯讀策略。** 附加[設定唯讀存取](./read-only-access.md)中的策略：方案 2，即 `config/defaults/iam-policy-read-only.json`，或方案 1（`ReadOnlyAccess` 加三個操作）。

- 對上傳範例，保留語句 `OptionalS3ReportUpload`，並把你的儲存貯體名稱填到 `YOUR-REPORTS-BUCKET-NAME` 的位置。它的資源以 `bom-reports/*` 結尾，所以鍵字首必須是 `bom-reports/`（預設值），否則就要修改該資源。使用 `aws:kms` 時，還要允許對該金鑰執行 `kms:GenerateDataKey`（[IAM 權限](../reference/iam-permissions.md)）。參見[定時把報告上傳到 S3](../examples/scheduled-s3-upload.md)。其他範例請刪除該語句。
- 對多帳戶範例，該角色還需要對每個帳戶的 `InvenTagReadOnly` 角色執行 `sts:AssumeRole`，並且這些角色都要信任此角色。儲存庫中的策略檔案沒有 `sts:AssumeRole` 語句。參見[設定唯讀存取](./read-only-access.md)和[掃描多個帳戶](./scan-multiple-accounts.md)。

InvenTag 保持唯讀。無論角色還是流水線，都不會讓任何帳戶符合任何合規要求。

#### 在自託管例項上 {#on-a-self-managed-instance}

未針對自託管 GitLab 例項驗證：本段內容。提供商 URL 和條件鍵使用你例項的主機名。在那裡 AWS 只支援 `sub` 和 `aud` 宣告，所以要刪除 `project_id` 這一行。在那裡 AWS 中沒有 `ref_protected` 鍵，所以要按名稱逐個固定分支。AWS 必須能從網際網路存取該例項；對非公開的例項，GitLab 描述了一種變通辦法，並稱之為高階用法（[GitLab：configure a non-public GitLab instance](https://docs.gitlab.com/ci/cloud_services/aws/)）。Runner 必須能夠執行容器映象。

### 新增 CI/CD 變數 {#add-the-cicd-variable}

在你的 GitLab 專案中，開啟 **Settings > CI/CD > Variables > Add variable**（需要 Maintainer 角色）。鍵填 `AWS_ROLE_ARN`，值填角色的 ARN，例如 `arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly`。GitLab 會把該變數作為環境變數傳給作業（[GitLab：CI/CD variables](https://docs.gitlab.com/ci/variables/)）。

- 對定時範例，勾選 **Protect variable** 並保護該分支。這樣該變數只會傳給受保護分支或標籤上的流水線。
- 對合並請求範例，不要保護該變數。除非源分支和目標分支都受保護，否則受保護的變數不會傳給合併請求流水線（[GitLab：merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。如果用了兩個角色，請在該範例的兩個作業中使用第二個變數名。
- 自 GitLab 18.3 起，GitLab 預設把新變數設為 **Masked**，而被遮蔽的值必須是一行、至少 8 個字元且不含空格。角色 ARN 不是機密。如果 GitLab 拒絕遮蔽該值，請選擇 **Visible**。未針對 GitLab 驗證：GitLab 是否接受把角色 ARN 作為遮蔽值。
- 上傳範例還需要另外兩個變數，`INVENTAG_REPORTS_BUCKET` 和 `INVENTAG_KMS_KEY_ID`。兩者都不是機密。

### 新增流水線 {#add-the-pipeline}

這個作業每晚執行 InvenTag，並把報告儲存為作業產物。它需要第 2 步中的 `.inventag/templates/nightly.yaml`。把檔案以 `.gitlab-ci.yml` 為名放到儲存庫根目錄。如果該檔案已經有 `stages`，就把階段名加到那個列表裡。

未針對 GitLab Runner 或真實的 AWS 帳戶驗證：此流水線尚未在 GitLab 上執行。它的 YAML 和 `inventag` 命令列會在建置文件時檢查。它的作業已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）針對模擬的 AWS 執行，使用的是虛擬權杖。

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"   # the pipeline schedule
    - if: $CI_PIPELINE_SOURCE == "web"        # "New pipeline" in the GitLab UI
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    key: pip
    paths:
      - .cache/pip
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --template nightly --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports even when the tag check fails
    paths:
      - bom_output/
    expire_in: 30 days
```

各部分的作用：

| 部分 | 作用 |
|---|---|
| `stages:` 和 `stage:` | 宣告階段，並把作業放進該階段。沒有 `stage` 的作業會進入 `test`（[GitLab：`stages`](https://docs.gitlab.com/ci/yaml/#stages)）。 |
| `image: python:3.12` | 作業在這個容器映象中執行，形式為 `<image-name>:<tag>`。InvenTag 需要 Python 3.11 或更高版本，GitHub 範例用的是 3.12（[GitLab：`image`](https://docs.gitlab.com/ci/yaml/#image)）。 |
| 帶 `schedule` 和 `web` 的 `rules:` | 作業只會加入定時流水線，以及在 GitLab 介面中用 **New pipeline** 啟動的流水線。在其他所有流水線（推送、合併請求）中，沒有規則匹配，作業不會被加入（[GitLab：job rules](https://docs.gitlab.com/ci/jobs/job_rules/)）。 |
| `timeout: 2 hours` | 超過該時間後停止作業（[GitLab：`timeout`](https://docs.gitlab.com/ci/yaml/#timeout)）。它還決定 ID 權杖的有效期：如果設定了作業超時，GitLab 把權杖的過期時間設為該超時；沒有設定則為 5 分鐘（[GitLab：ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。InvenTag 在一次執行中不止一次交換權杖（已在本地對模擬的 AWS 驗證），所以請始終設定 `timeout`。GitLab.com 上由 GitLab 託管的 Runner 會在 3 小時後停止每個作業（[GitLab：hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)）。 |
| `id_tokens:` | GitLab 為這個作業生成一個 OIDC ID 權杖（一種 JSON Web 權杖），受眾寫在 `aud` 中。指令碼以 `$GITLAB_OIDC_TOKEN` 讀取它。它在 Free、Premium 和 Ultimate 套餐中可用，適用於 GitLab.com、Self-Managed 和 Dedicated（[GitLab：`id_tokens`](https://docs.gitlab.com/ci/yaml/#id_tokens)）。 |
| `AWS_DEFAULT_REGION` | AWS SDK 在登入呼叫中使用的區域。請設定這個變數：只設 `AWS_REGION` 不夠，因為 botocore（AWS 的 Python SDK）不讀取它（已在本地驗證）。 |
| `pip install "inventag-aws==..."` | 安裝 InvenTag 的固定版本。 |
| 帶 `AWS_WEB_IDENTITY_TOKEN_FILE` 的兩行 | 把權杖寫入專案資料夾之外的一個新的私有檔案，並告訴 AWS SDK 它在哪裡。有了 `AWS_ROLE_ARN`（CI/CD 變數），SDK 會自己把權杖換成臨時憑證（[AWS：assume role credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)）。不需要 AWS CLI，也不需要存取金鑰。專案資料夾之外的檔案不會變成產物或快取條目，因為兩者都只接受專案資料夾內的路徑（[GitLab：`artifacts:paths`](https://docs.gitlab.com/ci/yaml/#artifactspaths)、[GitLab：caching](https://docs.gitlab.com/ci/caching/)）。已在本地對模擬的 AWS 驗證：該檔案的權限是 600，SDK 用該權杖登入。 |
| `PIP_CACHE_DIR` 和 `cache:` | 在作業之間保留 pip 的下載快取。快取必須在專案資料夾內，因為 GitLab 只快取那裡的路徑（[GitLab：caching examples](https://docs.gitlab.com/ci/caching/examples/)）。可選：沒有這幾行，作業也能執行。 |
| `inventag --template nightly --fail-on-account-error --fail-if-empty` | 與 GitHub 工作流中的命令相同。標籤策略發現違規且範本中寫了 `fail_on_tag_violations: true` 時結束代碼為 3，有帳戶無法掃描時為 5，沒有找到任何資源時為 6。任何非 0 的結束代碼都會讓作業失敗（[GitLab：`script`](https://docs.gitlab.com/ci/yaml/script/)）。在本地（用替身代替 rsync），作業以結束代碼 3 結束，並收集到了四個報告檔案。 |
| `artifacts:` | 把 `bom_output/` 作為作業產物上傳。有 `when: always` 時，作業失敗 GitLab 也會上傳；沒有它，則只在作業成功時上傳。`always` 不包括超時的作業。`expire_in` 指定 GitLab 保留產物多久。無論 `expire_in` 如何，GitLab 都會保留某個 ref 最新流水線的產物（預設的專案設定）（[GitLab：`artifacts:when`](https://docs.gitlab.com/ci/yaml/#artifactswhen)、[GitLab：`artifacts:expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)、[GitLab：job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)）。`expire_in: 30 days` 與 GitHub 工作流中的 `retention-days: 30` 對應。InvenTag 在以結束代碼 3、4 或 5 退出之前就已寫出報告。 |
| 角色 ARN | 不在 YAML 中。它是上一步的 CI/CD 變數 `AWS_ROLE_ARN`。 |

這個範例還有兩部分沒有驗證：

- 未針對 GitLab 驗證：`image`、`timeout`、`expire_in` 和 `cache`（gitlab-ci-local 會忽略它們）。
- 未針對 GitLab 流水線計劃驗證：本地執行時，流水線來源是手動設定的。

### 設定定時執行 {#schedule-it}

定時設定不在檔案裡。請在 GitLab 中建立一個 schedule：開啟 **Build > Pipeline schedules > New schedule**，填寫 cron 表示式（例如 `17 2 * * 1-5`）和目標分支，然後儲存。你需要 Developer 或更高的角色。流水線以該 schedule 所有者的權限執行（[GitLab：pipeline schedules](https://docs.gitlab.com/ci/pipelines/schedules/)）。要手動執行該作業，請在 GitLab 介面中選擇 **New pipeline**，或在該 schedule 上選擇 **Run**。

未針對 GitLab 驗證：流水線計劃對 cron 表示式使用的時區。

### 與 GitHub Actions 的差異 {#what-differs-from-github-actions}

GitHub 一欄只描述上面的 GitHub 工作流所展示的內容。

| 主題 | GitHub Actions | GitLab CI/CD |
|---|---|---|
| 檔案 | `.github/workflows/inventory.yml` | 儲存庫根目錄的 `.gitlab-ci.yml` |
| 定時 | 檔案內的 `on: schedule: - cron:` | 不在檔案裡。在 GitLab 介面中建立 schedule（**Build > Pipeline schedules**），再用一行 `rules` 讓作業進入定時流水線 |
| 手動執行 | `workflow_dispatch` | 介面中的 **New pipeline**（`$CI_PIPELINE_SOURCE == "web"`），或在 schedule 上點 **Run** |
| 請求 OIDC 權杖 | `permissions: id-token: write` | 作業上的 `id_tokens:`，受眾寫在 `aud` 中 |
| 獲取 AWS 憑證 | 動作 `aws-actions/configure-aws-credentials` | 沒有動作。指令碼中兩行把權杖寫入檔案，由 InvenTag 內部的 AWS SDK 交換（`AWS_ROLE_ARN`、`AWS_WEB_IDENTITY_TOKEN_FILE`） |
| 角色 ARN | 在 YAML 中（`role-to-assume`） | CI/CD 變數 `AWS_ROLE_ARN`，不在 YAML 中 |
| 區域 | `aws-region: us-east-1` | `AWS_DEFAULT_REGION: us-east-1`。只設 `AWS_REGION` 不夠 |
| AWS 中的身份提供商 | `token.actions.githubusercontent.com` | `gitlab.com`，或你自己例項的主機 |
| 信任策略限定什麼 | 儲存庫和分支 | `sub` 宣告：專案路徑、ref 型別和 ref 名稱。在 GitLab.com 上還有專案 ID |
| 權杖有效期 | 本頁未說明 | 作業的 `timeout`；作業沒有設定則為 5 分鐘。請始終設定 `timeout` |
| Python | `actions/setup-python`，`python-version: "3.12"` | `image: python:3.12` |
| 固定版本 | 每個動作按完整的提交 SHA 固定 | 映象按次版本標籤固定。映象摘要（`<image-name>@<digest>`）是更嚴格的形式；範例沒有使用（[GitLab：`image`](https://docs.gitlab.com/ci/yaml/#image)） |
| 儲存報告 | `actions/upload-artifact`，帶 `if: always()` 和 `retention-days: 30` | `artifacts:`，帶 `when: always` 和 `expire_in: 30 days`。作業超時則不會上傳。產物中還包含 `bom_output/state/` |
| 容忍某個結束代碼 | 本頁未展示 | 作業上的 `allow_failure: exit_codes:`（[GitLab：`allow_failure:exit_codes`](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)） |
| 作業最長時間 | 本頁未說明 | GitLab.com 上由 GitLab 託管的 Runner 為 3 小時（[GitLab：hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)） |
| 合併請求或提取要求的執行 | 本頁未展示 | 權杖帶的是源分支，受保護的變數只在 GitLab 的條件下才會傳入。參見[標籤策略範例](../examples/tag-policy-in-ci.md#gitlab-cicd) |
| 作業摘要 | `$GITHUB_STEP_SUMMARY`（見[標籤策略範例](../examples/tag-policy-in-ci.md)） | 這些範例中沒有使用 |

## 發生違規時會怎樣 {#what-happens-on-a-violation}

設定了 `fail_on_tag_violations: true` 時，InvenTag 會先寫出所有報告，然後以結束代碼 3 退出。
作業會失敗，而構件中仍然儲存著 Excel 檔案和 `tag_compliance_<timestamp>.json`，
後者包含每個不合規的資源。

下面是離線執行 `inventag --template ci-pipeline` 的範例輸出（範例資料）：

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

## 結束代碼 {#exit-codes}

| 結束代碼 | 含義 |
|---|---|
| 0 | 報告已寫出，沒有標籤違規（或沒有會導致失敗的策略）。有帳戶失敗或什麼都沒找到時也是 0，除非你傳了對應結束代碼 5 和 6 的引數 |
| 1 | 錯誤：範本或設定檔無效、憑證問題、所有帳戶都失敗、某個報告格式無法寫出，或 S3 上傳失敗 |
| 2 | 選項無效或相互衝突，例如 `--accounts-file` 與 `--accounts-prompt` 同用，或 `--compliance-standard`（未實現）。不會掃描任何內容 |
| 3 | 報告已寫出，發現標籤策略違規（`fail_on_tag_violations: true`） |
| 4 | 報告已寫出，有對網際網路開放的安全組規則達到或超過 `--risk-threshold` |
| 5 | 報告已寫出，有帳戶無法掃描或只掃描了一部分（`--fail-on-account-error`） |
| 6 | 沒有可報告的資源（`--fail-if-empty`） |

如果同時滿足多個條件，先是 5，然後是 6，然後是 3，最後是 4，因為缺少帳戶時，標籤或風險結果背後的資料是不完整的。
結束代碼 3、4 和 5 會寫出報告。對於結束代碼 6，帶 `--template` 的執行會寫出一份不列出任何資源的報告，不帶 `--template` 的執行則不寫檔案。

## 保持安全 {#keep-it-safe}

- 在 CI 中避免使用 `--debug`。除錯日誌中的機密會被遮蔽，但日誌很長，仍然會描述你的帳戶。
- 如果想把報告儲存在 S3 中（代替構件，或與構件並用），請新增 `--s3-bucket`，
  並授予對該儲存貯體的 `s3:PutObject` 權限。參見
  [定時把報告上傳到 S3](../examples/scheduled-s3-upload.md)。
- 保持角色唯讀，並把它限定在需要它的儲存庫和分支。
- 在 GitLab CI/CD 中，保護執行流水線的分支，把角色的信任策略限制在該分支上，並把角色 ARN 儲存在 CI/CD 變數中。參見 [GitLab CI/CD](#gitlab-cicd)。
- 把 InvenTag 固定到某個發佈版本（`inventag-aws==%INVENTAG_VERSION%`），而不是最新版本。想升級時再自己提高版本號。

## 下一步 {#next-steps}

- [範例：在 CI 中強制執行標籤策略](../examples/tag-policy-in-ci.md)
- [跟蹤兩次執行之間的變化](./track-changes.md)
