---
title: 发布操作手册
description: 推送到 main 如何变成 InvenTag 的一次发布，发布工作流遵循的规则（每条都附有证明它的测试），以及标签推送失败时如何完成发布。
sidebar_position: 3
---

# 发布操作手册

**适合谁阅读：** 向 `main` 推送、并在工作流中途停止时完成发布的维护者。

**读完后你会知道：** 一次推送何时发布版本、得到哪种版本递增、发布任务写入什么，以及标签推送失败时的手动步骤。

发布工作流是 `.github/workflows/release.yml`（“Automated Release”）。它的设置（令牌、PyPI 可信发布、分支保护）见 `.github/REPOSITORY_CONFIGURATION.md`。

## 规则 {#rules}

每条规则都写明证明它的测试。这些测试在本地 git 仓库上运行工作流自己的 shell 代码，或它调用的脚本。

未针对 GitHub Actions 运行器验证：下面的规则；测试在本地机器上运行同样的 shell 代码。

| 规则 | 会发生什么 | 证明 |
| --- | --- | --- |
| R1 | 只有当应用自被推送提交历史中最新的发布标签 `vX.Y.Z` 以来发生了变化，推送到 `main` 才会发布新版本。 | `tests/unit/test_release_needed.py::test_docs_only_change_is_not_a_release`, `tests/unit/test_release_needed.py::test_step_docs_only_push_is_no_release_and_says_why` |
| R2 | 应用是 `inventag/`、`pyproject.toml`、`setup.py`、`setup.cfg`、`MANIFEST.in`、`requirements.txt` 和 `LICENSE`。`templates/`、启动脚本 `inventag_cli.py`、`.github/`、文档、站点、测试和示例都不是。 | `tests/unit/test_release_needed.py::test_build_and_dependency_files_are_application`, `tests/unit/test_release_needed.py::test_site_markdown_examples_config_and_templates_are_not_application`, `tests/unit/test_release_needed.py::test_the_root_launcher_and_the_templates_folder_are_not_application`, `tests/unit/test_release_needed.py::test_github_actions_only_change_is_not_a_release` |
| R3 | 一次发布涵盖自该标签以来的所有提交：即使最后一个提交只改了文档，之前的代码提交仍然算数。 | `tests/unit/test_release_needed.py::test_an_earlier_unreleased_code_commit_still_counts` |
| R4 | 被推送提交的消息中有 `[skip release]` 或 `[skip ci]`：不发布，即使有代码变更。 | `tests/unit/test_release_needed.py::test_step_skip_release_wins_over_a_code_change` |
| R5 | 只读取被推送的（最后一个）提交的消息。同一次推送中较早提交里的 `Release-As` 和 `[skip release]` 行会被忽略。 | `tests/unit/test_release_needed.py::test_step_reads_only_the_head_commit_for_release_as_and_skip` |
| R6 | 发布默认是补丁版本。被推送提交消息中的 `Release-As: minor` 或 `Release-As: major` 行决定递增级别。 | `tests/unit/test_release_needed.py::test_step_code_push_is_a_patch_release`, `tests/unit/test_release_needed.py::test_step_release_as_line_with_code_sets_the_bump` |
| R7 | 合并提交 `Merge pull request #N` 从拉取请求的标签 `release:patch`、`release:minor` 或 `release:major` 取递增级别，没有标签时为补丁版本。 | `tests/unit/test_release_needed.py::test_step_pr_label_with_code_sets_the_bump` |
| R8 | 没有应用变更时，`Release-As` 或发布标签不会发布任何内容；日志会说明该行或该标签被忽略。 | `tests/unit/test_release_needed.py::test_step_release_as_line_without_code_is_no_release`, `tests/unit/test_release_needed.py::test_step_pr_label_without_code_is_no_release` |
| R9 | 发布任务自己的 `chore: bump version to vX.Y.Z` 提交，以及已经包含在某个发布标签中的提交，永远不会发布。 | `tests/unit/test_release_needed.py::test_step_bump_commit_is_no_release`, `tests/unit/test_release_needed.py::test_step_commit_inside_a_release_tag_is_no_release` |
| R10 | 手动运行并选择 `patch`、`minor` 或 `major` 时，即使没有应用变更也会发布。手动运行并填写 `publish_existing_tag` 时，只把该标签上传到 PyPI。 | `tests/unit/test_release_needed.py::test_step_manual_run_with_a_bump_forces_a_release`, `tests/unit/test_release_needed.py::test_step_publish_only_run_is_no_release` |
| R11 | 永远不会发布的运行（被推送提交带有 `[skip release]` 或 `[skip ci]`，或只发布的运行）有自己的并发组。其他所有运行共用 `release-main` 组。 | `tests/unit/test_release_runbook.py::test_runs_that_cannot_release_have_their_own_concurrency_group` |
| R12 | 新版本是在最新的 GitHub 发布和 `inventag/_version.py` 两者中较高的那个上应用递增。 | `tests/unit/test_release_runbook.py::test_next_version_bumps_the_higher_of_release_and_file` |
| R13 | 版本递增提交包含 `version.json`、`inventag/_version.py` 和 `CHANGELOG.md`：`## [Unreleased]` 下的说明移到 `## [vX.Y.Z] - 日期` 下，空的 `[Unreleased]` 保持不变。 | `tests/unit/test_roll_changelog.py::test_filled_section_is_rolled_with_a_new_empty_unreleased`, `tests/unit/test_roll_changelog.py::test_empty_unreleased_changes_nothing`, `tests/unit/test_roll_changelog.py::test_release_workflow_rolls_the_changelog_into_the_bump_commit` |
| R14 | 标签打在版本递增步骤推送的那个提交上。推送最多尝试 5 次，中间分别等待 5、10、15 和 20 秒，并用 `git ls-remote` 读回标签。失败时，日志会写明下面的手动恢复步骤。 | `tests/unit/test_release_tag.py::test_the_given_commit_wins_over_head`, `tests/unit/test_release_tag.py::test_a_passing_rejection_is_retried_and_the_tag_lands`, `tests/unit/test_release_tag.py::test_a_lasting_rejection_fails_with_the_recovery_named`, `tests/unit/test_release_tag.py::test_tag_step_calls_the_script_with_the_bump_sha` |
| R15 | 如果同名标签已在另一个提交上，打标签步骤会停止，且不做任何更改。 | `tests/unit/test_release_tag.py::test_a_tag_on_another_commit_is_refused_and_left_alone` |
| R16 | 只有当标签 `vX.Y.Z` 指向检出的提交且对应的 GitHub 发布存在时，PyPI 才会收到该版本。缺少它们时，推送触发的运行不发布任何内容，手动运行则失败。 | `tests/unit/test_release_runbook.py::test_publish_guard_passes_with_the_tag_and_the_release`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_push_without_the_tag_publishes_nothing`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_manual_run_without_the_release_fails` |
| R17 | 推送版本递增提交时，如果 `[Unreleased]` 不为空，任务“Changelog rolled”会失败。它不会改动标签、发布或 PyPI。 | `tests/unit/test_roll_changelog.py::test_check_fails_on_notes_left_under_unreleased`, `tests/unit/test_roll_changelog.py::test_release_workflow_runs_the_check_on_the_bump_commit_push_only` |
| R18 | 每次发布后，文档版本任务会提交当前文档版本的翻译标签（`current.json`），因此它写的是已发布的版本。 | `tests/unit/test_release_runbook.py::test_docs_versioning_commits_the_current_json_labels`, `tests/unit/test_release_runbook.py::test_committed_current_labels_name_a_released_version` |
| R19 | 在一次附加了文件的发布运行之后，Package 工作流的最后一个任务 `publish-tap` 会把 Homebrew formula 写入仓库变量 `HOMEBREW_TAP_REPO` 指定的 tap。只有在文件附加和 formula 安装（`smoke-homebrew`）都通过时它才运行。在试运行、拉取请求中，`HOMEBREW_TAP_REPO` 为空时，以及关闭 macOS 时，它会被跳过。没有任务等待它，所以它失败时，发布、PyPI 和已附加的文件保持不变。 | `tests/unit/test_packaging_workflow.py::test_publish_tap_is_skipped_in_a_dry_run_a_pull_request_and_without_a_tap`, `tests/unit/test_packaging_workflow.py::test_no_job_waits_for_publish_tap_so_a_failure_turns_only_it_red` |
| R20 | formula 根据 GitHub 发布上的 `SHA256SUMS` 文件生成，并且只在该文件与本次运行的文件相同时生成。 | `tests/unit/test_packaging_workflow.py::test_the_published_sums_must_equal_the_sums_of_the_run` |
| R21 | tap 在 `main` 上得到一个提交 `inventag X.Y.Z`，作者是 `Alex <alex.ng@ollion.com>`，没有 trailer。再次写入同一个文件时不推送任何内容，并以绿色结束，所以重新运行是安全的。比 tap 中更低的版本会被拒绝。 | `tests/unit/test_publish_tap.py::test_the_commit_is_alex_with_the_subject_only_and_no_trailer`, `tests/unit/test_publish_tap.py::test_the_same_file_again_ends_with_success_and_pushes_nothing`, `tests/unit/test_publish_tap.py::test_a_version_lower_than_the_taps_is_refused` |
| R22 | 如果因为 tap 的 `main` 已前进而推送被拒绝，会在新的 `main` 上再做一次，并再次检查版本。第二次被拒绝时任务失败。 | `tests/unit/test_publish_tap.py::test_a_push_refused_because_main_moved_is_tried_once_more_on_the_new_main`, `tests/unit/test_publish_tap.py::test_a_second_refused_push_fails_the_run` |
| R23 | 密钥 `HOMEBREW_TAP_TOKEN` 只在唯一的推送步骤的 env 中。git 只通过 `GIT_ASKPASS` 的回答得到它，从不出现在 URL 或参数中。 | `tests/unit/test_packaging_workflow.py::test_the_token_is_in_the_env_of_the_push_step_only_and_never_traced`, `tests/unit/test_publish_tap.py::test_the_token_never_reaches_a_git_argument_the_output_or_the_tap` |
| R24 | `publish-tap` 失败时，它的最后一步会输出手动发布 formula 的命令，其中已填好版本号。 | `tests/unit/test_publish_tap.py::test_the_hand_procedure_is_printed_with_the_version_filled_in` |
| R25 | 在每次不是 pull request 的运行中，Package 工作流的 `tap-status` 任务会在日志和任务摘要中列出 `publish-tap` 的每个条件、它的值以及是否成立，最后给出 “publish-tap will run” 或 “publish-tap is skipped because: ...”，并指出第一个不成立的条件。它不读取任何机密，所以令牌显示为 “not checked”。 | `tests/unit/test_packaging_workflow.py::test_tap_status_names_the_first_false_condition`, `tests/unit/test_packaging_workflow.py::test_tap_status_reads_no_secret_checks_nothing_out_and_reads_values_from_env` |

