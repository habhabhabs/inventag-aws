---
title: Sortie Google Sheets et Docs
description: "Écrivez l’inventaire InvenTag dans Google Sheets et Google Docs : connexion, qui peut ouvrir les fichiers, comment le tester avec votre propre compte Google, et ce qui n’a pas été vérifié avec le vrai Google."
sidebar_position: 9
---

# Sortie Google Sheets et Docs

**À qui s’adresse cette page :** vous voulez l’inventaire dans Google Drive à la place d’un fichier Excel ou
Word, ou en plus.

**Ce que vous saurez après lecture :** comment installer les bibliothèques Google,
vous connecter, quelles options utiliser, qui peut ouvrir les fichiers, comment tester la sortie avec votre propre compte Google, et ce qui n’a pas été
vérifié.

## Ce que vous obtenez {#what-you-get}

- `--create-google-sheets` écrit le même classeur que `--create-excel` (mêmes
  feuilles, même ordre des lignes, mêmes modèles) sous forme de feuille de calcul Google Sheets.
- `--create-google-docs` écrit le même rapport que `--create-word` sous forme de
  document Google Docs.
- InvenTag construit d’abord les rapports Excel et Word, puis les copie ; un
  `--template` modifie donc les fichiers Google exactement comme il modifie les fichiers locaux.
- L’exécution affiche l’URL de chaque fichier, par exemple `Google Sheet: https://docs.google.com/spreadsheets/d/...` et `Google Doc: https://docs.google.com/document/d/...`.
- Avec `--per-account-reports`, InvenTag crée une paire de fichiers par compte. Le titre se termine par ` - ` et l’ID du compte, et chaque ligne d’URL commence par `[123456789012]`.
- Si une exécution ne trouve aucune ressource, elle ne crée aucun fichier Google.

## Installer le module complémentaire Google {#install-the-google-add-on}

Écrire dans Google demande quelques paquets Python supplémentaires (les bibliothèques de connexion et d’API
de Google). La plupart des gens n’utilisent jamais la sortie Google ; ces paquets ne sont donc pas
installés par défaut avec InvenTag. Vous les ajoutez une seule fois avec cette commande :

```bash title="Terminal"
pip install "inventag-aws[google]"
```

Lisez-la comme « installer InvenTag, plus son module complémentaire Google ». Ce qui figure entre crochets
est le nom du module complémentaire. Ce n’est pas un espace réservé : tapez-le exactement
comme indiqué, avec les guillemets (zsh, l’interpréteur par défaut de macOS, en a besoin).

- **Vous avez déjà InvenTag.** Lancez la même commande. pip conserve votre
  InvenTag et ajoute seulement les paquets Google.
- **Vous l’avez installé avec pipx.** Lancez `pipx install "inventag-aws[google]"`, ou
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  pour ajouter les paquets à l’InvenTag que vous avez déjà.
- **Vous utilisez un environnement virtuel.** Activez-le d’abord, afin que les paquets soient installés
  à côté d’InvenTag.

Vous n’avez pas besoin du module complémentaire pour Excel, Word ou tout le reste. Si vous utilisez une option
Google sans lui, InvenTag s’arrête avec le code de sortie 2, indique quel paquet
manque et affiche cette commande.

## Se connecter {#sign-in}

Choisissez l’une des méthodes :

| Méthode | Option | Quand l’utiliser |
|---|---|---|
| Clé de compte de service | `--google-credentials key.json` | Exécutions planifiées et CI |
| Votre propre compte Google | `--google-oauth-client client_secret.json` | Une exécution sur votre portable. Un navigateur s’ouvre une fois, et le jeton est enregistré dans `~/.config/inventag/google-token.json`, lisible par vous seul. |
| Application Default Credentials | aucune | Vous avez lancé `gcloud auth application-default login` |

Activez les API Google Sheets, Google Docs et Google Drive dans le projet Google
Cloud des identifiants.

InvenTag lit le fichier de clé ou le fichier client OAuth avant d’analyser AWS ; un fichier incorrect arrête donc l’exécution aussitôt avec le code de sortie 2 et un message qui commence par `inventag: error: Google:`.

