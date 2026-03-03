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