## 推送之前 {#before-you-push}

- 把变更日志条目写在 `CHANGELOG.md` 的 `## [Unreleased]` 下。发布会移动它们（R13）。
- 不含应用代码的变更：在每个提交的标题中写上 `[skip release]`，尤其是最后一个（R4、R5）。
- 次版本或主版本发布：把 `Release-As` 行写在这次推送的最后一个提交中，或在拉取请求上加标签（R5、R6、R7）。请在正在运行的发布结束后再推送。未针对 GitHub Actions 验证：排在正在运行的发布之后的运行可能被更新的排队运行替换，这时使用的是更新那次运行的递增级别。

## 已知限制 {#known-limits}

- 未针对 GitHub Actions 运行器验证：版本递增步骤用 `git pull --rebase` 拉入的提交包含在标签和 PyPI 包中，但不在发布说明中，发布说明只列出检出时为止的提交。
  这类提交的变更日志条目会留在 `[Unreleased]` 下，此时任务“Changelog rolled”会失败（R17）。
- 未针对 GitHub 验证：v1.2.2 标签失败的原因。在运行 44499441432 中，标签推送在版本递增提交推送后的下一步被拒绝，提示 `missing necessary objects`。当服务器显示某个分支指向该提交、却读不到该提交时，git 会给出这个回答；测试 `tests/unit/test_release_tag.py::test_missing_necessary_objects_is_the_answer_git_gives` 在本地重现了它。

