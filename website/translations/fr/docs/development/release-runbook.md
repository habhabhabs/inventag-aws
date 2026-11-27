---
title: Runbook des releases
description: Comment un push sur main devient une release d’InvenTag, les règles que suit le workflow de release, chacune avec le test qui la prouve, et comment terminer une release dont le push du tag a échoué.
sidebar_position: 3
---

# Runbook des releases

**Pour qui :** le mainteneur qui pousse sur `main` et termine une release
quand le workflow s’arrête à mi-chemin.

**Ce que vous saurez après la lecture :** quand un push publie une version,
quel incrément il reçoit, ce qu’écrit le job de release, et les étapes
manuelles quand le push du tag échoue.

Le workflow de release est `.github/workflows/release.yml` (« Automated Release »).
Ses réglages (jeton, publication de confiance PyPI, protection de branche) sont
dans `.github/REPOSITORY_CONFIGURATION.md`.

## Règles {#rules}

Chaque règle nomme le test qui la prouve. Les tests exécutent le code shell du
workflow, ou les scripts qu’il appelle, sur des dépôts git locaux.

Non vérifié sur un runner GitHub Actions : les règles ci-dessous ; les tests exécutent le même code shell sur une machine locale.

| Règle | Ce qui se passe | Prouvé par |
| --- | --- | --- |
| R1 | Un push sur `main` publie une nouvelle version seulement si l’application a changé depuis le tag de release `vX.Y.Z` le plus récent dans l’historique du commit poussé. | `tests/unit/test_release_needed.py::test_docs_only_change_is_not_a_release`, `tests/unit/test_release_needed.py::test_step_docs_only_push_is_no_release_and_says_why` |
| R2 | L’application, c’est `inventag/`, `pyproject.toml`, `setup.py`, `setup.cfg`, `MANIFEST.in`, `requirements.txt` et `LICENSE`. `templates/`, le lanceur `inventag_cli.py`, `.github/`, la documentation, le site, les tests et les exemples n’en font pas partie. | `tests/unit/test_release_needed.py::test_build_and_dependency_files_are_application`, `tests/unit/test_release_needed.py::test_site_markdown_examples_config_and_templates_are_not_application`, `tests/unit/test_release_needed.py::test_the_root_launcher_and_the_templates_folder_are_not_application`, `tests/unit/test_release_needed.py::test_github_actions_only_change_is_not_a_release` |
| R3 | Une release couvre tous les commits depuis ce tag : un commit de code antérieur compte encore quand le dernier commit ne change que la documentation. | `tests/unit/test_release_needed.py::test_an_earlier_unreleased_code_commit_still_counts` |
| R4 | `[skip release]` ou `[skip ci]` dans le message du commit poussé : pas de release, même avec un changement de code. | `tests/unit/test_release_needed.py::test_step_skip_release_wins_over_a_code_change` |
| R5 | Seul le message du commit poussé (le dernier) est lu. Les lignes `Release-As` et `[skip release]` des commits antérieurs du même push sont ignorées. | `tests/unit/test_release_needed.py::test_step_reads_only_the_head_commit_for_release_as_and_skip` |
| R6 | Une release est un patch par défaut. Une ligne `Release-As: minor` ou `Release-As: major` dans le message du commit poussé fixe l’incrément. | `tests/unit/test_release_needed.py::test_step_code_push_is_a_patch_release`, `tests/unit/test_release_needed.py::test_step_release_as_line_with_code_sets_the_bump` |
| R7 | Un commit de fusion `Merge pull request #N` prend l’incrément du label de la pull request `release:patch`, `release:minor` ou `release:major`, et un patch sans label. | `tests/unit/test_release_needed.py::test_step_pr_label_with_code_sets_the_bump` |
| R8 | `Release-As` ou un label de release sans changement de l’application ne publie rien ; le journal dit que la ligne ou le label est ignoré. | `tests/unit/test_release_needed.py::test_step_release_as_line_without_code_is_no_release`, `tests/unit/test_release_needed.py::test_step_pr_label_without_code_is_no_release` |
| R9 | Le commit `chore: bump version to vX.Y.Z` du job de release, et un commit déjà contenu dans un tag de release, ne publient jamais. | `tests/unit/test_release_needed.py::test_step_bump_commit_is_no_release`, `tests/unit/test_release_needed.py::test_step_commit_inside_a_release_tag_is_no_release` |
| R10 | Une exécution manuelle avec `patch`, `minor` ou `major` publie même sans changement de l’application. Une exécution manuelle avec `publish_existing_tag` envoie seulement ce tag sur PyPI. | `tests/unit/test_release_needed.py::test_step_manual_run_with_a_bump_forces_a_release`, `tests/unit/test_release_needed.py::test_step_publish_only_run_is_no_release` |
| R11 | Les exécutions qui ne peuvent jamais publier (un commit poussé avec `[skip release]` ou `[skip ci]`, une exécution de publication seule) ont leur propre groupe de concurrence. Toutes les autres partagent le groupe `release-main`. | `tests/unit/test_release_runbook.py::test_runs_that_cannot_release_have_their_own_concurrency_group` |
| R12 | La nouvelle version est l’incrément appliqué à la plus haute des deux : la dernière release GitHub et `inventag/_version.py`. | `tests/unit/test_release_runbook.py::test_next_version_bumps_the_higher_of_release_and_file` |
| R13 | Le commit d’incrément contient `version.json`, `inventag/_version.py` et `CHANGELOG.md` : les notes sous `## [Unreleased]` passent sous `## [vX.Y.Z] - date`, et un `[Unreleased]` vide reste tel quel. | `tests/unit/test_roll_changelog.py::test_filled_section_is_rolled_with_a_new_empty_unreleased`, `tests/unit/test_roll_changelog.py::test_empty_unreleased_changes_nothing`, `tests/unit/test_roll_changelog.py::test_release_workflow_rolls_the_changelog_into_the_bump_commit` |
| R14 | Le tag va sur le commit que l’étape d’incrément a poussé. Le push est tenté jusqu’à 5 fois, avec des attentes de 5, 10, 15 et 20 secondes, et le tag est relu avec `git ls-remote`. En cas d’échec, le journal nomme la reprise manuelle ci-dessous. | `tests/unit/test_release_tag.py::test_the_given_commit_wins_over_head`, `tests/unit/test_release_tag.py::test_a_passing_rejection_is_retried_and_the_tag_lands`, `tests/unit/test_release_tag.py::test_a_lasting_rejection_fails_with_the_recovery_named`, `tests/unit/test_release_tag.py::test_tag_step_calls_the_script_with_the_bump_sha` |
| R15 | Un tag du même nom sur un autre commit arrête l’étape du tag et ne change rien. | `tests/unit/test_release_tag.py::test_a_tag_on_another_commit_is_refused_and_left_alone` |
| R16 | PyPI reçoit une version seulement si le tag `vX.Y.Z` désigne le commit extrait et que sa release GitHub existe. Sans eux, une exécution de push ne publie rien et une exécution manuelle échoue. | `tests/unit/test_release_runbook.py::test_publish_guard_passes_with_the_tag_and_the_release`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_push_without_the_tag_publishes_nothing`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_manual_run_without_the_release_fails` |
| R17 | Au push du commit d’incrément, le job « Changelog rolled » échoue quand `[Unreleased]` n’est pas vide. Il ne touche ni au tag, ni à la release, ni à PyPI. | `tests/unit/test_roll_changelog.py::test_check_fails_on_notes_left_under_unreleased`, `tests/unit/test_roll_changelog.py::test_release_workflow_runs_the_check_on_the_bump_commit_push_only` |
| R18 | Après chaque release, le job de versionnement de la documentation commite le libellé traduit de la version courante de la documentation (`current.json`), qui nomme ainsi la version publiée. | `tests/unit/test_release_runbook.py::test_docs_versioning_commits_the_current_json_labels`, `tests/unit/test_release_runbook.py::test_committed_current_labels_name_a_released_version` |
| R19 | Après une exécution de release qui a joint ses fichiers, le dernier job du workflow Package, `publish-tap`, écrit la formule Homebrew dans le tap que nomme la variable du dépôt `HOMEBREW_TAP_REPO`. Il ne s’exécute que si l’envoi des fichiers et l’installation de la formule (`smoke-homebrew`) ont réussi. Il est ignoré lors d’un essai à blanc, sur une pull request, quand `HOMEBREW_TAP_REPO` est vide et quand macOS est désactivé. Aucun job ne l’attend : son échec laisse la release, PyPI et les fichiers joints tels quels. | `tests/unit/test_packaging_workflow.py::test_publish_tap_is_skipped_in_a_dry_run_a_pull_request_and_without_a_tap`, `tests/unit/test_packaging_workflow.py::test_no_job_waits_for_publish_tap_so_a_failure_turns_only_it_red` |
| R20 | La formule est générée à partir du fichier `SHA256SUMS` de la release GitHub, et seulement quand ce fichier est identique à celui de l’exécution. | `tests/unit/test_packaging_workflow.py::test_the_published_sums_must_equal_the_sums_of_the_run` |
| R21 | Le tap reçoit un commit `inventag X.Y.Z` sur `main`, par `Alex <alex.ng@ollion.com>`, sans trailer. Le même fichier une seconde fois ne pousse rien et finit en vert : relancer est donc sans risque. Une version inférieure à celle du tap est refusée. | `tests/unit/test_publish_tap.py::test_the_commit_is_alex_with_the_subject_only_and_no_trailer`, `tests/unit/test_publish_tap.py::test_the_same_file_again_ends_with_success_and_pushes_nothing`, `tests/unit/test_publish_tap.py::test_a_version_lower_than_the_taps_is_refused` |
| R22 | Un push refusé parce que `main` du tap a avancé est refait une fois sur le nouveau `main`, avec de nouveau la vérification de version. Un second refus fait échouer le job. | `tests/unit/test_publish_tap.py::test_a_push_refused_because_main_moved_is_tried_once_more_on_the_new_main`, `tests/unit/test_publish_tap.py::test_a_second_refused_push_fails_the_run` |
| R23 | Le secret `HOMEBREW_TAP_TOKEN` est dans l’env de la seule étape de push. git ne le reçoit que comme réponse de `GIT_ASKPASS`, jamais dans une URL ni dans un argument. | `tests/unit/test_packaging_workflow.py::test_the_token_is_in_the_env_of_the_push_step_only_and_never_traced`, `tests/unit/test_publish_tap.py::test_the_token_never_reaches_a_git_argument_the_output_or_the_tap` |
| R24 | Quand `publish-tap` échoue, sa dernière étape affiche les commandes pour publier la formule à la main, avec la version déjà remplie. | `tests/unit/test_publish_tap.py::test_the_hand_procedure_is_printed_with_the_version_filled_in` |
| R25 | Dans chaque exécution qui n’est pas une pull request, le job `tap-status` du workflow Package liste chaque condition de `publish-tap`, sa valeur et si elle est remplie, dans son journal et son résumé de job, et termine par « publish-tap will run » ou « publish-tap is skipped because: ... » avec la première condition non remplie. Il ne lit aucun secret : il affiche le jeton comme « not checked ». | `tests/unit/test_packaging_workflow.py::test_tap_status_names_the_first_false_condition`, `tests/unit/test_packaging_workflow.py::test_tap_status_reads_no_secret_checks_nothing_out_and_reads_values_from_env` |

