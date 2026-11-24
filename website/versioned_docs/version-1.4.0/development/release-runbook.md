---
title: Release runbook
description: How a push to main becomes an InvenTag release, the rules the release workflow follows, each with the test that proves it, and how to finish a release whose tag push failed.
sidebar_position: 3
---

# Release runbook

**Who this is for:** the maintainer who pushes to `main` and finishes a release
when the workflow stops half-way.

**What you will know after reading:** when a push releases a version, which
bump it gets, what the release job writes, and the manual steps when the tag
push fails.

The release workflow is `.github/workflows/release.yml` ("Automated Release").
Its settings (token, PyPI trusted publishing, branch protection) are in
`.github/REPOSITORY_CONFIGURATION.md`.

## Rules

Each rule names the test that proves it. The tests run the workflow's own
shell code, or the scripts it calls, against local git repositories.

Not verified against a GitHub Actions runner: the rules below; the tests run the same shell code on a local machine.

| Rule | What happens | Proved by |
| --- | --- | --- |
| R1 | A push to `main` releases a new version only when the application changed since the newest release tag `vX.Y.Z` in the history of the pushed commit. | `tests/unit/test_release_needed.py::test_docs_only_change_is_not_a_release`, `tests/unit/test_release_needed.py::test_step_docs_only_push_is_no_release_and_says_why` |
| R2 | The application is `inventag/`, `pyproject.toml`, `setup.py`, `setup.cfg`, `MANIFEST.in`, `requirements.txt` and `LICENSE`. `templates/`, the launcher `inventag_cli.py`, `.github/`, docs, site, tests and examples are not. | `tests/unit/test_release_needed.py::test_build_and_dependency_files_are_application`, `tests/unit/test_release_needed.py::test_site_markdown_examples_config_and_templates_are_not_application`, `tests/unit/test_release_needed.py::test_the_root_launcher_and_the_templates_folder_are_not_application`, `tests/unit/test_release_needed.py::test_github_actions_only_change_is_not_a_release` |
| R3 | One release covers every commit since that tag: an earlier code commit still counts when the last commit changes only docs. | `tests/unit/test_release_needed.py::test_an_earlier_unreleased_code_commit_still_counts` |
| R4 | `[skip release]` or `[skip ci]` in the message of the pushed commit means no release, even with a code change. | `tests/unit/test_release_needed.py::test_step_skip_release_wins_over_a_code_change` |
| R5 | Only the message of the pushed (last) commit is read. `Release-As` and `[skip release]` lines in earlier commits of the same push are ignored. | `tests/unit/test_release_needed.py::test_step_reads_only_the_head_commit_for_release_as_and_skip` |
| R6 | A release is a patch by default. A line `Release-As: minor` or `Release-As: major` in the pushed commit's message sets the bump. | `tests/unit/test_release_needed.py::test_step_code_push_is_a_patch_release`, `tests/unit/test_release_needed.py::test_step_release_as_line_with_code_sets_the_bump` |
| R7 | A merge commit `Merge pull request #N` takes the bump from the pull request label `release:patch`, `release:minor` or `release:major`, and is a patch without one. | `tests/unit/test_release_needed.py::test_step_pr_label_with_code_sets_the_bump` |
| R8 | `Release-As` or a release label without an application change releases nothing; the log says the line or label is ignored. | `tests/unit/test_release_needed.py::test_step_release_as_line_without_code_is_no_release`, `tests/unit/test_release_needed.py::test_step_pr_label_without_code_is_no_release` |
| R9 | The release job's own `chore: bump version to vX.Y.Z` commit, and a commit that is already in a release tag, never release. | `tests/unit/test_release_needed.py::test_step_bump_commit_is_no_release`, `tests/unit/test_release_needed.py::test_step_commit_inside_a_release_tag_is_no_release` |
| R10 | A manual run with `patch`, `minor` or `major` releases even without an application change. A manual run with `publish_existing_tag` only uploads that tag to PyPI. | `tests/unit/test_release_needed.py::test_step_manual_run_with_a_bump_forces_a_release`, `tests/unit/test_release_needed.py::test_step_publish_only_run_is_no_release` |
| R11 | Runs that can never release (a pushed commit with `[skip release]` or `[skip ci]`, a publish-only run) get a concurrency group of their own. Every other run shares the group `release-main`. | `tests/unit/test_release_runbook.py::test_runs_that_cannot_release_have_their_own_concurrency_group` |
| R12 | The new version is the bump applied to the higher of the latest GitHub release and `inventag/_version.py`. | `tests/unit/test_release_runbook.py::test_next_version_bumps_the_higher_of_release_and_file` |
| R13 | The bump commit holds `version.json`, `inventag/_version.py` and `CHANGELOG.md`: the notes under `## [Unreleased]` move under `## [vX.Y.Z] - date`, and an empty `[Unreleased]` stays as it is. | `tests/unit/test_roll_changelog.py::test_filled_section_is_rolled_with_a_new_empty_unreleased`, `tests/unit/test_roll_changelog.py::test_empty_unreleased_changes_nothing`, `tests/unit/test_roll_changelog.py::test_release_workflow_rolls_the_changelog_into_the_bump_commit` |
| R14 | The tag goes on the commit that the bump step pushed. The push is tried up to 5 times, with waits of 5, 10, 15 and 20 seconds, and the tag is read back with `git ls-remote`. When it fails, the log names the manual recovery below. | `tests/unit/test_release_tag.py::test_the_given_commit_wins_over_head`, `tests/unit/test_release_tag.py::test_a_passing_rejection_is_retried_and_the_tag_lands`, `tests/unit/test_release_tag.py::test_a_lasting_rejection_fails_with_the_recovery_named`, `tests/unit/test_release_tag.py::test_tag_step_calls_the_script_with_the_bump_sha` |
| R15 | A tag of the same name on another commit stops the tag step and changes nothing. | `tests/unit/test_release_tag.py::test_a_tag_on_another_commit_is_refused_and_left_alone` |
| R16 | PyPI gets a version only when tag `vX.Y.Z` names the checked-out commit and its GitHub release exists. Without them, a push run publishes nothing and a manual run fails. | `tests/unit/test_release_runbook.py::test_publish_guard_passes_with_the_tag_and_the_release`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_push_without_the_tag_publishes_nothing`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_manual_run_without_the_release_fails` |
| R17 | On the push of the bump commit, the job "Changelog rolled" fails when `[Unreleased]` is not empty. It does not touch the tag, the release or PyPI. | `tests/unit/test_roll_changelog.py::test_check_fails_on_notes_left_under_unreleased`, `tests/unit/test_roll_changelog.py::test_release_workflow_runs_the_check_on_the_bump_commit_push_only` |
| R18 | After each release, the docs versioning job commits the translated label of the current docs version (`current.json`), so it names the released version. | `tests/unit/test_release_runbook.py::test_docs_versioning_commits_the_current_json_labels`, `tests/unit/test_release_runbook.py::test_committed_current_labels_name_a_released_version` |

