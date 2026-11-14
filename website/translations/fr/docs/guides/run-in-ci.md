---
title: Exécuter InvenTag en CI/CD
description: Exécutez InvenTag selon un calendrier dans GitHub Actions ou GitLab CI/CD avec des identifiants OIDC de courte durée, gardez les rapports et faites échouer le job si besoin.
sidebar_position: 7
---

# Exécuter InvenTag en CI/CD

**À qui s’adresse cette page :** vous voulez un inventaire selon un calendrier, ou un pipeline qui
échoue lorsque des ressources ne sont pas correctement étiquetées.

**Ce que vous saurez faire après lecture :** mettre en place un workflow GitHub Actions ou un pipeline GitLab CI/CD qui exécute InvenTag avec des identifiants de courte durée et conserve les rapports.

## Les éléments {#the-pieces}

1. **Des identifiants sans clés stockées.** Utilisez OpenID Connect (OIDC) : le système de CI prouve l’identité du job, et AWS lui accorde une session de rôle temporaire. Aucune
   clé d’accès ne se trouve dans les secrets de votre dépôt.
2. **Un modèle de configuration** avec vos régions, vos sorties et votre politique d’étiquetage. Le modèle
   intégré `ci-pipeline` est un bon point de départ.
3. **Un artefact** pour conserver `bom_output/`.

## 1. Laisser GitHub assumer un rôle en lecture seule {#1-let-github-assume-a-read-only-role}

Dans AWS, ajoutez GitHub comme fournisseur d’identité OIDC
(`token.actions.githubusercontent.com`) et créez un rôle avec la politique en lecture seule
de [Configurer un accès en lecture seule](./read-only-access.md). Limitez sa politique
d’approbation à votre dépôt et à votre branche. Le guide AWS
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
détaille la procédure.

## 2. Ajouter un modèle de configuration à votre dépôt {#2-add-a-config-template-to-your-repository}

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

Définissez vos régions et votre politique d’étiquetage, puis validez le fichier dans le dépôt.

## 3. Ajouter le workflow {#3-add-the-workflow}

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

Épinglez chaque action sur un SHA de commit complet, avec la version en commentaire. Cela
vous protège si une balise est déplacée vers du code malveillant. Les quatre SHA ci-dessus sont les commits des balises indiquées dans les commentaires. Mettez à jour les SHA lorsque vous mettez à jour les versions.

InvenTag s’exécute depuis le dossier de votre dépôt ; `.inventag/templates/nightly.yaml`
est donc trouvé par son nom.

Sans les deux options de code de sortie, le job réussit même si un compte n’a pas pu être analysé ou si rien n’a été trouvé.
`--fail-on-account-error` fait échouer le job avec le code 5 dans le premier cas, et `--fail-if-empty` avec le code 6 dans le second.
Les rapports sont quand même écrits, l’étape des artefacts peut donc les conserver.

## GitLab CI/CD {#gitlab-cicd}

