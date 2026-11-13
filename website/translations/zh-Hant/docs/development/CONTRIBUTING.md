---
title: 參與貢獻 InvenTag
description: 搭建 InvenTag 的開發環境，執行測試和程式碼檢查工具，構建文件站點，並提交拉取請求。
sidebar_position: 1
---

# 參與貢獻 InvenTag

**適合誰閱讀：** 你想修復一個缺陷、新增一項功能或改進文件。

**讀完後你可以：** 搭建好程式碼環境，執行專案使用的檢查，並提交一個便於審查的拉取請求。

## 開始之前 {#before-you-start}

1. 先查詢已有的 [issue](https://github.com/habhabhabs/inventag-aws/issues)。
   如果沒有，就新建一個並描述這項更改。
2. 對於較大的更改，請在編寫大量程式碼之前，等待維護者的回覆。

## 搭建環境 {#set-up}

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # includes moto
pip install -e .          # optional: gives you the `inventag` command
git checkout -b fix/short-description
```

分支字首：`feat/`、`fix/`、`docs/`、`refactor/`、`test/`。

## 執行檢查 {#run-the-checks}

```bash
black --check scripts/ inventag/
flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

CI 會執行相同的 `black --check` 和 `flake8` 命令，然後在 Python 3.11、3.12、3.13、3.14 和 3.15 上執行測試。
完整的測試套件（`python -m pytest -q`）需要幾分鐘，在 `main` 上全部透過（9 個效能基準測試被取消選中），
並且不需要 AWS 賬戶：測試使用 moto 或模擬客戶端，並使用假憑證。你的更改必須保持它全部透過。
只有在需要時才執行基準測試：`python -m pytest -m performance`。
更改依賴項時請執行 `pip-audit -r requirements.txt`；出現新的安全公告時，CI 會失敗。

**千萬不要不小心對真實的 AWS 賬戶執行測試。** 請取消設定 `AWS_PROFILE` 和真實金鑰，或者使用 moto。

## 處理模板 {#work-on-templates}

- 內建模板位於 `inventag/templating/builtin/`。每個模板都需要在
  `tests/integration/templating/` 中有一個渲染它的測試。
- 模板格式只在 `inventag/templating/schema.py` 中描述一次。修改它之後，請重新生成文件參考：
  `python -m inventag.templating.reference --write`。如果你忘了，會有一個單元測試失敗。
- 文件頁面上的示例輸出來自 `scripts/docs/generate_example_outputs.py`，
  它會針對 moto 執行真實的 CLI。行為發生變化後，請執行 `pip install pillow` 和
  `python scripts/docs/generate_example_outputs.py`，並提交結果。
  `--check` 會告訴你頁面是否已經過時。生成圖片需要 LibreOffice（`soffice`）和 `pdftoppm`。

## 處理文件 {#work-on-the-docs}

文件是 `docs/` 中的 Markdown 檔案，透過 Docusaurus 從 `website/` 釋出。

```bash
cd website
npm ci
npm run build          # fails on broken links and missing SEO metadata
npm run check:links    # checks links in the built site
npm run start          # local preview at http://localhost:3000/inventag-aws/
```

寫作規則：

- 每個頁面的 front matter 中都有唯一的 `title` 和 `description`，並且恰好有一個 `#` 標題。
- 開頭先說明頁面適合誰閱讀，以及讀者讀完後能做什麼。
- 句子簡短，使用主動語態，用詞平實。解釋所有行話。
- 每條命令、每個標誌和每份輸出都必須與程式碼一致。寫下之前先執行一遍，並把示例輸出標註為示例資料。
- 不要編造數字，不用最高階，不聲稱合規或認證。
- 標題按順序排列，表格帶有表頭行，圖片帶有替代文字，不要僅靠表情符號或顏色來傳達含義。

側邊欄由各資料夾以及每個資料夾的 `_category_.json` 生成。

## 提交併建立拉取請求 {#commit-and-open-a-pull-request}

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
feat(templates): add landscape option for Word reports
fix(discovery): include EC2 instances in comprehensive discovery
docs: explain tag policy scopes
```

在拉取請求中，說明改了什麼、如何測試的，以及更新了哪些文件。
修復或新增功能時，請更新[功能狀態](../getting-started/status.md)。

## 下一步 {#next-steps}

- [程式碼如何組合在一起](./architecture.md)
- [安全](../security/index.md)