## Before you push

- Write the changelog entries under `## [Unreleased]` in `CHANGELOG.md`. The
  release moves them (R13).
- A change with no application code: put `[skip release]` in every commit
  subject, and above all in the last one (R4, R5).
- A minor or major release: put the `Release-As` line in the last commit of the
  push, or the label on the pull request (R5, R6, R7). Push it only after the
  running release has finished. Not verified against GitHub Actions: a run queued behind a running release can be replaced by a newer queued run, and then the newer run's bump is used.

## Known limits

- Not verified against a GitHub Actions runner: a commit that the bump step pulls in with `git pull --rebase` is in the tag and the PyPI package but not in the release notes, which list the commits up to the checkout.
  Changelog entries of such a commit stay under `[Unreleased]`, and the job
  "Changelog rolled" then fails (R17).
- Not verified against GitHub: the cause of the v1.2.2 tag failure. In run 44499441432 the tag push was refused with `missing necessary objects` one step after the bump commit was pushed. git gives that answer when the server shows a branch at the commit but cannot read the commit; the test `tests/unit/test_release_tag.py::test_missing_necessary_objects_is_the_answer_git_gives` makes it locally.

## The tag push failed

The step "Create Git Tag" of the job "Create Release" ends with a line
`Tag vX.Y.Z was not pushed to commit <sha>`. The bump commit is on `main`, but
there is no tag, no GitHub release and nothing on PyPI. This is how v1.2.2 was
finished on 19 Nov 2026.

1. Do not re-run the job. It would bump again from the version in
   `inventag/_version.py` and give the next number (R12).
2. Check that the tag is missing and that the commit is the bump commit on
   `main`:

   ```bash
   git fetch origin
   git ls-remote origin refs/tags/vX.Y.Z          # no output
   git log -1 --format=%s <sha>                    # chore: bump version to vX.Y.Z
   git merge-base --is-ancestor <sha> origin/main && echo "on main"
   ```

3. On the GitHub releases page, draft a new release. Tag: `vX.Y.Z` (new tag on
   publish). Target: the commit `<sha>`. Title:
   `🏷️ InvenTag Release vX.Y.Z`. Notes: copy them from the log of the step
   "Generate release notes" of the failed run. Mark it as the latest release
   and publish it.
4. Run **Automated Release** by hand with `publish_existing_tag` set to
   `vX.Y.Z`. The publish job checks the tag and the release (R16), then uploads
   to PyPI.
5. Optional: the failed run did not attach the source archives. From a clone at
   the tag:

   ```bash
   git archive --format=tar.gz --prefix=inventag-aws-X.Y.Z/ vX.Y.Z > inventag-aws-X.Y.Z.tar.gz
   gh release upload vX.Y.Z inventag-aws-X.Y.Z.tar.gz
   ```

Not verified against GitHub: the steps of the releases page and of a manual run; they are the steps used for v1.2.2.

## After every release

- `CHANGELOG.md` on `main`: `[Unreleased]` is empty and the new version has its
  heading (the job "Changelog rolled" is green, R17).
- The docs deployment of the bump commit and the docs versioning run are green.
- The live status page describes the released version.
- The reviewers' notes are read once more against the release notes.
