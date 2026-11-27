---
title: 發佈操作手冊
description: 推送到 main 如何變成 InvenTag 的一次發佈，發佈工作流遵循的規則（每條都附有證明它的測試），以及標籤推送失敗時如何完成發佈。
sidebar_position: 3
---

# 發佈操作手冊

**適合誰閱讀：** 向 `main` 推送、並在工作流中途停止時完成發佈的維護者。

**讀完後你會知道：** 一次推送何時發佈版本、得到哪種版本遞增、發佈任務寫入什麼，以及標籤推送失敗時的手動步驟。

發佈工作流是 `.github/workflows/release.yml`（「Automated Release」）。它的設定（權杖、PyPI 可信發佈、分支保護）見 `.github/REPOSITORY_CONFIGURATION.md`。

## 規則 {#rules}

每條規則都寫明證明它的測試。這些測試在本地 git 儲存庫上執行工作流自己的 shell 程式碼，或它呼叫的指令碼。

未針對 GitHub Actions 執行器驗證：下面的規則；測試在本地機器上執行同樣的 shell 程式碼。

| 規則 | 會發生什麼 | 證明 |
| --- | --- | --- |
| R1 | 只有當應用自被推送提交歷史中最新的發佈標籤 `vX.Y.Z` 以來發生了變化，推送到 `main` 才會發佈新版本。 | `tests/unit/test_release_needed.py::test_docs_only_change_is_not_a_release`, `tests/unit/test_release_needed.py::test_step_docs_only_push_is_no_release_and_says_why` |
| R2 | 應用是 `inventag/`、`pyproject.toml`、`setup.py`、`setup.cfg`、`MANIFEST.in`、`requirements.txt` 和 `LICENSE`。`templates/`、啟動指令碼 `inventag_cli.py`、`.github/`、文件、網站、測試和範例都不是。 | `tests/unit/test_release_needed.py::test_build_and_dependency_files_are_application`, `tests/unit/test_release_needed.py::test_site_markdown_examples_config_and_templates_are_not_application`, `tests/unit/test_release_needed.py::test_the_root_launcher_and_the_templates_folder_are_not_application`, `tests/unit/test_release_needed.py::test_github_actions_only_change_is_not_a_release` |
| R3 | 一次發佈涵蓋自該標籤以來的所有提交：即使最後一個提交只改了文件，之前的程式碼提交仍然算數。 | `tests/unit/test_release_needed.py::test_an_earlier_unreleased_code_commit_still_counts` |
| R4 | 被推送提交的訊息中有 `[skip release]` 或 `[skip ci]`：不發佈，即使有程式碼變更。 | `tests/unit/test_release_needed.py::test_step_skip_release_wins_over_a_code_change` |
| R5 | 唯讀取被推送的（最後一個）提交的訊息。同一次推送中較早提交裡的 `Release-As` 和 `[skip release]` 行會被忽略。 | `tests/unit/test_release_needed.py::test_step_reads_only_the_head_commit_for_release_as_and_skip` |
| R6 | 發佈預設是補丁版本。被推送提交訊息中的 `Release-As: minor` 或 `Release-As: major` 行決定遞增級別。 | `tests/unit/test_release_needed.py::test_step_code_push_is_a_patch_release`, `tests/unit/test_release_needed.py::test_step_release_as_line_with_code_sets_the_bump` |
| R7 | 合併提交 `Merge pull request #N` 從提取要求的標籤 `release:patch`、`release:minor` 或 `release:major` 取遞增級別，沒有標籤時為補丁版本。 | `tests/unit/test_release_needed.py::test_step_pr_label_with_code_sets_the_bump` |
| R8 | 沒有應用變更時，`Release-As` 或發佈標籤不會發布任何內容；日誌會說明該行或該標籤被忽略。 | `tests/unit/test_release_needed.py::test_step_release_as_line_without_code_is_no_release`, `tests/unit/test_release_needed.py::test_step_pr_label_without_code_is_no_release` |
| R9 | 發佈任務自己的 `chore: bump version to vX.Y.Z` 提交，以及已經包含在某個發佈標籤中的提交，永遠不會發布。 | `tests/unit/test_release_needed.py::test_step_bump_commit_is_no_release`, `tests/unit/test_release_needed.py::test_step_commit_inside_a_release_tag_is_no_release` |
| R10 | 手動執行並選擇 `patch`、`minor` 或 `major` 時，即使沒有應用變更也會發布。手動執行並填寫 `publish_existing_tag` 時，只把該標籤上傳到 PyPI。 | `tests/unit/test_release_needed.py::test_step_manual_run_with_a_bump_forces_a_release`, `tests/unit/test_release_needed.py::test_step_publish_only_run_is_no_release` |
| R11 | 永遠不會發布的執行（被推送提交帶有 `[skip release]` 或 `[skip ci]`，或只發布的執行）有自己的併發組。其他所有執行共用 `release-main` 組。 | `tests/unit/test_release_runbook.py::test_runs_that_cannot_release_have_their_own_concurrency_group` |
| R12 | 新版本是在最新的 GitHub 發佈和 `inventag/_version.py` 兩者中較高的那個上應用遞增。 | `tests/unit/test_release_runbook.py::test_next_version_bumps_the_higher_of_release_and_file` |
| R13 | 版本遞增提交包含 `version.json`、`inventag/_version.py` 和 `CHANGELOG.md`：`## [Unreleased]` 下的說明移到 `## [vX.Y.Z] - 日期` 下，空的 `[Unreleased]` 保持不變。 | `tests/unit/test_roll_changelog.py::test_filled_section_is_rolled_with_a_new_empty_unreleased`, `tests/unit/test_roll_changelog.py::test_empty_unreleased_changes_nothing`, `tests/unit/test_roll_changelog.py::test_release_workflow_rolls_the_changelog_into_the_bump_commit` |
| R14 | 標籤打在版本遞增步驟推送的那個提交上。推送最多嘗試 5 次，中間分別等待 5、10、15 和 20 秒，並用 `git ls-remote` 讀回標籤。失敗時，日誌會寫明下面的手動恢復步驟。 | `tests/unit/test_release_tag.py::test_the_given_commit_wins_over_head`, `tests/unit/test_release_tag.py::test_a_passing_rejection_is_retried_and_the_tag_lands`, `tests/unit/test_release_tag.py::test_a_lasting_rejection_fails_with_the_recovery_named`, `tests/unit/test_release_tag.py::test_tag_step_calls_the_script_with_the_bump_sha` |
| R15 | 如果同名標籤已在另一個提交上，打標籤步驟會停止，且不做任何更改。 | `tests/unit/test_release_tag.py::test_a_tag_on_another_commit_is_refused_and_left_alone` |
| R16 | 只有當標籤 `vX.Y.Z` 指向檢出的提交且對應的 GitHub 發佈存在時，PyPI 才會收到該版本。缺少它們時，推送觸發的執行不發佈任何內容，手動執行則失敗。 | `tests/unit/test_release_runbook.py::test_publish_guard_passes_with_the_tag_and_the_release`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_push_without_the_tag_publishes_nothing`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_manual_run_without_the_release_fails` |
| R17 | 推送版本遞增提交時，如果 `[Unreleased]` 不為空，任務「Changelog rolled」會失敗。它不會改動標籤、發佈或 PyPI。 | `tests/unit/test_roll_changelog.py::test_check_fails_on_notes_left_under_unreleased`, `tests/unit/test_roll_changelog.py::test_release_workflow_runs_the_check_on_the_bump_commit_push_only` |
| R18 | 每次發佈後，文件版本任務會提交目前文件版本的翻譯標籤（`current.json`），因此它寫的是已發佈的版本。 | `tests/unit/test_release_runbook.py::test_docs_versioning_commits_the_current_json_labels`, `tests/unit/test_release_runbook.py::test_committed_current_labels_name_a_released_version` |
| R19 | 在一次附加了檔案的發佈執行之後，Package 工作流的最後一個任務 `publish-tap` 會把 Homebrew formula 寫入儲存庫變數 `HOMEBREW_TAP_REPO` 指定的 tap。只有在檔案附加和 formula 安裝（`smoke-homebrew`）都透過時它才執行。在試執行、提取要求中，`HOMEBREW_TAP_REPO` 為空時，以及關閉 macOS 時，它會被跳過。沒有任務等待它，所以它失敗時，發佈、PyPI 和已附加的檔案保持不變。 | `tests/unit/test_packaging_workflow.py::test_publish_tap_is_skipped_in_a_dry_run_a_pull_request_and_without_a_tap`, `tests/unit/test_packaging_workflow.py::test_no_job_waits_for_publish_tap_so_a_failure_turns_only_it_red` |
| R20 | formula 根據 GitHub 發佈上的 `SHA256SUMS` 檔案生成，並且只在該檔案與本次執行的檔案相同時生成。 | `tests/unit/test_packaging_workflow.py::test_the_published_sums_must_equal_the_sums_of_the_run` |
| R21 | tap 在 `main` 上得到一個提交 `inventag X.Y.Z`，作者是 `Alex <alex.ng@ollion.com>`，沒有 trailer。再次寫入同一個檔案時不推送任何內容，並以綠色結束，所以重新執行是安全的。比 tap 中更低的版本會被拒絕。 | `tests/unit/test_publish_tap.py::test_the_commit_is_alex_with_the_subject_only_and_no_trailer`, `tests/unit/test_publish_tap.py::test_the_same_file_again_ends_with_success_and_pushes_nothing`, `tests/unit/test_publish_tap.py::test_a_version_lower_than_the_taps_is_refused` |
| R22 | 如果因為 tap 的 `main` 已前進而推送被拒絕，會在新的 `main` 上再做一次，並再次檢查版本。第二次被拒絕時任務失敗。 | `tests/unit/test_publish_tap.py::test_a_push_refused_because_main_moved_is_tried_once_more_on_the_new_main`, `tests/unit/test_publish_tap.py::test_a_second_refused_push_fails_the_run` |
| R23 | 金鑰 `HOMEBREW_TAP_TOKEN` 只在唯一的推送步驟的 env 中。git 只透過 `GIT_ASKPASS` 的回答得到它，從不出現在 URL 或引數中。 | `tests/unit/test_packaging_workflow.py::test_the_token_is_in_the_env_of_the_push_step_only_and_never_traced`, `tests/unit/test_publish_tap.py::test_the_token_never_reaches_a_git_argument_the_output_or_the_tap` |
| R24 | `publish-tap` 失敗時，它的最後一步會輸出手動發佈 formula 的命令，其中已填好版本號。 | `tests/unit/test_publish_tap.py::test_the_hand_procedure_is_printed_with_the_version_filled_in` |
| R25 | 在每次不是 pull request 的執行中，Package 工作流的 `tap-status` 任務會在日誌和任務摘要中列出 `publish-tap` 的每個條件、它的值以及是否成立，最後給出 “publish-tap will run” 或 “publish-tap is skipped because: ...”，並指出第一個不成立的條件。它不讀取任何機密，所以權杖顯示為 “not checked”。 | `tests/unit/test_packaging_workflow.py::test_tap_status_names_the_first_false_condition`, `tests/unit/test_packaging_workflow.py::test_tap_status_reads_no_secret_checks_nothing_out_and_reads_values_from_env` |

