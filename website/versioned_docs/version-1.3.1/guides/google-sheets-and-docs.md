---
title: Google Sheets and Docs output
description: "Write the InvenTag inventory to Google Sheets and Google Docs: how to sign in, who can open the files, how to test it against your own Google account, and what has not been verified against real Google."
sidebar_position: 9
---

# Google Sheets and Docs output

**Who this is for:** you want the inventory in Google Drive instead of, or as
well as, an Excel or Word file.

**What you will know after reading:** how to install the Google libraries,
how to sign in, which flags to use, who can open the files, how to test the
output against your own Google account, and what has not been verified.

## What you get

- `--create-google-sheets` writes the same workbook as `--create-excel` (same
  sheets, same row order) as a Google Sheets spreadsheet.
- `--create-google-docs` writes the same report as `--create-word` as a Google
  Doc.
- InvenTag builds the Excel and Word reports first and copies them. With
  `--template`, InvenTag writes no Google file: it logs that the format is skipped, and the run exits with code 0.
- The run prints the URL of each file, for example `Google Sheet: https://docs.google.com/spreadsheets/d/...`
  and `Google Doc: https://docs.google.com/document/d/...`.
- With `--per-account-reports`, InvenTag makes one pair of files for each
  account. The title ends with ` - ` and the account ID, and the URL lines
  read `Google Sheet: [123456789012] https://...` and `Google Doc: [123456789012] https://...`.
- If a run finds no resources, it makes no Google file.

Not verified against real Google: the files look like the Excel and Word reports, and the URLs have this form.

## Install the Google add-on

Writing to Google needs a few extra Python packages (Google's sign-in and API
libraries). Most people never use Google output, so these packages are not
installed with InvenTag by default. You add them once with this command:

```bash title="Terminal"
pip install "inventag-aws[google]"
```

Read it as "install InvenTag, plus its Google add-on". The part in square
brackets is the name of the add-on. It is not a placeholder, so type it exactly
as shown, with the quotes (zsh, the default shell on macOS, needs them).

- **You already have InvenTag.** Run the same command. pip keeps your
  InvenTag and only adds the Google packages.
- **You installed with pipx.** Run `pipx install "inventag-aws[google]"`, or
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  to add the packages to the InvenTag you already have.
- **You use a virtual environment.** Activate it first, so the packages land
  next to InvenTag.

You do not need the add-on for Excel, Word or anything else. If you use a
Google flag without it, InvenTag stops with exit code 2, says which package is
missing and prints this command.

Not verified against pip and pipx: the install commands for the Google add-on.

## Sign in

Pick one:

| Way | Flag | When to use it |
|---|---|---|
| Service account key | `--google-credentials key.json` | Scheduled runs and CI |
| Your own Google account | `--google-oauth-client client_secret.json` | A run on your laptop. A browser opens once, and the token is saved in `~/.config/inventag/google-token.json`, readable by you only. |
| Application Default Credentials | none | You ran `gcloud auth application-default login` |

Enable the Google Sheets, Google Docs and Google Drive APIs in the Google
Cloud project of the credentials.

InvenTag reads the key file or the OAuth client file before it scans AWS, so a
wrong file stops the run at once with exit code 2 and a message that starts
`inventag: error: Google:`.

The scope is `drive.file`: InvenTag can touch only files it created. With
`--google-folder-id` it asks for the full Drive scope, because it has to put
a file into a folder that already exists.

Not verified against real Google: the browser sign-in, the saved token, Application Default Credentials, the APIs to enable and what the `drive.file` scope allows.

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

Not verified against real Google: that new files stay private, sharing, and that you cannot open a file a service account owns.

## Credentials are never logged

The key file path is not printed, and secrets that look like Google private
keys, access tokens, refresh tokens or client secrets are masked in every log
line, including `--debug`. Error messages from the Google libraries are
shortened to the error type, because they can quote the key file.

## Limits

- A Google Sheets cell holds up to 50,000 characters. InvenTag cuts longer
  text at 49,000 characters. A spreadsheet holds up to 10 million cells and a
  sheet up to 18,278 columns.

  Not verified against real Google: the cell, size and column limits.
- InvenTag counts the cells before it calls Google. If the report is too big,
  it creates nothing and says so, and the run exits with code 1. The Excel and
  Word files are still written. For example:
  `The report has 12,000,000 cells; a Google spreadsheet allows 10,000,000. No
  spreadsheet was created. Send fewer resources (filters or an account subset)
  or use the Excel report.`
