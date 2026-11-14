---
title: Google Sheets 和 Docs 輸出
description: 如何把 InvenTag 清單寫入 Google Sheets 電子表格和 Google Docs 文件、如何登入、誰能開啟這些檔案、如何用你自己的 Google 帳號測試，以及哪些部分尚未對真實的 Google 驗證過。
sidebar_position: 9
---

# Google Sheets 和 Docs 輸出

**適合誰閱讀：** 你希望把清單放在 Google Drive 中，替代或補充 Excel、Word 檔案。

**讀完後你會了解：** 如何安裝 Google 庫、如何登入、該用哪些引數、誰能開啟這些檔案、如何用你自己的 Google 帳號測試輸出，以及哪些部分尚未驗證。

## 你會得到什麼 {#what-you-get}

- `--create-google-sheets` 把與 `--create-excel` 相同的工作簿（相同的工作表、相同的列順序）寫成 Google Sheets 電子表格。
- `--create-google-docs` 把與 `--create-word` 相同的報告寫成 Google Docs 文件。
- InvenTag 先生成 Excel 和 Word 報告，再複製它們。使用 `--template` 時，InvenTag 不會寫出任何 Google 檔案：它會記錄該格式被跳過，執行以結束代碼 0 結束。
- 執行時會列印每個檔案的 URL，例如 `Google Sheet: https://docs.google.com/spreadsheets/d/...` 和 `Google Doc: https://docs.google.com/document/d/...`。
- 使用 `--per-account-reports` 時，InvenTag 為每個帳戶生成一對檔案。標題以 ` - ` 和帳戶 ID 結尾，URL 行形如 `Google Sheet: [123456789012] https://...` 和 `Google Doc: [123456789012] https://...`。
- 如果執行沒有找到任何資源，就不會生成 Google 檔案。

未針對 真實的 Google 驗證：這些檔案與 Excel 和 Word 報告外觀一致，且 URL 為這種形式。

## 安裝 Google 附加包 {#install-the-google-add-on}

寫入 Google 需要幾個額外的 Python 包（Google 的登入和 API 庫）。大多數人從不使用 Google 輸出，
所以這些包預設不隨 InvenTag 一起安裝。你只需用下面這條命令新增一次：

```bash title="Terminal"
pip install "inventag-aws[google]"
```

可以把它理解為「安裝 InvenTag，外加它的 Google 附加包」。方括號裡的部分是附加包的名稱，
不是佔位符，所以請按原樣輸入，包括引號（macOS 預設的 shell zsh 需要引號）。

- **你已經安裝了 InvenTag。** 執行同一條命令。pip 會保留你現有的 InvenTag，只新增 Google 包。
- **你是用 pipx 安裝的。** 執行 `pipx install "inventag-aws[google]"`，或者執行
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  把這些包新增到你已有的 InvenTag 中。
- **你使用虛擬環境。** 先啟用它，這樣這些包就會裝在 InvenTag 旁邊。

Excel、Word 或其他功能都不需要這個附加包。如果在沒有它的情況下使用 Google 引數，
InvenTag 會以結束代碼 2 停止，說明缺少哪個包，並列印這條命令。

未針對 pip 和 pipx 驗證：Google 附加包的安裝命令。

## 登入 {#sign-in}

任選一種：

| 方式 | 引數 | 適用場景 |
|---|---|---|
| 服務帳號金鑰 | `--google-credentials key.json` | 定時執行和 CI |
| 你自己的 Google 帳號 | `--google-oauth-client client_secret.json` | 在膝上型電腦上執行。瀏覽器只會開啟一次，權杖儲存在 `~/.config/inventag/google-token.json`，只有你本人可讀。 |
| 應用預設憑證 | 無 | 你執行過 `gcloud auth application-default login` |

在憑證所屬的 Google Cloud 專案中啟用 Google Sheets、Google Docs 和 Google Drive API。

InvenTag 會在掃描 AWS 之前讀取金鑰檔案或 OAuth 客戶端檔案，因此檔案有誤時，執行會立即以結束代碼 2 停止，並給出以 `inventag: error: Google:` 開頭的訊息。

