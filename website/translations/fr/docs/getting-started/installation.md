---
title: Installer InvenTag
description: Choisissez comment installer InvenTag (pipx, une archive autonome, un paquet .deb ou .rpm, Homebrew ou pip), connectez vos identifiants AWS et vérifiez que tout fonctionne.
sidebar_position: 2
---

# Installer InvenTag

**À qui s’adresse cette page :** à toute personne qui installe InvenTag sur un ordinateur portable, un serveur ou un
exécuteur d’intégration continue.

**Ce que vous saurez faire après lecture :** choisir une méthode d’installation, installer
InvenTag, le mettre à jour et le supprimer, et confirmer qu’InvenTag peut joindre votre compte AWS.

## Ce dont vous avez besoin {#what-you-need}

- **Python 3.11 ou version ultérieure**, pour les méthodes pipx, pip et sources. Python 3.10
  ne reçoit plus de correctifs de sécurité depuis octobre 2026. Voir l’[état des versions de Python](https://devguide.python.org/versions/).
  Vérifiez votre version avec `python3 --version`. L’archive autonome, le
  `.deb` et le `.rpm` apportent leur propre Python. Ils n’ont pas besoin de Python sur votre machine.
- Des **identifiants AWS** pour une identité en lecture seule. L’
  [interface de ligne de commande AWS (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  est facultative, mais c’est le moyen le plus simple de les configurer.

## Choisir comment installer {#choose-how-to-install}

| Méthode | À utiliser quand | Ce qu’il faut sur votre machine | Systèmes |
|---|---|---|---|
| [pipx](#install-with-pipx-recommended) (premier choix) | Vous avez Python 3.11 ou ultérieur. Vous voulez une commande pour installer et une pour mettre à jour. | Python 3.11 ou ultérieur et pipx | Tout système avec Python |
| [Archive autonome](#install-the-standalone-archive) (`.tar.gz`) | La machine n’a pas Python, ou vous voulez une copie sans gestionnaire de paquets. | Rien | Linux x86_64 et arm64 (glibc 2.34 ou ultérieure). macOS arm64 (Apple silicon). |
| [Paquet `.deb`](#install-the-deb-package) | Debian, Ubuntu et les systèmes qui utilisent `dpkg`. | Rien | Linux x86_64 et arm64 (glibc 2.34 ou ultérieure) |
| [Paquet `.rpm`](#install-the-rpm-package) | Fedora, la famille RHEL et Amazon Linux. | Rien | Linux x86_64 et arm64 (glibc 2.34 ou ultérieure) |
| [Homebrew](#install-with-homebrew) | macOS ou Linux avec Homebrew. Pas encore publié. | Homebrew | Voir la section |
| [pip dans un environnement virtuel](#install-with-pip-in-a-virtual-environment) | Vous voulez InvenTag dans un environnement de projet. | Python 3.11 ou ultérieur | Tout système avec Python |
| [Depuis les sources](#install-from-source) | Vous voulez le code non publié le plus récent, ou vous modifiez InvenTag. | Python 3.11 ou ultérieur et Git | Tout système avec Python |

### Systèmes pris en charge par chaque version empaquetée {#systems-that-each-packaged-build-supports}

- L’exécutable, le `.deb` et le `.rpm` pour Linux demandent la glibc 2.34 ou ultérieure.
  Les systèmes Linux du tableau ci-dessous la respectent.
  Sur un système plus ancien, par exemple RHEL, AlmaLinux et Rocky Linux 8,
  Debian 11, Ubuntu 20.04 ou Amazon Linux 2, utilisez pipx si le système a
  Python 3.11 ou ultérieur.
- Il n’y a pas d’exécutable pour les Mac Intel : une bibliothèque dont InvenTag a besoin
  (cryptography, à partir de la version 50) ne publie pas de version déjà compilée pour eux.
- L’exécutable macOS est réservé à Apple silicon (arm64). Le relevé de
  construction indique que ses fichiers demandent macOS 11.0 ou ultérieur.
- Alpine et les autres systèmes qui utilisent musl ne sont pas pris en charge par l’exécutable.
  Utilisez pipx.
- Windows n’a pas de version empaquetée.

Non vérifié sur un Mac Intel : `pipx install inventag-aws`, qui doit compiler cette bibliothèque et demande une chaîne d’outils Rust.

Non vérifié sur des systèmes dont la glibc est antérieure à 2.34 : l’exécutable, le `.deb` et le `.rpm`.

Non vérifié sur Alpine ni sur d’autres systèmes musl : l’exécutable ; utilisez pipx.

Non vérifié sur Windows : aucune méthode d’installation.

Non vérifié sur un Mac sous macOS 11.0 : l’exécutable. Le numéro vient du relevé de construction, pas d’une exécution sur cette version.

### Ce qui a été testé {#what-was-tested}

Le workflow de publication construit chaque format, puis l’installe sur un système
neuf. Chaque type de job fait ceci :

- **Linux x86_64 :** installe le paquet ou décompresse l’archive, exécute
  `inventag --version` et `inventag selftest`, lit le fichier de la page de
  manuel, charge les fichiers de complétion, analyse un AWS simulé, supprime le
  paquet et vérifie qu’aucun fichier du paquet ne reste.
- **Linux arm64 :** installe le `.deb` sur Debian 12 et le `.rpm` sur Rocky
  Linux 9, exécute `inventag --version` et `inventag selftest`, supprime le
  paquet et vérifie que `inventag` n’est plus dans le PATH. Il ne vérifie ni la
  page de manuel, ni les fichiers de complétion, ni une analyse, et il ne vérifie
  pas qu’aucun fichier du paquet ne reste.
- **macOS arm64 :** décompresse l’archive dans un dossier temporaire, exécute
  `inventag --version` et `inventag selftest`, lit le fichier de la page de
  manuel, vérifie la syntaxe des fichiers de complétion bash et zsh avec
  `bash -n` et `zsh -n` (rien n’est chargé, et le fichier fish n’est pas
  vérifié), analyse un AWS simulé et supprime le dossier temporaire.
- **pipx sur Ubuntu 24.04 :** installe le wheel construit depuis le tag, exécute
  `inventag --version` et `inventag selftest`, le supprime et vérifie que
  `inventag` n’est plus dans le PATH.

Ces systèmes ont réussi :

| Système | Format | CPU |
|---|---|---|
| Ubuntu 22.04 | `.deb` | x86_64 |
| Ubuntu 24.04 | `.deb` | x86_64 |
| Debian 12 | `.deb` et archive autonome | x86_64 |
| Debian 12 | `.deb` (installation, version, selftest, suppression) | arm64 |
| Fedora (la version actuelle le jour du test) | `.rpm` | x86_64 |
| Rocky Linux 9 | `.rpm` et archive autonome | x86_64 |
| Rocky Linux 9 | `.rpm` (installation, version, selftest, suppression) | arm64 |
| AlmaLinux 9 (le système de construction, glibc 2.34) | `.rpm` | x86_64 |
| Amazon Linux 2023 | `.rpm` | x86_64 |
| macOS 15 sur un runner GitHub | archive autonome | arm64 |
| Ubuntu 24.04 | pipx, depuis le wheel construit à partir de l’étiquette (installation, version, selftest, suppression) | x86_64 |

Non vérifié sur de vrais comptes AWS : une analyse depuis une version empaquetée ; le test analyse un AWS simulé.

Non vérifié sur un système Linux arm64 neuf : l’archive autonome. La construction a exécuté `inventag selftest` dessus, et aucun autre test ne l’a décompressée.

Non vérifié sur GitHub : que la publication contienne les fichiers de cette page. Les exécutions de test jusqu’ici ne joignent rien à une publication, et la première exécution de publication avec ces fichiers n’a pas encore eu lieu.

## Installer avec pipx (recommandé) {#install-with-pipx-recommended}

[pipx](https://pipx.pypa.io/) installe InvenTag dans son propre environnement caché
et place la commande `inventag` dans votre PATH. Vous n’avez jamais rien à activer.
Le paquet du Python Package Index est
[`inventag-aws`](https://pypi.org/project/inventag-aws/). Installez d’abord pipx.
Utilisez la méthode que votre système propose. Voir la documentation de pipx.

```bash title="Terminal"
pipx install inventag-aws
inventag --version
inventag selftest
```

`inventag selftest` vérifie, hors ligne, que cette copie d’InvenTag fonctionne.
Il n’appelle pas AWS, n’ouvre aucune connexion réseau et n’a pas besoin d’identifiants.
Le code de sortie 0 signifie que toutes les vérifications ont réussi. Le code de
sortie 1 signifie qu’une vérification a échoué.

Si vous utilisez [uv](https://docs.astral.sh/uv/), la commande est
`uv tool install inventag-aws`.

- **Mettre à jour :** `pipx upgrade inventag-aws`. Pour installer une version
  précise, épinglez-la : `pipx install inventag-aws==%INVENTAG_VERSION%`.
- **Désinstaller :** `pipx uninstall inventag-aws`. Cela supprime le programme. Cela
  ne supprime pas vos rapports et instantanés dans `bom_output/`.
- **Complétion :** `inventag completion bash`, `inventag completion zsh` et
  `inventag completion fish` affichent un script de complétion. Voir
  [Complétion du shell](#shell-completion).
- **Page de manuel :** cette méthode n’en installe aucune. Utilisez `inventag --help`.

Non vérifié sur pipx : les commandes de mise à jour et d’épinglage de version.

Non vérifié sur uv : que `uv tool install inventag-aws` donne un `inventag` et un `inventag selftest` qui fonctionnent, et les commandes de mise à jour et de désinstallation.

## Installer l’archive autonome {#install-the-standalone-archive}

L’archive contient un seul répertoire, `inventag`. Il contient le programme, son
propre Python et ses bibliothèques. La publication a une archive pour chaque système :

- `inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz`
- `inventag-%INVENTAG_VERSION%-linux-arm64.tar.gz`
- `inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz` (macOS, Apple silicon)

Exécutez `uname -m` pour voir votre CPU. Linux affiche `x86_64` ou `aarch64`. Utilisez
l’archive arm64 pour `aarch64`. Téléchargez l’archive et `SHA256SUMS` depuis la
[page des publications](https://github.com/habhabhabs/inventag-aws/releases), ou avec
la CLI GitHub :

```bash title="Terminal"
gh release download v%INVENTAG_VERSION% --repo habhabhabs/inventag-aws \
  --pattern 'inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz' --pattern SHA256SUMS
```

[Vérifiez le téléchargement](#check-the-download) avant de le décompresser. Ensuite, sous
Linux :

```bash title="Terminal"
sudo tar -xzf inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz -C /opt
sudo ln -s /opt/inventag/inventag /usr/local/bin/inventag
inventag --version
inventag selftest
```

Sous macOS, décompressez l’archive dans un dossier de votre choix et lancez le
programme par son chemin. Le test a procédé ainsi. Il n’a pas créé de lien dans le PATH.

```bash title="Terminal"
mkdir -p "$HOME/inventag-install"
tar -xzf inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz -C "$HOME/inventag-install"
"$HOME/inventag-install/inventag/inventag" --version
```

L’exécutable macOS n’est pas notarié par Apple. macOS peut bloquer un fichier
téléchargé par un navigateur.

Non vérifié sur macOS hors d’un runner GitHub : l’installation avec Homebrew et le comportement de Gatekeeper.

- **Mettre à jour :** supprimez l’ancien répertoire, puis décompressez la nouvelle
  archive au même endroit.
- **Désinstaller (Linux) :** `sudo rm -rf /opt/inventag` et
  `sudo rm /usr/local/bin/inventag`. Sous macOS, supprimez le dossier que vous
  avez décompressé.
- **Complétion :** le répertoire contient les scripts dans `share/completions/` :
  `inventag.bash`, `_inventag` (zsh) et `inventag.fish`. Voir
  [Complétion du shell](#shell-completion).
- **Page de manuel :** le répertoire contient la page dans
  `share/man/man1/inventag.1`. Lisez-la avec
  `man /opt/inventag/share/man/man1/inventag.1`.

Non vérifié sur les outils man de chaque système : que `man` affiche la page. Le test a lu le fichier de la page et vérifié son en-tête et sa ligne de nom.

Non vérifié sur un système qui a une ancienne version d’InvenTag au même endroit : les étapes de mise à jour.

## Installer le paquet .deb {#install-the-deb-package}

Utilisez le `.deb` sur Debian, Ubuntu et les systèmes qui utilisent `dpkg`. Le nom du fichier est
`inventag_%INVENTAG_VERSION%_amd64.deb` pour x86_64 et
`inventag_%INVENTAG_VERSION%_arm64.deb` pour arm64. Téléchargez le fichier et
[vérifiez-le](#check-the-download). Ensuite, exécutez :

```bash title="Terminal"
sudo dpkg -i inventag_%INVENTAG_VERSION%_amd64.deb
inventag --version
inventag selftest
```

Le paquet place le programme dans `/opt/inventag/` et un lien dans
`/usr/bin/inventag`. Il installe aussi la page de manuel, les fichiers de
complétion et les fichiers de licence dans `/usr/share/doc/inventag/`. Le paquet
n’a pas de script d’installation.

- **Mettre à jour :** installez le `.deb` plus récent avec `sudo dpkg -i`.
- **Désinstaller :** `sudo dpkg -r inventag`. Sur x86_64, le test a vérifié
  qu’aucun fichier du paquet ne reste. Sur arm64, il a seulement vérifié que
  `inventag` n’est plus dans le PATH.
- **Complétion :** le paquet installe les fichiers pour bash, zsh et fish. Voir
  [Complétion du shell](#shell-completion).
- **Page de manuel :** `man inventag`. Le fichier est
  `/usr/share/man/man1/inventag.1.gz`.

Non vérifié sur un système qui a un ancien paquet InvenTag : la mise à jour.

Non vérifié sur les outils man de chaque système : que `man inventag` affiche la page. Le test a lu le fichier de la page et vérifié son en-tête et sa ligne de nom.

## Installer le paquet .rpm {#install-the-rpm-package}

Utilisez le `.rpm` sur Fedora, la famille RHEL et Amazon Linux. Le nom du fichier est
`inventag-%INVENTAG_VERSION%-1.x86_64.rpm` pour x86_64 et
`inventag-%INVENTAG_VERSION%-1.aarch64.rpm` pour arm64. Téléchargez le fichier et
[vérifiez-le](#check-the-download). Ensuite, exécutez :

```bash title="Terminal"
sudo dnf install ./inventag-%INVENTAG_VERSION%-1.x86_64.rpm
inventag --version
inventag selftest
```

Le paquet place le programme dans `/opt/inventag/` et un lien dans
`/usr/bin/inventag`. Il installe aussi la page de manuel, les fichiers de
complétion et les fichiers de licence dans `/usr/share/doc/inventag/`.

- **Mettre à jour :** installez le `.rpm` plus récent avec `sudo dnf install`.
- **Désinstaller :** `sudo dnf remove inventag`. Sur x86_64, le test a vérifié
  qu’aucun fichier du paquet ne reste. Sur arm64, il a seulement vérifié que
  `inventag` n’est plus dans le PATH.
- **Complétion :** le paquet installe les fichiers pour bash, zsh et fish. Voir
  [Complétion du shell](#shell-completion).
- **Page de manuel :** `man inventag`. Le fichier est
  `/usr/share/man/man1/inventag.1.gz`.

Non vérifié sur un système qui a un ancien paquet InvenTag : la mise à jour.

Non vérifié sur les outils man de chaque système : que `man inventag` affiche la page. Le test a lu le fichier de la page et vérifié son en-tête et sa ligne de nom.

## Installer avec Homebrew {#install-with-homebrew}

Le propriétaire du projet crée le tap Homebrew. Le tap n’est pas encore publié,
donc la commande ci-dessous ne fonctionne pas aujourd’hui :

```bash title="Terminal"
brew install habhabhabs/inventag/inventag
```

La formule est écrite. Elle est dans le dépôt, dans
`packaging/homebrew-tap/Formula/inventag.rb`, et
`scripts/packaging/render_formula.py` la complète avec le `SHA256SUMS` d’une
publication. Elle installe l’exécutable depuis l’archive de la publication, la
page de manuel et les fichiers de complétion pour bash, zsh et fish. Elle est
prévue pour macOS arm64 et les deux CPU Linux. Elle n’est pas prévue pour les Mac
Intel : sur l’un d’eux, l’installation s’arrête avec un message.

- **Mettre à jour :** `brew upgrade inventag`.
- **Désinstaller :** `brew uninstall inventag`.

Non vérifié sur Homebrew : la formule. `brew install`, `brew audit`, `brew style`
et `brew test` n’ont pas été exécutés sur elle. Les commandes de mise à jour et de
désinstallation n’ont pas été exécutées.

Non vérifié sur un Mac Intel : le message que l’installation y affiche.

Non vérifié sur macOS hors d’un runner GitHub : l’installation avec Homebrew et le comportement de Gatekeeper.

## Installer avec pip dans un environnement virtuel {#install-with-pip-in-a-virtual-environment}

InvenTag n’a pas besoin d’un environnement virtuel. Un environnement virtuel garde ses
dépendances (boto3, openpyxl et d’autres) à l’écart de vos autres outils Python.
De nombreux systèmes récents (Debian, Ubuntu, Python de Homebrew) refusent
`pip install` dans le Python du système avec l’erreur « externally-managed-environment ».
Les deux options qui fonctionnent sur ces systèmes sont un environnement virtuel ou
[pipx](#install-with-pipx-recommended).

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

- **Mettre à jour :** `pip install --upgrade inventag-aws`. Pour installer une
  version précise, épinglez-la : `pip install inventag-aws==%INVENTAG_VERSION%`.
- **Désinstaller :** `pip uninstall inventag-aws`.
- **Complétion et page de manuel :** comme pour [pipx](#install-with-pipx-recommended).

Non vérifié sur pip : les commandes de mise à jour, d’épinglage de version et de désinstallation.

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

La racine du dépôt contient aussi deux scripts de lancement, `inventag.sh` et
`inventag.bat`. Utilisez plutôt la commande `inventag`. Les scripts de lancement ne font pas partie du
paquet installé, et aucun test ne les exécute.

Pour utiliser depuis les sources une version figée plutôt que le code le plus récent, extrayez son étiquette, par
exemple `git checkout v%INVENTAG_VERSION%`. La
[page des versions](https://github.com/habhabhabs/inventag-aws/releases) liste
toutes les versions.

## Complétion du shell {#shell-completion}

`inventag completion bash`, `inventag completion zsh` et `inventag completion fish`
affichent un script de complétion. La commande lit seulement ses propres options.
Elle n’appelle pas AWS et n’ouvre aucune connexion réseau. Un nom de shell inconnu
s’arrête avec le code de sortie 2.

```bash title="Terminal"
source <(inventag completion bash)                                    # bash, this session
inventag completion zsh > "${fpath[1]}/_inventag"                     # zsh
inventag completion fish > ~/.config/fish/completions/inventag.fish  # fish
```

Le `.deb` et le `.rpm` installent les trois scripts pour vous :

| Shell | `.deb` | `.rpm` |
|---|---|---|
| bash | `/usr/share/bash-completion/completions/inventag` | `/usr/share/bash-completion/completions/inventag` |
| zsh | `/usr/share/zsh/vendor-completions/_inventag` | `/usr/share/zsh/site-functions/_inventag` |
| fish | `/usr/share/fish/vendor_completions.d/inventag.fish` | `/usr/share/fish/vendor_completions.d/inventag.fish` |

Non vérifié sur chaque configuration de shell : qu’un nouveau shell charge ces fichiers de lui-même. Le test a chargé chaque fichier à la main dans bash, zsh et fish. Il n’a pas chargé le fichier fish sur Rocky Linux 9, AlmaLinux 9 ni Amazon Linux 2023.

## Vérifier le téléchargement {#check-the-download}

Chaque publication liste tous ses fichiers dans `SHA256SUMS`. Une somme de contrôle
montre que le fichier est complet. Elle ne montre pas qui l’a produit. Une attestation
de construction le montre.

Sous Linux, mettez le fichier et `SHA256SUMS` dans un même dossier et exécutez :

```bash title="Terminal"
sha256sum --check --ignore-missing SHA256SUMS
```

Sous macOS, affichez la somme de contrôle de votre fichier et comparez-la à l’œil
avec la ligne de `SHA256SUMS` :

```bash title="Terminal"
shasum -a 256 inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz
grep darwin-arm64.tar.gz SHA256SUMS
```

Le workflow de publication signe les fichiers sans clé qui nous appartienne. Il
donne `SHA256SUMS` à l’étape `actions/attest` de GitHub. Cette étape écrit une
attestation de construction au nom du workflow. Pour vérifier un fichier, utilisez
la CLI GitHub :

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

`--repo` nomme le dépôt. `--signer-workflow` fait échouer la vérification si un
autre fichier de workflow a créé l’attestation.

Non vérifié sur GitHub : `gh attestation verify` avec ces options sur un fichier
de publication. Les options sont lues dans `gh attestation verify --help`. Les exécutions de test ne créent aucune attestation. La première attestation réelle est créée par la première exécution de publication, et cette exécution n’a pas encore eu lieu.

Chaque `.tar.gz`, `.deb` et `.rpm` a aussi un SBOM, nommé comme le fichier avec
`.cdx.json` ajouté. Voir [Nomenclature logicielle (SBOM)](../security/sbom.md).

## Licences dans les versions empaquetées {#licenses-in-packaged-builds}

InvenTag est sous licence MIT. Les archives de l’exécutable, le `.deb` et le `.rpm`
contiennent GNU libiconv, une bibliothèque sous la licence publique générale
limitée de GNU (LGPL) version 2.1. La formule Homebrew (pas encore
publiée) installe la même archive, donc elle la contient aussi. Le code de libiconv
se trouve dans les modules d’extension de lxml. InvenTag a besoin de lxml pour
écrire des fichiers Word. Le projet lxml construit ces modules et y lie libiconv.
Dans l’archive, le `.deb` et le `.rpm`, InvenTag embarque les fichiers de lxml sans
modification.

- Une installation avec pip, pipx ou uv ne contient pas libiconv dans un fichier
  d’InvenTag. Votre installateur télécharge le wheel propre de lxml depuis le Python
  Package Index.
- Le fichier de mentions est `THIRD-PARTY-LICENSES.txt`. Il nomme chaque composant
  embarqué, sa licence et le texte de sa licence. Il contient le texte complet de la
  LGPL 2.1. La publication a un fichier de mentions pour chaque système, nommé
  `inventag-%INVENTAG_VERSION%-<os>-<cpu>.THIRD-PARTY-LICENSES.txt`.
  Le même fichier est dans le paquet :
  - archive autonome : `inventag/THIRD-PARTY-LICENSES.txt`
  - `.deb` et `.rpm` : `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` et
    `/opt/inventag/THIRD-PARTY-LICENSES.txt`
- Le fichier de mentions nomme la version de libiconv et les emplacements du code
  source. Dans cette publication, il nomme libiconv 1.18 dans lxml 6.1.3 :
  - libiconv : <https://www.gnu.org/software/libiconv/> et
    <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>
  - lxml : <https://github.com/lxml/lxml>
- InvenTag ne fait aucune offre écrite d’envoyer le code source. Les adresses
  ci-dessus sont le code source. Si une adresse ne fonctionne pas, ouvrez un ticket
  sur <https://github.com/habhabhabs/inventag-aws/issues>.
- Les modules de lxml sont des fichiers séparés dans le répertoire d’installation.
  Vous pouvez les remplacer par votre propre build de lxml de la même version. Le
  dossier est `inventag/_internal/lxml/` dans l’archive autonome et
  `/opt/inventag/_internal/lxml/` pour le `.deb` et le `.rpm`. Sous macOS, signez de
  nouveau un module après l’avoir remplacé : `codesign -s - --force <file>`.

Non vérifié sur votre propre build de lxml : qu’un module que vous construisez fonctionne à la place du module inclus.

Non vérifié sur une installation Homebrew : que Homebrew laisse les fichiers de lxml sans modification.

Non vérifié sur macOS hors d’un runner GitHub : l’installation avec Homebrew et le comportement de Gatekeeper.

Cette page ne constitue pas un avis juridique.

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

Si les identifiants sont absents, ou si le jeton de sécurité n’est pas valide ou a expiré, InvenTag explique pourquoi et suggère une solution. Voir
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
| `inventag: command not found` | Activez l’environnement virtuel dans lequel vous avez exécuté `pip install inventag-aws`, ou exécutez `python -m pip show inventag-aws` pour vérifier qu’il est installé. Si vous utilisez l’archive autonome, créez le lien depuis `/opt/inventag/inventag` vers un dossier de votre PATH, ou lancez le programme par son chemin complet. |
| `ModuleNotFoundError` | Activez l’environnement virtuel et exécutez de nouveau `pip install -r requirements.txt`. |
| `inventag selftest` échoue | Installez de nouveau InvenTag, ou téléchargez de nouveau la publication, et exécutez de nouveau `inventag selftest`. Si l’échec se répète, ouvrez un ticket sur <https://github.com/habhabhabs/inventag-aws/issues> et ajoutez la sortie. |
| `No AWS credentials found!` | Exécutez `aws sso login` ou `aws configure`, ou définissez `AWS_PROFILE`. |

Non vérifié sur l’AWS CLI : les commandes de la colonne « Que faire ».

## Étape suivante {#next-step}

[Démarrage rapide](./quick-start.md)
