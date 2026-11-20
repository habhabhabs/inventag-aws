---
title: Configurer un accès en lecture seule
description: Donnez à InvenTag une identité AWS en lecture seule, au moindre privilège, avec IAM Identity Center ou un rôle IAM, et vérifiez qu’elle ne peut rien modifier.
sidebar_position: 2
slug: /user-guides/production-safety
---

# Configurer un accès en lecture seule

**À qui s’adresse cette page :** à la personne qui crée l’identité AWS sous laquelle InvenTag s’exécute.

**Ce que vous saurez faire après lecture :** créer une identité en lecture seule pour InvenTag
et confirmer qu’elle ne peut pas modifier vos ressources.

## Pourquoi c’est important {#why-this-matters}

InvenTag n’a besoin que d’un accès en lecture, plus `s3:PutObject` si vous téléversez des rapports avec `--s3-bucket`. Il possède sa propre protection en lecture seule, qui bloque
tout appel AWS qui n’est pas une lecture avant son envoi. Votre politique IAM est un
second filet de sécurité, indépendant : si un bogue venait à contourner la protection, AWS
refuserait quand même l’appel. Ne donnez à InvenTag rien de plus que ce dont il a besoin.

Non vérifié sur un vrai AWS : qu’une politique IAM en lecture seule refuse un appel qui contourne la protection.

## Option 1 : la politique gérée AWS ReadOnlyAccess plus trois ajouts (la plus simple) {#option-1-aws-managed-readonlyaccess-plus-three-extras-simplest}

