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
echo $?
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

## Siguientes pasos {#next-steps}

- Empieza en modo solo informe: pon `fail_on_tag_violations: false` hasta que
  las cifras estén cerca de cero y entonces actívalo.
- No dejes que una ejecución incompleta pase por limpia: `--fail-on-account-error`
  termina con el código 5 cuando no se pudo analizar una cuenta y
  `--fail-if-empty` termina con el código 6 cuando no se encontró ningún recurso.
  Ambos tienen prioridad sobre el código 3.
- Usa tus propias reglas: [Comprobar etiquetas con una política](../guides/check-tag-compliance.md#write-your-own-policy).
