---
title: Runbook de versiones
description: Cómo un push a main se convierte en una versión de InvenTag, las reglas que sigue el flujo de trabajo de versiones, cada una con la prueba que la demuestra, y cómo terminar una versión cuyo push de la etiqueta falló.
sidebar_position: 3
---

# Runbook de versiones

**Para quién es:** el mantenedor que hace push a `main` y termina una versión
cuando el flujo de trabajo se detiene a mitad de camino.

**Qué sabrá después de leer:** cuándo un push publica una versión, qué
incremento recibe, qué escribe el trabajo de versión y los pasos manuales
cuando falla el push de la etiqueta.

El flujo de trabajo de versiones es `.github/workflows/release.yml` («Automated Release»).
Su configuración (token, publicación de confianza en PyPI, protección de rama)
está en `.github/REPOSITORY_CONFIGURATION.md`.

## Reglas {#rules}

Cada regla nombra la prueba que la demuestra. Las pruebas ejecutan el código
shell del flujo de trabajo, o los scripts que llama, contra repositorios git
locales.

No verificado contra un runner de GitHub Actions: las reglas de abajo; las pruebas ejecutan el mismo código shell en una máquina local.

| Regla | Qué ocurre | Lo demuestra |
| --- | --- | --- |
| R1 | Un push a `main` publica una versión nueva solo cuando la aplicación cambió desde la etiqueta de versión `vX.Y.Z` más reciente en el historial del commit enviado. | `tests/unit/test_release_needed.py::test_docs_only_change_is_not_a_release`, `tests/unit/test_release_needed.py::test_step_docs_only_push_is_no_release_and_says_why` |
| R2 | La aplicación es `inventag/`, `pyproject.toml`, `setup.py`, `setup.cfg`, `MANIFEST.in`, `requirements.txt` y `LICENSE`. `templates/`, el lanzador `inventag_cli.py`, `.github/`, la documentación, el sitio, las pruebas y los ejemplos no lo son. | `tests/unit/test_release_needed.py::test_build_and_dependency_files_are_application`, `tests/unit/test_release_needed.py::test_site_markdown_examples_config_and_templates_are_not_application`, `tests/unit/test_release_needed.py::test_the_root_launcher_and_the_templates_folder_are_not_application`, `tests/unit/test_release_needed.py::test_github_actions_only_change_is_not_a_release` |
| R3 | Una versión cubre todos los commits desde esa etiqueta: un commit de código anterior sigue contando cuando el último commit solo cambia la documentación. | `tests/unit/test_release_needed.py::test_an_earlier_unreleased_code_commit_still_counts` |
| R4 | `[skip release]` o `[skip ci]` en el mensaje del commit enviado: no hay versión, aunque haya un cambio de código. | `tests/unit/test_release_needed.py::test_step_skip_release_wins_over_a_code_change` |
| R5 | Solo se lee el mensaje del commit enviado (el último). Las líneas `Release-As` y `[skip release]` de commits anteriores del mismo push se ignoran. | `tests/unit/test_release_needed.py::test_step_reads_only_the_head_commit_for_release_as_and_skip` |
| R6 | Una versión es un parche por defecto. Una línea `Release-As: minor` o `Release-As: major` en el mensaje del commit enviado fija el incremento. | `tests/unit/test_release_needed.py::test_step_code_push_is_a_patch_release`, `tests/unit/test_release_needed.py::test_step_release_as_line_with_code_sets_the_bump` |
| R7 | Un commit de fusión `Merge pull request #N` toma el incremento de la etiqueta de la pull request `release:patch`, `release:minor` o `release:major`, y es un parche sin ella. | `tests/unit/test_release_needed.py::test_step_pr_label_with_code_sets_the_bump` |
| R8 | `Release-As` o una etiqueta de versión sin cambio de la aplicación no publica nada; el registro dice que la línea o la etiqueta se ignora. | `tests/unit/test_release_needed.py::test_step_release_as_line_without_code_is_no_release`, `tests/unit/test_release_needed.py::test_step_pr_label_without_code_is_no_release` |
| R9 | El commit `chore: bump version to vX.Y.Z` del propio trabajo de versión, y un commit que ya está en una etiqueta de versión, nunca publican. | `tests/unit/test_release_needed.py::test_step_bump_commit_is_no_release`, `tests/unit/test_release_needed.py::test_step_commit_inside_a_release_tag_is_no_release` |
| R10 | Una ejecución manual con `patch`, `minor` o `major` publica aunque no haya cambio de la aplicación. Una ejecución manual con `publish_existing_tag` solo sube esa etiqueta a PyPI. | `tests/unit/test_release_needed.py::test_step_manual_run_with_a_bump_forces_a_release`, `tests/unit/test_release_needed.py::test_step_publish_only_run_is_no_release` |
| R11 | Las ejecuciones que nunca pueden publicar (un commit enviado con `[skip release]` o `[skip ci]`, una ejecución solo de publicación) tienen su propio grupo de concurrencia. Todas las demás comparten el grupo `release-main`. | `tests/unit/test_release_runbook.py::test_runs_that_cannot_release_have_their_own_concurrency_group` |
| R12 | La versión nueva es el incremento aplicado a la mayor de dos: la última versión de GitHub y `inventag/_version.py`. | `tests/unit/test_release_runbook.py::test_next_version_bumps_the_higher_of_release_and_file` |
| R13 | El commit de incremento contiene `version.json`, `inventag/_version.py` y `CHANGELOG.md`: las notas bajo `## [Unreleased]` pasan a `## [vX.Y.Z] - fecha`, y un `[Unreleased]` vacío queda como está. | `tests/unit/test_roll_changelog.py::test_filled_section_is_rolled_with_a_new_empty_unreleased`, `tests/unit/test_roll_changelog.py::test_empty_unreleased_changes_nothing`, `tests/unit/test_roll_changelog.py::test_release_workflow_rolls_the_changelog_into_the_bump_commit` |
| R14 | La etiqueta va al commit que envió el paso de incremento. El push se intenta hasta 5 veces, con esperas de 5, 10, 15 y 20 segundos, y la etiqueta se vuelve a leer con `git ls-remote`. Si falla, el registro nombra la recuperación manual de abajo. | `tests/unit/test_release_tag.py::test_the_given_commit_wins_over_head`, `tests/unit/test_release_tag.py::test_a_passing_rejection_is_retried_and_the_tag_lands`, `tests/unit/test_release_tag.py::test_a_lasting_rejection_fails_with_the_recovery_named`, `tests/unit/test_release_tag.py::test_tag_step_calls_the_script_with_the_bump_sha` |
| R15 | Una etiqueta del mismo nombre en otro commit detiene el paso de la etiqueta y no cambia nada. | `tests/unit/test_release_tag.py::test_a_tag_on_another_commit_is_refused_and_left_alone` |
| R16 | PyPI recibe una versión solo cuando la etiqueta `vX.Y.Z` nombra el commit extraído y su versión de GitHub existe. Sin ellas, una ejecución de push no publica nada y una ejecución manual falla. | `tests/unit/test_release_runbook.py::test_publish_guard_passes_with_the_tag_and_the_release`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_push_without_the_tag_publishes_nothing`, `tests/unit/test_release_runbook.py::test_publish_guard_on_a_manual_run_without_the_release_fails` |
| R17 | En el push del commit de incremento, el trabajo «Changelog rolled» falla cuando `[Unreleased]` no está vacío. No toca la etiqueta, la versión de GitHub ni PyPI. | `tests/unit/test_roll_changelog.py::test_check_fails_on_notes_left_under_unreleased`, `tests/unit/test_roll_changelog.py::test_release_workflow_runs_the_check_on_the_bump_commit_push_only` |
| R18 | Después de cada versión, el trabajo de versionado de la documentación hace commit de la etiqueta traducida de la versión actual de la documentación (`current.json`), que así nombra la versión publicada. | `tests/unit/test_release_runbook.py::test_docs_versioning_commits_the_current_json_labels`, `tests/unit/test_release_runbook.py::test_committed_current_labels_name_a_released_version` |
| R19 | Después de una ejecución de versión que adjuntó sus archivos, el último trabajo del flujo Package, `publish-tap`, escribe la fórmula de Homebrew en el tap que indica la variable del repositorio `HOMEBREW_TAP_REPO`. Solo se ejecuta cuando la subida de archivos y la instalación de la fórmula (`smoke-homebrew`) pasaron. Se omite en una ejecución de prueba, en un pull request, cuando `HOMEBREW_TAP_REPO` está vacía y cuando macOS está desactivado. Ningún trabajo lo espera, así que su fallo deja la versión, PyPI y los archivos adjuntos como están. | `tests/unit/test_packaging_workflow.py::test_publish_tap_is_skipped_in_a_dry_run_a_pull_request_and_without_a_tap`, `tests/unit/test_packaging_workflow.py::test_no_job_waits_for_publish_tap_so_a_failure_turns_only_it_red` |
| R20 | La fórmula se genera a partir del archivo `SHA256SUMS` de la versión de GitHub, y solo cuando ese archivo es igual al de la ejecución. | `tests/unit/test_packaging_workflow.py::test_the_published_sums_must_equal_the_sums_of_the_run` |
| R21 | El tap recibe un commit `inventag X.Y.Z` en `main`, de `Alex <alex.ng@ollion.com>`, sin trailer. El mismo archivo otra vez no hace push y termina en verde, así que repetir la ejecución es seguro. Una versión menor que la del tap se rechaza. | `tests/unit/test_publish_tap.py::test_the_commit_is_alex_with_the_subject_only_and_no_trailer`, `tests/unit/test_publish_tap.py::test_the_same_file_again_ends_with_success_and_pushes_nothing`, `tests/unit/test_publish_tap.py::test_a_version_lower_than_the_taps_is_refused` |
| R22 | Un push rechazado porque `main` del tap avanzó se repite una vez sobre el nuevo `main`, con la comprobación de versión otra vez. Un segundo rechazo hace fallar el trabajo. | `tests/unit/test_publish_tap.py::test_a_push_refused_because_main_moved_is_tried_once_more_on_the_new_main`, `tests/unit/test_publish_tap.py::test_a_second_refused_push_fails_the_run` |
| R23 | El secreto `HOMEBREW_TAP_TOKEN` está en el env del único paso de push. git lo recibe solo como respuesta de `GIT_ASKPASS`, nunca en una URL ni en un argumento. | `tests/unit/test_packaging_workflow.py::test_the_token_is_in_the_env_of_the_push_step_only_and_never_traced`, `tests/unit/test_publish_tap.py::test_the_token_never_reaches_a_git_argument_the_output_or_the_tap` |
| R24 | Cuando `publish-tap` falla, su último paso muestra los comandos para publicar la fórmula a mano, con la versión ya escrita. | `tests/unit/test_publish_tap.py::test_the_hand_procedure_is_printed_with_the_version_filled_in` |
| R25 | En cada ejecución que no es una pull request, el trabajo `tap-status` del flujo Package lista cada condición de `publish-tap`, su valor y si se cumple, en su registro y en el resumen del trabajo, y termina con "publish-tap will run" o "publish-tap is skipped because: ..." con la primera condición que no se cumple. No lee ningún secreto, así que muestra el token como "not checked". | `tests/unit/test_packaging_workflow.py::test_tap_status_names_the_first_false_condition`, `tests/unit/test_packaging_workflow.py::test_tap_status_reads_no_secret_checks_nothing_out_and_reads_values_from_env` |

## Antes de hacer push {#before-you-push}

- Escriba las entradas del changelog bajo `## [Unreleased]` en `CHANGELOG.md`.
  La versión las mueve (R13).
