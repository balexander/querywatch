from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from querywatch.core.models import (
    BenchmarkComparison,
    BenchmarkMetrics,
    QueryRecord,
    RewriteResult,
)
from querywatch.job import entrypoint


def _query_record() -> QueryRecord:
    return QueryRecord(
        query_id="q-1",
        query_text="select * from sales",
        duration_ms=1000,
        bytes_scanned=5000,
        execution_count=4,
        user="alice",
        warehouse_id="wh-1",
        started_at=datetime.now(timezone.utc),
    )


def _rewrite_result() -> RewriteResult:
    return RewriteResult(
        original_query="select * from sales",
        rewritten_query="select * from sales where ds >= current_date() - interval 7 day",
        reasoning="Adds pruning.",
        hypothesized_issue="Missing date predicate.",
        confidence="high",
    )


def _comparison() -> BenchmarkComparison:
    return BenchmarkComparison(
        original_runs=[
            BenchmarkMetrics(duration_ms=1000, bytes_scanned=5000),
            BenchmarkMetrics(duration_ms=900, bytes_scanned=4500),
            BenchmarkMetrics(duration_ms=1100, bytes_scanned=5500),
        ],
        rewritten_runs=[
            BenchmarkMetrics(duration_ms=700, bytes_scanned=3000),
            BenchmarkMetrics(duration_ms=650, bytes_scanned=2800),
            BenchmarkMetrics(duration_ms=720, bytes_scanned=3100),
        ],
        original_median_ms=1000.0,
        rewritten_median_ms=700.0,
        original_bytes_scanned=5000,
        rewritten_bytes_scanned=3000,
    )


def test_main_orchestrates_pipeline_and_writes_rows(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_dbutils = mocker.Mock()
    fake_dbutils.secrets.get.return_value = "or-key"
    fake_client = mocker.Mock()
    query = _query_record()
    rewrite = _rewrite_result()
    comparison = _comparison()

    mocker.patch.object(entrypoint, "_get_spark_session", return_value=fake_spark)
    mocker.patch.object(entrypoint, "_resolve_dbutils", return_value=fake_dbutils)
    mocker.patch.object(entrypoint, "_build_openai_client", return_value=fake_client)
    mocker.patch.object(entrypoint, "_read_query_history", return_value=pd.DataFrame([{"x": 1}]))
    mocker.patch.object(entrypoint, "parse_query_history", return_value=[query])
    mocker.patch.object(entrypoint, "score_queries", return_value=[query])
    mocker.patch.object(entrypoint, "analyze_and_rewrite", return_value=rewrite)
    benchmark_pair_mock = mocker.patch.object(entrypoint, "benchmark_pair", return_value=comparison)
    run_query_mock = mocker.Mock(
        side_effect=[
            (pd.DataFrame({"x": [1]}), BenchmarkMetrics(duration_ms=100, bytes_scanned=1)),
            (pd.DataFrame({"x": [1]}), BenchmarkMetrics(duration_ms=90, bytes_scanned=1)),
        ]
    )
    mocker.patch.object(entrypoint, "_build_run_query", return_value=run_query_mock)
    check_equiv_mock = mocker.patch.object(entrypoint, "check_equivalence", return_value=True)
    to_delta_row_mock = mocker.patch.object(entrypoint, "to_delta_row", return_value={"query_id": "q-1"})
    write_results_mock = mocker.patch.object(entrypoint, "_write_results")

    entrypoint.main()

    fake_dbutils.secrets.get.assert_called_once()
    benchmark_pair_mock.assert_called_once()
    assert run_query_mock.call_count == 2
    check_equiv_mock.assert_called_once()
    to_delta_row_mock.assert_called_once()
    write_results_mock.assert_called_once()


def test_main_sets_improvement_none_when_not_equivalent(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_dbutils = mocker.Mock()
    fake_dbutils.secrets.get.return_value = "or-key"
    query = _query_record()
    rewrite = _rewrite_result()
    comparison = _comparison()
    captured_results = []

    mocker.patch.object(entrypoint, "_get_spark_session", return_value=fake_spark)
    mocker.patch.object(entrypoint, "_resolve_dbutils", return_value=fake_dbutils)
    mocker.patch.object(entrypoint, "_build_openai_client", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_read_query_history", return_value=pd.DataFrame([{"x": 1}]))
    mocker.patch.object(entrypoint, "parse_query_history", return_value=[query])
    mocker.patch.object(entrypoint, "score_queries", return_value=[query])
    mocker.patch.object(entrypoint, "analyze_and_rewrite", return_value=rewrite)
    mocker.patch.object(entrypoint, "benchmark_pair", return_value=comparison)
    run_query_mock = mocker.Mock(
        side_effect=[
            (pd.DataFrame({"x": [1]}), BenchmarkMetrics(duration_ms=100, bytes_scanned=1)),
            (pd.DataFrame({"x": [1, 2]}), BenchmarkMetrics(duration_ms=90, bytes_scanned=1)),
        ]
    )
    mocker.patch.object(entrypoint, "_build_run_query", return_value=run_query_mock)
    mocker.patch.object(entrypoint, "check_equivalence", return_value=False)
    mocker.patch.object(entrypoint, "_write_results")

    def capture(result):
        captured_results.append(result)
        return {"query_id": result.query_record.query_id}

    mocker.patch.object(entrypoint, "to_delta_row", side_effect=capture)

    entrypoint.main()

    assert len(captured_results) == 1
    assert captured_results[0].improvement_pct is None
