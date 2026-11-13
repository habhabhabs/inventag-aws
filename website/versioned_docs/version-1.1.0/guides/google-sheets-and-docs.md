---
title: Google Sheets and Docs output
description: How to write the InvenTag inventory to a Google Sheets spreadsheet and a Google Doc, how to sign in, who can open the files, and what has not been verified against real Google.
sidebar_position: 9
---

# Google Sheets and Docs output

**Who this is for:** you want the inventory in Google Drive instead of, or as
well as, an Excel or Word file.

**What you will know after reading:** how to install the Google libraries,
how to sign in, which flags to use, who can open the files, and what has not
been verified.

## What you get

- `--create-google-sheets` writes the same workbook as `--create-excel` (same
  sheets, same row order, same templates) as a Google Sheets spreadsheet.
- `--create-google-docs` writes the same report as `--create-word` as a Google
  Doc.
- InvenTag builds the Excel and Word reports first and copies them, so a
  `--template` changes the Google files exactly as it changes the local ones.
- The run prints the URL of each file.

## Install the Google libraries

The Google libraries are an optional extra. Without them everything else works.

```bash title="Terminal"
pip install "inventag-aws[google]"
```

If you use a Google flag without the extra, InvenTag stops with exit code 2
and prints this command.

## Sign in

Pick one:

| Way | Flag | When to use it |
|---|---|---|
| Service account key | `--google-credentials key.json` | Scheduled runs and CI |
| Your own Google account | `--google-oauth-client client_secret.json` | A run on your laptop. A browser opens once, and the token is saved in `~/.config/inventag/google-token.json`, readable by you only. |
| Application Default Credentials | none | You ran `gcloud auth application-default login` |

Enable the Google Sheets, Google Docs and Google Drive APIs in the Google
Cloud project of the credentials.

The scope is `drive.file`: InvenTag can touch only files it created. With
`--google-folder-id` it asks for the full Drive scope, because it has to put
a file into a folder that already exists.

## Who can open the files

Files are **private** to the account that creates them. Nothing is shared
unless you ask.

```bash title="Terminal"
inventag --create-google-sheets --create-google-docs \
  --google-credentials key.json \
  --google-share-with you@example.com \
  --google-share-with team@example.com --google-share-role commenter \
  --google-folder-id 1AbCdEfGh \
  --google-title "AWS inventory, May"
```

- `--google-share-with EMAIL` can be repeated. `--google-share-role` sets
  `reader` (default), `commenter` or `writer` for all of them.
- `--google-share-anyone` makes the files readable by anyone who has the link.
  Use it only for data you would publish.
- A service account owns what it creates, in its own Drive, where you cannot
  open it. If you sign in with a service account and give neither
  `--google-share-with` nor `--google-folder-id`, InvenTag warns about this.
- `--google-share-with`, `--google-share-role`, `--google-share-anyone`,
  `--google-folder-id` and `--google-title` without `--create-google-sheets`
  or `--create-google-docs` stop with exit code 2.

## Credentials are never logged

The key file path is not printed, and secrets that look like Google private
keys, access tokens, refresh tokens or client secrets are masked in every log
line, including `--debug`. Error messages from the Google libraries are
shortened to the error type, because they can quote the key file.

## Limits

- A Google Sheets cell holds up to 50,000 characters, and a spreadsheet up to
  10 million cells. A very large inventory can exceed them; the run then fails
  with the Google error.
- The Word report's tables show up to 50 resources per service by default
  (`max_rows`), and so does the Google Doc.
- Cell values are written as text, so a tag value that starts with `=` is not
  run as a formula.

## What is not verified

All tests use mocked Google clients. **No test has run against real Google
APIs**, because that needs a Google account. In particular, the positions
InvenTag computes when it fills the tables of a Google Doc are checked against
the rules of the Docs API as we read them, not against the real service. Try
a small account first, and report a problem with the Doc layout as an issue.

## Where to next

- [Run a scan](./run-a-scan.md)
- [CLI reference](../reference/cli.md#output)
- [Report templates](../templates/index.md)
