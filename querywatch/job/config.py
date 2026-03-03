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
        return cls(
            source_table=os.getenv("QUERYWATCH_SOURCE_TABLE", "system.query.history"),
            results_table=os.getenv(
                "QUERYWATCH_RESULTS_TABLE", "main.querywatch.optimization_results"
            ),
            top_n=int(os.getenv("QUERYWATCH_TOP_N", "10")),
            n_runs=int(os.getenv("QUERYWATCH_N_RUNS", "3")),
            secret_scope=os.getenv("QUERYWATCH_SECRET_SCOPE", "querywatch-secrets"),
            secret_key=os.getenv("QUERYWATCH_SECRET_KEY", "openrouter-api-key"),
            openrouter_base_url=os.getenv(
                "OPENAI_BASE_URL", "https://openrouter.ai/api/v1"
            ),
        )

