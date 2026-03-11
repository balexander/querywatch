from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class JobConfig:
    source_table: str
    results_table: str
    top_n: int
    n_runs: int
    secret_scope: str
    secret_key: str
    openrouter_base_url: str

    @classmethod
    def from_env(cls) -> "JobConfig":
        source_table = _read_non_empty_env(
            "QUERYWATCH_SOURCE_TABLE", "system.query.history"
        )
        results_table = _read_non_empty_env(
            "QUERYWATCH_RESULTS_TABLE", "main.querywatch.optimization_results"
        )
        top_n = _read_int_env("QUERYWATCH_TOP_N", 10)
        n_runs = _read_int_env("QUERYWATCH_N_RUNS", 3)
        if n_runs < 3:
            raise ValueError("QUERYWATCH_N_RUNS must be >= 3")

        return cls(
            source_table=source_table,
            results_table=results_table,
            top_n=top_n,
            n_runs=n_runs,
            secret_scope=_read_non_empty_env("QUERYWATCH_SECRET_SCOPE", "querywatch-secrets"),
            secret_key=_read_non_empty_env("QUERYWATCH_SECRET_KEY", "openrouter-api-key"),
            openrouter_base_url=_read_non_empty_env(
                "OPENAI_BASE_URL", "https://openrouter.ai/api/v1"
            ),
        )


def _read_non_empty_env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
