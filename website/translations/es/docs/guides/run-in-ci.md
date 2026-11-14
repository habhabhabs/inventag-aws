---
title: Ejecutar InvenTag en CI/CD
description: Ejecuta InvenTag de forma programada en GitHub Actions o GitLab CI/CD con credenciales OIDC de corta duración, conserva los informes y falla el trabajo si hay incumplimientos.
sidebar_position: 7
---

# Ejecutar InvenTag en CI/CD

**Para quién es:** quieres un inventario programado, o una canalización que
falle cuando los recursos no están bien etiquetados.

**Qué podrás hacer después de leerlo:** configurar un flujo de trabajo de GitHub Actions o un pipeline de GitLab CI/CD que ejecute InvenTag con credenciales de corta duración y
conserve los informes.

## Las piezas {#the-pieces}

1. **Credenciales sin claves almacenadas.** Usa OpenID Connect (OIDC): el sistema de CI demuestra quién es el trabajo y AWS le da una sesión de rol
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
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
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
Eso te protege si una etiqueta (tag) se mueve a código malicioso. Los cuatro SHA de arriba son los commits de las etiquetas (tags) indicadas en los comentarios. Actualiza los SHA cuando actualices las versiones.

InvenTag se ejecuta desde la carpeta de tu repositorio, así que
`.inventag/templates/nightly.yaml` se encuentra por nombre.

Sin las dos opciones de código de salida, el trabajo termina bien aunque una cuenta no se haya podido analizar o no se haya encontrado nada.
`--fail-on-account-error` hace fallar el trabajo con el código 5 en el primer caso, y `--fail-if-empty` con el código 6 en el segundo.
Los informes se escriben igualmente, así que el paso de artefactos puede conservarlos.

## GitLab CI/CD {#gitlab-cicd}

Esta sección es el equivalente en GitLab de los pasos de GitHub Actions de arriba. La plantilla de configuración del paso 2 es la misma. Los ejemplos están escritos para GitLab.com. Una [instancia autoalojada](#on-a-self-managed-instance) necesita algunos cambios.

### Deja que GitLab asuma un rol de solo lectura {#let-gitlab-assume-a-read-only-role}

No verificado contra GitLab ni AWS: que GitLab emita el token de ID y que AWS lo acepte para el rol, con las condiciones de la política de confianza sobre `aud` y `sub`.

**Paso 1: añade GitLab como proveedor de identidad OIDC en IAM.** En la consola de IAM, abre **Identity providers > Add provider** y elige OpenID Connect ([AWS: crear un proveedor de identidad OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)).

| Campo | Valor |
|---|---|
| URL del proveedor | `https://gitlab.com` para GitLab.com. Para una instancia autoalojada, la dirección de tu propia instancia, por ejemplo `https://gitlab.example.com`. AWS exige una URL que empiece por `https://`. GitLab indica que la dirección debe ser de acceso público ([GitLab: OpenID Connect in AWS](https://docs.gitlab.com/ci/cloud_services/aws/)). |
| Audiencia | `sts.amazonaws.com`. Debe ser el mismo texto que `aud` bajo `id_tokens` en el pipeline. |
| Huella digital | No hay que introducir nada. IAM la obtiene y AWS comprueba antes el certificado del proveedor con su propia lista de CA raíz de confianza ([AWS: `create-open-id-connect-provider`](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)). |

Solo puedes añadir un proveedor por URL y cuenta de AWS. Un segundo "add" para la misma URL falla. Si tu cuenta ya confía en `gitlab.com`, añade la audiencia al proveedor existente.

**Paso 2: crea el rol con una política de confianza.** Crea un rol para este proveedor. La política de confianza de abajo permite que un proyecto de GitLab.com, en una rama, asuma el rol. Es el caso de los ejemplos programados, que se ejecutan en `main`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.com:aud": "sts.amazonaws.com",
          "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main",
          "gitlab.com:project_id": "67890"
        }
      }
    }
  ]
}
```

Sustituye estos valores:

| Valor | Sustitúyelo por |
|---|---|
| `123456789012` | El ID de la cuenta de AWS que contiene el proveedor de identidad y el rol. El proveedor y el rol deben estar en la misma cuenta. |
| `gitlab.com` (cuatro veces) | Déjalo para GitLab.com. En una instancia autoalojada, usa el nombre de host de tu instancia, sin `https://`. |
| `sts.amazonaws.com` | Déjalo, salvo que hayas elegido otra audiencia en el paso 1 y bajo `id_tokens`. |
| `mygroup/myproject` | La ruta completa del proyecto: grupo, subgrupos y proyecto. |
| `main` | La rama en la que se ejecuta la programación. |
| `67890` | El ID del proyecto. Esta línea funciona solo en GitLab.com. En una instancia autoalojada o Dedicated, AWS solo admite las claims `sub` y `aud`, así que borra la línea allí. |