## Avant de pousser {#before-you-push}

- Écrivez les entrées du changelog sous `## [Unreleased]` dans `CHANGELOG.md`.
  La release les déplace (R13).
- Un changement sans code de l’application : mettez `[skip release]` dans le
  sujet de chaque commit, et surtout dans le dernier (R4, R5).
- Une release mineure ou majeure : mettez la ligne `Release-As` dans le dernier
  commit du push, ou le label sur la pull request (R5, R6, R7). Poussez-la
  seulement après la fin de la release en cours. Non vérifié sur GitHub Actions : une exécution en attente derrière une release en cours peut être remplacée par une exécution plus récente, et c’est alors l’incrément de la plus récente qui est utilisé.

## Limites connues {#known-limits}

- Non vérifié sur un runner GitHub Actions : un commit que l’étape d’incrément récupère avec `git pull --rebase` est dans le tag et le package PyPI mais pas dans les notes de release, qui listent les commits jusqu’à l’extraction.
  Les entrées de changelog d’un tel commit restent sous `[Unreleased]`, et le
  job « Changelog rolled » échoue alors (R17).
- Non vérifié sur GitHub : la cause de l’échec du tag de v1.2.2. Dans l’exécution 44499441432, le push du tag a été refusé avec `missing necessary objects` une étape après le push du commit d’incrément. git donne cette réponse quand le serveur montre une branche sur le commit mais ne peut pas lire le commit ; le test `tests/unit/test_release_tag.py::test_missing_necessary_objects_is_the_answer_git_gives` la reproduit en local.