## 标签推送失败了 {#the-tag-push-failed}

任务“Create Release”的步骤“Create Git Tag”以一行 `Tag vX.Y.Z was not pushed to commit <sha>` 结束。版本递增提交已在 `main` 上，但没有标签、没有 GitHub 发布，PyPI 上也什么都没有。v1.2.2 就是在 2026 年 11 月 19 日这样完成的。

1. 不要重新运行该任务。它会从 `inventag/_version.py` 中的版本再次递增，得到下一个编号（R12）。
2. 确认标签确实缺失，并且该提交是 `main` 上的版本递增提交：

   ```bash
   git fetch origin
   git ls-remote origin refs/tags/vX.Y.Z          # no output
   git log -1 --format=%s <sha>                    # chore: bump version to vX.Y.Z
   git merge-base --is-ancestor <sha> origin/main && echo "on main"
   ```

3. 在 GitHub 发布页面起草新发布。标签：`vX.Y.Z`（发布时创建新标签）。目标：提交 `<sha>`。标题：`🏷️ InvenTag Release vX.Y.Z`。说明：从失败运行中步骤“Generate release notes”的日志里复制。把它标记为最新发布并发布。
4. 手动运行 **Automated Release**，把 `publish_existing_tag` 设为 `vX.Y.Z`。发布任务会检查标签和发布（R16），然后上传到 PyPI。
5. 可选：失败的运行没有附上源码归档。在检出到该标签的克隆中：

   ```bash
   git archive --format=tar.gz --prefix=inventag-aws-X.Y.Z/ vX.Y.Z > inventag-aws-X.Y.Z.tar.gz
   gh release upload vX.Y.Z inventag-aws-X.Y.Z.tar.gz
   ```