- InvenTag sends a big sheet in several requests, each with at most 2,000 rows
  and about 1 million characters.
- If Google answers "429 too many requests", InvenTag logs `Google rate limit
  reached; waiting 5 seconds` and tries again. It waits 5, 10, 20, 40 and then
  60 seconds before the last try.

  Not verified against real Google: the request sizes, and that the 429 waits are long enough.
- If a call fails after the file was created, the run exits with code 1 and the
  message gives the URL of the half-written file: `The spreadsheet was already
  created and may be incomplete: <url> (delete it in Google Drive).` The same
  holds for a Google Doc. Delete that file and run again.
- The Word report's tables show up to 50 resources per service by default
  (`max_rows_per_service` in a report template, `max_rows` in a layout file),
  and so does the Google Doc.
- Cell values are written as text, so a tag value that starts with `=` is not
  run as a formula.

Not verified against real Google: text that starts with `=` is stored as text.

## What is not verified

Most tests use mocked Google clients. **We have not recorded a run against real
Google APIs**, because that needs a Google account. In particular, the
positions InvenTag computes when it fills the tables of a Google Doc are
checked against the rules of the Docs API as we read them, not against the
real service. Try a small account first, and report a problem with the Doc
layout as an issue. Each section above that depends on Google says what is not verified.

## Check it against your own Google account

The repository has a script that does the real-Google test for you. It builds
a fictional estate with moto (a mock of AWS), so it needs no AWS account and
touches only Google. It runs InvenTag with `--create-google-sheets` and
`--create-google-docs`, reads the files back from Google and compares them
with the Excel and Word files made in the same run. It prints a PASS or FAIL
table, the two URLs and `RESULT: PASS` or `RESULT: FAIL`. The exit code is 0
for a pass.

Run it from a checkout of the repository.

1. Install the Google libraries and moto:

   ```bash title="Terminal"
   pip install "inventag-aws[google]"
   pip install moto
   ```

2. In the Google Cloud project of your credentials, enable the Google Sheets
   API, the Google Docs API and the Google Drive API. If one is off, Google
   answers HTTP 403 and the script names the API to enable.
3. Create an OAuth client of type "Desktop app", download it as
   `client_secret.json`, and run:

   ```bash title="Terminal"
   python scripts/google_live_test.py --google-oauth-client client_secret.json --large
   ```

   A browser opens once. If the app is in "Testing" status, add your account
   under OAuth consent screen, Test users.

Not verified against Google Cloud: the console steps to enable the APIs, create the OAuth client and add test users.

To use a service account key, pass `--google-credentials key.json`. The service
account owns the files in its own Drive, so add `--share-with you@example.com`
if you want to open them.

| Flag | What it does |
|---|---|
| `--large` | Also tests a 20,000-row sheet and a 300-row Doc table. It counts the API calls and injects two "429" answers to prove the retry. |
| `--share-with EMAIL` | Shares the files (reader) with this address and checks that only that address and the owner can open them. Repeat it for more. |
| `--keep` | Leaves the files in Drive. By default the script moves every file it made to the Drive trash at the end. |
| `--folder-id ID` | Also creates a pair of files in this Drive folder. This needs the full Drive scope. With `--google-oauth-client`, delete `~/.config/inventag/google-token.json` first, so that it asks again. |

With no sign-in flag, the script uses Application Default Credentials. Google
blocks the sign-in client of `gcloud` for the Drive, Docs and Sheets scopes, so
you need your own OAuth client file here too. Run `python
scripts/google_live_test.py --help` for the exact `gcloud` command. We have not
verified that route. Prefer the OAuth client.

The script checks these things:

- The spreadsheet and the Doc exist and match the printed URL.
- Sheet names and order, rows and columns, and every cell match the Excel file.
- Text that starts with `=` comes back as text, not as a formula.
- Long, accented and CJK text and an empty sheet survive.
- The header row is bold and colored, and the top rows are frozen.
- The headings and every table cell of the Doc match the Word file.
- Both files are private to the account (and to the `--share-with` addresses).

If you run it, please send us the final table. We will change this page only
after a pass on a real account.

## Where to next

- [Run a scan](./run-a-scan.md)
- [CLI reference](../reference/cli.md#output)
- [Report templates](../templates/index.md)
