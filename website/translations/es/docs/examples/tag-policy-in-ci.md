---
title: "Ejemplo: aplicar una política de etiquetas en CI"
description: Haz fallar un trabajo de CI con el código de salida 3 cuando los recursos de AWS incumplan tu política de etiquetas y conserva los informes como artefactos.
sidebar_position: 4
---

# Ejemplo: aplicar una política de etiquetas en CI

**Objetivo:** un paso de la canalización que falle cuando a los recursos les
falten etiquetas obligatorias o tengan valores incorrectos, y que conserve las
pruebas.

**Necesitas:** un ejecutor de CI con credenciales de AWS de solo lectura,
idealmente mediante OIDC (OpenID Connect). Consulta
[Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md).

## Plantilla {#template}

La plantilla de configuración integrada `ci-pipeline` escribe Excel y un
archivo JSON, comprueba `finops-cost-allocation` y falla si hay incumplimientos:

```yaml title="ci-pipeline (built-in)"
format_version: 1
kind: config
name: ci-pipeline
description: Excel report plus tag-compliance JSON; exits with code 3 on tag policy violations.
spec:
  regions: [us-east-1]
  outputs: [excel]
  output_directory: bom_output
  report_template: standard-bom
  tag_policy: finops-cost-allocation
  fail_on_tag_violations: true
  parallel_processing: false
```

## Comando {#command}

```bash title="Terminal"
inventag --template ci-pipeline
```

## Salida {#output}

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

Solo se escriben el archivo de Excel y el archivo JSON, porque la plantilla
indica `outputs: [excel]`:

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

Para enumerar los diez primeros recursos que no cumplen en el resumen de un
trabajo de GitHub Actions:

```bash title="Workflow step"
python3 -c "
import json, glob
r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))
print(f\"{r['summary']['non_compliant']} non-compliant resources\")
for x in r['non_compliant_resources'][:10]:
    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))
" >> "$GITHUB_STEP_SUMMARY"
```

```text title="Job summary"
22 non-compliant resources
- ATHENA primary missing: CostCenter, Owner, Project, Environment
- DYNAMODB acme-orders missing: CostCenter, Project
- EC2 i-855a01aabe3d29d3a missing: CostCenter, Project
- EC2 snap-3585ce88e25ef1196 missing: CostCenter, Owner, Project, Environment
- EC2 vol-680d0e08d01dd52e7 missing: CostCenter, Owner, Project, Environment
- EC2 vol-57d5df4cfc9884b48 missing: CostCenter, Owner, Project, Environment
- EVENTS default missing: CostCenter, Owner, Project, Environment
- IAM acme-orders-api-role missing: CostCenter, Owner, Project, Environment
- LAMBDA acme-orders-api missing: CostCenter, Project
- S3 acme-data-lake missing: Project
```

`acme-reports` tiene todas las etiquetas, pero dos valores son incorrectos. La
lista `invalid` del archivo JSON y la columna Problems del libro indican cuáles.

## GitLab CI/CD {#gitlab-cicd}

La misma comprobación puede ejecutarse como un job de GitLab CI/CD en los pipelines de solicitudes de fusión. **La comprobación lee AWS tal como está ahora. No lee los cambios de la solicitud de fusión.**

