---
title: "Exemple : appliquer une politique d’étiquetage en CI"
description: Faites échouer un job CI avec le code de sortie 3 quand des ressources AWS enfreignent votre politique d’étiquetage, et gardez les rapports comme artefacts.
sidebar_position: 4
---

# Exemple : appliquer une politique d’étiquetage en CI

**Objectif :** une étape de pipeline qui échoue lorsque des ressources n’ont pas les étiquettes
requises ou comportent de mauvaises valeurs, et qui conserve les preuves.

**Ce qu’il vous faut :** un exécuteur CI avec des identifiants AWS en lecture seule, idéalement via
OIDC (OpenID Connect). Voir [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md).

## Modèle {#template}

Le modèle de configuration intégré `ci-pipeline` écrit un fichier Excel et un fichier JSON,
vérifie `finops-cost-allocation` et échoue en cas de violation :

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

## Commande {#command}

```bash title="Terminal"
inventag --template ci-pipeline
echo $?
```

## Sortie {#output}

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
3
```

Seuls le fichier Excel et le fichier JSON sont écrits, car le modèle indique
`outputs: [excel]` :

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

Pour lister les dix premières ressources non conformes dans le résumé d’un job
GitHub Actions :

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

`acme-reports` possède toutes les étiquettes, mais deux valeurs sont erronées. La liste `invalid`
du fichier JSON et la colonne Problems du classeur indiquent lesquelles.

## Étapes suivantes {#next-steps}

- Commencez en mode rapport seul : définissez `fail_on_tag_violations: false` jusqu’à ce que
  les chiffres soient proches de zéro, puis activez-le.
- Ne laissez pas une exécution incomplète passer pour propre :
  `--fail-on-account-error` se termine avec le code 5 quand un compte n’a pas pu
  être analysé, et `--fail-if-empty` avec le code 6 quand aucune ressource n’a
  été trouvée. Les deux l’emportent sur le code 3.
- Utilisez vos propres règles : [Vérifier les étiquettes selon une politique](../guides/check-tag-compliance.md#write-your-own-policy).
