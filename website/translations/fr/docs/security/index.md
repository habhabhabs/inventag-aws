---
title: Sécurité
description: Signaler une vulnérabilité d’InvenTag, versions de Python à utiliser, vérification des dépendances et conduite à tenir après un incident de sécurité.
sidebar_position: 1
---

# Sécurité

**À qui s’adresse cette page :** aux évaluateurs de sécurité, et à toute personne qui exécute InvenTag sur
des comptes de production.

**Ce que vous saurez après lecture :** comment signaler un problème, comment les
dépendances d’InvenTag sont vérifiées et comment limiter les dégâts en cas
de problème.

## Signaler une vulnérabilité {#report-a-vulnerability}

Merci de ne pas publier de détails d’exploitation dans un problème (issue) public.

Ce dépôt n’a pas encore de fichier `SECURITY.md` ni de signalement privé de vulnérabilités
GitHub configuré (vérifié en novembre 2026). D’ici là,
ouvrez un [problème (issue)](https://github.com/habhabhabs/inventag-aws/issues) intitulée
« Security contact request », sans détails techniques, et demandez au
mainteneur un canal privé.

## Ce qu’InvenTag fait de vos comptes {#what-inventag-does-with-your-accounts}

- **Il ne fait que lire, à part un téléversement que vous demandez.** Une protection en lecture seule vérifie
  chaque appel AWS avant son envoi. La seule exception est le téléversement de ses propres fichiers de rapport
  vers votre compartiment S3, et seulement lorsque vous passez `--s3-bucket`. Elle bloque tout ce qui n’est pas une lecture, ainsi que les lectures qui renvoient des secrets
  ou des données, comme `secretsmanager:GetSecretValue`, `s3:GetObject`,
  `cloudformation:GetTemplate` ou `ec2:GetLaunchTemplateData`. Elle bloque aussi des
  opérations autorisées quand un paramètre demande un secret (clés d’API avec
  `includeValue`, `ec2:DescribeInstanceAttribute` pour `userData`), et elle vérifie
  les URL présignées et les jetons d’authentification de base de données, qui sont
  signés sans appel à AWS. Elle bloque aussi les lectures qui fournissent une URL
  signée, le corps d’un fichier ou d’un document, la sortie d’une commande ou une
  définition enregistrée contenant des secrets (par exemple `ssm:GetDocument`,
  `ssm:GetCommandInvocation`, les exports API Gateway, les définitions Data
  Pipeline et les pièces jointes Support et Connect), ainsi que
  `cognito-identity:GetId`, qui crée une identité. Chaque entrée de la liste de
  refus est vérifiée par rapport à la liste des opérations du SDK AWS. Elle est
  toujours active.
- **La connexion fonctionne toujours.** La protection laisse le SDK AWS échanger un
  jeton IAM Identity Center (SSO), d’identité web ou `aws login` contre des
  identifiants. Elle n’autorise que ces quatre appels non signés :
  `sso:GetRoleCredentials`, `sso-oidc:CreateToken`,
  `sts:AssumeRoleWithWebIdentity` et `signin:CreateOAuth2Token`. Un client signé qui
  fait le même appel est bloqué.

  Non vérifié sur AWS IAM Identity Center : les appels de connexion qu’envoie un vrai SDK.
- **Il masque les valeurs secrètes des réponses autorisées.** Les valeurs des
  champs qui contiennent souvent des secrets, comme les variables d’environnement
  Lambda, les données utilisateur EC2 ou les valeurs de paramètres CloudFormation,
  deviennent `***REDACTED***` dans les rapports, les instantanés et les journaux.
  Les noms restent. Voir
  [État des fonctionnalités](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).
- **Il n’envoie aucune donnée d’utilisation.** InvenTag n’a pas de télémétrie. L’outil en ligne de commande
  ne communique qu’avec AWS, et avec Google lorsque vous utilisez une option Google. L’assistant CI facultatif de la bibliothèque Python peut publier vers
  Slack, Microsoft Teams ou une Prometheus Pushgateway, mais uniquement vers des adresses
  que vous configurez vous-même.
- **Ses fichiers sont privés.** Les rapports, instantanés et journaux sont créés lisibles
  par votre seul utilisateur.

  Non vérifié sur Windows : fichiers lisibles uniquement par votre utilisateur.
- **Ses journaux masquent les secrets.** Les jetons de session, les clés, les signatures de requête et les
  valeurs masquées ci-dessus sont cachés, même avec `--debug`.

Vous pouvez vérifier ce qu’une exécution a fait avec `--audit-output audit.json`, et ce que la
protection autorise avec `--validate-operations` :

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

## Utiliser une version de Python prise en charge {#use-a-supported-python-version}

Utilisez Python 3.11 ou une version ultérieure. Python 3.10 et les versions antérieures ne reçoivent plus de correctifs
de sécurité : la version 3.10 a atteint sa fin de vie en octobre 2026
([état des versions de Python](https://devguide.python.org/versions/)).

## Comment les dépendances sont vérifiées {#how-dependencies-are-checked}

| Quoi | Comment, sur la branche `main` actuelle |
|---|---|
| Dépendances Python | Listées dans `requirements.txt` avec des versions minimales (`>=`), et non des versions exactes. Chaque plancher de sécurité nomme l’avis qu’il évite. Une installation neuve obtient les dernières versions correspondantes. |
| Outils de développement | Listés dans `requirements-dev.txt` avec des versions exactes (`==`) pour les outils de test et de lint, plus des versions minimales pour leurs dépendances. |
| Site web | Verrouillé dans `website/package-lock.json`. |
| Vérification des dépendances en CI | Le workflow de CI exécute `pip-audit -r requirements.txt` et échoue en cas de résultat. Il exécute aussi Bandit et `npm audit`, mais n’échoue pas sur leurs résultats. |
| Analyse planifiée | Un workflow distinct s’exécute à chaque push sur `main` et `develop`, sur les pull requests vers `main` et chaque semaine (le dimanche, 02:00 UTC). Il exécute Bandit, Safety, pip-audit, `npm audit` et detect-secrets. Les résultats sont signalés mais ne font pas échouer ce workflow. |
| Nomenclature logicielle | La génération de la documentation produit des fichiers SBOM pour les dépendances Python et du site web. |

Non vérifié sur un runner GitHub Actions : ce que font les workflows de CI, planifiés et de documentation ; ce tableau est lu dans les fichiers de workflow.

Pour vérifier votre propre installation :

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

La fonctionnalité de modèles n’ajoute aucune nouvelle dépendance. Elle utilise PyYAML, openpyxl et
python-docx, dont InvenTag a déjà besoin.

## Réduire l’impact en cas de problème {#reduce-the-impact-if-something-goes-wrong}

InvenTag lit vos comptes AWS ; les identifiants que vous lui donnez comptent donc plus que l’outil
lui-même.

- **Lecture seule, moindre privilège.** Ne donnez à InvenTag que des autorisations de lecture :
  [Configurer un accès en lecture seule](../guides/read-only-access.md).
- **Identifiants de courte durée.** Utilisez IAM Identity Center ou un rôle assumé,
  pas des clés d’accès sur disque ou dans les secrets de CI. Dans GitHub Actions, utilisez OIDC.
- **Gardez les journaux privés.** Les secrets sont masqués dans les journaux, mais les journaux décrivent
  tout de même vos comptes.
- **Épinglez ce que vous exécutez.** Récupérez une balise de version d’InvenTag, et épinglez les GitHub
  Actions sur des SHA de commit.

## Après un incident de chaîne d’approvisionnement {#after-a-supply-chain-incident}

Si une dépendance, une action de CI ou la machine qui exécute InvenTag a pu être
compromise :

1. **Révoquez et renouvelez** les identifiants qu’InvenTag a utilisés : supprimez les clés d’accès,
   révoquez les sessions de rôle actives et déconnectez les sessions SSO.
2. **Vérifiez AWS CloudTrail** pour repérer les appels de cette identité qu’InvenTag
   ne ferait pas, notamment tout ce qui n’est pas `List`, `Describe` ou `Get`.
3. **Vérifiez que la politique IAM est toujours en lecture seule** et retirez tout ajout.
4. **Reconstruisez l’environnement** à partir d’un environnement virtuel propre :
   `pip install -r requirements.txt`, puis lancez `pip-audit`.
5. **Considérez les anciens rapports comme sensibles.** Ils listent vos ressources et vos étiquettes.

## Les modèles sont des données, pas du code {#templates-are-data-not-code}

Les modèles sont lus avec un chargeur YAML sûr, ne peuvent ni exécuter de code ni récupérer d’URL,
ne peuvent référencer que des fichiers situés dans leur propre dossier, et ne peuvent pas contenir de clés d’accès.
Détails : [Modèles](../templates/index.md#safe-by-design).