## 推送之前 {#before-you-push}

- 把變更日誌條目寫在 `CHANGELOG.md` 的 `## [Unreleased]` 下。發佈會移動它們（R13）。
- 不含應用程式碼的變更：在每個提交的標題中寫上 `[skip release]`，尤其是最後一個（R4、R5）。
- 次版本或主版本發佈：把 `Release-As` 行寫在這次推送的最後一個提交中，或在提取要求上加標籤（R5、R6、R7）。請在正在執行的發佈結束後再推送。未針對 GitHub Actions 驗證：排在正在執行的發佈之後的執行可能被更新的排隊執行替換，這時使用的是更新那次執行的遞增級別。

## 已知限制 {#known-limits}

- 未針對 GitHub Actions 執行器驗證：版本遞增步驟用 `git pull --rebase` 拉入的提交包含在標籤和 PyPI 包中，但不在發行說明中，發行說明只列出檢出時為止的提交。
  這類提交的變更日誌條目會留在 `[Unreleased]` 下，此時任務「Changelog rolled」會失敗（R17）。
- 未針對 GitHub 驗證：v1.2.2 標籤失敗的原因。在執行 44499441432 中，標籤推送在版本遞增提交推送後的下一步被拒絕，提示 `missing necessary objects`。當伺服器顯示某個分支指向該提交、卻讀不到該提交時，git 會給出這個回答；測試 `tests/unit/test_release_tag.py::test_missing_necessary_objects_is_the_answer_git_gives` 在本地重現了它。