Le périmètre est `drive.file` : InvenTag ne peut toucher que les fichiers qu’il a créés. Avec
`--google-folder-id`, il demande le périmètre Drive complet, car il doit placer
un fichier dans un dossier qui existe déjà.

## Qui peut ouvrir les fichiers {#who-can-open-the-files}

Les fichiers sont **privés** pour le compte qui les crée. Rien n’est partagé
sauf si vous le demandez.

```bash title="Terminal"
inventag --create-google-sheets --create-google-docs \
  --google-credentials key.json \
  --google-share-with you@example.com \
  --google-share-with team@example.com --google-share-role commenter \
  --google-folder-id 1AbCdEfGh \
  --google-title "AWS inventory, May"
```

- `--google-share-with EMAIL` peut être répété. `--google-share-role` définit
  `reader` (par défaut), `commenter` ou `writer` pour tous.
- `--google-share-anyone` rend les fichiers lisibles par toute personne qui a le lien.
  Ne l’utilisez que pour des données que vous publieriez.
- Un compte de service est propriétaire de ce qu’il crée, dans son propre Drive, où vous ne pouvez pas
  l’ouvrir. Si vous vous connectez avec un compte de service sans donner
  `--google-share-with` ni `--google-folder-id`, InvenTag vous en avertit.
- `--google-share-with`, `--google-share-role`, `--google-share-anyone`,
  `--google-folder-id` et `--google-title` sans `--create-google-sheets`
  ni `--create-google-docs` s’arrêtent avec le code de sortie 2.

## Les identifiants ne sont jamais journalisés {#credentials-are-never-logged}

Le chemin du fichier de clé n’est pas affiché, et les secrets qui ressemblent à des clés privées Google,
des jetons d’accès, des jetons d’actualisation ou des secrets client sont masqués dans chaque ligne de
journal, y compris avec `--debug`. Les messages d’erreur des bibliothèques Google
sont réduits au type d’erreur, car ils peuvent citer le fichier de clé.

## Limites {#limits}

- Une cellule Google Sheets peut contenir jusqu’à 50 000 caractères. InvenTag coupe les textes plus longs à 49 000 caractères. Une feuille de calcul peut contenir jusqu’à 10 millions de cellules et une feuille jusqu’à 18 278 colonnes.
- InvenTag compte les cellules avant d’appeler Google. Si le rapport est trop grand, il ne crée rien et le dit, et l’exécution se termine avec le code 1. Les fichiers Excel et Word sont tout de même écrits. Par exemple :
  `The report has 12,000,000 cells; a Google spreadsheet allows 10,000,000. No
  spreadsheet was created. Send fewer resources (filters or an account subset)
  or use the Excel report.`
- InvenTag envoie une grande feuille en plusieurs requêtes, chacune de 2 000 lignes au plus et d’environ 1 million de caractères.
- Si Google répond « 429 too many requests », InvenTag consigne `Google rate limit
  reached; waiting 5 seconds` et réessaie. Il attend 5, 10, 20, 40 puis 60 secondes avant la dernière tentative.
- Si un appel échoue après la création du fichier, l’exécution se termine avec le code 1 et le message donne l’URL du fichier à moitié écrit : `The spreadsheet was already
  created and may be incomplete: <url> (delete it in Google Drive).` Il en va de même pour un Google Doc. Supprimez ce fichier et relancez.
- Les tableaux du rapport Word affichent par défaut jusqu’à 50 ressources par service
  (`max_rows_per_service` dans un modèle de rapport, `max_rows` dans un fichier de mise en page), et il en va de même pour le document Google Docs.
- Les valeurs des cellules sont écrites comme du texte : une valeur d’étiquette qui commence par `=` n’est donc pas
  exécutée comme une formule.

## Ce qui n’est pas vérifié {#what-is-not-verified}

La plupart des tests utilisent des clients Google simulés. **Nous n’avons pas enregistré d’exécution avec les vraies API Google**, car cela demande un compte Google. En particulier, les positions qu’InvenTag calcule pour remplir les tableaux d’un Google Doc sont vérifiées d’après les règles de l’API Docs telles que nous les comprenons, et non avec le vrai service. Essayez d’abord avec un petit compte, et signalez tout problème de mise en page du Doc dans un problème (issue).