- Un cambio sin código de la aplicación: ponga `[skip release]` en el asunto
  de cada commit, y sobre todo en el último (R4, R5).
- Una versión menor o mayor: ponga la línea `Release-As` en el último commit
  del push, o la etiqueta en la pull request (R5, R6, R7). Envíela solo cuando
  haya terminado la versión en curso. No verificado contra GitHub Actions: una ejecución en espera detrás de una versión en curso puede ser sustituida por una ejecución más nueva, y entonces se usa el incremento de la más nueva.

## Límites conocidos {#known-limits}

- No verificado contra un runner de GitHub Actions: un commit que el paso de incremento trae con `git pull --rebase` está en la etiqueta y en el paquete de PyPI pero no en las notas de la versión, que listan los commits hasta la extracción.
  Las entradas del changelog de ese commit quedan bajo `[Unreleased]`, y
  entonces el trabajo «Changelog rolled» falla (R17).
- No verificado contra GitHub: la causa del fallo de la etiqueta de v1.2.2. En la ejecución 44499441432 el push de la etiqueta se rechazó con `missing necessary objects` un paso después del push del commit de incremento. git da esa respuesta cuando el servidor muestra una rama en el commit pero no puede leer el commit; la prueba `tests/unit/test_release_tag.py::test_missing_necessary_objects_is_the_answer_git_gives` la reproduce en local.