## 標籤推送失敗了 {#the-tag-push-failed}

任務「Create Release」的步驟「Create Git Tag」以一行 `Tag vX.Y.Z was not pushed to commit <sha>` 結束。版本遞增提交已在 `main` 上，但沒有標籤、沒有 GitHub 發佈，PyPI 上也什麼都沒有。v1.2.2 就是在 2026 年 11 月 19 日這樣完成的。

1. 不要重新執行該任務。它會從 `inventag/_version.py` 中的版本再次遞增，得到下一個編號（R12）。
2. 確認標籤確實缺失，並且該提交是 `main` 上的版本遞增提交：

   ```bash
   git fetch origin
   git ls-remote origin refs/tags/vX.Y.Z          # no output
   git log -1 --format=%s <sha>                    # chore: bump version to vX.Y.Z
   git merge-base --is-ancestor <sha> origin/main && echo "on main"
   ```

3. 在 GitHub 發佈頁面起草新發布。標籤：`vX.Y.Z`（發佈時建立新標籤）。目標：提交 `<sha>`。標題：`🏷️ InvenTag Release vX.Y.Z`。說明：從失敗執行中步驟「Generate release notes」的日誌裡複製。把它標記為最新發布併發布。
4. 手動執行 **Automated Release**，把 `publish_existing_tag` 設為 `vX.Y.Z`。發佈任務會檢查標籤和發佈（R16），然後上傳到 PyPI。
5. 可選：失敗的執行沒有附上原始碼歸檔。在檢出到該標籤的克隆中：

   ```bash
   git archive --format=tar.gz --prefix=inventag-aws-X.Y.Z/ vX.Y.Z > inventag-aws-X.Y.Z.tar.gz
   gh release upload vX.Y.Z inventag-aws-X.Y.Z.tar.gz
   ```

