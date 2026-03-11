# querywatch

Agentic Databricks job that reads `system.query.history`, proposes SQL rewrites with an LLM, benchmarks original vs rewritten queries, validates equivalence, and writes results to Delta.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Test

```bash
python -m pytest tests/ -v
```

## Build wheel

```bash
hatch build
```

## Databricks wheel entrypoint

- Script: `querywatch-job`
- Target: `querywatch.job.entrypoint:main`

## Deploy runbook (Databricks Asset Bundle)

### Prerequisites

1. Databricks CLI v0.290.1+ installed.
2. `~/.databrickscfg` has a working profile (default: `DEFAULT`).
3. Secret scope/key exist with your OpenRouter key:
   - Scope: `querywatch-secrets`
   - Key: `openrouter-api-key`

### One-time secret setup

```bash
databricks secrets create-scope querywatch-secrets
databricks secrets put-secret querywatch-secrets openrouter-api-key
```

### Validate and deploy

Run from repo root:

```bash
source .venv/bin/activate
python -m pytest tests/ -v
hatch build
cd deploy
databricks bundle validate --target dev
databricks bundle deploy --target dev
databricks bundle run querywatch --target dev
```

### Variable overrides

Override deploy-time values with `--var`:

```bash
databricks bundle deploy --target dev \
  --var="job_name=querywatch-dev" \
  # PERSONALIZE: Replace this example results table with your own destination.
  --var="results_table=dev.de.querywatch_optimization_results" \
  --var="source_table=system.query.history" \
  --var="top_n=10" \
  --var="n_runs=3"
```

The canonical bundle file is `deploy/bundle.yml`.

### Update workflow

1. Change code/config.
2. Re-run tests and wheel build.
3. Re-run `databricks bundle deploy --target dev`.
4. Trigger a fresh run with `databricks bundle run querywatch --target dev`.

### Rollback workflow

1. Check out the previous known-good commit/tag.
2. Rebuild wheel (`hatch build`).
3. Re-deploy bundle (`databricks bundle deploy --target dev`).
4. Re-run job to confirm recovery.

## Release checklist

1. Bump version in `pyproject.toml` before release.
2. Run local gates:
   - `python -m pytest tests/ -v`
   - `hatch build`
   - `cd deploy && databricks bundle validate --target dev`
3. Verify artifacts exist:
   - `dist/querywatch-<version>.tar.gz`
   - `dist/querywatch-<version>-py3-none-any.whl`
4. Deploy and run smoke job:
   - `databricks bundle deploy --target dev`
   - `databricks bundle run querywatch --target dev`