未针对 GitHub 验证：发布页面和手动运行的步骤；它们是完成 v1.2.2 时使用的步骤。

## Homebrew tap {#the-homebrew-tap}

这个 tap 是 `habhabhabs/homebrew-inventag`。Package 工作流在每次发布之后更新它（R19 到 R25）。
Homebrew 可以在 Apple silicon 版 Mac 和 Linux（x86_64 和 arm64）上安装 InvenTag。不支持 Intel 版 Mac。

1. 打开任务 `publish-tap` 的日志。最后一行指出 tap 中的提交。
   “already published”表示 tap 中已经是同一个文件。
2. 在 tap 中查看这个提交的“Tap checks”。两个任务都必须是绿色。
3. 如果“Tap checks”为红色：在 tap 中撤销这个提交，然后在本仓库中修正 formula：

   ```bash
   git clone https://github.com/habhabhabs/homebrew-inventag.git tap && cd tap
   git revert --no-edit <sha>
   git push
   ```

4. `publish-tap` 失败：发布、PyPI 和已附加的文件都已完成。
   运行它最后一步输出的命令，或者重新运行这个任务（R21）。
5. `packaging/homebrew-tap/` 存放 tap 的 `README.md` 和 `.github/workflows/ci.yml`。
   那里的修改需要手动复制到 tap。
6. `publish-tap` 被跳过：打开同一次运行中 `tap-status` 的任务摘要。
   它会指出第一个不成立的条件（R25）。

未针对 GitHub 验证：任务 `publish-tap` 和 `tap-status`。v1.4.0 之后的第一次发布是它的第一次运行。v1.4.0 是手动放进 tap 的。

## 每次发布之后 {#after-every-release}

- `main` 上的 `CHANGELOG.md`：`[Unreleased]` 为空，新版本有自己的标题（任务“Changelog rolled”为绿色，R17）。
- 版本递增提交的文档部署和文档版本运行均为绿色。
- 线上状态页面描述的是已发布的版本。
- 撰写发布说明时，再读一遍审阅者的记录。
- Package 运行中的任务 `publish-tap` 为绿色，并且 tap 中该任务指出的提交的“Tap checks”为绿色（R19）。
