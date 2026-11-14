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

InvenTag n’a besoin que de lire. Il possède sa propre protection en lecture seule, qui bloque
tout appel AWS qui n’est pas une lecture avant son envoi. Votre politique IAM est un
second filet de sécurité, indépendant : si un bogue venait à contourner la protection, AWS
refuserait quand même l’appel. Ne donnez à InvenTag rien de plus que ce dont il a besoin.

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
| `ce:GetCostAndUsage` | Trouve les services qui ont des dépenses. AWS facture chaque requête. |
| `ec2:DescribeRegions` | Liste les régions activées dans le compte. |

InvenTag appelle aussi `account:ListRegions`, mais seulement quand `ec2:DescribeRegions` échoue, pour lire les régions activées.
Ajoutez-la si vous voulez ce repli.

Ajoutez `pricing:GetProducts` uniquement si vous utilisez `--enable-cost-analysis` (cette option
appelle aussi `cloudwatch:GetMetricStatistics`, que `ReadOnlyAccess` couvre), et
`s3:PutObject` sur votre bucket de rapports si vous utilisez `--s3-bucket`.

`ReadOnlyAccess` est large : elle peut lire des données comme les listes d’objets S3 et
certaines configurations qu’InvenTag ne consulte jamais. Si c’est trop pour votre
organisation, utilisez l’option 2.

## Option 2 : la politique plus restreinte du dépôt {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` liste 122 actions de lecture précises,
dont `tag:GetResources`, `ce:GetCostAndUsage` et `pricing:GetProducts`, et `apigateway:GET` pour les métadonnées d’API seulement (pas les clés d’API).
Elle est générée à partir de la même liste que celle utilisée par le code ; elle correspond donc à ce
qu’InvenTag appelle. Elle inclut les actions des services qu’InvenTag liste avec ses propres appels,
et `ec2:DescribeRouteTables` et `ec2:DescribeNetworkInterfaces` pour l’
[analyse réseau et de sécurité](./network-and-security-analysis.md#permissions).
Si vous avez copié une ancienne version du fichier, copiez-la de nouveau. Une action manquante n’arrête pas l’exécution, mais ce service ou ce détail est absent.

Son instruction `OptionalS3ReportUpload` autorise `s3:PutObject` avec le chiffrement
côté serveur, pour `--s3-bucket`. Remplacez `YOUR-REPORTS-BUCKET-NAME` par votre
bucket, ou supprimez l’instruction si vous ne téléversez pas de rapports.

Lorsqu’une action de listage manque, InvenTag journalise un avertissement pour ce service et continue sans ses ressources :

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Lorsqu’une action pour un détail d’une ressource manque, la découverte continue et laisse ce détail vide.

## Ce que bloque la protection en lecture seule {#what-the-read-only-guard-blocks}

InvenTag vérifie chaque appel AWS du processus avant son envoi. Il n’autorise que les opérations dont le nom commence par `List`, `Describe`, `Get`, `Head`,
`Lookup`, `Search` ou `BatchGet`, plus `sts:AssumeRole` pour atteindre d’autres comptes. Elle ne peut pas être désactivée.

Certaines opérations ressemblent à des lectures mais renvoient des secrets ou des données clients. La protection les bloque aussi, pour qu’une politique large ne puisse pas les exposer via InvenTag.
Exemples : `secretsmanager:GetSecretValue`, `ssm:GetParameter`, `s3:GetObject`, `dynamodb:GetItem`, `lambda:GetFunction` (il renvoie un lien de téléchargement du code),
`cloudformation:GetTemplate`, `ec2:GetLaunchTemplateData`, `glue:GetConnection` et les résultats de requêtes Athena.
Elle bloque aussi les clés d’API avec leurs valeurs et `ec2:DescribeInstanceAttribute` pour les données utilisateur, et vérifie les URL présignées et les jetons d’authentification de base de données selon les mêmes règles.
Vérifiez un nom avec `inventag --validate-operations <service>:<Operation>`.

Les profils IAM Identity Center (SSO) et d’identité web fonctionnent avec la protection active. La protection laisse l’étape de connexion échanger un jeton contre des identifiants, et rien d’autre.

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

Connectez-vous ensuite avec `aws sso login --profile <profile>` et lancez InvenTag avec
`AWS_PROFILE=<profile>`.

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

## Vérifier qu’elle ne peut pas écrire {#check-that-it-cannot-write}

Utilisez le simulateur de politiques IAM pour confirmer qu’une écriture est refusée :

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Les deux doivent afficher `implicitDeny` ou `explicitDeny`.

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
