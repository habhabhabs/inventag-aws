---
title: Sortie Google Sheets et Docs
description: Comment écrire l’inventaire InvenTag dans une feuille de calcul Google Sheets et un document Google Docs, comment vous connecter, qui peut ouvrir les fichiers, et ce qui n’a pas été vérifié avec le vrai Google.
sidebar_position: 9
---

# Sortie Google Sheets et Docs

**À qui s’adresse cette page :** vous voulez l’inventaire dans Google Drive à la place d’un fichier Excel ou
Word, ou en plus.

**Ce que vous saurez après lecture :** comment installer les bibliothèques Google,
vous connecter, quelles options utiliser, qui peut ouvrir les fichiers et ce qui n’a pas été
vérifié.

## Ce que vous obtenez {#what-you-get}

- `--create-google-sheets` écrit le même classeur que `--create-excel` (mêmes
  feuilles, même ordre des lignes, mêmes modèles) sous forme de feuille de calcul Google Sheets.
- `--create-google-docs` écrit le même rapport que `--create-word` sous forme de
  document Google Docs.
- InvenTag construit d’abord les rapports Excel et Word, puis les copie ; un
  `--template` modifie donc les fichiers Google exactement comme il modifie les fichiers locaux.
- L’exécution affiche l’URL de chaque fichier.

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

- Une cellule Google Sheets contient au plus 50 000 caractères, et une feuille de calcul au plus
  10 millions de cellules. Un très grand inventaire peut les dépasser ; l’exécution échoue alors
  avec l’erreur de Google.
- Les tableaux du rapport Word affichent par défaut jusqu’à 50 ressources par service
  (`max_rows_per_service` dans un modèle de rapport, `max_rows` dans un fichier de mise en page), et il en va de même pour le document Google Docs.
- Les valeurs des cellules sont écrites comme du texte : une valeur d’étiquette qui commence par `=` n’est donc pas
  exécutée comme une formule.

## Ce qui n’est pas vérifié {#what-is-not-verified}

Tous les tests utilisent des clients Google simulés. **Aucun test n’a été exécuté avec les vraies API
Google**, car cela demande un compte Google. En particulier, les positions
qu’InvenTag calcule lorsqu’il remplit les tableaux d’un document Google Docs sont vérifiées par rapport aux
règles de l’API Docs telles que nous les comprenons, et non par rapport au vrai service. Essayez
d’abord avec un petit compte, et signalez tout problème de mise en page du document dans une issue.

## Pour aller plus loin {#where-to-next}

- [Lancer une analyse](./run-a-scan.md)
- [Référence de la CLI](../reference/cli.md#output)
- [Modèles de rapport](../templates/index.md)