## Le push du tag a échoué {#the-tag-push-failed}

L’étape « Create Git Tag » du job « Create Release » se termine par une ligne
`Tag vX.Y.Z was not pushed to commit <sha>`. Le commit d’incrément est sur
`main`, mais il n’y a ni tag, ni release GitHub, ni rien sur PyPI. C’est ainsi
que v1.2.2 a été terminée le 19 novembre 2026.

1. Ne relancez pas le job. Il incrémenterait de nouveau à partir de la version
   de `inventag/_version.py` et donnerait le numéro suivant (R12).
2. Vérifiez que le tag manque et que le commit est le commit d’incrément sur
   `main` :

   ```bash
   git fetch origin
   git ls-remote origin refs/tags/vX.Y.Z          # no output
   git log -1 --format=%s <sha>                    # chore: bump version to vX.Y.Z
   git merge-base --is-ancestor <sha> origin/main && echo "on main"
   ```

3. Sur la page des releases GitHub, rédigez une nouvelle release. Tag :
   `vX.Y.Z` (nouveau tag à la publication). Cible : le commit `<sha>`. Titre :
   `🏷️ InvenTag Release vX.Y.Z`. Notes : copiez-les du journal de l’étape
   « Generate release notes » de l’exécution échouée. Marquez-la comme dernière
   release et publiez-la.
