# AGENTS.md

> For Codex and OpenAI-compatible agent tools.

---

## Project

**querywatch** — Python 3.11+ wheel deployed as a Databricks Workflow job. Reads `system.query.history`, uses an LLM agent to rewrite slow queries, benchmarks and validates results, writes to Delta.

```bash
pip install -e ".[dev]"
pytest tests/ -v        # must pass without a live workspace
hatch build             # produces dist/*.whl
```

---

## Hard Rules

- `querywatch/core/` must not import `databricks.sdk`, `pyspark`, or any Databricks Runtime library
- `job/entrypoint.py` is the only place Databricks-specific code lives; keep it ~50 lines
- All LLM calls live in `core/agent.py` only — use OpenRouter via the `openai` SDK directly, no LangChain
- Type hints on every function signature
- Pydantic v2 for all domain objects — no raw dicts
- No silent exception handling — log and re-raise
- `improvement_pct` must be `None` when `equivalent=False` — never compute it otherwise
- Every `RewriteResult` must have non-empty `reasoning` and `hypothesized_issue`
- Tests must mock all OpenRouter and Databricks clients — no live calls in CI
- `querywatch/cli/` does not exist yet — `README.md` placeholder only

---

## Interface Contracts

All types (`QueryRecord`, `RewriteResult`, `BenchmarkMetrics`, `BenchmarkComparison`, `BenchmarkResult`) are defined in `core/models.py`.

```python
# core/ingestion.py
def parse_query_history(df: pd.DataFrame) -> list[QueryRecord]: ...

# core/triage.py
# Score = duration_ms * execution_count; sort descending, return top_n
def score_queries(queries: list[QueryRecord], top_n: int = 10) -> list[QueryRecord]: ...

# core/agent.py
def analyze_and_rewrite(
    query: QueryRecord,
    client: openai.OpenAI
) -> RewriteResult: ...

# core/benchmark.py
def benchmark_pair(
    original: str,
    rewritten: str,
    run_query: Callable[[str], tuple[pd.DataFrame, BenchmarkMetrics]],
    n_runs: int = 3,
) -> BenchmarkComparison: ...

# core/validator.py
def check_equivalence(result_a: pd.DataFrame, result_b: pd.DataFrame) -> bool: ...

# core/reporter.py
def to_delta_row(result: BenchmarkResult) -> dict: ...
def to_slack_message(results: list[BenchmarkResult]) -> str: ...  # v2 — stub only
```

---

## What Not to Build in v1

- Slack integration
- CLI entry point
- Lakeview dashboard
- Multi-warehouse or cross-workspace support
- Any web UI or API server