La claim `sub` tiene por defecto la forma `project_path:{group}/{project}:ref_type:{type}:ref:{branch_name}`. Un proyecto puede cambiar esa forma mediante la API de proyectos, y entonces el valor de arriba no coincide ([GitLab: ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). Se recomienda una condición sobre un ID estable como `project_id`, porque otra persona puede volver a crear la ruta de un proyecto borrado ([AWS: claves de condición de IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)).

Un comodín en una condición necesita `StringLike`. Con `StringEquals`, AWS rechaza la llamada.

**Variante: cualquier rama protegida (GitLab.com).** Sustituye el bloque `Condition`:

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890",
    "gitlab.com:ref_protected": "true"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

No verificado contra AWS: que `"true"` sea el texto exacto que AWS compara para `ref_protected`. `ref_protected` y `pipeline_source` son claves de condición solo de GitLab.com.

**Variante: etiquetas protegidas (GitLab.com).** El mismo bloque, con `ref_type:tag:ref:*` (o `ref_type:tag:ref:v*`) en la línea `sub`.

**Variante: pipelines de solicitud de fusión.** El token de un pipeline de solicitud de fusión lleva la rama de origen, así que el rol debe aceptar todas las ramas del proyecto:

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

No verificado contra GitLab: el texto exacto de `sub` en un pipeline de solicitud de fusión.

Con esta variante, cualquiera que pueda subir una rama al proyecto y abrir una solicitud de fusión puede ejecutar un job con este rol, y puede cambiar el script del job en su rama. El rol es de solo lectura, así que puede leer lo que InvenTag puede leer. Usa un rol aparte para esta variante. No reutilices el rol de los jobs programados y no le des `s3:PutObject`. Consulta [el ejemplo de política de etiquetas](../examples/tag-policy-in-ci.md#gitlab-cicd).

**Paso 3: adjunta la política de solo lectura.** Adjunta la política de [Configurar el acceso de solo lectura](./read-only-access.md): la opción 2, `config/defaults/iam-policy-read-only.json`, o la opción 1 (`ReadOnlyAccess` más tres acciones).

- Para el ejemplo de subida, conserva la instrucción `OptionalS3ReportUpload` y pon el nombre de tu bucket en lugar de `YOUR-REPORTS-BUCKET-NAME`. Su recurso termina en `bom-reports/*`, así que el prefijo de clave debe ser `bom-reports/` (el valor por defecto), o cambias el recurso. Con `aws:kms`, permite también `kms:GenerateDataKey` sobre la clave ([Permisos de IAM](../reference/iam-permissions.md)). Consulta [Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md). Para los demás ejemplos, elimina la instrucción.
- Para el ejemplo con varias cuentas, el rol necesita además `sts:AssumeRole` sobre el rol `InvenTagReadOnly` de cada cuenta, y cada uno de esos roles confía en este rol. El archivo de política del repositorio no tiene ninguna instrucción `sts:AssumeRole`. Consulta [Configurar el acceso de solo lectura](./read-only-access.md) y [Analizar varias cuentas](./scan-multiple-accounts.md).

InvenTag sigue siendo de solo lectura. Ni el rol ni el pipeline hacen que una cuenta cumpla ninguna normativa.

#### En una instancia autoalojada {#on-a-self-managed-instance}

No verificado contra una instancia de GitLab autoalojada: este párrafo. La URL del proveedor y las claves de condición usan el nombre de host de tu instancia. Allí AWS solo admite las claims `sub` y `aud`, así que la línea `project_id` se quita. Allí no existe la clave `ref_protected` en AWS, así que fija cada rama por su nombre. AWS debe poder llegar a la instancia desde internet; GitLab describe una solución alternativa para una instancia que no es pública y la llama avanzada ([GitLab: configure a non-public GitLab instance](https://docs.gitlab.com/ci/cloud_services/aws/)). El runner debe poder ejecutar imágenes de contenedor.

### Añade la variable de CI/CD {#add-the-cicd-variable}

En tu proyecto de GitLab, abre **Settings > CI/CD > Variables > Add variable** (rol Maintainer). Usa la clave `AWS_ROLE_ARN` y como valor el ARN del rol, por ejemplo `arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly`. GitLab pasa la variable al job como variable de entorno ([GitLab: CI/CD variables](https://docs.gitlab.com/ci/variables/)).

- Para los ejemplos programados, marca **Protect variable** y protege la rama. Así la variable llega solo a los pipelines de ramas o etiquetas protegidas.
- Para el ejemplo de solicitud de fusión, no protejas la variable. Una variable protegida no se pasa a un pipeline de solicitud de fusión a menos que la rama de origen y la de destino estén protegidas ([GitLab: merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). Con dos roles, usa un segundo nombre de variable en los dos jobs de ese ejemplo.
- Desde GitLab 18.3, GitLab marca por defecto una variable nueva como **Masked**, y un valor enmascarado debe ser de una sola línea, de al menos 8 caracteres y sin espacios. Un ARN de rol no es un secreto. Elige **Visible** si GitLab se niega a enmascarar el valor. No verificado contra GitLab: que GitLab acepte un ARN de rol como valor enmascarado.
- El ejemplo de subida necesita dos variables más, `INVENTAG_REPORTS_BUCKET` e `INVENTAG_KMS_KEY_ID`. Ninguna es un secreto.

### Añade el pipeline {#add-the-pipeline}

Este job ejecuta InvenTag cada noche y conserva los informes como artefactos del job. Necesita `.inventag/templates/nightly.yaml` del paso 2. Añade el archivo a la raíz de tu repositorio con el nombre `.gitlab-ci.yml`. Si el archivo ya tiene `stages`, añade el nombre de la etapa a esa lista.

No verificado contra un runner de GitLab ni una cuenta real de AWS: este pipeline no se ha ejecutado en GitLab. Su YAML y su línea de comandos de `inventag` se comprueban al compilar la documentación. Su job se ejecutó en local con gitlab-ci-local 4.77.1 (con un sustituto de rsync) contra un AWS simulado, con un token ficticio.

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"   # the pipeline schedule
    - if: $CI_PIPELINE_SOURCE == "web"        # "New pipeline" in the GitLab UI
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    key: pip
    paths:
      - .cache/pip
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --template nightly --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports even when the tag check fails
    paths:
      - bom_output/
    expire_in: 30 days
```

Qué hace cada parte:

| Parte | Qué hace |
|---|---|
| `stages:` y `stage:` | Declaran la etapa y ponen el job en ella. Un job sin `stage` va a `test` ([GitLab: `stages`](https://docs.gitlab.com/ci/yaml/#stages)). |
| `image: python:3.12` | El job se ejecuta en esta imagen de contenedor, con la forma `<image-name>:<tag>`. InvenTag necesita Python 3.11 o posterior, y el ejemplo de GitHub usa 3.12 ([GitLab: `image`](https://docs.gitlab.com/ci/yaml/#image)). |
| `rules:` con `schedule` y `web` | El job se añade solo a los pipelines programados y a los iniciados con **New pipeline** en la interfaz de GitLab. En cualquier otro pipeline (push, solicitud de fusión) ninguna regla coincide y el job no se añade ([GitLab: job rules](https://docs.gitlab.com/ci/jobs/job_rules/)). |
| `timeout: 2 hours` | Detiene el job pasado ese tiempo ([GitLab: `timeout`](https://docs.gitlab.com/ci/yaml/#timeout)). También fija la vida del token de ID: GitLab fija la caducidad del token al timeout del job si hay uno, y a 5 minutos si no ([GitLab: ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). InvenTag intercambia el token más de una vez en una ejecución (comprobado en local contra un AWS simulado), así que define siempre `timeout`. Los runners alojados por GitLab en GitLab.com detienen cada job a las 3 horas ([GitLab: hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)). |
| `id_tokens:` | GitLab crea un token de ID OIDC (un JSON Web Token) para este job, con la audiencia en `aud`. El script lo lee como `$GITLAB_OIDC_TOKEN`. Está disponible en los niveles Free, Premium y Ultimate, en GitLab.com, Self-Managed y Dedicated ([GitLab: `id_tokens`](https://docs.gitlab.com/ci/yaml/#id_tokens)). |
| `AWS_DEFAULT_REGION` | La región que usa el SDK de AWS en la llamada de inicio de sesión. Define esta variable: `AWS_REGION` sola no basta, porque botocore, el SDK de AWS para Python, no la lee (comprobado en local). |
| `pip install "inventag-aws==..."` | Instala una versión fijada de InvenTag. |
| Las dos líneas con `AWS_WEB_IDENTITY_TOKEN_FILE` | Escriben el token en un archivo nuevo y privado fuera de la carpeta del proyecto, y le dicen al SDK de AWS dónde está. Con `AWS_ROLE_ARN` (la variable de CI/CD), el SDK cambia el token por credenciales temporales por sí mismo ([AWS: assume role credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)). No hacen falta AWS CLI ni clave de acceso. Un archivo fuera de la carpeta del proyecto no puede convertirse en artefacto ni en entrada de caché, porque ambos admiten solo rutas dentro de la carpeta del proyecto ([GitLab: `artifacts:paths`](https://docs.gitlab.com/ci/yaml/#artifactspaths), [GitLab: caching](https://docs.gitlab.com/ci/caching/)). Comprobado en local contra un AWS simulado: el archivo tiene modo 600 y el SDK inicia sesión con el token. |
| `PIP_CACHE_DIR` y `cache:` | Conservan la caché de descargas de pip entre jobs. La caché debe estar dentro de la carpeta del proyecto, porque GitLab solo guarda en caché rutas de ahí ([GitLab: caching examples](https://docs.gitlab.com/ci/caching/examples/)). Opcional: el job funciona sin estas líneas. |
| `inventag --template nightly --fail-on-account-error --fail-if-empty` | El mismo comando que en el flujo de trabajo de GitHub. Código de salida 3 cuando la política de etiquetas encuentra incumplimientos y la plantilla dice `fail_on_tag_violations: true`, 5 cuando una cuenta no se pudo escanear y 6 cuando no se encontró ningún recurso. Cualquier código de salida distinto de 0 hace fallar el job ([GitLab: `script`](https://docs.gitlab.com/ci/yaml/script/)). En local (con un sustituto de rsync), el job terminó con código de salida 3 y se recogieron los cuatro archivos de informe. |
| `artifacts:` | Sube `bom_output/` como artefactos del job. Con `when: always`, GitLab los sube también cuando el job falla; sin él, solo cuando el job tiene éxito. `always` no cubre un job que agota el tiempo. `expire_in` indica cuánto tiempo los conserva GitLab. GitLab conserva los artefactos del último pipeline de una ref con independencia de `expire_in` (ajuste por defecto del proyecto) ([GitLab: `artifacts:when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [GitLab: `artifacts:expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in), [GitLab: job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)). `expire_in: 30 days` equivale a `retention-days: 30` del flujo de trabajo de GitHub. InvenTag escribe los informes antes de terminar con el código 3, 4 o 5. |
| El ARN del rol | No está en el YAML. Es la variable de CI/CD `AWS_ROLE_ARN` del paso anterior. |

Otras dos partes de este ejemplo no están verificadas:

- No verificado contra GitLab: `image`, `timeout`, `expire_in` y `cache` (gitlab-ci-local los ignora).
- No verificado contra una programación de pipeline de GitLab: la ejecución en local fijó el origen del pipeline a mano.

### Prográmalo {#schedule-it}

La programación no está en el archivo. Créala en GitLab: abre **Build > Pipeline schedules > New schedule**, escribe un patrón cron (por ejemplo `17 2 * * 1-5`) y la rama de destino, y guarda. Necesitas el rol Developer o superior. El pipeline se ejecuta con los permisos del propietario de la programación ([GitLab: pipeline schedules](https://docs.gitlab.com/ci/pipelines/schedules/)). Para ejecutar el job a mano, elige **New pipeline** en la interfaz de GitLab, o **Run** en la programación.

No verificado contra GitLab: la zona horaria que usa una programación de pipeline para el patrón cron.

### Qué cambia respecto a GitHub Actions {#what-differs-from-github-actions}

La columna de GitHub describe solo lo que muestra el flujo de trabajo de GitHub de arriba.

| Tema | GitHub Actions | GitLab CI/CD |
|---|---|---|
| Archivo | `.github/workflows/inventory.yml` | `.gitlab-ci.yml` en la raíz del repositorio |
| Programación | `on: schedule: - cron:` dentro del archivo | No está en el archivo. Una programación de pipeline en la interfaz de GitLab (**Build > Pipeline schedules**), y una línea `rules` que deja entrar el job en los pipelines programados |
| Ejecutar a mano | `workflow_dispatch` | **New pipeline** en la interfaz (`$CI_PIPELINE_SOURCE == "web"`), o **Run** en la programación |
| Pedir un token OIDC | `permissions: id-token: write` | `id_tokens:` en el job, con la audiencia en `aud` |
| Obtener credenciales de AWS | La acción `aws-actions/configure-aws-credentials` | Ninguna acción. Dos líneas del script escriben el token en un archivo y el SDK de AWS dentro de InvenTag lo intercambia (`AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE`) |
| ARN del rol | En el YAML (`role-to-assume`) | Una variable de CI/CD `AWS_ROLE_ARN`, no en el YAML |
| Región | `aws-region: us-east-1` | `AWS_DEFAULT_REGION: us-east-1`. `AWS_REGION` sola no basta |
| Proveedor de identidad en AWS | `token.actions.githubusercontent.com` | `gitlab.com`, o el host de tu propia instancia |
| Qué fija la política de confianza | Repositorio y rama | La claim `sub`: ruta del proyecto, tipo de ref y nombre de ref. En GitLab.com también el ID del proyecto |
| Vida del token | No se indica en esta página | El `timeout` del job; 5 minutos si el job no define ninguno. Define siempre `timeout` |
| Python | `actions/setup-python` con `python-version: "3.12"` | `image: python:3.12` |
| Fijar versiones | Cada acción por SHA de commit completo | La imagen por etiqueta de versión menor. Un digest de imagen (`<image-name>@<digest>`) es la forma más estricta; los ejemplos no lo usan ([GitLab: `image`](https://docs.gitlab.com/ci/yaml/#image)) |
| Conservar los informes | `actions/upload-artifact` con `if: always()` y `retention-days: 30` | `artifacts:` con `when: always` y `expire_in: 30 days`. No se suben si el job agota el tiempo. El artefacto incluye también `bom_output/state/` |
| Tolerar un código de salida | No se muestra en esta página | `allow_failure: exit_codes:` en el job ([GitLab: `allow_failure:exit_codes`](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| Job más largo | No se indica en esta página | 3 horas en los runners alojados por GitLab de GitLab.com ([GitLab: hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)) |
| Ejecuciones de solicitudes de fusión o de extracción | No se muestra en esta página | El token lleva la rama de origen, y las variables protegidas se pasan solo bajo las condiciones de GitLab. Consulta [el ejemplo de política de etiquetas](../examples/tag-policy-in-ci.md#gitlab-cicd) |
| Resumen del job | `$GITHUB_STEP_SUMMARY` (en [el ejemplo de política de etiquetas](../examples/tag-policy-in-ci.md)) | No se usa en estos ejemplos |

## Qué pasa ante un incumplimiento {#what-happens-on-a-violation}

Con `fail_on_tag_violations: true`, InvenTag escribe primero todos los informes
y después termina con el código 3. El trabajo falla y el artefacto sigue
conteniendo el archivo de Excel y `tag_compliance_<timestamp>.json` con todos
los recursos no conformes.

Ejemplo de salida de `inventag --template ci-pipeline` en una ejecución sin
conexión (datos de ejemplo):

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
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

Si se aplica más de uno, primero va el 5, luego el 6, después el 3 y por último el 4, porque los datos detrás de un resultado de etiquetas o de riesgo están incompletos cuando falta una cuenta.
Se escriben informes con los códigos 3, 4 y 5. Con el código 6, una ejecución con `--template` escribe un informe que no lista ningún recurso, y una ejecución sin ella no escribe ningún archivo.

## Mantenlo seguro {#keep-it-safe}

- Evita `--debug` en CI. Los secretos se enmascaran en los registros de
  depuración, pero los registros son largos y aun así describen tus cuentas.
- Para conservar los informes en S3 en lugar de (o además de) como artefactos,
  añade `--s3-bucket` y concede `s3:PutObject` en ese bucket. Consulta
  [Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md).
- Mantén el rol de solo lectura y limitado al repositorio y la rama que lo
  necesitan.
- En GitLab CI/CD, protege la rama que ejecuta el pipeline, limita la política de confianza del rol a esa rama y guarda el ARN del rol en una variable de CI/CD. Consulta [GitLab CI/CD](#gitlab-cicd).
- Fija InvenTag a una versión publicada (`inventag-aws==%INVENTAG_VERSION%`), no a la última versión. Sube el número cuando decidas actualizar.

## Siguientes pasos {#next-steps}

- [Ejemplo: aplicar una política de etiquetas en CI](../examples/tag-policy-in-ci.md)
- [Seguir los cambios entre ejecuciones](./track-changes.md)
