---
title: Google Sheets 和 Docs 輸出
description: 如何把 InvenTag 清單寫入 Google Sheets 電子表格和 Google Docs 文件、如何登入、誰能開啟這些檔案，以及哪些部分尚未對真實的 Google 驗證過。
sidebar_position: 9
---

# Google Sheets 和 Docs 輸出

**適合誰閱讀：** 你希望把清單放在 Google Drive 中，替代或補充 Excel、Word 檔案。

**讀完後你會了解：** 如何安裝 Google 庫、如何登入、該用哪些引數、誰能開啟這些檔案，以及哪些部分尚未驗證。

## 你會得到什麼 {#what-you-get}

- `--create-google-sheets` 把與 `--create-excel` 相同的工作簿（相同的工作表、相同的行順序、相同的模板）寫成 Google Sheets 電子表格。
- `--create-google-docs` 把與 `--create-word` 相同的報告寫成 Google Docs 文件。
- InvenTag 先生成 Excel 和 Word 報告，再複製它們，因此 `--template` 對 Google 檔案的影響與對本地檔案完全一樣。
- 執行時會列印每個檔案的 URL。

## 安裝 Google 附加包 {#install-the-google-add-on}

寫入 Google 需要幾個額外的 Python 包（Google 的登入和 API 庫）。大多數人從不使用 Google 輸出，
所以這些包預設不隨 InvenTag 一起安裝。你只需用下面這條命令新增一次：

```bash title="Terminal"
pip install "inventag-aws[google]"
```

可以把它理解為“安裝 InvenTag，外加它的 Google 附加包”。方括號裡的部分是附加包的名稱，
不是佔位符，所以請按原樣輸入，包括引號（macOS 預設的 shell zsh 需要引號）。

- **你已經安裝了 InvenTag。** 執行同一條命令。pip 會保留你現有的 InvenTag，只新增 Google 包。
- **你是用 pipx 安裝的。** 執行 `pipx install "inventag-aws[google]"`，或者執行
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  把這些包新增到你已有的 InvenTag 中。
- **你使用虛擬環境。** 先啟用它，這樣這些包就會裝在 InvenTag 旁邊。

Excel、Word 或其他功能都不需要這個附加包。如果在沒有它的情況下使用 Google 引數，
InvenTag 會以退出碼 2 停止，說明缺少哪個包，並列印這條命令。

## 登入 {#sign-in}

任選一種：

| 方式 | 引數 | 適用場景 |
|---|---|---|
| 服務賬號金鑰 | `--google-credentials key.json` | 定時執行和 CI |
| 你自己的 Google 賬號 | `--google-oauth-client client_secret.json` | 在膝上型電腦上執行。瀏覽器只會開啟一次，令牌儲存在 `~/.config/inventag/google-token.json`，只有你本人可讀。 |
| 應用預設憑證 | 無 | 你執行過 `gcloud auth application-default login` |

在憑證所屬的 Google Cloud 專案中啟用 Google Sheets、Google Docs 和 Google Drive API。

許可權範圍是 `drive.file`：InvenTag 只能訪問它自己建立的檔案。使用
`--google-folder-id` 時，它會請求完整的 Drive 許可權範圍，因為它必須把檔案放進一個已有的資料夾。

## 誰能開啟這些檔案 {#who-can-open-the-files}

檔案對建立它們的賬號**私有**。除非你提出要求，否則不會共享任何內容。

```bash title="Terminal"
inventag --create-google-sheets --create-google-docs \
  --google-credentials key.json \
  --google-share-with you@example.com \
  --google-share-with team@example.com --google-share-role commenter \
  --google-folder-id 1AbCdEfGh \
  --google-title "AWS inventory, May"
```

- `--google-share-with EMAIL` 可以重複使用。`--google-share-role` 為所有這些人統一設定
  `reader`（預設）、`commenter` 或 `writer`。
- `--google-share-anyone` 讓任何拿到連結的人都能讀取這些檔案。僅用於你會公開發布的資料。
- 服務賬號擁有它所建立的檔案，這些檔案在它自己的 Drive 中，你無法開啟。如果你用服務賬號登入，
  又既沒有給出 `--google-share-with` 也沒有給出 `--google-folder-id`，InvenTag 會對此發出警告。
- 如果在沒有 `--create-google-sheets` 或 `--create-google-docs` 的情況下使用
  `--google-share-with`、`--google-share-role`、`--google-share-anyone`、
  `--google-folder-id` 和 `--google-title`，會以退出碼 2 停止。

## 憑證絕不會寫入日誌 {#credentials-are-never-logged}

金鑰檔案的路徑不會被列印；看起來像 Google 私鑰、訪問令牌、重新整理令牌或客戶端金鑰的機密，
在每一行日誌中都會被遮蔽，包括 `--debug`。Google 庫的錯誤資訊會被縮短為錯誤型別，
因為它們可能引用金鑰檔案。

## 限制 {#limits}

- Google Sheets 的單元格最多容納 50,000 個字元，一個電子表格最多 1,000 萬個單元格。
  非常大的清單可能超出限制；此時執行會因 Google 的錯誤而失敗。
- Word 報告的表格預設每個服務最多顯示 50 個資源（報告模板中是 `max_rows_per_service`，佈局檔案中是 `max_rows`），Google Docs 文件也是如此。
- 單元格的值以文字形式寫入，因此以 `=` 開頭的標籤值不會被當作公式執行。

## 尚未驗證的部分 {#what-is-not-verified}

所有測試都使用模擬的 Google 客戶端。**沒有任何測試針對真實的 Google API 執行過**，
因為那需要一個 Google 賬號。特別是，InvenTag 填充 Google Docs 文件中表格時計算的位置，
是按我們對 Docs API 規則的理解來檢查的，而不是對真實服務檢查的。請先用一個小賬戶試一試，
如果 Google Docs 文件的版式有問題，請提交 issue 反饋。

## 接下來 {#where-to-next}

- [選擇要掃描什麼、生成什麼](./run-a-scan.md)
- [CLI 參考](../reference/cli.md#output)
- [報告模板](../templates/index.md)
