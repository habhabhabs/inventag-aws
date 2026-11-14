---
title: Installer InvenTag
description: Installez InvenTag dans un environnement virtuel Python, connectez vos identifiants AWS et vérifiez que tout fonctionne.
sidebar_position: 2
---

# Installer InvenTag

**À qui s’adresse cette page :** à toute personne qui installe InvenTag sur un ordinateur portable, un serveur ou un
exécuteur d’intégration continue.

**Ce que vous saurez faire après lecture :** exécuter `inventag --help` et confirmer qu’
InvenTag peut joindre votre compte AWS.

## Ce dont vous avez besoin {#what-you-need}

- **Python 3.11 ou version ultérieure.** Python 3.10 ne reçoit plus de correctifs de sécurité depuis
  octobre 2026. Voir l’[état des versions de Python](https://devguide.python.org/versions/). Vérifiez votre version avec `python3 --version`.
- **pip** pour ce Python. (Git n’est nécessaire que pour installer depuis les sources.)
- Des **identifiants AWS** pour une identité en lecture seule. L’
  [interface de ligne de commande AWS (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  est facultative, mais c’est le moyen le plus simple de les configurer.

## Installer avec pip (recommandé) {#install-with-pip-recommended}

InvenTag est publié sur le Python Package Index sous le nom
[`inventag-aws`](https://pypi.org/project/inventag-aws/). Un environnement virtuel
est la manière propre de l’installer, mais InvenTag n’en a pas besoin. C’est un paquet
Python ordinaire. Un environnement virtuel garde ses dépendances
(boto3, openpyxl et d’autres) à l’écart de vos autres outils Python, et de nombreux
systèmes récents (Debian, Ubuntu, Python de Homebrew) refusent `pip install` dans le
Python du système avec l’erreur « externally-managed-environment ». Les deux options
qui fonctionnent sur ces systèmes sont un environnement virtuel ou `pipx` :

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

Non vérifié sur Debian, Ubuntu ni sur Homebrew : l’erreur externally-managed-environment et les deux moyens de la contourner.

Vous disposez ainsi de la commande `inventag` qu’utilise cette documentation. Les
modèles de rapport sont inclus dans le paquet.

Pour mettre à jour, exécutez `pip install --upgrade inventag-aws`. Pour installer une version
précise, épinglez-la, par exemple `pip install inventag-aws==%INVENTAG_VERSION%`. Vous préférez le tenir à l’écart de vos
environnements de projet ? `pipx install inventag-aws` l’installe dans son propre
environnement caché et place la commande `inventag` dans votre PATH ; vous n’avez donc jamais rien
à activer. Si votre système l’autorise, un simple `pip install inventag-aws`
dans votre Python utilisateur ou système fonctionne aussi.

Non vérifié sur pip ni sur pipx : les commandes de mise à jour, d’épinglage de version et de pipx.

## Installer depuis les sources {#install-from-source}

Utilisez cette méthode si vous voulez le code non publié le plus récent ou si vous comptez modifier InvenTag.

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` installe les dépendances de `requirements.txt` et une commande
`inventag` qui exécute votre copie des sources ; vos modifications du code prennent
donc effet sans réinstallation. Vous pouvez aussi exécuter directement
`python inventag_cli.py --help` après `pip install -r requirements.txt`.

Pour utiliser depuis les sources une version figée plutôt que le code le plus récent, extrayez son étiquette, par
exemple `git checkout v%INVENTAG_VERSION%`. La
[page des versions](https://github.com/habhabhabs/inventag-aws/releases) liste
toutes les versions.

## Connecter vos identifiants AWS {#connect-your-aws-credentials}

InvenTag utilise la chaîne standard d’identifiants AWS ; n’importe laquelle de ces méthodes convient :

Avec IAM Identity Center (recommandé) :

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

Avec des clés d’accès de longue durée (à éviter si possible) :

```bash title="Terminal"
aws configure
```

Non vérifié sur l’AWS CLI : les commandes de connexion de cette section.

Préférez des identifiants de courte durée, comme IAM Identity Center ou un rôle
assumé, plutôt que des clés d’accès stockées sur disque.

## Vérifier que ça fonctionne {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

Le code de sortie 0 signifie qu’InvenTag a pu se connecter. Avec `--verbose`, vous voyez aussi les
étapes. Exemple de sortie d’une exécution hors ligne sur un AWS simulé (données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
0
```

Si les identifiants sont absents, ou si le jeton de sécurité n’est pas valide ou a expiré, InvenTag explique pourquoi et suggère une solution. Un jeton IAM Identity Center (SSO) expiré fait exception : voir [État des fonctionnalités](./status.md#when-a-run-goes-wrong). Voir
[Résoudre les problèmes courants](../guides/troubleshooting.md#credentials).

## Accorder à InvenTag des autorisations en lecture seule {#give-inventag-read-only-permissions}

Avant votre première vraie analyse, donnez à l’identité une politique en lecture seule :
[Configurer l’accès en lecture seule](../guides/read-only-access.md).

## Mettre à jour depuis v1.1.x {#upgrade-from-v11x}

Ce que vous remarquerez après `pip install --upgrade inventag-aws` :

- **Les valeurs secrètes sont masquées.** Les valeurs des champs qui contiennent
  souvent des secrets, comme les variables d’environnement Lambda, deviennent
  `***REDACTED***` dans les rapports, les instantanés et les journaux. La première
  exécution après la mise à jour signale une fois ces ressources comme modifiées.
  Les rapports et instantanés des versions précédentes peuvent encore contenir
  ces valeurs : supprimez-les ou restreignez leur accès.
- **Nouvelles colonnes.** Chaque feuille de service a les colonnes `source`,
  `sources` et `detail_level`. Voir [Fichiers de sortie](../reference/outputs.md).
- **Plus de services et plus d’appels d’API.** InvenTag liste 22 services de
  plus, ce qui ajoute des feuilles, des lignes et des appels. La politique du
  dépôt compte 17 nouvelles actions de lecture (et ne liste plus `cloudtrail:LookupEvents`) ; sans elles, chaque listage refusé est un
  avertissement, et ces ressources sont trouvées par l’API Tagging comme avant, si elles sont étiquetées. Le premier rapport de changements après la mise à jour affiche les ressources des services nouvellement listés comme ajoutées, alors qu’elles existaient déjà. Voir [Permissions IAM](../reference/iam-permissions.md).
- **Des fichiers vérifiés plus strictement.** Un fichier de réglages vide, une
  clé écrite deux fois ou une valeur `--bom-config` du mauvais type arrêtent
  l’exécution avec le code de sortie 1.
- **Les options incompatibles s’arrêtent avec le code de sortie 2**, par exemple
  `--accounts-file` avec `--accounts-prompt`, ou `--s3-kms-key-id` sans
  `--s3-encryption aws:kms`.
- **La limite de temps est par compte**, comptée à partir du début de son
  analyse. Un compte qui dépasse son temps garde les ressources trouvées et
  compte comme en échec.
- **Les codes de sortie par défaut ne changent pas.** Les codes 5 et 6 sont
  nouveaux et n’apparaissent qu’avec `--fail-on-account-error` et `--fail-if-empty`.
  Un format de rapport impossible à écrire se termine avec le code 1.
- **Les noms de service et de feuille restent.** Les ressources que v1.1.4
  trouvait seulement par l’API Tagging gardent leur nom de service et leur
  feuille (par exemple `ELASTICFILESYSTEM`, `STATES`, `COGNITO-IDP`,
  `ELASTICMAPREDUCE`, `KAFKA`, `ES`). Leurs lignes portent maintenant les détails
  de l’API du service, et la colonne ID des secrets Secrets Manager et des
  clusters MSK contient le nom au lieu de la dernière partie de l’ARN.

La liste complète figure dans le
[journal des modifications](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md).

## Installer pour le développement {#install-for-development}

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Le [guide de contribution](../development/CONTRIBUTING.md) explique la suite
de tests complète.

## Résoudre les problèmes d’installation {#fix-install-problems}

| Ce que vous voyez | Que faire |
|---|---|
| `Error: No suitable Python interpreter found.` ou `InvenTag requires Python 3.11 or later` | Installez Python 3.11 ou une version ultérieure et vérifiez que `python3 --version` fonctionne. |
| `inventag: command not found` | Activez l’environnement virtuel dans lequel vous avez exécuté `pip install inventag-aws`, ou exécutez `python -m pip show inventag-aws` pour vérifier qu’il est installé. |
| `ModuleNotFoundError` | Activez l’environnement virtuel et exécutez de nouveau `pip install -r requirements.txt`. |
| `No AWS credentials found!` | Exécutez `aws sso login` ou `aws configure`, ou définissez `AWS_PROFILE`. |

Non vérifié sur l’AWS CLI : les commandes de la colonne « Que faire ».

## Étape suivante {#next-step}

[Démarrage rapide](./quick-start.md)
