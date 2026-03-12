from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pytest

from querywatch.core.benchmark import benchmark_pair
from querywatch.core.models import BenchmarkMetrics


def test_benchmark_pair_runs_each_query_n_times_and_computes_medians() -> None:
    calls: list[str] = []
    per_sql_metrics: dict[str, list[BenchmarkMetrics]] = {
        "select 1": [
            BenchmarkMetrics(duration_ms=300, bytes_scanned=3000),
            BenchmarkMetrics(duration_ms=100, bytes_scanned=1000),
            BenchmarkMetrics(duration_ms=200, bytes_scanned=2000),
        ],
        "select 2": [
            BenchmarkMetrics(duration_ms=700, bytes_scanned=7000),
            BenchmarkMetrics(duration_ms=500, bytes_scanned=5000),
            BenchmarkMetrics(duration_ms=600, bytes_scanned=6000),
        ],
    }
    counters: dict[str, int] = defaultdict(int)

    def run_query(sql: str) -> tuple[pd.DataFrame, BenchmarkMetrics]:
        calls.append(sql)
        idx = counters[sql]
        counters[sql] += 1
        return pd.DataFrame({"x": [1]}), per_sql_metrics[sql][idx]

    comparison = benchmark_pair(
        original="select 1",
        rewritten="select 2",
        run_query=run_query,
        n_runs=3,
    )

    assert calls.count("select 1") == 3
    assert calls.count("select 2") == 3
    assert len(comparison.original_runs) == 3
    assert len(comparison.rewritten_runs) == 3
    assert comparison.original_median_ms == 200
    assert comparison.rewritten_median_ms == 600
    assert comparison.original_bytes_scanned == 2000
    assert comparison.rewritten_bytes_scanned == 6000


def test_benchmark_pair_requires_at_least_three_runs() -> None:
    def run_query(_: str) -> tuple[pd.DataFrame, BenchmarkMetrics]:
        return pd.DataFrame({"x": [1]}), BenchmarkMetrics(duration_ms=10, bytes_scanned=1)

    with pytest.raises(ValueError):
        benchmark_pair(
            original="select 1",
            rewritten="select 2",
            run_query=run_query,
            n_runs=2,
        )
