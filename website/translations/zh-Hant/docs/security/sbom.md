---
title: 軟體物料清單
description: InvenTag 軟體物料清單（SBOM）列出了什麼、如何生成，以及如何檢查你所安裝的依賴項。
sidebar_position: 3
---

# 軟體物料清單

**適合誰閱讀：** 需要了解 InvenTag 由什麼構成的安全和採購審查人員。

**讀完後你會了解：** 有哪些 SBOM 檔案、它們如何生成，以及如何為你自己的安裝生成一份。

## 文件構建會生成什麼 {#what-the-documentation-build-generates}

每次部署文件網站時，構建都會為倉庫及其依賴項生成 SBOM 檔案，並隨網站一起釋出：

| 檔案 | 列出什麼 | 格式 |
|---|---|---|
| 倉庫 SBOM | Syft 在倉庫中發現的所有內容 | Syft JSON、CycloneDX JSON 和 SPDX JSON |
| Python，來自 `requirements.txt` | InvenTag 宣告的最低版本 | CycloneDX JSON 和 XML |
| Python，來自全新安裝 | 實際安裝的版本 | CycloneDX JSON 和 `pip freeze` 列表 |
| 文件網站 | 構建本網站所用的 Node.js 包 | CycloneDX JSON |

同一次構建還會向本節新增一個摘要頁面，**Software Bill of Materials (SBOM)**，
因此它出現線上上網站中，但不會出現在本地構建中。

Python 依賴項宣告的是最低版本，而不是精確固定，所以“已安裝版本”的檔案才能顯示，
在構建當天一次真實安裝會得到什麼。

## 為你自己的安裝生成 SBOM {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

請在你安裝 InvenTag 的虛擬環境中執行，這樣檔案列出的就恰好是你所執行的內容。

## 留意漏洞 {#keep-an-eye-on-vulnerabilities}

有一個定時工作流會掃描依賴項中的已知漏洞。執行了什麼、什麼會讓構建失敗，
請閱讀[依賴項如何檢查](./index.md#how-dependencies-are-checked)；
如果你認為有東西被入侵了，請閱讀[供應鏈事件之後](./index.md#after-a-supply-chain-incident)。