Configura primero el rol y la variable de CI/CD: consulta [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Los jobs de solicitudes de fusión necesitan un segundo rol, como explica el tercer punto de más abajo.

No verificado contra un runner de GitLab ni una cuenta real de AWS: este pipeline no se ha ejecutado en GitLab. Su YAML y su línea de comandos de `inventag` se comprueban al compilar la documentación. Su job se ejecutó en local con gitlab-ci-local 4.77.1 (con un sustituto de rsync) contra un AWS simulado, con un token ficticio.

```yaml
# .gitlab-ci.yml
stages:
  - check

tag-policy:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour                             # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # Exit code 3 (tag policy violations) fails this job.
    # Exit code 5 (an account could not be scanned) and 6 (no resources found) fail it too.
    - inventag --template ci-pipeline --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports when the job fails
    paths:
      - bom_output/
    expire_in: 1 week

security-groups:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour
  allow_failure:
    exit_codes: 4                             # warn only; delete these two lines to block on exit code 4
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --create-excel --enable-security-analysis --risk-threshold HIGH --fail-on-account-error --fail-if-empty
  artifacts:
    when: always
    paths:
      - bom_output/
    expire_in: 1 week
```

### Qué hace cada código de salida {#what-each-exit-code-does}

Lo que hace GitLab con cada código de salida de InvenTag en este archivo:

| Código de salida | Job `tag-policy` | Job `security-groups` |
|---|---|---|
| 0 | pasa | pasa |
| 3 (incumplimientos de la política de etiquetas) | **falla**, igual que el ejemplo de GitHub Actions | no se da (este comando no tiene política de etiquetas) |
| 4 (regla de grupo de seguridad en `HIGH` o por encima) | no se da (no hay `--risk-threshold`) | «se permite que falle»: el job muestra una advertencia, el pipeline continúa y cuenta como superado ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| 5 (no se pudo analizar una cuenta; `--fail-on-account-error`), 6 (no se encontraron recursos; `--fail-if-empty`) | falla | falla: el código no está en `exit_codes`, así que `allow_failure` es falso para él |
| 1, 2 | falla | falla |

### Qué hace cada parte {#what-each-part-does}

Las líneas que comparten todos los ejemplos de GitLab (`image`, `timeout`, `id_tokens`, las dos líneas del token y `artifacts`) están en la tabla de [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Esta tabla recoge las partes de este ejemplo:

| Parte | Qué hace |
|---|---|
| `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"` | El job se ejecuta solo en pipelines de solicitudes de fusión ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). |
| `inventag --template ci-pipeline --fail-on-account-error --fail-if-empty` | El comando de esta página más las dos opciones que hay que activar. Los códigos de salida 5 y 6 tienen prioridad sobre el 3 (el orden es 5, 6, 3, 4), así que una ejecución con una cuenta que no se pudo analizar, o sin recursos, nunca se muestra como «sin incumplimientos». Una llamada de servicio fallida dentro de una cuenta a la que se llegó no da 5. En la ejecución local, este job terminó como fallido con el código de salida 3 y se recogieron sus archivos de informe. |
| `allow_failure: exit_codes: 4` | Solo se tolera el código de salida 4. Con cualquier otro código distinto de cero, el job falla como de costumbre. Para bloquear la solicitud de fusión con el código 4, borra las dos líneas. Para iniciar el job `tag-policy` en modo de advertencia, dale `allow_failure:` con `exit_codes: 3` de la misma forma, o mantén `fail_on_tag_violations: false`, como dice «Siguientes pasos» ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)). En la ejecución local, `security-groups` terminó con una advertencia y el código de salida 4. |
| `inventag --create-excel --enable-security-analysis --risk-threshold HIGH ...` | Código de salida 4 cuando una regla de grupo de seguridad está en `HIGH` o por encima. `--risk-threshold` necesita `--enable-security-analysis`; si no, el código de salida es 2. Aquí no hay `--template`, porque `--enable-security-analysis` no añade nada con `--template` (consulta la [referencia de la CLI](../reference/cli.md)). Este job analiza todas las regiones habilitadas. |

Lo que no está verificado:

- No verificado contra GitLab ni AWS: que GitLab emita el token de ID y que AWS lo acepte para el rol, con las condiciones de la política de confianza sobre `aud` y `sub`.
- No verificado contra GitLab: `image`, `timeout`, `expire_in` y `cache` (gitlab-ci-local los ignora).
- No verificado contra GitLab: cómo afecta un job fallido, o un job al que se permite fallar, a los jobs posteriores, al estado del pipeline y a la solicitud de fusión.

### Tres cosas que debes saber {#three-things-to-know}

1. **La comprobación lee AWS tal como está ahora. No lee los cambios de la solicitud de fusión.** Los comandos no dan a InvenTag nada del repositorio salvo sus archivos de plantilla. Cada job analiza la cuenta una vez, así que un pipeline de solicitud de fusión hace dos análisis. Por defecto, cada ejecución también usa Cost Explorer, y AWS cobra cada solicitud a Cost Explorer; `--no-billing-validation` detiene esas llamadas (consulta la [referencia de la CLI](../reference/cli.md)).
2. **Un job fallido bloquea la fusión solo si el proyecto lo exige.** Activa **Settings > Merge requests > Merge checks > Pipelines must succeed**. Necesitas el rol Maintainer u Owner ([GitLab](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)).
3. **En un pipeline de solicitud de fusión, el token de ID nombra la rama de origen, no `main`** ([GitLab](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). Un rol cuya política de confianza solo permite `ref:main` rechaza estos jobs. Crea un segundo rol de solo lectura para ellos, sin la instrucción de subida (`s3:PutObject`). La política de confianza para este caso está en [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Cualquiera que pueda subir una rama al proyecto y abrir una solicitud de fusión puede ejecutar un job con este rol, y puede cambiar el script del job en su rama. El rol es de solo lectura, así que puede leer lo que InvenTag puede leer. No reutilices el rol de tus jobs programados.
   - Una variable de CI/CD protegida solo se pasa a un pipeline de solicitud de fusión si la rama de origen y la rama de destino están protegidas, ambas están en el mismo proyecto y el usuario puede fusionar en la rama de destino. Nunca se pasa desde un fork ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). Por eso, no protejas `AWS_ROLE_ARN` para estos jobs.
   - El ejemplo lee `AWS_ROLE_ARN`, lo que es correcto para un proyecto que solo tiene estos jobs de solicitud de fusión. Un proyecto que también ejecuta jobs programados con el primer rol necesita otro nombre de variable para el segundo rol. Este ejemplo no muestra cómo asignarlo.

## Siguientes pasos {#next-steps}

- Empieza en modo solo informe: pon `fail_on_tag_violations: false` hasta que
  las cifras estén cerca de cero y entonces actívalo.
- No dejes que una ejecución incompleta pase por limpia: `--fail-on-account-error`
  termina con el código 5 cuando no se pudo analizar una cuenta y
  `--fail-if-empty` termina con el código 6 cuando no se encontró ningún recurso.
  Ambos tienen prioridad sobre el código 3.
- Usa tus propias reglas: [Comprobar etiquetas con una política](../guides/check-tag-compliance.md#write-your-own-policy).