## Falló el push de la etiqueta {#the-tag-push-failed}

El paso «Create Git Tag» del trabajo «Create Release» termina con una línea
`Tag vX.Y.Z was not pushed to commit <sha>`. El commit de incremento está en
`main`, pero no hay etiqueta, ni versión de GitHub, ni nada en PyPI. Así se
terminó v1.2.2 el 19 de noviembre de 2026.

1. No vuelva a ejecutar el trabajo. Incrementaría otra vez desde la versión de
   `inventag/_version.py` y daría el número siguiente (R12).
2. Compruebe que falta la etiqueta y que el commit es el commit de incremento
   en `main`:

   ```bash
   git fetch origin
   git ls-remote origin refs/tags/vX.Y.Z          # no output
   git log -1 --format=%s <sha>                    # chore: bump version to vX.Y.Z
   git merge-base --is-ancestor <sha> origin/main && echo "on main"
   ```

3. En la página de versiones de GitHub, redacte una versión nueva. Etiqueta:
   `vX.Y.Z` (etiqueta nueva al publicar). Destino: el commit `<sha>`. Título:
   `🏷️ InvenTag Release vX.Y.Z`. Notas: cópielas del registro del paso
   «Generate release notes» de la ejecución fallida. Márquela como la última
   versión y publíquela.
