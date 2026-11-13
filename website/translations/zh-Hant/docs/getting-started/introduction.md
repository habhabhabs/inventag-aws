---
title: InvenTag 是什麼
description: InvenTag 一次執行做什麼——查詢 AWS 資源、檢查標籤、生成 Excel 和 Word 報告——它寫出什麼，以及它不是什麼。
sidebar_position: 1
---

# InvenTag 是什麼

**適合誰閱讀：** 正在判斷 InvenTag 是否適合自己工作的人。

**讀完後你會了解：** 一次執行做了什麼、它會改動什麼（只有你磁碟上的檔案），
以及它的侷限在哪裡。

## 三個問題，一份報告 {#three-questions-one-report}

InvenTag 回答關於你的 AWS 賬戶的三個問題：

1. **有什麼？** 跨賬戶、跨區域的資源清單。
2. **標籤規範嗎？** 報告中的標籤列；配合[標籤策略模板](../templates/index.md)，
   還能檢查必填標籤和允許的取值。
3. **和上次相比有什麼變化？** 每次執行都會儲存快照，以便比較。
   參見[追蹤兩次執行之間的變化](../guides/track-changes.md)。

結果就是一份物料清單（BOM）：一個 Excel 工作簿、一個 Word 文件，或兩者都有。

## 一次執行如何進行 {#how-a-run-works}

```text
your AWS credentials
        |
        v
  1. find resources   --> List/Describe/Get calls per service,
        |                 the Resource Groups Tagging API, Cost Explorer
        v
  2. tidy and enrich  --> service names, IDs, tags
        |
        v
  3. check tags       --> only when a tag policy is active
        |
        v
  4. write files      --> bom_output/*.xlsx, *.docx, state/ snapshot
```

1. **憑證。** InvenTag 使用標準的 AWS 憑證鏈：配置檔案、環境變數、
   IAM Identity Center（SSO）會話或 IAM 角色。它也可以在其他賬戶中代入角色。
2. **發現。** 對每個賬戶和區域，它呼叫只讀的 AWS 應用程式程式設計介面（API）。
   預設情況下，它還會呼叫 Cost Explorer 的 `GetCostAndUsage`，找出產生費用的服務。
   AWS 會對 Cost Explorer API 請求收費；`--no-billing-validation` 可關閉這些呼叫。
3. **處理。** 它統一服務名稱和 ID，並收集標籤。
4. **輸出。** 它把檔案寫入輸出資料夾（預設為 `bom_output/`），
   並把快照寫入 `bom_output/state/`。

## 它會改動什麼 {#what-it-changes}

只有你磁碟上的檔案。InvenTag 讀取你的 AWS 賬戶，絕不會修改它們。

**只讀防護**會在每次 AWS 呼叫發出前進行檢查。不屬於讀取的呼叫
（`List`、`Describe`、`Get` 等以外的呼叫）會被攔截，會返回金鑰或檔案內容的讀取
（例如讀取金鑰值或下載 S3 物件）也會被攔截。你無法關閉這道防護。

仍然請給 InvenTag 使用只讀的 IAM 身份。兩道相互獨立的保險勝過一道：
[設定只讀訪問](../guides/read-only-access.md)。

## 它不是什麼 {#what-it-is-not}

- **不是合規工具。** InvenTag 可以收集證據，例如資源清單和標籤覆蓋率。
  它不評估也不認證對 SOC 2、PCI DSS、HIPAA、GDPR 或任何其他框架的合規性。
- **不是成本工具。** 它列出資源和標籤，不計算它們的費用。
- **與 AWS 無關聯。**
- **並不完整。** 它自帶 24 種 AWS 服務的發現程式碼，並非所有服務，
  而且從未在真實的 AWS 賬戶上測試過。
  [功能狀態與已知限制](./status.md)列出了這些限制。

## 下一步 {#next-steps}

- [安裝 InvenTag](./installation.md)
- [生成第一份報告](./quick-start.md)
