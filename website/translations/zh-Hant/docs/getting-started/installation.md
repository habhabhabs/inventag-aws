---
title: 安裝 InvenTag
description: 選擇安裝 InvenTag 的方式（pipx、獨立壓縮包、.deb 或 .rpm 軟體包、Homebrew 或 pip），連線你的 AWS 憑證，並確認一切正常。
sidebar_position: 2
---

# 安裝 InvenTag

**適合誰閱讀：** 在膝上型電腦、伺服器或 CI 執行器上安裝 InvenTag 的人。

**讀完後你可以：** 選擇安裝方式，安裝、升級和解除安裝 InvenTag，並確認 InvenTag 能連上你的 AWS 帳戶。

## 你需要準備 {#what-you-need}

- **Python 3.11 或更高版本**，用於 pipx、pip 和原始碼這三種方式。Python 3.10 自 2026 年 10 月起不再獲得安全修復。
  請參閱 [Python 版本狀態](https://devguide.python.org/versions/)。
  用 `python3 --version` 檢視你的版本。獨立壓縮包、`.deb` 和 `.rpm` 自帶 Python，你的機器上不需要安裝 Python。
- 唯讀身份的 **AWS 憑證**。
  [AWS 命令列介面（AWS CLI）](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  是可選的，但它是最簡單的設定方式。

## 選擇安裝方式 {#choose-how-to-install}

| 方式 | 適用情況 | 你的機器上需要 | 系統 |
|---|---|---|---|
| [pipx](#install-with-pipx-recommended)（首選） | 你有 Python 3.11 或更高版本。你想用一條命令安裝、一條命令升級。 | Python 3.11 或更高版本和 pipx | 任何有 Python 的系統 |
| [獨立壓縮包](#install-the-standalone-archive)（`.tar.gz`） | 機器上沒有 Python，或者你想要一份不依賴包管理器的副本。 | 無 | Linux x86_64 和 arm64（glibc 2.34 或更高版本）。macOS arm64（Apple 晶片）。 |
| [`.deb` 軟體包](#install-the-deb-package) | Debian、Ubuntu 以及使用 `dpkg` 的系統。 | 無 | Linux x86_64 和 arm64（glibc 2.34 或更高版本） |
| [`.rpm` 軟體包](#install-the-rpm-package) | Fedora、RHEL 系列和 Amazon Linux。 | 無 | Linux x86_64 和 arm64（glibc 2.34 或更高版本） |
| [Homebrew](#install-with-homebrew) | 裝有 Homebrew 的 macOS 或 Linux。 | Homebrew | macOS arm64（Apple silicon）。Linux x86_64 和 arm64。不支援 Intel 版 Mac。 |
| [虛擬環境中的 pip](#install-with-pip-in-a-virtual-environment) | 你想把 InvenTag 裝進專案環境。 | Python 3.11 或更高版本 | 任何有 Python 的系統 |
| [從原始碼安裝](#install-from-source) | 你想用最新的未發佈程式碼，或者要修改 InvenTag。 | Python 3.11 或更高版本和 Git | 任何有 Python 的系統 |

### 每種打包建置支援的系統 {#systems-that-each-packaged-build-supports}

- Linux 的可執行檔案、`.deb` 和 `.rpm` 需要 glibc 2.34 或更高版本。
  下表中的 Linux 系統都滿足這個要求。
  在更舊的系統上，例如 RHEL、AlmaLinux 和 Rocky Linux 8、Debian 11、Ubuntu 20.04 或
  Amazon Linux 2，如果系統有 Python 3.11 或更高版本，請使用 pipx。
- 不支援 Intel 版 Mac，也沒有為它們製作建置的計劃。InvenTag 所需的一個庫（cryptography，從第 50 版起）沒有為它們發佈現成的建置。
- macOS 可執行檔案只適用於 Apple 晶片（arm64）。建置記錄顯示，它的檔案需要 macOS 11.0 或更高版本。
- 可執行檔案不支援 Alpine 和其他使用 musl 的系統。請使用 pipx。
- Windows 沒有打包建置。

未針對 Intel 版 Mac 驗證：`pipx install inventag-aws`，它必須編譯那個庫，並且需要 Rust 工具鏈。

未針對 glibc 低於 2.34 的系統驗證：可執行檔案、`.deb` 和 `.rpm`。

未針對 Alpine 或其他 musl 系統驗證：可執行檔案；請使用 pipx。

未針對 Windows 驗證：任何安裝方式。

未針對 macOS 11.0 的 Mac 驗證：可執行檔案。這個版本號來自建置記錄，不是在該版本上執行得到的。

### 測試了什麼 {#what-was-tested}

發佈工作流先建置每種格式，再把它安裝到一個全新的系統上。每種任務做的事如下：

- **Linux x86_64：** 安裝軟體包或解壓壓縮包，執行 `inventag --version` 和 `inventag selftest`，
  讀取手冊頁檔案，載入補全檔案，掃描一個模擬的 AWS，解除安裝軟體包，並檢查軟體包的檔案是否一個不剩。
- **Linux arm64：** 在 Debian 12 上安裝 `.deb`，在 Rocky Linux 9 上安裝 `.rpm`，
  執行 `inventag --version` 和 `inventag selftest`，解除安裝軟體包，並檢查 `inventag` 已不在 PATH 中。
  它不檢查手冊頁、補全檔案和掃描，也不檢查軟體包的檔案是否一個不剩。
- **macOS arm64：** 把壓縮包解壓到一個臨時資料夾，執行 `inventag --version` 和 `inventag selftest`，
  讀取手冊頁檔案，用 `bash -n` 和 `zsh -n` 檢查 bash 和 zsh 補全檔案的語法
  （不載入任何檔案，也不檢查 fish 檔案），掃描一個模擬的 AWS，並刪除這個臨時資料夾。
- **Ubuntu 24.04 上的 pipx：** 安裝由標籤建置的 wheel，執行 `inventag --version` 和 `inventag selftest`，
  解除安裝它，並檢查 `inventag` 已不在 PATH 中。

下面這些系統透過了測試：

| 系統 | 格式 | CPU |
|---|---|---|
| Ubuntu 22.04 | `.deb` | x86_64 |
| Ubuntu 24.04 | `.deb` | x86_64 |
| Debian 12 | `.deb` 和獨立壓縮包 | x86_64 |
| Debian 12 | `.deb`（安裝、版本、selftest、解除安裝） | arm64 |
| Fedora（測試當天的最新版本） | `.rpm` | x86_64 |
| Rocky Linux 9 | `.rpm` 和獨立壓縮包 | x86_64 |
| Rocky Linux 9 | `.rpm`（安裝、版本、selftest、解除安裝） | arm64 |
| AlmaLinux 9（建置系統，glibc 2.34） | `.rpm` | x86_64 |
| Amazon Linux 2023 | `.rpm` | x86_64 |
| GitHub Runner上的 macOS 15 | 獨立壓縮包 | arm64 |
| Ubuntu 24.04 | pipx，使用由標籤建置的 wheel（安裝、版本、selftest、解除安裝） | x86_64 |

未針對真實的 AWS 驗證：從打包建置發起的掃描；這個測試掃描的是模擬的 AWS。

未針對全新的 Linux arm64 系統驗證：獨立壓縮包。建置過程在它上面執行了 `inventag selftest`，沒有其他測試解壓過它。

未針對 GitHub 驗證：發佈頁是否帶有本頁所說的檔案。到目前為止的測試執行不會向發佈頁附加任何檔案，帶有這些檔案的第一次正式發佈執行還沒有進行。

## 用 pipx 安裝（推薦） {#install-with-pipx-recommended}

[pipx](https://pipx.pypa.io/) 把 InvenTag 安裝到它自己的隱藏環境中，並把 `inventag` 命令放到你的 PATH 上。
你不需要啟用任何東西。Python 包索引上的包名是
[`inventag-aws`](https://pypi.org/project/inventag-aws/)。請先安裝 pipx，
使用你的系統建議的方式。請參閱 pipx 文件。

```bash title="Terminal"
pipx install inventag-aws
inventag --version
inventag selftest
```

`inventag selftest` 在離線狀態下檢查這份 InvenTag 是否能正常工作。它不呼叫 AWS，不開啟網路連線，
也不需要憑證。結束代碼 0 表示所有檢查都透過。結束代碼 1 表示有檢查失敗。

如果你使用 [uv](https://docs.astral.sh/uv/)，命令是 `uv tool install inventag-aws`。

- **升級：** `pipx upgrade inventag-aws`。要安裝某個指定版本，請固定版本：
  `pipx install inventag-aws==%INVENTAG_VERSION%`。
- **解除安裝：** `pipx uninstall inventag-aws`。這會刪除程式，但不會刪除 `bom_output/` 中的報告和快照。
- **補全：** `inventag completion bash`、`inventag completion zsh` 和
  `inventag completion fish` 會輸出補全指令碼。見[命令列補全](#shell-completion)。
- **手冊頁：** 這種方式不安裝手冊頁。請使用 `inventag --help`。

未針對 pipx 驗證：升級命令和固定版本命令。

未針對 uv 驗證：`uv tool install inventag-aws` 能得到可用的 `inventag` 和 `inventag selftest`，以及升級和解除安裝命令。

## 安裝獨立壓縮包 {#install-the-standalone-archive}

壓縮包裡只有一個目錄 `inventag`。目錄中有程式、它自帶的 Python 和它的庫。每個發佈版本為每種系統提供一個壓縮包：

- `inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz`
- `inventag-%INVENTAG_VERSION%-linux-arm64.tar.gz`
- `inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz`（macOS，Apple 晶片）

執行 `uname -m` 檢視你的 CPU。Linux 會輸出 `x86_64` 或 `aarch64`。`aarch64` 使用 arm64 壓縮包。
從[發佈頁](https://github.com/habhabhabs/inventag-aws/releases)下載壓縮包和 `SHA256SUMS`，
或者使用 GitHub CLI：

```bash title="Terminal"
gh release download v%INVENTAG_VERSION% --repo habhabhabs/inventag-aws \
  --pattern 'inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz' --pattern SHA256SUMS
```

解壓之前，先[檢查下載的檔案](#check-the-download)。然後，在 Linux 上：

```bash title="Terminal"
sudo tar -xzf inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz -C /opt
sudo ln -s /opt/inventag/inventag /usr/local/bin/inventag
inventag --version
inventag selftest
```

在 macOS 上，把壓縮包解壓到你選的資料夾，並用路徑執行程式。測試就是這樣做的，它沒有在 PATH 上建立連結。

```bash title="Terminal"
mkdir -p "$HOME/inventag-install"
tar -xzf inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz -C "$HOME/inventag-install"
"$HOME/inventag-install/inventag/inventag" --version
```

macOS 可執行檔案沒有經過 Apple 公證。macOS 可能會攔截瀏覽器下載的檔案。

未針對 GitHub Runner 之外的 macOS 驗證：Gatekeeper 對瀏覽器下載的壓縮包的行為。

- **升級：** 刪除舊目錄，再把新壓縮包解壓到同一位置。
- **解除安裝（Linux）：** `sudo rm -rf /opt/inventag` 和 `sudo rm /usr/local/bin/inventag`。
  在 macOS 上，刪除你解壓出來的資料夾。
- **補全：** 目錄的 `share/completions/` 中有指令碼：`inventag.bash`、`_inventag`（zsh）和 `inventag.fish`。
  見[命令列補全](#shell-completion)。
- **手冊頁：** 目錄中的手冊頁是 `share/man/man1/inventag.1`。
  用 `man /opt/inventag/share/man/man1/inventag.1` 閱讀。

未針對每個系統的 man 工具驗證：`man` 能顯示這個頁面。測試讀取了頁面檔案，並檢查了它的標題行和名稱行。

未針對同一位置已有舊版 InvenTag 的系統驗證：升級步驟。

## 安裝 .deb 軟體包 {#install-the-deb-package}

在 Debian、Ubuntu 以及使用 `dpkg` 的系統上使用 `.deb`。x86_64 的檔名是
`inventag_%INVENTAG_VERSION%_amd64.deb`，arm64 的檔名是
`inventag_%INVENTAG_VERSION%_arm64.deb`。下載檔案並[檢查它](#check-the-download)。然後執行：

```bash title="Terminal"
sudo dpkg -i inventag_%INVENTAG_VERSION%_amd64.deb
inventag --version
inventag selftest
```

軟體包把程式放在 `/opt/inventag/`，並在 `/usr/bin/inventag` 建立一個連結。它還會安裝手冊頁、補全檔案，
並把授權檔案放在 `/usr/share/doc/inventag/`。軟體包沒有安裝指令碼。

- **升級：** 用 `sudo dpkg -i` 安裝更新的 `.deb`。
- **解除安裝：** `sudo dpkg -r inventag`。在 x86_64 上，測試檢查過軟體包的檔案一個不剩。在 arm64 上，測試只檢查了 `inventag` 已不在 PATH 中。
- **補全：** 軟體包會安裝 bash、zsh 和 fish 的檔案。見[命令列補全](#shell-completion)。
- **手冊頁：** `man inventag`。檔案是 `/usr/share/man/man1/inventag.1.gz`。

未針對已有舊版 InvenTag 軟體包的系統驗證：升級。

未針對每個系統的 man 工具驗證：`man inventag` 能顯示這個頁面。測試讀取了頁面檔案，並檢查了它的標題行和名稱行。

## 安裝 .rpm 軟體包 {#install-the-rpm-package}

在 Fedora、RHEL 系列和 Amazon Linux 上使用 `.rpm`。x86_64 的檔名是
`inventag-%INVENTAG_VERSION%-1.x86_64.rpm`，arm64 的檔名是
`inventag-%INVENTAG_VERSION%-1.aarch64.rpm`。下載檔案並[檢查它](#check-the-download)。然後執行：

```bash title="Terminal"
sudo dnf install ./inventag-%INVENTAG_VERSION%-1.x86_64.rpm
inventag --version
inventag selftest
```

軟體包把程式放在 `/opt/inventag/`，並在 `/usr/bin/inventag` 建立一個連結。它還會安裝手冊頁、補全檔案，
並把授權檔案放在 `/usr/share/doc/inventag/`。

- **升級：** 用 `sudo dnf install` 安裝更新的 `.rpm`。
- **解除安裝：** `sudo dnf remove inventag`。在 x86_64 上，測試檢查過軟體包的檔案一個不剩。在 arm64 上，測試只檢查了 `inventag` 已不在 PATH 中。
- **補全：** 軟體包會安裝 bash、zsh 和 fish 的檔案。見[命令列補全](#shell-completion)。
- **手冊頁：** `man inventag`。檔案是 `/usr/share/man/man1/inventag.1.gz`。

未針對已有舊版 InvenTag 軟體包的系統驗證：升級。

未針對每個系統的 man 工具驗證：`man inventag` 能顯示這個頁面。測試讀取了頁面檔案，並檢查了它的標題行和名稱行。

## 用 Homebrew 安裝 {#install-with-homebrew}

Homebrew 可以在 Apple silicon 版 Mac 和 Linux（x86_64 和 arm64）上安裝 InvenTag。
在 Intel 版 Mac 上，它會停下並給出一條提示；請改用 `pipx`，在那裡它需要 Rust 工具鏈。

```bash title="Terminal"
brew install habhabhabs/inventag/inventag
inventag --version
inventag selftest
```

這個 tap 是儲存庫 `habhabhabs/homebrew-inventag`。它的 formula 從發佈壓縮包安裝可執行檔案、手冊頁，
以及 bash、zsh 和 fish 的補全檔案。formula 由 `scripts/packaging/render_formula.py`
根據 `packaging/homebrew-tap/Formula/inventag.rb` 和該版本的 `SHA256SUMS` 寫成。
每次發佈之後，發佈工作流會把新的 formula 寫入這個 tap。

在 Mac 上，Homebrew 需要最新的 Command Line Tools。如果 Homebrew 因為它們過舊而拒絕安裝，
請在「軟體更新」中更新它們，或者執行 `sudo rm -rf /Library/Developer/CommandLineTools`，
然後執行 `sudo xcode-select --install`。

- **升級：** `brew upgrade inventag`。
- **解除安裝：** `brew uninstall inventag`。

已在一臺裝有 macOS 27 的 Apple silicon Mac 上針對 v1.4.0 檢查：
`brew install habhabhabs/inventag/inventag` 成功，`inventag --version` 輸出 1.4.0，
`inventag selftest` 透過了全部 8 項檢查。

未針對那一臺以外的 Mac 驗證：Homebrew 安裝和 Gatekeeper 的行為。

未針對 GitHub Runner 之外的 Linux 驗證：Homebrew 安裝。

未針對 Homebrew 驗證：`brew upgrade inventag`。目前還沒有進行過升級。
`brew uninstall inventag` 只在 GitHub Runner 上執行過。

未針對 Intel 版 Mac 驗證：那裡的安裝所顯示的提示。

未針對 GitHub 驗證：發佈工作流會更新這個 tap。v1.4.0 之後的第一次發佈是這一步的第一次執行。

## 在虛擬環境中用 pip 安裝 {#install-with-pip-in-a-virtual-environment}

InvenTag 並不要求使用虛擬環境。虛擬環境能讓它的依賴（boto3、openpyxl 等）與你其他的 Python 工具互不干擾。
許多較新的系統（Debian、Ubuntu、Homebrew 的 Python）會拒絕向系統 Python 執行 `pip install`，
並報出「externally-managed-environment」錯誤。在這些系統上可行的兩種辦法是虛擬環境，
或者 [pipx](#install-with-pipx-recommended)。

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

未針對 Debian、Ubuntu 或 Homebrew 驗證：externally-managed-environment 錯誤以及繞過它的兩種辦法。

這樣你就有了本文件所使用的 `inventag` 命令。報告範本已包含在包中。

- **升級：** `pip install --upgrade inventag-aws`。要安裝某個指定版本，請固定版本：
  `pip install inventag-aws==%INVENTAG_VERSION%`。
- **解除安裝：** `pip uninstall inventag-aws`。
- **補全和手冊頁：** 與 [pipx](#install-with-pipx-recommended) 相同。

未針對 pip 驗證：升級、固定版本和解除安裝命令。

## 從原始碼安裝 {#install-from-source}

如果你想用最新的未發佈程式碼，或打算修改 InvenTag，請用這種方式。

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` 會安裝 `requirements.txt` 中的依賴，以及一個執行你的原始碼副本的
`inventag` 命令，因此程式碼改動無需重新安裝即可生效。你也可以在
`pip install -r requirements.txt` 之後直接執行 `python inventag_cli.py --help`。

儲存庫根目錄還有兩個啟動指令碼：`inventag.sh` 和 `inventag.bat`。請改用 `inventag` 命令。這兩個指令碼不屬於已安裝的包，也沒有測試執行過它們。

若要從原始碼使用固定的發佈版本，而不是最新程式碼，請檢出它的標籤，例如
`git checkout v%INVENTAG_VERSION%`。
[發佈頁面](https://github.com/habhabhabs/inventag-aws/releases)列出了所有版本。

## 命令列補全 {#shell-completion}

`inventag completion bash`、`inventag completion zsh` 和 `inventag completion fish` 會輸出補全指令碼。
這個命令唯讀取它自己的選項，不呼叫 AWS，也不開啟網路連線。未知的 shell 名稱會以結束代碼 2 結束。

```bash title="Terminal"
source <(inventag completion bash)                                    # bash, this session
inventag completion zsh > "${fpath[1]}/_inventag"                     # zsh
inventag completion fish > ~/.config/fish/completions/inventag.fish  # fish
```

`.deb` 和 `.rpm` 會為你安裝這三個指令碼：

| Shell | `.deb` | `.rpm` |
|---|---|---|
| bash | `/usr/share/bash-completion/completions/inventag` | `/usr/share/bash-completion/completions/inventag` |
| zsh | `/usr/share/zsh/vendor-completions/_inventag` | `/usr/share/zsh/site-functions/_inventag` |
| fish | `/usr/share/fish/vendor_completions.d/inventag.fish` | `/usr/share/fish/vendor_completions.d/inventag.fish` |

未針對每種 shell 設定驗證：新開的 shell 會自動載入這些檔案。測試在 bash、zsh 和 fish 中手動載入了每個檔案。
在 Rocky Linux 9、AlmaLinux 9 和 Amazon Linux 2023 上，測試沒有載入 fish 檔案。

## 檢查下載的檔案 {#check-the-download}

每個發佈版本都在 `SHA256SUMS` 中列出它的所有檔案。校驗和能說明檔案是完整的，但不能說明是誰製作的。
建置證明可以說明這一點。

在 Linux 上，把檔案和 `SHA256SUMS` 放在同一個資料夾中，然後執行：

```bash title="Terminal"
sha256sum --check --ignore-missing SHA256SUMS
```

在 macOS 上，輸出你的檔案的校驗和，並用肉眼與 `SHA256SUMS` 中的那一行比對：

```bash title="Terminal"
shasum -a 256 inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz
grep darwin-arm64.tar.gz SHA256SUMS
```

發佈工作流在簽名檔案時不使用我們自己的金鑰。它把 `SHA256SUMS` 交給 GitHub 的 `actions/attest` 步驟，
該步驟以這個工作流的名義寫入建置證明。要檢查一個檔案，請使用 GitHub CLI：

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

`--repo` 指明儲存庫。如果證明是由另一個工作流檔案生成的，`--signer-workflow` 會讓檢查失敗。

未針對 GitHub 驗證：對發佈檔案使用這些選項執行 `gh attestation verify`。這些選項讀自 `gh attestation verify --help`。測試執行不會生成任何建置證明。第一份真實的建置證明由第一次正式發佈執行生成，這次執行還沒有進行。

每個 `.tar.gz`、`.deb` 和 `.rpm` 還有一份 SBOM，檔名是在原檔名後加 `.cdx.json`。
見[軟體物料清單](../security/sbom.md)。

## 打包建置中的授權 {#licenses-in-packaged-builds}

InvenTag 使用 MIT 授權。可執行檔案壓縮包、`.deb` 和 `.rpm` 包含 GNU libiconv，
這是一個使用 GNU 寬通用公共授權（LGPL）2.1 版的庫。Homebrew formula 安裝同一個壓縮包，所以它也包含 libiconv。
libiconv 的程式碼位於 lxml 的擴充套件模組內部。InvenTag 需要 lxml 來寫 Word 檔案。lxml 專案建置這些模組，並把 libiconv 連結進去。
在壓縮包、`.deb` 和 `.rpm` 中，InvenTag 原樣攜帶 lxml 的檔案，不做任何修改。

- 用 pip、pipx 或 uv 安裝時，InvenTag 的檔案中不包含 libiconv。你的安裝工具會從 Python 包索引下載 lxml 自己的 wheel。
- 宣告檔案是 `THIRD-PARTY-LICENSES.txt`。它列出每個攜帶的元件、它的授權和授權文字，幷包含 LGPL 2.1 的全文。
  每個發佈版本為每種系統提供一個宣告檔案，檔名是
  `inventag-%INVENTAG_VERSION%-<os>-<cpu>.THIRD-PARTY-LICENSES.txt`。
  同一個檔案也在軟體包裡面：
  - 壓縮包：`inventag/THIRD-PARTY-LICENSES.txt`
  - `.deb` 和 `.rpm`：`/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` 和
    `/opt/inventag/THIRD-PARTY-LICENSES.txt`
- 宣告檔案寫明瞭 libiconv 的版本和原始碼的位置。在這個發佈版本中，它寫明的是 lxml 6.1.3 內部的 libiconv 1.18：
  - libiconv：<https://www.gnu.org/software/libiconv/> 和
    <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>
  - lxml：<https://github.com/lxml/lxml>
- InvenTag 不提供寄送原始碼的書面承諾。上面的地址就是原始碼所在。如果某個地址打不開，
  請到 <https://github.com/habhabhabs/inventag-aws/issues> 提交一個 issue。
- lxml 的模組是安裝目錄中的獨立檔案。你可以用你自己建置的同版本 lxml 替換它們。
  資料夾在壓縮包中是 `inventag/_internal/lxml/`，在 `.deb` 和 `.rpm` 中是 `/opt/inventag/_internal/lxml/`。
  在 macOS 上，替換模組之後要重新簽名：`codesign -s - --force <file>`。

未針對你自己建置的 lxml 驗證：你建置的模組能代替內建的模組正常工作。

未針對 Homebrew 安裝驗證：Homebrew 不會改動 lxml 的檔案。

未針對已檢查的那一臺 Apple silicon Mac 以外的 Mac 驗證：Homebrew 安裝和 Gatekeeper 的行為。

本頁不構成法律意見。

## 連線你的 AWS 憑證 {#connect-your-aws-credentials}

InvenTag 使用標準的 AWS 憑證鏈，因此以下任一方式都可以：

使用 IAM Identity Center（推薦）：

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

使用長期存取金鑰（儘量避免）：

```bash title="Terminal"
aws configure
```

未針對 AWS CLI 驗證：本節中的登入命令。

請優先使用短期憑證，例如 IAM Identity Center 或擔任的角色，
而不是存放在磁碟上的存取金鑰。

## 檢查是否可用 {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

結束代碼為 0 表示 InvenTag 能夠登入。加上 `--verbose` 還能看到各個步驟。
下面是針對模擬 AWS 離線執行得到的範例輸出（範例資料）：

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
0
```

如果憑證缺失，或安全權杖無效或已過期，InvenTag 會說明原因並給出修復建議。
參見[解決常見問題](../guides/troubleshooting.md#credentials)。

## 授予 InvenTag 唯讀權限 {#give-inventag-read-only-permissions}

在第一次真正掃描之前，請給該身份設定唯讀策略：
[設定唯讀存取](../guides/read-only-access.md)。

## 從 v1.1.x 升級 {#upgrade-from-v11x}

執行 `pip install --upgrade inventag-aws` 之後你會注意到：

- **機密值會被遮蓋。** 常用於存放機密的欄位（例如 Lambda 環境變數）的值，在報告、快照和日誌中會變成
  `***REDACTED***`。升級後的第一次執行會把這些資源報告為已更改一次。早期版本寫出的報告和快照可能仍包含這些值：
  請刪除它們或限制其存取。
- **新欄。** 每個服務工作表都有 `source`、`sources` 和 `detail_level` 欄。參見[輸出檔案](../reference/outputs.md)。
- **更多服務和更多 API 呼叫。** InvenTag 多列出 22 個服務，因此會增加工作表、行和呼叫。
  儲存庫中的策略新增了 17 個讀取操作（並且不再列出 `cloudtrail:LookupEvents`；從 v1.4.3 起還包含 `ce:ListCostAllocationTags`，只供 `--finops-cost-allocation` 使用）；沒有這些權限時，每個被拒絕的列出呼叫都會給出一條警告，這些資源仍會像以前一樣透過 Tagging API 找到（如果它們帶有標籤）。升級後的第一份變更報告會把新列出服務的資源顯示為新增，儘管它們之前就存在。
  參見 [IAM 權限](../reference/iam-permissions.md)。
- **更嚴格的檔案檢查。** 空的設定檔案、寫了兩次的鍵，或型別錯誤的 `--bom-config` 值，都會以結束代碼 1 停止執行。
- **相互衝突的選項會以結束代碼 2 停止**，例如同時使用 `--accounts-file` 和 `--accounts-prompt`，
  或給了 `--s3-kms-key-id` 但沒有 `--s3-encryption aws:kms`。
- **時間限制按帳戶計算**，從該帳戶開始掃描時算起。超時的帳戶保留已找到的資源，並算作失敗。
- **預設結束代碼不變。** 結束代碼 5 和 6 是新增的，只在使用 `--fail-on-account-error` 和 `--fail-if-empty` 時出現。無法寫出的報告格式會以結束代碼 1 結束。
- **服務名稱和工作表名稱保持不變。** v1.1.4 只透過 Tagging API 找到的資源保留其服務名稱和工作表（例如
  `ELASTICFILESYSTEM`、`STATES`、`COGNITO-IDP`、`ELASTICMAPREDUCE`、`KAFKA`、`ES`）。它們的行現在帶有服務 API 的詳細資訊，
  Secrets Manager 金鑰和 MSK 叢集的 ID 欄顯示名稱，而不是 ARN 的最後一部分。

完整列表見[更新日誌](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)。

## 為開發而安裝 {#install-for-development}

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

[貢獻指南](../development/CONTRIBUTING.md)介紹了完整的測試套件。

## 解決安裝問題 {#fix-install-problems}

| 你看到的現象 | 怎麼辦 |
|---|---|
| `Error: No suitable Python interpreter found.` 或 `InvenTag requires Python 3.11 or later` | 安裝 Python 3.11 或更高版本，並確認 `python3 --version` 可用。 |
| `inventag: command not found` | 啟用你執行 `pip install inventag-aws` 的那個虛擬環境，或執行 `python -m pip show inventag-aws` 檢查是否已安裝。如果你使用獨立壓縮包，請把 `/opt/inventag/inventag` 連結到 PATH 中的某個資料夾，或者用完整路徑執行程式。 |
| `ModuleNotFoundError` | 啟用虛擬環境，再次執行 `pip install -r requirements.txt`。 |
| `inventag selftest` 失敗 | 重新安裝 InvenTag，或重新下載發佈檔案，然後再次執行 `inventag selftest`。如果再次失敗，請到 <https://github.com/habhabhabs/inventag-aws/issues> 提交 issue，並附上輸出。 |
| `No AWS credentials found!` | 執行 `aws sso login` 或 `aws configure`，或設定 `AWS_PROFILE`。 |

未針對 AWS CLI 驗證：「怎麼辦」欄中的命令。

## 下一步 {#next-step}

[快速開始](./quick-start.md)