Cette section est l’équivalent GitLab des étapes GitHub Actions ci-dessus. Le modèle de configuration de l’étape 2 est le même. Les exemples sont écrits pour GitLab.com. Une [instance auto-hébergée](#on-a-self-managed-instance) demande quelques changements.

### Laissez GitLab assumer un rôle en lecture seule {#let-gitlab-assume-a-read-only-role}

Non vérifié auprès de GitLab ni d’AWS : que GitLab émette le jeton d’ID et qu’AWS l’accepte pour le rôle, avec les conditions de la politique d’approbation sur `aud` et `sub`.

**Étape 1 : ajoutez GitLab comme fournisseur d’identité OIDC dans IAM.** Dans la console IAM, ouvrez **Identity providers > Add provider** et choisissez OpenID Connect ([AWS : créer un fournisseur d’identité OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)).

| Champ | Valeur |
|---|---|
| URL du fournisseur | `https://gitlab.com` pour GitLab.com. Pour une instance auto-hébergée, l’adresse de votre propre instance, par exemple `https://gitlab.example.com`. AWS exige une URL qui commence par `https://`. GitLab indique que l’adresse doit être accessible publiquement ([GitLab : OpenID Connect in AWS](https://docs.gitlab.com/ci/cloud_services/aws/)). |
| Audience | `sts.amazonaws.com`. Ce doit être le même texte que `aud` sous `id_tokens` dans le pipeline. |
| Empreinte | Rien à saisir. IAM la récupère, et AWS vérifie d’abord le certificat du fournisseur avec sa propre liste d’autorités de certification racine de confiance ([AWS : `create-open-id-connect-provider`](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)). |

Vous pouvez ajouter un seul fournisseur par URL et par compte AWS. Un second « add » pour la même URL échoue. Si votre compte fait déjà confiance à `gitlab.com`, ajoutez l’audience au fournisseur existant.

**Étape 2 : créez le rôle avec une politique d’approbation.** Créez un rôle pour ce fournisseur. La politique d’approbation ci-dessous permet à un projet de GitLab.com, sur une branche, d’assumer le rôle. C’est le cas des exemples planifiés, qui s’exécutent sur `main`.

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

Remplacez ces valeurs :

| Valeur | Remplacez par |
|---|---|
| `123456789012` | L’ID du compte AWS qui contient le fournisseur d’identité et le rôle. Le fournisseur et le rôle doivent être dans le même compte. |
| `gitlab.com` (quatre fois) | Gardez-le pour GitLab.com. Pour une instance auto-hébergée, utilisez le nom d’hôte de votre instance, sans `https://`. |
| `sts.amazonaws.com` | Gardez-le, sauf si vous avez choisi une autre audience à l’étape 1 et sous `id_tokens`. |
| `mygroup/myproject` | Le chemin complet du projet : groupe, sous-groupes et projet. |
| `main` | La branche sur laquelle la planification s’exécute. |
| `67890` | L’ID du projet. Cette ligne ne fonctionne que sur GitLab.com. Sur une instance auto-hébergée ou Dedicated, AWS ne prend en charge que les claims `sub` et `aud` ; supprimez donc la ligne dans ce cas. |

La claim `sub` a par défaut la forme `project_path:{group}/{project}:ref_type:{type}:ref:{branch_name}`. Un projet peut changer cette forme via l’API des projets, et la valeur ci-dessus ne correspond alors plus ([GitLab : ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). Une condition sur un ID stable comme `project_id` est recommandée, car le chemin d’un projet supprimé peut être recréé par quelqu’un d’autre ([AWS : clés de condition IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)).

Un caractère générique dans une condition demande `StringLike`. Avec `StringEquals`, AWS refuse l’appel.

**Variante : toute branche protégée (GitLab.com).** Remplacez le bloc `Condition` :

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

Non vérifié auprès d’AWS : que `"true"` soit le texte exact qu’AWS compare pour `ref_protected`. `ref_protected` et `pipeline_source` sont des clés de condition propres à GitLab.com.

**Variante : balises protégées (GitLab.com).** Le même bloc, avec `ref_type:tag:ref:*` (ou `ref_type:tag:ref:v*`) dans la ligne `sub`.

**Variante : pipelines de requête de fusion.** Le jeton d’un pipeline de requête de fusion porte la branche source ; le rôle doit donc accepter toutes les branches du projet :

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

Non vérifié auprès de GitLab : le texte exact de `sub` dans un pipeline de requête de fusion.

Avec cette variante, toute personne qui peut pousser une branche dans le projet et ouvrir une requête de fusion peut exécuter un job avec ce rôle, et peut modifier le script du job dans sa branche. Le rôle est en lecture seule, ces personnes peuvent donc lire ce qu’InvenTag peut lire. Utilisez un rôle distinct pour cette variante. Ne réutilisez pas le rôle des jobs planifiés, et ne lui donnez pas `s3:PutObject`. Voir [l’exemple de politique de balises](../examples/tag-policy-in-ci.md#gitlab-cicd).

**Étape 3 : attachez la politique en lecture seule.** Attachez la politique de [Configurer l’accès en lecture seule](./read-only-access.md) : l’option 2, `config/defaults/iam-policy-read-only.json`, ou l’option 1 (`ReadOnlyAccess` plus trois actions).

- Pour l’exemple d’envoi, gardez l’instruction `OptionalS3ReportUpload` et mettez le nom de votre bucket à la place de `YOUR-REPORTS-BUCKET-NAME`. Sa ressource se termine par `bom-reports/*` ; le préfixe de clé doit donc être `bom-reports/` (la valeur par défaut), sinon vous changez la ressource. Avec `aws:kms`, autorisez aussi `kms:GenerateDataKey` sur la clé ([Autorisations IAM](../reference/iam-permissions.md)). Voir [Téléverser les rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md). Pour les autres exemples, supprimez l’instruction.
- Pour l’exemple avec plusieurs comptes, le rôle a aussi besoin de `sts:AssumeRole` sur le rôle `InvenTagReadOnly` de chaque compte, et chacun de ces rôles fait confiance à ce rôle. Le fichier de politique du dépôt n’a pas d’instruction `sts:AssumeRole`. Voir [Configurer l’accès en lecture seule](./read-only-access.md) et [Analyser plusieurs comptes](./scan-multiple-accounts.md).

InvenTag reste en lecture seule. Ni le rôle ni le pipeline ne rendent un compte conforme à quoi que ce soit.

#### Sur une instance auto-hébergée {#on-a-self-managed-instance}

Non vérifié auprès d’une instance GitLab auto-hébergée : ce paragraphe. L’URL du fournisseur et les clés de condition utilisent le nom d’hôte de votre instance. Dans ce cas AWS ne prend en charge que les claims `sub` et `aud`, la ligne `project_id` disparaît donc. Il n’y a pas non plus de clé `ref_protected` dans AWS dans ce cas ; épinglez chaque branche par son nom. AWS doit pouvoir joindre l’instance depuis Internet ; GitLab décrit un contournement pour une instance non publique et le qualifie d’avancé ([GitLab : configure a non-public GitLab instance](https://docs.gitlab.com/ci/cloud_services/aws/)). Le runner doit pouvoir exécuter des images de conteneur.

### Ajoutez la variable CI/CD {#add-the-cicd-variable}

Dans votre projet GitLab, ouvrez **Settings > CI/CD > Variables > Add variable** (rôle Maintainer). Utilisez la clé `AWS_ROLE_ARN` et, comme valeur, l’ARN du rôle, par exemple `arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly`. GitLab transmet la variable au job comme variable d’environnement ([GitLab : CI/CD variables](https://docs.gitlab.com/ci/variables/)).

- Pour les exemples planifiés, cochez **Protect variable** et protégez la branche. La variable n’atteint alors que les pipelines des branches ou balises protégées.
- Pour l’exemple de requête de fusion, ne protégez pas la variable. Une variable protégée n’est pas transmise à un pipeline de requête de fusion, sauf si la branche source et la branche cible sont toutes deux protégées ([GitLab : merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)). Avec deux rôles, utilisez un second nom de variable dans les deux jobs de cet exemple.
- Depuis GitLab 18.3, GitLab met par défaut une nouvelle variable en **Masked**, et une valeur masquée doit tenir sur une ligne, faire au moins 8 caractères et ne pas contenir d’espaces. Un ARN de rôle n’est pas un secret. Choisissez **Visible** si GitLab refuse de masquer la valeur. Non vérifié auprès de GitLab : que GitLab accepte un ARN de rôle comme valeur masquée.
- L’exemple d’envoi demande deux variables de plus, `INVENTAG_REPORTS_BUCKET` et `INVENTAG_KMS_KEY_ID`. Aucune n’est un secret.

### Ajoutez le pipeline {#add-the-pipeline}

Ce job exécute InvenTag chaque nuit et conserve les rapports comme artefacts du job. Il a besoin de `.inventag/templates/nightly.yaml` de l’étape 2. Ajoutez le fichier à la racine de votre dépôt sous le nom `.gitlab-ci.yml`. Si le fichier a déjà des `stages`, ajoutez le nom de l’étape à cette liste.

Non vérifié auprès d’un runner GitLab ni d’un compte AWS réel : ce pipeline n’a pas été exécuté sur GitLab. Son YAML et sa ligne de commande `inventag` sont vérifiés à la construction de la documentation. Son job a été exécuté en local avec gitlab-ci-local 4.77.1 (avec un substitut de rsync) contre un AWS simulé, avec un jeton factice.

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

Ce que fait chaque partie :

| Partie | Ce qu’elle fait |
|---|---|
| `stages:` et `stage:` | Déclarent l’étape et y placent le job. Un job sans `stage` va dans `test` ([GitLab : `stages`](https://docs.gitlab.com/ci/yaml/#stages)). |
| `image: python:3.12` | Le job s’exécute dans cette image de conteneur, de la forme `<image-name>:<tag>`. InvenTag a besoin de Python 3.11 ou plus récent, et l’exemple GitHub utilise 3.12 ([GitLab : `image`](https://docs.gitlab.com/ci/yaml/#image)). |
| `rules:` avec `schedule` et `web` | Le job n’est ajouté qu’aux pipelines planifiés et à ceux lancés avec **New pipeline** dans l’interface GitLab. Dans tout autre pipeline (push, requête de fusion), aucune règle ne correspond et le job n’est pas ajouté ([GitLab : job rules](https://docs.gitlab.com/ci/jobs/job_rules/)). |
| `timeout: 2 hours` | Arrête le job après ce délai ([GitLab : `timeout`](https://docs.gitlab.com/ci/yaml/#timeout)). Il fixe aussi la durée de vie du jeton d’ID : GitLab fait expirer le jeton au délai du job s’il y en a un, et au bout de 5 minutes sinon ([GitLab : ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)). InvenTag échange le jeton plus d’une fois par exécution (vérifié en local contre un AWS simulé) ; définissez donc toujours `timeout`. Les runners hébergés par GitLab sur GitLab.com arrêtent chaque job au bout de 3 heures ([GitLab : hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)). |
| `id_tokens:` | GitLab crée un jeton d’ID OIDC (un JSON Web Token) pour ce job, avec l’audience dans `aud`. Le script le lit sous le nom `$GITLAB_OIDC_TOKEN`. Il est disponible dans les offres Free, Premium et Ultimate, sur GitLab.com, Self-Managed et Dedicated ([GitLab : `id_tokens`](https://docs.gitlab.com/ci/yaml/#id_tokens)). |
| `AWS_DEFAULT_REGION` | La région que le SDK AWS utilise pour l’appel de connexion. Définissez cette variable : `AWS_REGION` seule ne suffit pas, car botocore, le SDK AWS pour Python, ne la lit pas (vérifié en local). |
| `pip install "inventag-aws==..."` | Installe une version figée d’InvenTag. |
| Les deux lignes avec `AWS_WEB_IDENTITY_TOKEN_FILE` | Écrivent le jeton dans un nouveau fichier privé, hors du dossier du projet, et indiquent au SDK AWS où il se trouve. Avec `AWS_ROLE_ARN` (la variable CI/CD), le SDK échange lui-même le jeton contre des identifiants temporaires ([AWS : assume role credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)). Ni AWS CLI ni clé d’accès ne sont nécessaires. Un fichier hors du dossier du projet ne peut pas devenir un artefact ni une entrée de cache, car les deux n’acceptent que des chemins dans le dossier du projet ([GitLab : `artifacts:paths`](https://docs.gitlab.com/ci/yaml/#artifactspaths), [GitLab : caching](https://docs.gitlab.com/ci/caching/)). Vérifié en local contre un AWS simulé : le fichier a le mode 600 et le SDK se connecte avec le jeton. |
| `PIP_CACHE_DIR` et `cache:` | Conservent le cache de téléchargement de pip entre les jobs. Le cache doit être dans le dossier du projet, car GitLab ne met en cache que les chemins qui s’y trouvent ([GitLab : caching examples](https://docs.gitlab.com/ci/caching/examples/)). Facultatif : le job fonctionne sans ces lignes. |
| `inventag --template nightly --fail-on-account-error --fail-if-empty` | La même commande que dans le workflow GitHub. Code de sortie 3 quand la politique de balises trouve des violations et que le modèle indique `fail_on_tag_violations: true`, 5 quand un compte n’a pas pu être analysé, et 6 quand aucune ressource n’a été trouvée. Tout code de sortie autre que 0 fait échouer le job ([GitLab : `script`](https://docs.gitlab.com/ci/yaml/script/)). En local (avec un substitut de rsync), le job s’est terminé avec le code de sortie 3 et les quatre fichiers de rapport ont été collectés. |
| `artifacts:` | Envoie `bom_output/` comme artefacts du job. Avec `when: always`, GitLab les envoie aussi quand le job échoue ; sans cela, seulement quand le job réussit. `always` ne couvre pas un job qui dépasse son délai. `expire_in` indique combien de temps GitLab les conserve. GitLab conserve les artefacts du dernier pipeline d’une ref quel que soit `expire_in` (réglage par défaut du projet) ([GitLab : `artifacts:when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [GitLab : `artifacts:expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in), [GitLab : job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)). `expire_in: 30 days` correspond à `retention-days: 30` du workflow GitHub. InvenTag écrit les rapports avant de se terminer avec le code 3, 4 ou 5. |
| L’ARN du rôle | Pas dans le YAML. C’est la variable CI/CD `AWS_ROLE_ARN` de l’étape précédente. |

Deux autres parties de cet exemple ne sont pas vérifiées :

- Non vérifié auprès de GitLab : `image`, `timeout`, `expire_in` et `cache` (gitlab-ci-local les ignore).
- Non vérifié auprès d’une planification de pipeline GitLab : l’exécution en local a défini la source du pipeline à la main.

### Planifiez-le {#schedule-it}

La planification n’est pas dans le fichier. Créez-la dans GitLab : ouvrez **Build > Pipeline schedules > New schedule**, saisissez un motif cron (par exemple `17 2 * * 1-5`) et la branche cible, puis enregistrez. Il faut le rôle Developer ou supérieur. Le pipeline s’exécute avec les droits du propriétaire de la planification ([GitLab : pipeline schedules](https://docs.gitlab.com/ci/pipelines/schedules/)). Pour lancer le job à la main, choisissez **New pipeline** dans l’interface GitLab, ou **Run** sur la planification.

Non vérifié auprès de GitLab : le fuseau horaire qu’une planification de pipeline utilise pour le motif cron.

### Ce qui change par rapport à GitHub Actions {#what-differs-from-github-actions}

La colonne GitHub ne décrit que ce que montre le workflow GitHub ci-dessus.

| Sujet | GitHub Actions | GitLab CI/CD |
|---|---|---|
| Fichier | `.github/workflows/inventory.yml` | `.gitlab-ci.yml` à la racine du dépôt |
| Planification | `on: schedule: - cron:` dans le fichier | Pas dans le fichier. Une planification de pipeline dans l’interface GitLab (**Build > Pipeline schedules**), et une ligne `rules` qui fait entrer le job dans les pipelines planifiés |
| Lancer à la main | `workflow_dispatch` | **New pipeline** dans l’interface (`$CI_PIPELINE_SOURCE == "web"`), ou **Run** sur la planification |
| Demander un jeton OIDC | `permissions: id-token: write` | `id_tokens:` sur le job, avec l’audience dans `aud` |
| Obtenir des identifiants AWS | L’action `aws-actions/configure-aws-credentials` | Aucune action. Deux lignes du script écrivent le jeton dans un fichier, et le SDK AWS dans InvenTag l’échange (`AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE`) |
| ARN du rôle | Dans le YAML (`role-to-assume`) | Une variable CI/CD `AWS_ROLE_ARN`, pas dans le YAML |
| Région | `aws-region: us-east-1` | `AWS_DEFAULT_REGION: us-east-1`. `AWS_REGION` seule ne suffit pas |
| Fournisseur d’identité dans AWS | `token.actions.githubusercontent.com` | `gitlab.com`, ou l’hôte de votre propre instance |
| Ce que fixe la politique d’approbation | Le dépôt et la branche | La claim `sub` : chemin du projet, type de ref et nom de ref. Sur GitLab.com aussi l’ID du projet |
| Durée de vie du jeton | Non indiquée sur cette page | Le `timeout` du job ; 5 minutes si le job n’en définit pas. Définissez toujours `timeout` |
| Python | `actions/setup-python` avec `python-version: "3.12"` | `image: python:3.12` |
| Figer les versions | Chaque action par SHA de commit complet | L’image par balise de version mineure. Un digest d’image (`<image-name>@<digest>`) est la forme plus stricte ; les exemples ne l’utilisent pas ([GitLab : `image`](https://docs.gitlab.com/ci/yaml/#image)) |
| Conserver les rapports | `actions/upload-artifact` avec `if: always()` et `retention-days: 30` | `artifacts:` avec `when: always` et `expire_in: 30 days`. Pas envoyés si le job dépasse son délai. L’artefact contient aussi `bom_output/state/` |
| Tolérer un code de sortie | Non montré sur cette page | `allow_failure: exit_codes:` sur le job ([GitLab : `allow_failure:exit_codes`](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)) |
| Durée maximale d’un job | Non indiquée sur cette page | 3 heures sur les runners hébergés par GitLab de GitLab.com ([GitLab : hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)) |
| Exécutions pour requêtes de fusion ou pull requests | Non montré sur cette page | Le jeton porte la branche source, et les variables protégées ne sont transmises que dans les conditions de GitLab. Voir [l’exemple de politique de balises](../examples/tag-policy-in-ci.md#gitlab-cicd) |
| Résumé du job | `$GITHUB_STEP_SUMMARY` (dans [l’exemple de politique de balises](../examples/tag-policy-in-ci.md)) | Non utilisé dans ces exemples |

## Ce qui se passe en cas de violation {#what-happens-on-a-violation}

Avec `fail_on_tag_violations: true`, InvenTag écrit d’abord tous les rapports, puis
se termine avec le code 3. Le job échoue, et l’artefact contient toujours le fichier Excel
et `tag_compliance_<timestamp>.json` avec chaque ressource non conforme.

Exemple de sortie de `inventag --template ci-pipeline` d’une exécution hors ligne
(données d’exemple) :

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

## Codes de sortie {#exit-codes}

| Code de sortie | Signification |
|---|---|
| 0 | Rapports écrits, aucune violation d’étiquette (ou aucune politique bloquante). Aussi quand un compte a échoué ou que rien n’a été trouvé, sauf si vous passez les options des codes 5 et 6 |
| 1 | Erreur : modèle ou fichier de configuration invalide, identifiants, échec de tous les comptes, format de rapport impossible à écrire, ou échec d’un téléversement S3 |
| 2 | Options invalides ou en conflit, par exemple `--accounts-file` avec `--accounts-prompt`, ou `--compliance-standard` (non implémentée). Rien n’est analysé |
| 3 | Rapports écrits, violations de la politique d’étiquetage trouvées (`fail_on_tag_violations: true`) |
| 4 | Rapports écrits, une règle de groupe de sécurité ouverte à Internet atteint ou dépasse `--risk-threshold` |
| 5 | Rapports écrits, un compte n’a pas pu être analysé, ou seulement en partie (`--fail-on-account-error`) |
| 6 | Aucune ressource à signaler (`--fail-if-empty`) |

Si plusieurs codes s’appliquent, le 5 passe en premier, puis le 6, puis le 3, puis le 4, car les données derrière un résultat d’étiquettes ou de risque sont incomplètes quand un compte manque.
Des rapports sont écrits pour les codes 3, 4 et 5. Avec le code 6, une exécution avec `--template` écrit un rapport qui ne liste aucune ressource, et une exécution sans elle n’écrit aucun fichier.

## Rester prudent {#keep-it-safe}

- Évitez `--debug` en CI. Les secrets sont masqués dans les journaux de débogage, mais ces journaux sont
  longs et décrivent tout de même vos comptes.
- Pour conserver les rapports dans S3 plutôt que (ou en plus) des artefacts, ajoutez
  `--s3-bucket` et accordez `s3:PutObject` sur ce bucket. Voir
  [Téléverser les rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md).
- Gardez le rôle en lecture seule et limité au dépôt et à la branche qui en ont
  besoin.
- Dans GitLab CI/CD, protégez la branche qui exécute le pipeline, limitez la politique d’approbation du rôle à cette branche et gardez l’ARN du rôle dans une variable CI/CD. Voir [GitLab CI/CD](#gitlab-cicd).
- Épinglez InvenTag sur une version publiée (`inventag-aws==%INVENTAG_VERSION%`), pas sur la dernière version. Augmentez le numéro quand vous choisissez de mettre à jour.

## Étapes suivantes {#next-steps}

- [Exemple : appliquer une politique d’étiquetage en CI](../examples/tag-policy-in-ci.md)
- [Suivre les changements entre deux exécutions](./track-changes.md)
