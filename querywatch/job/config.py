from __future__ import annotations

import os
from collections.abc import Mapping
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
    def from_env(cls, overrides: Mapping[str, str] | None = None) -> "JobConfig":
        source_table = _read_non_empty_setting(
            "QUERYWATCH_SOURCE_TABLE",
            "source_table",
            "system.query.history",
            overrides,
        )
        # PERSONALIZE: Replace this environment-specific default results table before sharing broadly.
        results_table = _read_non_empty_setting(
            "QUERYWATCH_RESULTS_TABLE",
            "results_table",
            "dev.de.querywatch_optimization_results",
            overrides,
        )
        top_n = _read_int_setting("QUERYWATCH_TOP_N", "top_n", 10, overrides)
        n_runs = _read_int_setting("QUERYWATCH_N_RUNS", "n_runs", 3, overrides)
        if n_runs < 3:
            raise ValueError("QUERYWATCH_N_RUNS must be >= 3")

        return cls(
            source_table=source_table,
            results_table=results_table,
            top_n=top_n,
            n_runs=n_runs,
            secret_scope=_read_non_empty_setting(
                "QUERYWATCH_SECRET_SCOPE",
                "secret_scope",
                "querywatch-secrets",
                overrides,
            ),
            secret_key=_read_non_empty_setting(
                "QUERYWATCH_SECRET_KEY",
                "secret_key",
                "openrouter-api-key",
                overrides,
            ),
            openrouter_base_url=_read_non_empty_setting(
                "OPENAI_BASE_URL",
                "openai_base_url",
                "https://openrouter.ai/api/v1",
                overrides,
            ),
        )


def _read_non_empty_setting(
    env_name: str,
    override_name: str,
    default: str,
    overrides: Mapping[str, str] | None,
) -> str:
    value = _read_setting(env_name, override_name, default, overrides).strip()
    if not value:
        raise ValueError(f"{env_name} must be non-empty")
    return value


def _read_int_setting(
    env_name: str,
    override_name: str,
    default: int,
    overrides: Mapping[str, str] | None,
) -> int:
    raw = _read_setting(env_name, override_name, str(default), overrides).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer") from exc


def _read_setting(
    env_name: str,
    override_name: str,
    default: str,
    overrides: Mapping[str, str] | None,
) -> str:
    if overrides is not None and override_name in overrides:
        return overrides[override_name]
    return os.getenv(env_name, default)
