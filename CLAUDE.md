# CLAUDE.md

> Read by Claude Code at the start of every session.
> Update the build status as you go.

---

## Project

**querywatch** — agentic Databricks job: reads `system.query.history` → LLM diagnoses + rewrites slow queries → benchmarks → validates → writes to Delta.

---

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env          # add ANTHROPIC_API_KEY
pytest tests/ -v              # must pass without a live workspace
hatch build                   # produces dist/*.whl for deployment
```

---

## The One Rule That Cannot Break

**`querywatch/core/` must never import `databricks.sdk`, `pyspark`, or anything from Databricks Runtime.**

Allowed in `core/`: stdlib, `anthropic`, `pydantic`, `pandas`, `sqlglot`.

Databricks-specific code lives exclusively in `querywatch/job/`. If you're about to add a Databricks import to `core/`, stop and restructure.

---

## Module Responsibilities

| Module | Does | Does NOT |
|--------|------|----------|
| `core/ingestion.py` | DataFrame → `List[QueryRecord]` | Touch any data source |
| `core/triage.py` | Score + rank `QueryRecord` list | Make LLM calls |
| `core/agent.py` | LLM analyze + rewrite via tool use | Execute queries |
| `core/benchmark.py` | Accept `run_query` callable, measure timing | Know anything Databricks-specific |
| `core/validator.py` | Compare two DataFrames for equivalence | Run queries |
| `core/reporter.py` | Format `BenchmarkResult` for Delta / Slack | Write to Delta or call Slack |
| `job/entrypoint.py` | Wire everything with real Databricks clients | Contain business logic |

---

## LLM Conventions

- Reasoning calls: `claude-sonnet-4-5-20250929` with Anthropic tool use
- Triage calls: `claude-haiku-4-5-20251001`
- All LLM calls live in `core/agent.py` only — never in `job/`
- Every `RewriteResult` must have non-empty `reasoning` and `hypothesized_issue` — blank fields are a bug
- Low-confidence rewrites (`confidence="low"`) are stored in Delta but `improvement_pct` is set to `None`

---

## Benchmarking Rules

- 3 runs minimum per query pair
- Cache bust before each run
- Report median, not mean
- Always record `bytes_scanned` alongside duration — time alone is noisy on serverless
- `improvement_pct` stays `None` until `equivalent=True`

---

## Databricks Configuration

- **System table:** `system.query.history`
- **Results table:** `<catalog>.querywatch.optimization_results` (append-only Delta)
- **Secret scope:** `querywatch-secrets` → key: `anthropic-api-key`
- **Secrets call:** `dbutils.secrets.get(scope="querywatch-secrets", key="anthropic-api-key")`

---

## Key Files

| File | Note |
|------|------|
| `querywatch/core/models.py` | Read this first — single source of truth for data structures |
| `querywatch/core/agent.py` | Most complex — tool use loop lives here |
| `querywatch/job/entrypoint.py` | Should be ~50 lines; no logic |
| `tests/fixtures/` | Add realistic query history rows here |

---

## Build Status

- [ ] Repo + pyproject.toml scaffolded
- [ ] `core/models.py`
- [ ] `core/ingestion.py`
- [ ] `core/triage.py`
- [ ] `core/agent.py`
- [ ] `core/benchmark.py`
- [ ] `core/validator.py`
- [ ] `core/reporter.py`
- [ ] `job/entrypoint.py`
- [ ] Delta table created
- [ ] Tests passing (mocked)
- [ ] Wheel deployed + job running
- [ ] Slack (v2)
- [ ] CLI (v2)
