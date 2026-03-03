from __future__ import annotations

from collections.abc import Callable
from statistics import median

import pandas as pd

from querywatch.core.models import BenchmarkComparison, BenchmarkMetrics


def benchmark_pair(
    original: str,
    rewritten: str,
    run_query: Callable[[str], tuple[pd.DataFrame, BenchmarkMetrics]],
    n_runs: int = 3,
) -> BenchmarkComparison:
    if n_runs < 3:
        raise ValueError("n_runs must be at least 3")

    original_runs: list[BenchmarkMetrics] = []
    rewritten_runs: list[BenchmarkMetrics] = []

    for _ in range(n_runs):
        _, original_metrics = run_query(original)
        _, rewritten_metrics = run_query(rewritten)
        original_runs.append(original_metrics)
        rewritten_runs.append(rewritten_metrics)

    original_median_ms = float(median([run.duration_ms for run in original_runs]))
    rewritten_median_ms = float(median([run.duration_ms for run in rewritten_runs]))

    return BenchmarkComparison(
        original_runs=original_runs,
        rewritten_runs=rewritten_runs,
        original_median_ms=original_median_ms,
        rewritten_median_ms=rewritten_median_ms,
        original_bytes_scanned=_bytes_from_median_run(original_runs, original_median_ms),
        rewritten_bytes_scanned=_bytes_from_median_run(rewritten_runs, rewritten_median_ms),
    )


def _bytes_from_median_run(runs: list[BenchmarkMetrics], median_ms: float) -> int:
    median_run = min(runs, key=lambda run: abs(run.duration_ms - median_ms))
    return median_run.bytes_scanned

