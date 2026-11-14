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

## GitLab CI/CD {#gitlab-cicd}

La même vérification peut s’exécuter comme un job GitLab CI/CD dans les pipelines de requêtes de fusion. **La vérification lit AWS tel qu’il est maintenant. Elle ne lit pas les modifications de la requête de fusion.**

Configurez d’abord le rôle et la variable CI/CD : voir [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Les jobs de requêtes de fusion ont besoin d’un second rôle, comme l’explique le troisième point ci-dessous.

Non vérifié sur un runner GitLab ni sur un vrai compte AWS : ce pipeline n’a pas été exécuté sur GitLab. Son YAML et sa ligne de commande `inventag` sont vérifiés à la construction de la documentation. Son job a été exécuté en local avec gitlab-ci-local 4.77.1 (avec un substitut de rsync) contre un AWS simulé, avec un jeton factice.

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

### Ce que fait chaque code de sortie {#what-each-exit-code-does}

Ce que GitLab fait de chaque code de sortie d’InvenTag dans ce fichier :

| Code de sortie | Job `tag-policy` | Job `security-groups` |
|---|---|---|
| 0 | réussit | réussit |
| 3 (violations de la politique d’étiquetage) | **échoue**, comme l’exemple GitHub Actions ([GitLab : `script`](https://docs.gitlab.com/ci/yaml/script/)) | ne se produit pas (cette commande n’a pas de politique d’étiquetage) |
| 4 (règle de groupe de sécurité à `HIGH` ou au-dessus) | ne se produit pas (pas de `--risk-threshold`) | « autorisé à échouer » : le job affiche un avertissement, le pipeline continue et compte comme réussi ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| 5 (un compte n’a pas pu être analysé ; `--fail-on-account-error`), 6 (aucune ressource trouvée ; `--fail-if-empty`) | échoue | échoue : le code n’est pas dans `exit_codes`, donc `allow_failure` est faux pour lui |
| 1, 2 | échoue | échoue |

### Ce que fait chaque partie {#what-each-part-does}

Les lignes que tous les exemples GitLab ont en commun (`image`, `timeout`, `id_tokens`, les deux lignes du jeton et `artifacts`) sont dans le tableau de [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Ce tableau donne les parties propres à cet exemple :

| Partie | Ce qu’elle fait |
|---|---|
| `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"` | Le job s’exécute uniquement dans les pipelines de requêtes de fusion ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). |
| `inventag --template ci-pipeline --fail-on-account-error --fail-if-empty` | La commande de cette page plus les deux options à activer. Les codes de sortie 5 et 6 l’emportent sur 3 (l’ordre est 5, 6, 3, 4) : une exécution avec un compte qui n’a pas pu être analysé, ou sans ressource, n’est donc jamais présentée comme « sans violation ». Un appel de service qui échoue dans un compte atteint ne donne pas 5. Dans l’exécution locale, ce job s’est terminé en échec avec le code de sortie 3 et ses fichiers de rapport ont été collectés. |
| `allow_failure: exit_codes: 4` | Seul le code de sortie 4 est toléré. Avec tout autre code non nul, le job échoue comme d’habitude ([GitLab : `script`](https://docs.gitlab.com/ci/yaml/script/)). Pour bloquer la requête de fusion avec le code 4, supprimez les deux lignes. Pour lancer le job `tag-policy` en mode avertissement, donnez-lui `allow_failure:` avec `exit_codes: 3` de la même façon, ou gardez `fail_on_tag_violations: false`, comme le dit « Étapes suivantes » ([GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)). Dans l’exécution locale, `security-groups` s’est terminé avec un avertissement et le code de sortie 4. |
| `inventag --create-excel --enable-security-analysis --risk-threshold HIGH ...` | Code de sortie 4 quand une règle de groupe de sécurité est à `HIGH` ou au-dessus. `--risk-threshold` a besoin de `--enable-security-analysis`, sinon le code de sortie est 2. Il n’y a pas de `--template` ici, car `--enable-security-analysis` n’ajoute rien avec `--template` (voir la [référence de la CLI](../reference/cli.md)). Ce job analyse toutes les régions activées. |

Ce qui n’est pas vérifié :

- Non vérifié sur GitLab ni sur AWS : l’émission du jeton d’ID par GitLab et son acceptation par AWS pour le rôle, avec les conditions de la politique d’approbation sur `aud` et `sub`.
- Non vérifié sur GitLab : `image`, `timeout` et `expire_in` (gitlab-ci-local les ignore).
- Non vérifié sur GitLab : l’effet d’un job en échec, ou d’un job autorisé à échouer, sur les jobs suivants, l’état du pipeline et la requête de fusion.

### Trois choses à savoir {#three-things-to-know}

1. **La vérification lit AWS tel qu’il est maintenant. Elle ne lit pas les modifications de la requête de fusion.** Les commandes ne donnent à InvenTag rien du dépôt, hormis ses fichiers de modèle. Chaque job analyse le compte une fois : un pipeline de requête de fusion fait donc deux analyses. Par défaut, chaque exécution utilise aussi Cost Explorer, et AWS facture chaque requête Cost Explorer ; `--no-billing-validation` arrête ces appels (voir la [référence de la CLI](../reference/cli.md)).
2. **Un job en échec ne bloque la fusion que si le projet l’exige.** Activez **Settings > Merge requests > Merge checks > Pipelines must succeed**. Il faut le rôle Maintainer ou Owner ([GitLab](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)).
3. **Dans un pipeline de requête de fusion, le jeton d’ID nomme la branche source, pas `main`** ([GitLab](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). Un rôle dont la politique de confiance n’autorise que `ref:main` refuse ces jobs. Créez pour eux un second rôle en lecture seule, sans l’instruction de téléversement (`s3:PutObject`). La politique de confiance de ce cas est dans [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Toute personne qui peut pousser une branche dans le projet et ouvrir une requête de fusion peut exécuter un job avec ce rôle, et peut modifier le script du job dans sa branche. Le rôle est en lecture seule : elle peut donc lire ce qu’InvenTag peut lire. Ne réutilisez pas le rôle de vos jobs planifiés.
   - Une variable CI/CD protégée n’est transmise à un pipeline de requête de fusion que si la branche source et la branche cible sont toutes deux protégées, sont dans le même projet, et que l’utilisateur peut fusionner dans la branche cible. Elle n’est jamais transmise depuis un fork ([GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). Ne protégez donc pas `AWS_ROLE_ARN` pour ces jobs.
   - L’exemple lit `AWS_ROLE_ARN`, ce qui convient à un projet qui n’a que ces jobs de requête de fusion. Un projet qui exécute aussi des jobs planifiés avec le premier rôle a besoin d’un second nom de variable pour le second rôle. Cet exemple ne montre pas comment l’associer.

## Étapes suivantes {#next-steps}

- Commencez en mode rapport seul : définissez `fail_on_tag_violations: false` jusqu’à ce que
  les chiffres soient proches de zéro, puis activez-le.
- Ne laissez pas une exécution incomplète passer pour propre :
  `--fail-on-account-error` se termine avec le code 5 quand un compte n’a pas pu
  être analysé, et `--fail-if-empty` avec le code 6 quand aucune ressource n’a
  été trouvée. Les deux l’emportent sur le code 3.
- Utilisez vos propres règles : [Vérifier les étiquettes selon une politique](../guides/check-tag-compliance.md#write-your-own-policy).
