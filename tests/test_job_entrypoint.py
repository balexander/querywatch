from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

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


def _non_query_record() -> QueryRecord:
    return QueryRecord(
        query_id="q-use",
        query_text="use catalog prod",
        duration_ms=1000,
        bytes_scanned=0,
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
    run_query_mock = mocker.Mock()
    mocker.patch.object(entrypoint, "_build_run_query", return_value=run_query_mock)
    run_count_query_mock = mocker.patch.object(
        entrypoint, "_run_count_query", side_effect=[10, 10]
    )
    check_equiv_mock = mocker.patch.object(entrypoint, "check_equivalence", return_value=True)
    to_delta_row_mock = mocker.patch.object(entrypoint, "to_delta_row", return_value={"query_id": "q-1"})
    write_results_mock = mocker.patch.object(entrypoint, "_write_results")

    entrypoint.main()

    fake_dbutils.secrets.get.assert_called_once()
    benchmark_pair_mock.assert_called_once()
    run_count_query_mock.assert_has_calls(
        [mocker.call(fake_spark, query.query_text), mocker.call(fake_spark, rewrite.rewritten_query)]
    )
    assert run_query_mock.call_count == 0
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
    run_query_mock = mocker.Mock()
    mocker.patch.object(entrypoint, "_build_run_query", return_value=run_query_mock)
    mocker.patch.object(entrypoint, "_run_count_query", side_effect=[100, 90])
    mocker.patch.object(entrypoint, "check_equivalence", return_value=False)
    mocker.patch.object(entrypoint, "_write_results")

    def capture(result):
        captured_results.append(result)
        return {"query_id": result.query_record.query_id}

    mocker.patch.object(entrypoint, "to_delta_row", side_effect=capture)

    entrypoint.main()

    assert len(captured_results) == 1
    assert captured_results[0].improvement_pct is None
    assert run_query_mock.call_count == 0


def test_main_honors_top_n_from_task_parameters(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_dbutils = mocker.Mock()
    fake_dbutils.secrets.get.return_value = "or-key"
    query = _query_record()

    mocker.patch.object(entrypoint, "_get_spark_session", return_value=fake_spark)
    mocker.patch.object(entrypoint, "_resolve_dbutils", return_value=fake_dbutils)
    mocker.patch.object(entrypoint, "_build_openai_client", return_value=mocker.Mock())
    read_query_history_mock = mocker.patch.object(
        entrypoint, "_read_query_history", return_value=pd.DataFrame([{"x": 1}])
    )
    mocker.patch.object(entrypoint, "parse_query_history", return_value=[query])
    score_mock = mocker.patch.object(entrypoint, "score_queries", return_value=[query])
    mocker.patch.object(entrypoint, "analyze_and_rewrite", return_value=_rewrite_result())
    mocker.patch.object(entrypoint, "benchmark_pair", return_value=_comparison())
    mocker.patch.object(entrypoint, "_build_run_query", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_run_count_query", side_effect=[10, 10])
    mocker.patch.object(entrypoint, "check_equivalence", return_value=True)
    mocker.patch.object(entrypoint, "to_delta_row", return_value={"query_id": "q-1"})
    mocker.patch.object(entrypoint, "_write_results")

    entrypoint.main(top_n="50")

    assert read_query_history_mock.call_args[0][2] == 50
    assert score_mock.call_args.kwargs["top_n"] == 50


def test_main_filters_non_query_candidates_before_processing(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_dbutils = mocker.Mock()
    fake_dbutils.secrets.get.return_value = "or-key"
    bad_query = _non_query_record()
    good_query = _query_record()

    mocker.patch.object(entrypoint, "_get_spark_session", return_value=fake_spark)
    mocker.patch.object(entrypoint, "_resolve_dbutils", return_value=fake_dbutils)
    mocker.patch.object(entrypoint, "_build_openai_client", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_read_query_history", return_value=pd.DataFrame([{"x": 1}]))
    mocker.patch.object(entrypoint, "parse_query_history", return_value=[bad_query, good_query])
    score_mock = mocker.patch.object(entrypoint, "score_queries", return_value=[good_query])
    analyze_mock = mocker.patch.object(entrypoint, "analyze_and_rewrite", return_value=_rewrite_result())
    mocker.patch.object(entrypoint, "benchmark_pair", return_value=_comparison())
    mocker.patch.object(entrypoint, "_build_run_query", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_run_count_query", side_effect=[10, 10])
    mocker.patch.object(entrypoint, "check_equivalence", return_value=True)
    mocker.patch.object(entrypoint, "to_delta_row", return_value={"query_id": "q-1"})
    mocker.patch.object(entrypoint, "_write_results")

    entrypoint.main()

    passed_queries = score_mock.call_args[0][0]
    assert len(passed_queries) == 1
    assert passed_queries[0].query_id == "q-1"
    analyze_mock.assert_called_once()


def test_main_skips_query_when_processing_fails_and_continues(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_dbutils = mocker.Mock()
    fake_dbutils.secrets.get.return_value = "or-key"
    q1 = _query_record()
    q2 = QueryRecord(
        query_id="q-2",
        query_text="select count(*) from sales",
        duration_ms=800,
        bytes_scanned=4000,
        execution_count=3,
        user="alice",
        warehouse_id="wh-1",
        started_at=datetime.now(timezone.utc),
    )
    captured_results = []

    mocker.patch.object(entrypoint, "_get_spark_session", return_value=fake_spark)
    mocker.patch.object(entrypoint, "_resolve_dbutils", return_value=fake_dbutils)
    mocker.patch.object(entrypoint, "_build_openai_client", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_read_query_history", return_value=pd.DataFrame([{"x": 1}]))
    mocker.patch.object(entrypoint, "parse_query_history", return_value=[q1, q2])
    mocker.patch.object(entrypoint, "score_queries", return_value=[q1, q2])
    mocker.patch.object(
        entrypoint,
        "analyze_and_rewrite",
        side_effect=[ValueError("bad rewrite"), _rewrite_result()],
    )
    mocker.patch.object(entrypoint, "benchmark_pair", return_value=_comparison())
    mocker.patch.object(entrypoint, "_build_run_query", return_value=mocker.Mock())
    mocker.patch.object(entrypoint, "_run_count_query", side_effect=[10, 10])
    mocker.patch.object(entrypoint, "check_equivalence", return_value=True)
    mocker.patch.object(entrypoint, "_write_results")

    def capture(result):
        captured_results.append(result)
        return {"query_id": result.query_record.query_id}

    mocker.patch.object(entrypoint, "to_delta_row", side_effect=capture)

    entrypoint.main()

    assert [result.query_record.query_id for result in captured_results] == ["q-2"]


def test_run_count_query_rejects_non_query_statement(mocker) -> None:
    fake_spark = mocker.Mock()

    with pytest.raises(ValueError, match="Only query statements can be benchmarked"):
        entrypoint._run_count_query(fake_spark, "use catalog prod")


def test_run_count_query_strips_trailing_semicolon(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_spark.sql.return_value.collect.return_value = [{"__row_count__": 3}]

    count = entrypoint._run_count_query(fake_spark, "select 1;")

    assert count == 3
    generated_sql = fake_spark.sql.call_args[0][0]
    assert "select 1;" not in generated_sql.lower()
    assert "from (select 1)" in generated_sql.lower()


def test_read_query_history_limits_preaggregated_shape_before_to_pandas(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_table = mocker.Mock()
    fake_table.columns = [
        "query_id",
        "query_text",
        "duration_ms",
        "bytes_scanned",
        "execution_count",
        "user",
        "warehouse_id",
        "started_at",
    ]
    fake_spark.table.return_value = fake_table
    fake_spark.sql.return_value.toPandas.return_value = pd.DataFrame([{"query_id": "q-1"}])

    result = entrypoint._read_query_history(fake_spark, "main.query_history", top_n=10)

    sql_text = fake_spark.sql.call_args[0][0]
    assert "FROM `main`.`query_history`" in sql_text
    assert "LIMIT 50" in sql_text
    assert isinstance(result, pd.DataFrame)


def test_read_query_history_supports_raw_system_query_history_shape(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_table = mocker.Mock()
    fake_table.columns = [
        "statement_id",
        "statement_text",
        "total_duration_ms",
        "read_bytes",
        "executed_by",
        "warehouse_id",
        "start_time",
    ]
    fake_spark.table.return_value = fake_table
    fake_spark.sql.return_value.toPandas.return_value = pd.DataFrame([{"query_id": "q-1"}])

    entrypoint._read_query_history(fake_spark, "system.query.history", top_n=5)

    sql_text = fake_spark.sql.call_args[0][0]
    assert "statement_id AS query_id" in sql_text
    assert "statement_text AS query_text" in sql_text
    assert "LIMIT 50" in sql_text


def test_read_query_history_supports_raw_shape_with_compute_struct(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_table = mocker.Mock()
    fake_table.columns = [
        "statement_id",
        "statement_text",
        "total_duration_ms",
        "read_bytes",
        "executed_by",
        "compute",
        "start_time",
    ]
    fake_spark.table.return_value = fake_table
    fake_spark.sql.return_value.toPandas.return_value = pd.DataFrame([{"query_id": "q-1"}])

    entrypoint._read_query_history(fake_spark, "system.query.history", top_n=5)

    sql_text = fake_spark.sql.call_args[0][0]
    assert "compute.warehouse_id AS warehouse_id" in sql_text
    assert "LIMIT 50" in sql_text


def test_read_query_history_raises_for_unknown_schema(mocker) -> None:
    fake_spark = mocker.Mock()
    fake_table = mocker.Mock()
    fake_table.columns = ["a", "b", "c"]
    fake_spark.table.return_value = fake_table

    with pytest.raises(ValueError, match="does not contain the required columns"):
        entrypoint._read_query_history(fake_spark, "unknown.table", top_n=5)