權限範圍是 `drive.file`：InvenTag 只能存取它自己建立的檔案。使用
`--google-folder-id` 時，它會請求完整的 Drive 權限範圍，因為它必須把檔案放進一個已有的資料夾。

未針對真實的 Google 驗證：瀏覽器登入、儲存的權杖、應用預設憑證、要啟用的 API，以及 `drive.file` 權限範圍允許什麼。

## 誰能開啟這些檔案 {#who-can-open-the-files}

檔案對建立它們的帳號**私有**。除非你提出要求，否則不會共享任何內容。

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
- 服務帳號擁有它所建立的檔案，這些檔案在它自己的 Drive 中，你無法開啟。如果你用服務帳號登入，
  又既沒有給出 `--google-share-with` 也沒有給出 `--google-folder-id`，InvenTag 會對此發出警告。
- 如果在沒有 `--create-google-sheets` 或 `--create-google-docs` 的情況下使用
  `--google-share-with`、`--google-share-role`、`--google-share-anyone`、
  `--google-folder-id` 和 `--google-title`，會以結束代碼 2 停止。

未針對真實的 Google 驗證：新檔案是否保持私有、共享，以及你無法開啟服務帳號擁有的檔案。

## 憑證絕不會寫入日誌 {#credentials-are-never-logged}

金鑰檔案的路徑不會被列印；看起來像 Google 私鑰、存取權杖、重新整理權杖或客戶端金鑰的機密，
在每一行日誌中都會被遮蔽，包括 `--debug`。Google 庫的錯誤資訊會被縮短為錯誤型別，
因為它們可能引用金鑰檔案。

## 限制 {#limits}

- Google Sheets 的單元格最多容納 50,000 個字元。InvenTag 會把更長的文字在 49,000 個字元處截斷。一個電子表格最多 1,000 萬個單元格，一個工作表最多 18,278 欄。

  未針對 真實的 Google 驗證：單元格、大小和欄數的限制。
- InvenTag 會在呼叫 Google 之前先數單元格。如果報告太大，它不會建立任何內容並說明原因，執行以結束代碼 1 結束。Excel 和 Word 檔案仍會寫出。例如：
  `The report has 12,000,000 cells; a Google spreadsheet allows 10,000,000. No
  spreadsheet was created. Send fewer resources (filters or an account subset)
  or use the Excel report.`
- InvenTag 會把大的工作表分成多個請求傳送，每個請求最多 2,000 行，約 100 萬個字元。
- 如果 Google 返回「429 too many requests」，InvenTag 會記錄 `Google rate limit
  reached; waiting 5 seconds` 並重試。在最後一次嘗試之前，它依次等待 5、10、20、40 和 60 秒。

  未針對 真實的 Google 驗證：請求大小，以及 429 的等待時間是否足夠長。
- 如果檔案建立之後某個呼叫失敗，執行會以結束代碼 1 結束，訊息中會給出寫到一半的檔案的 URL：`The spreadsheet was already
  created and may be incomplete: <url> (delete it in Google Drive).` Google Docs 文件同理。請刪除該檔案，然後重新執行。
- Word 報告的表格預設每個服務最多顯示 50 個資源（報告範本中是 `max_rows_per_service`，佈局檔案中是 `max_rows`），Google Docs 文件也是如此。
- 單元格的值以文字形式寫入，因此以 `=` 開頭的標籤值不會被當作公式執行。

未針對 真實的 Google 驗證：以 `=` 開頭的文字會被存為文字。

## 尚未驗證的部分 {#what-is-not-verified}

大多數測試使用模擬的 Google 客戶端。**我們沒有記錄過針對真實 Google API 的執行**，
因為那需要一個 Google 帳號。特別是，InvenTag 填充 Google Docs 文件中表格時計算的位置，
是按我們對 Docs API 規則的理解來檢查的，而不是對真實服務檢查的。請先用一個小帳戶試一試，
如果 Google Docs 文件的版面配置有問題，請提交 issue 回饋。上面每個依賴 Google 的部分都會說明哪些內容尚未驗證。