4. Lancez **Automated Release** à la main avec `publish_existing_tag` égal à
   `vX.Y.Z`. Le job de publication vérifie le tag et la release (R16), puis
   envoie sur PyPI.
5. Facultatif : l’exécution échouée n’a pas joint les archives des sources.
   Depuis un clone au tag :

   ```bash
   git archive --format=tar.gz --prefix=inventag-aws-X.Y.Z/ vX.Y.Z > inventag-aws-X.Y.Z.tar.gz
   gh release upload vX.Y.Z inventag-aws-X.Y.Z.tar.gz
   ```

Non vérifié sur GitHub : les étapes de la page des releases et d’une exécution manuelle ; ce sont les étapes utilisées pour v1.2.2.

## Le tap Homebrew {#the-homebrew-tap}

Le tap est `habhabhabs/homebrew-inventag`. Le workflow Package le met à jour
après chaque release (R19 à R25). Homebrew installe InvenTag sur les Mac Apple
silicon et sur Linux (x86_64 et arm64). Les Mac Intel ne sont pas pris en charge.

1. Ouvrez le journal du job `publish-tap`. Sa dernière ligne nomme le commit du
   tap. « already published » signifie que le tap avait déjà le même fichier.
2. Dans le tap, regardez « Tap checks » pour ce commit. Les deux jobs doivent
   être verts.
3. Un « Tap checks » rouge : annulez ce commit dans le tap, puis corrigez la
   formule dans ce dépôt :

   ```bash
   git clone https://github.com/habhabhabs/homebrew-inventag.git tap && cd tap
   git revert --no-edit <sha>
   git push
   ```

4. `publish-tap` a échoué : la release, PyPI et les fichiers joints sont faits.
   Exécutez les commandes que sa dernière étape a affichées, ou relancez le job (R21).
5. `packaging/homebrew-tap/` contient le `README.md` et
   `.github/workflows/ci.yml` du tap. Une modification là est copiée dans le tap à la main.
6. `publish-tap` a été ignoré : ouvrez le résumé du job `tap-status` dans la
   même exécution. Il nomme la première condition non remplie (R25).

Non vérifié sur GitHub : les jobs `publish-tap` et `tap-status`. La première release après v1.4.0
est sa première exécution. v1.4.0 a été mise dans le tap à la main.

## Après chaque release {#after-every-release}

- `CHANGELOG.md` sur `main` : `[Unreleased]` est vide et la nouvelle version a
  son titre (le job « Changelog rolled » est vert, R17).
- Le déploiement de la documentation du commit d’incrément et l’exécution du
  versionnement de la documentation sont verts.
- La page d’état en ligne décrit la version publiée.
- Les notes des relecteurs sont relues une fois de plus face aux notes de release.
- Le job `publish-tap` de l’exécution Package est vert, et « Tap checks » du tap est vert pour le commit que nomme le job (R19).
