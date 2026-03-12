from __future__ import annotations

import pytest

from querywatch.job.config import JobConfig


def test_job_config_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    env_keys = [
        "QUERYWATCH_SOURCE_TABLE",
        "QUERYWATCH_RESULTS_TABLE",
        "QUERYWATCH_TOP_N",
        "QUERYWATCH_N_RUNS",
        "QUERYWATCH_SECRET_SCOPE",
        "QUERYWATCH_SECRET_KEY",
        "OPENAI_BASE_URL",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)

    config = JobConfig.from_env()

    assert config.source_table == "system.query.history"
    # PERSONALIZE: Update this assertion if you replace the default results table.
    assert config.results_table == "dev.de.querywatch_optimization_results"
    assert config.top_n == 10
    assert config.n_runs == 3
    assert config.secret_scope == "querywatch-secrets"
    assert config.secret_key == "openrouter-api-key"
    assert config.openrouter_base_url == "https://openrouter.ai/api/v1"


def test_job_config_rejects_invalid_integer_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERYWATCH_TOP_N", "abc")

    with pytest.raises(ValueError, match="QUERYWATCH_TOP_N must be an integer"):
        JobConfig.from_env()


def test_job_config_rejects_too_few_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERYWATCH_N_RUNS", "2")

    with pytest.raises(ValueError, match="QUERYWATCH_N_RUNS must be >= 3"):
        JobConfig.from_env()


def test_job_config_rejects_empty_required_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERYWATCH_RESULTS_TABLE", "   ")

    with pytest.raises(ValueError, match="QUERYWATCH_RESULTS_TABLE must be non-empty"):
        JobConfig.from_env()


def test_job_config_prefers_task_parameter_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUERYWATCH_TOP_N", "10")
    monkeypatch.setenv("QUERYWATCH_N_RUNS", "3")

    config = JobConfig.from_env({"top_n": "50", "n_runs": "5"})

    assert config.top_n == 50
    assert config.n_runs == 5
