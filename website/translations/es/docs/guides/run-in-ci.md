---
title: Ejecutar InvenTag en CI/CD
description: Ejecuta InvenTag de forma programada en GitHub Actions con credenciales OIDC de corta duración, conserva los informes y falla el trabajo si hay incumplimientos.
sidebar_position: 7
---

# Ejecutar InvenTag en CI/CD

**Para quién es:** quieres un inventario programado, o una canalización que
falle cuando los recursos no están bien etiquetados.

**Qué podrás hacer después de leerlo:** configurar un flujo de trabajo de
GitHub Actions que ejecute InvenTag con credenciales de corta duración y
conserve los informes.

## Las piezas {#the-pieces}

1. **Credenciales sin claves almacenadas.** Usa OpenID Connect (OIDC): GitHub
   demuestra quién es el flujo de trabajo y AWS le da una sesión de rol
   temporal. No hay claves de acceso en los secretos de tu repositorio.
2. **Una plantilla de configuración** con tus regiones, salidas y política de
   etiquetas. La plantilla integrada `ci-pipeline` es un buen punto de partida.
3. **Un artefacto** para conservar `bom_output/`.

## 1. Deja que GitHub asuma un rol de solo lectura {#1-let-github-assume-a-read-only-role}

En AWS, añade GitHub como proveedor de identidad OIDC
(`token.actions.githubusercontent.com`) y crea un rol con la política de solo
lectura de [Configurar el acceso de solo lectura](./read-only-access.md).
Limita su política de confianza a tu repositorio y rama. La guía de AWS
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
lo explica paso a paso.

## 2. Añade una plantilla de configuración a tu repositorio {#2-add-a-config-template-to-your-repository}

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

Indica tus regiones y tu política de etiquetas, y confirma el archivo en el
repositorio (commit).

## 3. Añade el flujo de trabajo {#3-add-the-workflow}

```yaml
# .github/workflows/inventory.yml
name: AWS inventory
on:
  schedule:
    - cron: "17 2 * * 1-5"   # 02:17 UTC on weekdays
  workflow_dispatch:

permissions:
  contents: read
  id-token: write            # needed for OIDC

jobs:
  inventory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
      - uses: aws-actions/configure-aws-credentials@<full-commit-SHA> # pin the current release
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly --fail-on-account-error --fail-if-empty
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

Fija cada acción a un SHA de commit completo, con la versión en un comentario.
Eso te protege si una etiqueta (tag) se mueve a código malicioso. Los SHA de
arriba para `checkout`, `setup-python` y `upload-artifact` son los que usan los
flujos de trabajo de este mismo repositorio. Para
`aws-actions/configure-aws-credentials`, busca el SHA de su versión actual en
su página de versiones (releases) de GitHub: no verificamos ninguno para esta
página. Actualiza los SHA cuando actualices las versiones.

InvenTag se ejecuta desde la carpeta de tu repositorio, así que
`.inventag/templates/nightly.yaml` se encuentra por nombre.

Sin las dos opciones de código de salida, el trabajo termina bien aunque una cuenta no se haya podido analizar o no se haya encontrado nada.
`--fail-on-account-error` hace fallar el trabajo con el código 5 en el primer caso, y `--fail-if-empty` con el código 6 en el segundo.
Los informes se escriben igualmente, así que el paso de artefactos puede conservarlos.

## Qué pasa ante un incumplimiento {#what-happens-on-a-violation}

Con `fail_on_tag_violations: true`, InvenTag escribe primero todos los informes
y después termina con el código 3. El trabajo falla y el artefacto sigue
conteniendo el archivo de Excel y `tag_compliance_<timestamp>.json` con todos
los recursos no conformes.

Ejemplo de salida de `inventag --template ci-pipeline` en una ejecución sin
conexión (datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
$ echo $?
3
```

## Códigos de salida {#exit-codes}

| Código de salida | Significado |
|---|---|
| 0 | Informes escritos, sin incumplimientos de etiquetas (o sin política que falle). También cuando una cuenta falló o no se encontró nada, salvo que pases las opciones de los códigos 5 y 6 |
| 1 | Error: plantilla o archivo de configuración no válido, credenciales, todas las cuentas fallaron, un formato de informe que no se pudo escribir o una subida a S3 fallida |
| 2 | Opciones no válidas o en conflicto, por ejemplo `--accounts-file` con `--accounts-prompt`, o `--compliance-standard` (no implementada). No se analiza nada |
| 3 | Informes escritos, se encontraron incumplimientos de la política de etiquetas (`fail_on_tag_violations: true`) |
| 4 | Informes escritos, una regla de grupo de seguridad abierta a internet con nivel igual o superior a `--risk-threshold` |
| 5 | Informes escritos, una cuenta no se pudo analizar o solo en parte (`--fail-on-account-error`) |
| 6 | No hay recursos que informar (`--fail-if-empty`) |

Si se aplica más de uno, primero va el 5, luego el 6 y después el 3 y el 4, porque los datos detrás de un resultado de etiquetas o de riesgo están incompletos cuando falta una cuenta.
Se escriben informes con los códigos 3, 4 y 5. Con el código 6, una ejecución con `--template` escribe un informe que no lista ningún recurso, y una ejecución sin ella no escribe ningún archivo.

## Mantenlo seguro {#keep-it-safe}

- Evita `--debug` en CI. Los secretos se enmascaran en los registros de
  depuración, pero los registros son largos y aun así describen tus cuentas.
- Para conservar los informes en S3 en lugar de (o además de) como artefactos,
  añade `--s3-bucket` y concede `s3:PutObject` en ese bucket. Consulta
  [Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md).
- Mantén el rol de solo lectura y limitado al repositorio y la rama que lo
  necesitan.
- Fija InvenTag a una versión publicada (`inventag-aws==%INVENTAG_VERSION%`), no a la última versión. Sube el número cuando decidas actualizar.

## Siguientes pasos {#next-steps}

- [Ejemplo: aplicar una política de etiquetas en CI](../examples/tag-policy-in-ci.md)
- [Seguir los cambios entre ejecuciones](./track-changes.md)