## Le vérifier avec votre propre compte Google {#check-it-against-your-own-google-account}

Le dépôt contient un script qui fait pour vous le test avec le vrai Google. Il construit un parc fictif avec moto (une simulation d’AWS) ; il n’a donc pas besoin de compte AWS et ne touche que Google. Il exécute InvenTag avec `--create-google-sheets` et `--create-google-docs`, relit les fichiers depuis Google et les compare aux fichiers Excel et Word créés lors de la même exécution. Il affiche un tableau PASS ou FAIL, les deux URL et `RESULT: PASS` ou `RESULT: FAIL`. Le code de sortie est 0 en cas de réussite.

Exécutez-le depuis une copie du dépôt.

1. Installez les bibliothèques Google et moto :

   ```bash title="Terminal"
   pip install "inventag-aws[google]"
   pip install moto
   ```

2. Dans le projet Google Cloud de vos identifiants, activez l’API Google Sheets, l’API Google Docs et l’API Google Drive. Si l’une est désactivée, Google répond HTTP 403 et le script nomme l’API à activer.
3. Créez un client OAuth de type « Desktop app », téléchargez-le sous le nom `client_secret.json`, puis exécutez :

   ```bash title="Terminal"
   python scripts/google_live_test.py --google-oauth-client client_secret.json --large
   ```

   Un navigateur s’ouvre une seule fois. Si l’application est en état « Testing », ajoutez votre compte sous OAuth consent screen, Test users.

Pour utiliser une clé de compte de service, passez `--google-credentials key.json`. Le compte de service possède les fichiers dans son propre Drive ; ajoutez donc `--share-with you@example.com` si vous voulez les ouvrir.

| Option | Ce qu’elle fait |
|---|---|
| `--large` | Teste aussi une feuille de 20 000 lignes et un tableau de 300 lignes dans le Doc. Il compte les appels d’API et injecte deux réponses « 429 » pour prouver la nouvelle tentative. Cela ajoute environ une minute. |
| `--share-with EMAIL` | Partage les fichiers (reader) avec cette adresse et vérifie que seules cette adresse et le propriétaire peuvent les ouvrir. Répétez-la pour en ajouter. |
| `--keep` | Laisse les fichiers dans Drive. Par défaut, le script déplace à la fin tous les fichiers qu’il a créés vers la corbeille de Drive. |
| `--folder-id ID` | Crée aussi une paire de fichiers dans ce dossier Drive. Cela demande le périmètre complet de Drive. Avec `--google-oauth-client`, supprimez d’abord `~/.config/inventag/google-token.json`, pour qu’il redemande l’autorisation. |

Sans option de connexion, le script utilise les identifiants par défaut de l’application (ADC). Google bloque le client de connexion de `gcloud` pour les périmètres Drive, Docs et Sheets ; il vous faut donc ici aussi votre propre fichier client OAuth. Exécutez `python
scripts/google_live_test.py --help` pour voir la commande `gcloud` exacte. Nous n’avons pas vérifié cette voie. Préférez le client OAuth.

Le script vérifie ceci :

- La feuille de calcul et le Doc existent et correspondent à l’URL affichée.
- Les noms et l’ordre des feuilles, les lignes et les colonnes, et chaque cellule correspondent au fichier Excel.
- Le texte qui commence par `=` revient comme texte, pas comme formule.
- Les textes longs, accentués et CJK, et une feuille vide, sont conservés.
- La ligne d’en-tête est en gras et colorée, et les premières lignes sont figées.
- Les titres et chaque cellule de tableau du Doc correspondent au fichier Word.
- Les deux fichiers sont privés pour le compte (et pour les adresses de `--share-with`).

Si vous l’exécutez, envoyez-nous le tableau final. Nous ne modifierons cette page qu’après une réussite sur un vrai compte.

## Pour aller plus loin {#where-to-next}

- [Lancer une analyse](./run-a-scan.md)
- [Référence de la CLI](../reference/cli.md#output)
- [Modèles de rapport](../templates/index.md)
