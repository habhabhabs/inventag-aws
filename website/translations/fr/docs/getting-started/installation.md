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
  octobre 2026. Vérifiez votre version avec `python3 --version`.
- **pip**, fourni avec Python. (Git n’est nécessaire que pour installer depuis les sources.)
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

Vous disposez ainsi de la commande `inventag`. Tout ce qui, dans cette documentation, montre
`inventag` fonctionne de la même façon. Les modèles de rapport sont
inclus dans le paquet.

Pour mettre à jour, exécutez `pip install --upgrade inventag-aws`. Pour installer une version
précise, exécutez `pip install inventag-aws==1.0.2`. Vous préférez le tenir à l’écart de vos
environnements de projet ? `pipx install inventag-aws` l’installe dans son propre
environnement caché et place la commande `inventag` dans votre PATH ; vous n’avez donc jamais rien
à activer. Si votre système l’autorise, un simple `pip install inventag-aws`
dans votre Python utilisateur ou système fonctionne aussi.

## Installer depuis les sources {#install-from-source}

Utilisez cette méthode si vous voulez le code non publié le plus récent ou si vous comptez modifier InvenTag.

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
inventag --help               # Windows: inventag --help
```

Exécutez `pip install -e .` dans le dossier cloné pour obtenir la commande `inventag` depuis
votre copie des sources. Vous pouvez aussi exécuter directement `python inventag_cli.py --help`.

Pour utiliser depuis les sources une version figée plutôt que le code le plus récent, extrayez son étiquette, par
exemple `git checkout v1.0.2`. La
[page des versions](https://github.com/habhabhabs/inventag-aws/releases) liste
toutes les versions.

## Connecter vos identifiants AWS {#connect-your-aws-credentials}

InvenTag utilise la chaîne standard d’identifiants AWS ; n’importe laquelle de ces méthodes convient :

```bash title="Terminal"
aws sso login --profile my-readonly     # IAM Identity Center (recommended)
export AWS_PROFILE=my-readonly

aws configure                           # long-lived access keys (avoid if you can)
```

Préférez des identifiants de courte durée, comme IAM Identity Center ou un rôle
assumé, plutôt que des clés d’accès stockées sur disque.

## Vérifier que ça fonctionne {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

Le code de sortie 0 signifie qu’InvenTag a pu se connecter. Avec `--verbose`, vous voyez aussi les
étapes. Exemple de sortie d’une exécution hors ligne sur un AWS simulé (données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
$ echo $?
0
```

Si les identifiants ne fonctionnent pas, InvenTag explique pourquoi et suggère une solution. Voir
[Résoudre les problèmes courants](../guides/troubleshooting.md#credentials).

## Accorder à InvenTag des autorisations en lecture seule {#give-inventag-read-only-permissions}

Avant votre première vraie analyse, donnez à l’identité une politique en lecture seule :
[Configurer l’accès en lecture seule](../guides/read-only-access.md).

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

## Étape suivante {#next-step}

[Générer votre premier rapport](./quick-start.md)
