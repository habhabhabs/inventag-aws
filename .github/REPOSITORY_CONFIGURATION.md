# Repository configuration for releases and the docs site

Who this is for: the maintainer who sets up or repairs the GitHub settings that the workflows in `.github/workflows/` need.

What you can do after reading: create the token, variable and environment that releases need, set safe Actions permissions, and control whether a push to `main` releases.

## What happens on a push to main

`release.yml` (Automated Release) runs on every push to `main`:

1. It decides whether to release. A commit whose message contains `[skip release]` (or `[skip ci]`) does not release. The bot's own `chore: bump version to vX.Y.Z` commit never releases. Every other push is a patch release, unless the commit message has a line `Release-As: minor` or `Release-As: major`. A merge commit ("Merge pull request #N") uses the PR label `release:patch`, `release:minor` or `release:major` if it has one.
2. It computes the next version from the latest GitHub release and `inventag/_version.py`. It writes `version.json` and `inventag/_version.py`, commits them as `chore: bump version to vX.Y.Z` and pushes `main`.
3. It tags that commit `vX.Y.Z`, creates the GitHub release and attaches a `.tar.gz` and a `.zip` of the source.
4. It builds the sdist and wheel and uploads them to PyPI through trusted publishing (no API token).

Release runs wait for each other (concurrency group `release-main`), and a release covers every commit on `main` since the previous tag. If two pushes arrive while a release is running, GitHub keeps only the newer queued run; it releases both commits with the bump of the newer one. So push a `Release-As: minor` or `release:minor` change only after the running release has finished. Pushes with `[skip release]` run in a group of their own and never replace a queued release.

The GitHub release starts `release-docs-versioning.yml`. The docs site is built and deployed by `docs-deploy.yml` whenever `docs/`, `website/` or `version.json` changes on `main`.

## Secret: VERSION_BUMP_WORKFLOW

The release, docs-versioning and docs-sync workflows push to `main`, push tags and create releases with this token. Pushes made with the default `GITHUB_TOKEN` do not start other workflows, so the bump commit would not redeploy the docs.

1. Create a fine-grained personal access token limited to this repository.
2. Permissions: **Contents: Read and write** (push commits and tags, create releases). Metadata: Read is added automatically.
3. Save it as the repository secret `VERSION_BUMP_WORKFLOW` (Settings → Secrets and variables → Actions → Secrets).
4. Set a reminder to rotate it before it expires. When it expires, releases fail at the checkout step.

## PyPI trusted publishing

1. On pypi.org, open the `inventag-aws` project → Publishing → add a trusted publisher:
   owner `habhabhabs`, repository `inventag-aws`, workflow `release.yml`, environment `pypi`.
2. In GitHub, create the environment `pypi` (Settings → Environments). Adding required reviewers is optional; with reviewers, every upload waits for an approval.
3. Create the repository variable `PYPI_PUBLISH` with the value `true` (Settings → Secrets and variables → Actions → Variables). Without it the publish job is skipped.

To upload a release that is already tagged but missing on PyPI, run **Automated Release** by hand with `publish_existing_tag` set to the tag, for example `v1.1.3`.

## Actions permissions

Settings → Actions → General:

- **Workflow permissions**: choose **Read repository contents and packages permissions**. Each workflow asks for the extra scopes it needs in its own `permissions:` block.
- **Fork pull request workflows**: keep "Require approval for first-time contributors". Fork pull requests run with a read-only token.

## Branch protection on main

If `main` is protected, the account that owns `VERSION_BUMP_WORKFLOW` must be allowed to push to `main` without a pull request (add it to the bypass list). Otherwise the bump commit is rejected and the release stops before the tag is created.

## Manual jobs

- **Sync Documentation Versions** (`sync-doc-versions.yml`): archives every release tag on `main`'s history that has no snapshot in `website/versioned_docs/` yet and rebuilds `website/versions.json`. Run it with `dry_run` first to see what it would change.
- **Automated Release** by hand: choose `patch`, `minor` or `major`, or fill in `publish_existing_tag` (see above).

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `remote rejected ... protected branch` in the release job | The token owner cannot bypass branch protection on `main`. |
| Release job fails at checkout | `VERSION_BUMP_WORKFLOW` is missing or expired. |
| Publish job skipped | `PYPI_PUBLISH` is not `true`. |
| PyPI upload fails with `invalid-publisher` | The trusted publisher on pypi.org does not match the workflow file name or the `pypi` environment. |