4. Ejecute **Automated Release** a mano con `publish_existing_tag` igual a
   `vX.Y.Z`. El trabajo de publicación comprueba la etiqueta y la versión
   (R16) y después sube a PyPI.
5. Opcional: la ejecución fallida no adjuntó los archivos de código fuente.
   Desde un clon en la etiqueta:

   ```bash
   git archive --format=tar.gz --prefix=inventag-aws-X.Y.Z/ vX.Y.Z > inventag-aws-X.Y.Z.tar.gz
   gh release upload vX.Y.Z inventag-aws-X.Y.Z.tar.gz
   ```

No verificado contra GitHub: los pasos de la página de versiones y de una ejecución manual; son los pasos usados para v1.2.2.

## El tap de Homebrew {#the-homebrew-tap}

El tap es `habhabhabs/homebrew-inventag`. El flujo Package lo actualiza
después de cada versión (R19 a R25). Homebrew instala InvenTag en los Mac con
Apple silicon y en Linux (x86_64 y arm64). Los Mac con Intel no son compatibles.

1. Abre el registro del trabajo `publish-tap`. Su última línea nombra el commit
   del tap. «already published» significa que el tap ya tenía el mismo archivo.
2. En el tap, mira «Tap checks» para ese commit. Los dos trabajos deben estar en
   verde.
3. Un «Tap checks» en rojo: revierte ese commit en el tap y después corrige la
   fórmula en este repositorio:

   ```bash
   git clone https://github.com/habhabhabs/homebrew-inventag.git tap && cd tap
   git revert --no-edit <sha>
   git push
   ```

4. `publish-tap` falló: la versión, PyPI y los archivos adjuntos ya están hechos.
   Ejecuta los comandos que mostró su último paso, o repite el trabajo (R21).
5. `packaging/homebrew-tap/` contiene el `README.md` y
   `.github/workflows/ci.yml` del tap. Un cambio ahí se copia al tap a mano.
6. `publish-tap` se omitió: abre el resumen del trabajo `tap-status` en la
   misma ejecución. Nombra la primera condición que no se cumple (R25).

No verificado contra GitHub: los trabajos `publish-tap` y `tap-status`. La primera versión
después de v1.4.0 es su primera ejecución. v1.4.0 se puso en el tap a mano.

## Después de cada versión {#after-every-release}

- `CHANGELOG.md` en `main`: `[Unreleased]` está vacío y la versión nueva tiene
  su encabezado (el trabajo «Changelog rolled» está en verde, R17).
- El despliegue de la documentación del commit de incremento y la ejecución del
  versionado de la documentación están en verde.
- La página de estado publicada describe la versión publicada.
- Las notas de los revisores se leen una vez más frente a las notas de la versión.
- El trabajo `publish-tap` de la ejecución Package está en verde, y «Tap checks» del tap está en verde para el commit que nombra el trabajo (R19).