未針對 GitHub 驗證：發佈頁面和手動執行的步驟；它們是完成 v1.2.2 時使用的步驟。

## Homebrew tap {#the-homebrew-tap}

這個 tap 是 `habhabhabs/homebrew-inventag`。Package 工作流在每次發佈之後更新它（R19 到 R25）。
Homebrew 可以在 Apple silicon 版 Mac 和 Linux（x86_64 和 arm64）上安裝 InvenTag。不支援 Intel 版 Mac。

1. 開啟任務 `publish-tap` 的日誌。最後一行指出 tap 中的提交。
   「already published」表示 tap 中已經是同一個檔案。
2. 在 tap 中檢視這個提交的「Tap checks」。兩個任務都必須是綠色。
3. 如果「Tap checks」為紅色：在 tap 中撤銷這個提交，然後在本儲存庫中修正 formula：

   ```bash
   git clone https://github.com/habhabhabs/homebrew-inventag.git tap && cd tap
   git revert --no-edit <sha>
   git push
   ```

4. `publish-tap` 失敗：發佈、PyPI 和已附加的檔案都已完成。
   執行它最後一步輸出的命令，或者重新執行這個任務（R21）。
5. `packaging/homebrew-tap/` 存放 tap 的 `README.md` 和 `.github/workflows/ci.yml`。
   那裡的修改需要手動複製到 tap。
6. `publish-tap` 被跳過：開啟同一次執行中 `tap-status` 的任務摘要。
   它會指出第一個不成立的條件（R25）。

未針對 GitHub 驗證：任務 `publish-tap` 和 `tap-status`。v1.4.0 之後的第一次發佈是它的第一次執行。v1.4.0 是手動放進 tap 的。

## 每次發佈之後 {#after-every-release}

- `main` 上的 `CHANGELOG.md`：`[Unreleased]` 為空，新版本有自己的標題（任務「Changelog rolled」為綠色，R17）。
- 版本遞增提交的文件部署和文件版本執行均為綠色。
- 線上狀態頁面描述的是已發佈的版本。
- 撰寫發行說明時，再讀一遍審閱者的記錄。
- Package 執行中的任務 `publish-tap` 為綠色，並且 tap 中該任務指出的提交的「Tap checks」為綠色（R19）。