## 用你自己的 Google 帳號檢查 {#check-it-against-your-own-google-account}

儲存庫裡有一個指令碼，可以替你做真實 Google 的測試。它用 moto（AWS 的模擬）建置一個虛構的資源環境，
因此不需要 AWS 帳號，只會接觸 Google。它用 `--create-google-sheets` 和
`--create-google-docs` 執行 InvenTag，從 Google 讀回這些檔案，並與同一次執行生成的 Excel 和 Word 檔案比較。
它會列印一張 PASS 或 FAIL 表、兩個 URL，以及 `RESULT: PASS` 或 `RESULT: FAIL`。透過時結束代碼為 0。

請在儲存庫的檢出目錄中執行它。

1. 安裝 Google 庫和 moto：

   ```bash title="Terminal"
   pip install "inventag-aws[google]"
   pip install moto
   ```

2. 在憑證所屬的 Google Cloud 專案中，啟用 Google Sheets API、Google Docs API 和 Google Drive API。
   如果其中一個沒有啟用，Google 會返回 HTTP 403，指令碼會指出要啟用哪個 API。
3. 建立一個型別為「Desktop app」的 OAuth 客戶端，把它下載為 `client_secret.json`，然後執行：

   ```bash title="Terminal"
   python scripts/google_live_test.py --google-oauth-client client_secret.json --large
   ```

   瀏覽器會開啟一次。如果應用處於「Testing」狀態，請把你的帳號新增到 OAuth consent screen 的 Test users 下。

未針對 Google Cloud 驗證：啟用 API、建立 OAuth 客戶端和新增測試使用者的控制檯步驟。

如果要使用服務帳號金鑰，請傳入 `--google-credentials key.json`。服務帳號擁有它自己 Drive 中的檔案，
所以如果你想開啟它們，請加上 `--share-with you@example.com`。

| 引數 | 作用 |
|---|---|
| `--large` | 還會測試一個 20,000 行的工作表和一個 300 行的 Doc 表格。它會統計 API 呼叫次數，並注入兩次「429」應答來證明重試有效。 |
| `--share-with EMAIL` | 把檔案共享（reader）給這個地址，並檢查只有該地址和所有者能開啟它們。可重複使用。 |
| `--keep` | 把檔案留在 Drive 中。預設情況下，指令碼會在最後把它建立的每個檔案移到 Drive 的回收站。 |
| `--folder-id ID` | 還會在這個 Drive 資料夾中建立一對檔案。這需要完整的 Drive 權限範圍。使用 `--google-oauth-client` 時，請先刪除 `~/.config/inventag/google-token.json`，這樣它會重新詢問。 |

不帶登入引數時，指令碼使用應用預設憑證。Google 會阻止 `gcloud` 自己的登入客戶端使用 Drive、Docs 和 Sheets 的權限範圍，
所以這裡也需要你自己的 OAuth 客戶端檔案。執行 `python
scripts/google_live_test.py --help` 查看确切的 `gcloud` 命令。我們沒有驗證過這條途徑。請優先使用 OAuth 客戶端。

指令碼會檢查這些內容：

- 電子表格和 Doc 存在，並且與列印出的 URL 一致。
- 工作表名稱和順序、行和欄，以及每個單元格都與 Excel 檔案一致。
- 以 `=` 開頭的文字回來時仍是文字，而不是公式。
- 長文字、帶重音的文字、CJK 文字和空工作表都能保留。
- 標題行為粗體並帶顏色，頂部幾行被凍結。
- Doc 的標題和每個表格單元格都與 Word 檔案一致。
- 兩個檔案對該帳號私有（以及對 `--share-with` 地址）。

如果你執行了它，請把最後的表格發給我們。只有在真實帳號上透過之後，我們才會修改本頁。

## 接下來 {#where-to-next}

- [選擇要掃描什麼、生成什麼](./run-a-scan.md)
- [CLI 參考](../reference/cli.md#output)
- [報告範本](../templates/index.md)
