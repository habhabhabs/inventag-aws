# Scripts

## Running the CI checks on this host (`scripts/dev/`)

`scripts/dev/ci-local.sh` (Python: `scripts/dev/ci_local.py`) runs what the workflows run, one area at a time:

```bash
scripts/dev/ci-local.sh env --venv .ci-venv --create   # clean venv from requirements.txt and requirements-dev.txt (needs the network)
scripts/dev/ci-local.sh run application --venv .ci-venv
scripts/dev/ci-local.sh run docs --venv .ci-venv
scripts/dev/ci-local.sh run actions --venv .ci-venv
scripts/dev/ci-local.sh plan site --locale fr          # prints the assembled two-locale build; `run site --allow-build` runs it
```

- Without `--venv` (for example `--python /path/to/python`) the run says it is not CI-equal and lists the packages and tools that differ from the pins.
- Tool versions of the runner are in `scripts/dev/ci-tools.json`; the Python packages are pinned in the two requirement files.
- `tests/unit/test_ci_local.py` fails when a workflow no longer contains a listed command, or when a workflow `run:` step is neither listed nor excluded with a reason.
- `site` builds English and one locale (one `docusaurus build --locale` each, under `flock`), assembles them with `website/scripts/assemble-locales.mjs` as `/` and `/<locale>/`, then runs `check:links` and (with `--a11y`) `check:a11y --strict-locales` on the assembly.