1. Attachez la politique gérée AWS `ReadOnlyAccess`.
2. Ajoutez cette politique en ligne pour les appels que `ReadOnlyAccess` peut ne pas couvrir :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    }
  ]
}
```

| Action | Pourquoi InvenTag en a besoin |
|---|---|
| `tag:GetResources` | Trouve les ressources étiquetées via l’API Resource Groups Tagging (son préfixe IAM est `tag`). |
| `ce:GetCostAndUsage` | Trouve les services qui ont des dépenses. |
| `ec2:DescribeRegions` | Liste les régions activées dans le compte. |

AWS facture chaque requête Cost Explorer : voir la [tarification de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

InvenTag appelle aussi `account:ListRegions`, mais seulement quand `ec2:DescribeRegions` échoue, pour lire les régions activées.
Ajoutez-la si vous voulez ce repli.

Ajoutez `pricing:GetProducts` uniquement si vous utilisez `--enable-cost-analysis` (cette option
appelle aussi `cloudwatch:GetMetricStatistics`, que `ReadOnlyAccess` couvre), et
`s3:PutObject` sur votre bucket de rapports si vous utilisez `--s3-bucket`.

Pour exécuter avec `ReadOnlyAccess` seul, voir [Exécuter avec ReadOnlyAccess seul](#run-with-only-readonlyaccess).

`ReadOnlyAccess` est large : elle peut lire des données comme les listes d’objets S3 et
certaines configurations qu’InvenTag ne consulte jamais. Si c’est trop pour votre
organisation, utilisez l’option 2.

Non vérifié sur AWS : ce que la politique gérée `ReadOnlyAccess` autorise aujourd’hui, et lesquels de ces appels elle couvre.

## Option 2 : la politique plus restreinte du dépôt {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` liste 122 actions de lecture précises,
dont `tag:GetResources`, `ce:GetCostAndUsage` et `pricing:GetProducts`, et `apigateway:GET` pour les métadonnées d’API seulement (pas les clés d’API).
Elle est générée à partir de la même liste que celle utilisée par le code ; elle correspond donc à ce
qu’InvenTag appelle. Elle inclut les actions des services qu’InvenTag liste avec ses propres appels,
et `ec2:DescribeRouteTables` et `ec2:DescribeNetworkInterfaces` pour l’
[analyse réseau et de sécurité](./network-and-security-analysis.md#permissions).
Si vous avez copié une ancienne version du fichier, copiez-la de nouveau. Une action manquante n’arrête pas l’exécution, mais ce service ou ce détail est absent.

Non vérifié sur un vrai AWS : que l’instruction `apigateway:GET` garde les valeurs des clés d’API hors de portée.

Son instruction `OptionalS3ReportUpload` autorise `s3:PutObject` avec le chiffrement
côté serveur, pour `--s3-bucket`. Remplacez `YOUR-REPORTS-BUCKET-NAME` par votre
bucket, ou supprimez l’instruction si vous ne téléversez pas de rapports.

Non vérifié sur un vrai AWS : que l’instruction n’autorise le téléversement qu’avec le chiffrement côté serveur.

Lorsqu’une action de listage manque, InvenTag journalise un avertissement pour ce service et continue sans ses ressources :

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Lorsqu’une action pour un détail d’une ressource manque, la découverte continue et laisse ce détail vide.

## Exécuter avec ReadOnlyAccess seul {#run-with-only-readonlyaccess}

Vous pouvez attacher à l’identité seulement la politique gérée AWS `ReadOnlyAccess` et n’ajouter rien d’autre. Cette section dit ce qui fonctionne, ce qui ne fonctionne pas, et ce qu’InvenTag affiche quand AWS refuse une action.

La liste de politique de cette section est PROVISOIRE. Le projet teste InvenTag avec une liste des actions de `ReadOnlyAccess` qu’il a écrite à la main d’après la page de référence d’AWS (version de la politique v192, 13 novembre 2026). La liste reste provisoire tant que le projet n’a pas une copie brute de la politique AWS. Non vérifié sur un vrai AWS : que la liste soit ce que `ReadOnlyAccess` autorise aujourd’hui, et une analyse avec seulement `ReadOnlyAccess` attachée.

### Ce qui fonctionne {#what-works}

D’après la liste provisoire, `ReadOnlyAccess` inclut les 122 actions de lecture de `config/defaults/iam-policy-read-only.json` et `apigateway:GET`. Parmi elles figurent `tag:GetResources`, `ce:GetCostAndUsage` et `ec2:DescribeRegions`. Les trois ajouts de l’option 1 sont donc une précaution, pas un besoin.

Dans les tests, une analyse d’un compte avec seulement ces actions se termine avec le code 0. AWS ne refuse aucun appel. Le journal n’a pas l’avertissement `No permission for`, et chaque ressource créée par le test est dans le rapport. C’est vrai avec `--create-excel --create-word`, et aussi quand vous ajoutez `--enable-network-analysis`, `--enable-security-analysis`, `--enable-cost-analysis` et la validation de la facturation.

### Trois actions que ReadOnlyAccess n’inclut pas {#three-actions-that-readonlyaccess-does-not-include}

| Action | Nécessaire seulement pour | Ce qui se passe sans elle |
|---|---|---|
| `sts:AssumeRole` | Analyser d’autres comptes par un rôle (`role_arn`, ou `--cross-account-role`) | Ce compte échoue. InvenTag analyse les autres comptes. L’exécution se termine avec le code 0, ou avec le code 5 si vous passez `--fail-on-account-error`. |
| `s3:PutObject` | Envoyer les rapports avec `--s3-bucket` | L’envoi échoue, et les rapports restent dans le dossier de sortie local. L’exécution se termine avec le code 1. |
| `kms:GenerateDataKey` | Envoyer les rapports avec `--s3-encryption aws:kms` et une clé KMS | Non testé. |

Non vérifié sur un vrai AWS : qu’un `kms:GenerateDataKey` refusé arrête l’envoi, et quelle action S3 nomme alors. Avec un AWS simulé, l’envoi en échec est nommé seulement `s3:PutObject`.

### Ce qui peut encore refuser un appel {#what-else-can-refuse-a-call}

Une identité avec `ReadOnlyAccess` peut encore être refusée. Voici les causes qu’InvenTag ne peut pas distinguer entre elles :

- une politique de contrôle de service ou une limite de permissions
- la politique d’une ressource, par exemple la politique d’une clé KMS ou d’un bucket
- une région ou un service qui n’est pas activé pour le compte
- une version plus récente de `ReadOnlyAccess`, parce qu’AWS modifie la politique

Non vérifié sur un vrai AWS : ces causes, et lesquelles AWS signale comme accès refusé.

La politique du dépôt de l’option 2 est le choix qui donne le moins de droits. `ReadOnlyAccess` est plus large que ce dont InvenTag a besoin, par exemple `s3:Get*`. La protection en lecture seule refuse quand même les appels qui renvoient le contenu d’objets ou des secrets, quoi que la politique autorise.

### Quand une action est refusée {#when-an-action-is-refused}

Aucune action refusée n’arrête l’exécution. Voici ce que fait l’exécution :

| Refusé | Ce que fait l’exécution |
|---|---|
| `sts:AssumeRole` pour un compte | Le compte échoue avec sa raison. Les autres comptes sont analysés. |
| `ec2:DescribeRegions` | InvenTag interroge `account:ListRegions`. Si cet appel échoue aussi, il analyse toutes les régions. |
| Un listage d’un service | Un avertissement pour le service. Les notes d’exécution disent `Not read`. Le prochain rapport de changements laisse ce listage de côté. |
| Un appel de détail d’une ressource | La ligne reste, et le détail est vide. Une note d’exécution compte les ressources. |
| `tag:GetResources` | Un avertissement. L’analyse continue avec les listages des services. |
| `ce:GetCostAndUsage` | Un avertissement. Les vérifications de facturation sont ignorées. |
| `pricing:GetProducts` avec `--enable-cost-analysis` | Un avertissement. Les estimations de coûts manquent. |
| `s3:PutObject` avec `--s3-bucket` | L’envoi échoue. Code de sortie 1. |

Quand seul `sts:GetCallerIdentity` est autorisé, l’exécution se termine. Elle n’écrit ni rapport ni instantané, et le journal dit `No resources to report: nothing could be read`. Le code de sortie est 0. Avec `--fail-on-account-error`, un compte dont tous les listages ont été refusés compte quand même comme analysé, et l’exécution se termine avec le code 0. Pour qu’un job de CI échoue quand rien n’a pu être lu, ajoutez `--fail-if-empty`.

### La ligne Permissions et permissions_denied {#the-permissions-line-and-permissions_denied}

Quand une exécution n’a pas le droit d’utiliser une action IAM, les notes d’exécution ont une ligne par compte. La ligne est dans la console et dans les « Run notes » du rapport Excel. Elle nomme chaque action, dit ce qui manque au rapport, et dit si `ReadOnlyAccess` inclut l’action. Une exécution à laquelle rien n’est refusé n’affiche pas cette ligne. Voici la ligne pour un rôle qui ne peut pas être assumé (exemple d’une exécution hors ligne) :

```text
Permissions: 1 action(s) were not allowed for account 222222222222: sts:AssumeRole. Effect: the account was not scanned. sts:AssumeRole is not in ReadOnlyAccess; it is needed only for scanning other accounts through a role.
```

La ligne a les mots propres d’InvenTag. Elle n’a aucun texte de l’erreur AWS. Un appel dont InvenTag ne connaît pas l’action IAM est nommé par son nom d’API, avec les mots `(IAM action not known to InvenTag)`.

L’envoi des rapports avec `--s3-bucket` utilise les identifiants par défaut, pas ceux d’un compte analysé. Quand S3 le refuse, la ligne ne nomme aucun compte. Elle nomme l’identité qui envoie les rapports (exemple des tests) :

```text
Permissions: 1 action(s) were not allowed for the identity that uploads the reports (the default credentials): s3:PutObject. Effect: the reports were not uploaded. s3:PutObject is not in ReadOnlyAccess; it is needed only for uploading the reports (--s3-bucket).
```

Avec `--audit-output`, le fichier a aussi la clé `permissions_denied`. La clé est là seulement quand quelque chose a été refusé. Chaque entrée a ces champs :

```json
{
  "permissions_denied": [
    {
      "account": "123456789012",
      "action": "s3:GetBucketLocation",
      "service": "s3",
      "operation": "GetBucketLocation",
      "regions": ["us-east-1"],
      "kind": "detail"
    }
  ]
}
```

| Champ | Sens |
|---|---|
| `account` | L’ID du compte. Vide pour le type `upload` : l’envoi utilise les identifiants par défaut, pas ceux d’un compte analysé. |
| `action` | L’action IAM, ou `null` quand InvenTag ne la connaît pas. |
| `service`, `operation` | Les noms d’API AWS de l’appel refusé. |
| `regions` | Les régions où l’appel a été refusé. Vide pour une entrée sans région, par exemple le type `role`. |
| `kind` | `role`, `listing`, `detail`, `tagging`, `billing`, `pricing`, `analysis` ou `upload`. |

La liste est triée par compte et par action. InvenTag ne fait aucun appel AWS supplémentaire pour la construire. Non vérifié sur un vrai AWS : les actions nommées sont celles des tables propres d’InvenTag, et un refus par une politique de contrôle de service ou une limite de permissions est aussi affiché comme l’action.

La ligne ne nomme pas `ec2:DescribeRegions` ni `account:ListRegions`. Voir [État des fonctionnalités](../getting-started/status.md#when-a-run-goes-wrong).

## Ce que bloque la protection en lecture seule {#what-the-read-only-guard-blocks}

InvenTag vérifie chaque appel AWS du processus avant son envoi. Il n’autorise que les opérations dont le nom commence par `List`, `Describe`, `Get`, `Head`,
`Lookup`, `Search` ou `BatchGet`, plus `sts:AssumeRole` pour atteindre d’autres comptes. Elle ne peut pas être désactivée.

Certaines opérations ressemblent à des lectures mais renvoient des secrets ou des données clients. La protection les bloque aussi, pour qu’une politique large ne puisse pas les exposer via InvenTag.
Exemples : `secretsmanager:GetSecretValue`, `ssm:GetParameter`, `s3:GetObject`, `dynamodb:GetItem`, `lambda:GetFunction` (il renvoie un lien de téléchargement du code),
`cloudformation:GetTemplate`, `ec2:GetLaunchTemplateData`, `glue:GetConnection` et les résultats de requêtes Athena.
Elle bloque aussi les clés d’API avec leurs valeurs et `ec2:DescribeInstanceAttribute` pour les données utilisateur, et vérifie les URL présignées et les jetons d’authentification de base de données selon les mêmes règles.
La protection connaît les opérations par leur nom. Une opération qu’ajoute un SDK AWS plus récent est autorisée quand son nom commence comme une lecture, jusqu’à ce qu’une version d’InvenTag la nomme. Vérifiez un nom avec `inventag --validate-operations <service>:<Operation>`. Quand la réponse dépend d’un paramètre, la commande nomme la règle : `apigateway:GetApiKeys` affiche `ALLOWED` avec `blocked when includeValues=true`, et `ec2:DescribeInstanceAttribute` affiche `ALLOWED` avec `blocked when Attribute=userdata`. La protection ne bloque ces appels que lorsqu’ils sont faits avec ce paramètre.

Les profils IAM Identity Center (SSO) et d’identité web fonctionnent avec la protection active. La protection laisse l’étape de connexion échanger un jeton contre des identifiants, et rien d’autre.

Non vérifié sur AWS IAM Identity Center : la connexion avec un vrai profil SSO ou d’identité web.

Deux fonctions de la bibliothèque Python peuvent écrire dans AWS quand vous les appelez depuis votre propre code. La commande `inventag` ne les appelle jamais, et la protection les bloque lors d’une exécution de la commande.
`CredentialManager.setup_cross_account_roles()` crée des rôles IAM et ne s’exécute qu’avec `allow_iam_writes=True`.
La fonction d’aide au cycle de vie S3 modifie les règles du bucket et ne s’exécute qu’avec `allow_bucket_writes=True`.

## Avec IAM Identity Center (SSO) {#with-iam-identity-center-sso}

Créez un jeu d’autorisations qui contient la politique, puis affectez-le à chaque compte
que vous voulez analyser :

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

Non vérifié sur un vrai AWS : les commandes `aws sso-admin` et le jeu d’autorisations qu’elles créent.

Non vérifié sur AWS : ce que la politique gérée `ReadOnlyAccess` autorise aujourd’hui, et lesquels de ces appels elle couvre.

Connectez-vous ensuite avec `aws sso login --profile <profile>` et lancez InvenTag avec
`AWS_PROFILE=<profile>`.

Non vérifié sur l’AWS CLI : les commandes de connexion de cette section.

## Avec un rôle IAM dans chaque compte {#with-an-iam-role-in-each-account}

Pour des analyses sur de nombreux comptes, créez un rôle portant le même nom, par exemple
`InvenTagReadOnly`, dans chaque compte. Attachez-lui la politique, et laissez seule votre
identité d’analyse l’assumer. Une politique d’approbation pour cela ressemble à ceci :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::999999999999:role/InvenTagScanner" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Remplacez `999999999999:role/InvenTagScanner` par l’identité qui exécute
InvenTag. L’identité d’analyse elle-même n’a besoin que de `sts:AssumeRole` sur ces
rôles.

Non vérifié sur un vrai AWS : que la politique d’approbation et `sts:AssumeRole` suffisent à elles seules pour l’analyse.

## Vérifier qu’elle ne peut pas écrire {#check-that-it-cannot-write}

Utilisez le simulateur de politiques IAM pour confirmer qu’une écriture est refusée :

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Les deux doivent afficher `implicitDeny` ou `explicitDeny`.

Non vérifié sur un vrai AWS : le résultat du simulateur de politiques pour ces deux actions.

Vous pouvez aussi demander à la protection d’InvenTag quelles opérations elle autoriserait (exemple de
sortie d’une exécution hors ligne) :

```text title="Sortie"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

Pour voir ce qu’une vraie exécution a appelé, ajoutez `--audit-output audit.json`. Un extrait
d’une exécution hors ligne (données d’exemple) :

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 96,
  "allowed_calls": 96,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## Après un incident de sécurité {#after-a-security-incident}

Si vous soupçonnez que vos identifiants ou une dépendance ont été compromis, faites tourner ou
révoquez les identifiants qu’InvenTag a utilisés, vérifiez dans AWS CloudTrail les appels inattendus
provenant de cette identité, et maintenez l’identité en lecture seule. Plus de détails sur la page
[Sécurité](../security/index.md).

## Étapes suivantes {#next-steps}

- [Référence des autorisations IAM](../reference/iam-permissions.md)
- [Analyser plusieurs comptes](./scan-multiple-accounts.md)
