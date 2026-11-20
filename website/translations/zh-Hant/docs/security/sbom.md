---
title: 軟體物料清單
description: InvenTag 軟體物料清單（SBOM）列出了什麼、如何生成，以及如何檢查你所安裝的依賴項。
sidebar_position: 3
---

# 軟體物料清單

**適合誰閱讀：** 需要了解 InvenTag 由什麼構成的安全和採購審查人員。

**讀完後你會了解：** 有哪些 SBOM 檔案、它們如何生成，如何檢查發佈檔案，以及如何為你自己的安裝生成一份 SBOM。

## 文件建置會生成什麼 {#what-the-documentation-build-generates}

每次部署文件網站時，建置都會為儲存庫及其依賴項生成 SBOM 檔案，並隨網站一起發佈：

| 檔案 | 列出什麼 | 格式 |
|---|---|---|
| 儲存庫 SBOM | Syft 在儲存庫中發現的所有內容 | Syft JSON、CycloneDX JSON 和 SPDX JSON |
| Python，來自 `requirements.txt` | InvenTag 宣告的最低版本 | CycloneDX JSON 和 XML |
| Python，來自全新安裝 | 實際安裝的版本 | CycloneDX JSON 和 `pip freeze` 列表 |
| 文件網站 | 建置本網站所用的 Node.js 包 | CycloneDX JSON |

未針對 GitHub Actions Runner 驗證：文件建置發佈的 SBOM 檔案；本頁讀自工作流檔案。

同一次建置還會向本節新增一個摘要頁面，**Software Bill of Materials (SBOM)**，
因此它出現線上上網站中，但不會出現在本地建置中。

Python 依賴項宣告的是最低版本，而不是精確固定，所以「已安裝版本」的檔案才能顯示，
在建置當天一次真實安裝會得到什麼。

## 一個發佈版本包含什麼 {#what-a-release-carries}

每個發佈版本都有打包建置：可執行檔案壓縮包、`.deb` 和 `.rpm` 軟體包。發佈工作流為它們生成下面的檔案。
這些建置見[安裝 InvenTag](../getting-started/installation.md#choose-how-to-install)。

| 檔案 | 內容 |
|---|---|
| `inventag-<version>-<os>-<cpu>.tar.gz`、`inventag_<version>_<cpu>.deb`、`inventag-<version>-1.<cpu>.rpm` | 打包建置 |
| 上述每個檔案對應一個 `.cdx.json` 檔案，例如 `inventag_<version>_amd64.deb.cdx.json` | 該檔案的 SBOM：它的 Python 包和 C 庫，含名稱、版本和授權 |
| `inventag-<version>-<os>-<cpu>.THIRD-PARTY-LICENSES.txt` | 宣告檔案：每個所攜帶元件的授權文字 |
| `inventag-<version>-<os>-<cpu>.components.json` | 用來生成 SBOM 和宣告檔案的元件列表 |
| `inventag-<version>-linux-<cpu>.build-image.txt` | Linux 建置系統的記錄：它的發行版本，以及建置所攜帶的庫的版本 |
| `SHA256SUMS` | 該發佈版本其他每個檔案的 SHA-256 校驗和 |

SBOM 檔案使用 CycloneDX 格式，1.5 版，JSON 編碼。工作流根據建置結果寫出它們，所以它們列出的是檔案裡實際有的內容，
而不是 `requirements.txt` 所允許的內容。

未針對 CycloneDX 架構驗證：SBOM 檔案能透過驗證器。

未針對 GitHub 驗證：發佈頁帶有這些檔案。到目前為止的測試執行不會向發佈頁附加任何檔案，帶有這些檔案的第一次正式發佈執行還沒有進行。

### 檢查發佈檔案 {#check-a-release-file}

發佈工作流在簽名檔案時不使用我們自己的金鑰。它把 `SHA256SUMS` 交給 GitHub 的 `actions/attest` 步驟，
該步驟以這個工作流的名義寫入建置證明。用 GitHub CLI 檢查一個檔案：

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb --repo habhabhabs/inventag-aws
```

檢查校驗和，見[檢查下載的檔案](../getting-started/installation.md#check-the-download)。

未針對 GitHub 驗證：對發佈檔案執行 `gh attestation verify`。測試執行不會生成任何建置證明。第一份真實的建置證明由第一次正式發佈執行生成，這次執行還沒有進行。

### 打包建置中的授權 {#licenses-in-the-packaged-builds}

InvenTag 使用 MIT 授權。打包建置還攜帶其他專案的檔案。宣告檔案列出了它們和它們的授權文字。

可執行檔案壓縮包、`.deb` 和 `.rpm` 包含 GNU libiconv，這是一個使用 GNU 寬通用公共授權（LGPL）2.1 版的庫。
計劃中的 Homebrew formula 安裝同一個壓縮包，所以它也包含 libiconv。libiconv 的程式碼位於 lxml 的擴充套件模組內部。
InvenTag 需要 lxml 來寫 Word 檔案。lxml 專案建置這些模組，並把 libiconv 連結進去。
InvenTag 原樣攜帶 lxml 的檔案：建置時會把每個檔案與鎖定檔案所指定的 wheel 中的檔案逐位元組比較。

- 用 pip、pipx 或 uv 安裝時，InvenTag 的檔案中不包含 libiconv。你的安裝工具會從 Python 包索引下載 lxml 自己的 wheel。
- 宣告檔案是 `THIRD-PARTY-LICENSES.txt`：在壓縮包中是 `inventag/THIRD-PARTY-LICENSES.txt`，
  在 `.deb` 和 `.rpm` 中是 `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` 和
  `/opt/inventag/THIRD-PARTY-LICENSES.txt`。發佈頁還為每種系統單獨列出它。它包含 LGPL 2.1 的全文。
- 這個庫的原始碼位於宣告檔案所寫明的地址。在這個發佈版本中：libiconv 1.18 位於
  <https://www.gnu.org/software/libiconv/> 和
  <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>，lxml 6.1.3 位於
  <https://github.com/lxml/lxml>。發佈工作流在簽名檔案之前會請求這兩個 libiconv 地址，其中任何一個沒有回應就會停止。
- InvenTag 不提供寄送原始碼的書面承諾。如果某個地址打不開，
  請到 <https://github.com/habhabhabs/inventag-aws/issues> 提交一個 issue。
- lxml 的模組是安裝目錄中的獨立檔案。你可以用你自己建置的同版本 lxml 替換它們。
  資料夾在壓縮包中是 `inventag/_internal/lxml/`，在 `.deb` 和 `.rpm` 中是 `/opt/inventag/_internal/lxml/`。
  在 macOS 上，替換模組之後要重新簽名：`codesign -s - --force <file>`。

未針對你自己建置的 lxml 驗證：你建置的模組能代替內建的模組正常工作。

未針對 GNU 的伺服器驗證：這兩個 libiconv 地址會一直有回應。工作流在它的測試執行當天取到了這兩個地址。

本節不構成法律意見。

## 為你自己的安裝生成 SBOM {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

未針對你安裝的 cyclonedx-bom 版本驗證：`cyclonedx-py environment` 的選項。

請在你安裝 InvenTag 的虛擬環境中執行，這樣檔案列出的就恰好是你所執行的內容。

## 留意漏洞 {#keep-an-eye-on-vulnerabilities}

有一個定時工作流會掃描依賴項中的已知漏洞。執行了什麼、什麼會讓建置失敗，
請閱讀[依賴項如何檢查](./index.md#how-dependencies-are-checked)；
如果你認為有東西被入侵了，請閱讀[供應鏈事件之後](./index.md#after-a-supply-chain-incident)。
