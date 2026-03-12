from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable

import openai
import pandas as pd
import sqlglot.expressions as exp
from sqlglot import parse_one
from sqlglot.errors import ParseError

from querywatch.core.agent import analyze_and_rewrite
from querywatch.core.benchmark import benchmark_pair
from querywatch.core.ingestion import parse_query_history
from querywatch.core.models import BenchmarkMetrics, BenchmarkResult
from querywatch.core.reporter import to_delta_row
from querywatch.core.triage import score_queries
from querywatch.core.validator import check_equivalence
from querywatch.job.config import JobConfig

LOGGER = logging.getLogger(__name__)
ROW_COUNT_COLUMN = "__row_count__"
HISTORY_FETCH_MULTIPLIER = 5
MIN_HISTORY_FETCH_ROWS = 50

PREAGGREGATED_HISTORY_COLUMNS: set[str] = {
    "query_id",
    "query_text",
    "duration_ms",
    "bytes_scanned",
    "execution_count",
    "user",
    "warehouse_id",
    "started_at",
}

RAW_HISTORY_COLUMNS: set[str] = {
    "statement_id",
    "statement_text",
    "total_duration_ms",
    "read_bytes",
    "executed_by",
    "start_time",
}


def main(**task_parameters: str) -> None:
    config = JobConfig.from_env(task_parameters or None)
    spark = _get_spark_session()
    dbutils = _resolve_dbutils(spark)
    api_key = dbutils.secrets.get(scope=config.secret_scope, key=config.secret_key)
    client = _build_openai_client(api_key=api_key, base_url=config.openrouter_base_url)

    query_history_df = _read_query_history(spark, config.source_table, config.top_n)
    queries = parse_query_history(query_history_df)
    benchmarkable_queries = [query for query in queries if _is_benchmarkable_query(query.query_text)]
    if len(benchmarkable_queries) != len(queries):
        LOGGER.info(
            "Skipping %s non-query statements from query history.",
            len(queries) - len(benchmarkable_queries),
        )
    candidates = score_queries(benchmarkable_queries, top_n=config.top_n)
    run_query = _build_run_query(spark)

    results: list[BenchmarkResult] = []
    for query in candidates:
        try:
            rewrite = analyze_and_rewrite(query, client)
            comparison = benchmark_pair(
                original=query.query_text,
                rewritten=rewrite.rewritten_query,
                run_query=run_query,
                n_runs=config.n_runs,
            )
            original_row_count = _run_count_query(spark, query.query_text)
            rewritten_row_count = _run_count_query(spark, rewrite.rewritten_query)
            original_result = pd.DataFrame({ROW_COUNT_COLUMN: [original_row_count]})
            rewritten_result = pd.DataFrame({ROW_COUNT_COLUMN: [rewritten_row_count]})
            equivalent = check_equivalence(original_result, rewritten_result)
            improvement_pct = _calculate_improvement(
                comparison.original_median_ms, comparison.rewritten_median_ms
            ) if equivalent else None
            results.append(
                BenchmarkResult(
                    query_record=query,
                    rewrite_result=rewrite,
                    original_median_ms=comparison.original_median_ms,
                    rewritten_median_ms=comparison.rewritten_median_ms,
                    original_bytes_scanned=comparison.original_bytes_scanned,
                    rewritten_bytes_scanned=comparison.rewritten_bytes_scanned,
                    improvement_pct=improvement_pct,
                    equivalent=equivalent,
                    run_count=config.n_runs,
                    timestamp=datetime.now(timezone.utc),
                )
            )
        except Exception:
            LOGGER.exception("Failed to process query %s.", query.query_id)
            continue

    if results:
        rows = [to_delta_row(result) for result in results]
        _write_results(spark, config.results_table, rows)


def _get_spark_session() -> Any:
    from pyspark.sql import SparkSession

    return SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()


def _resolve_dbutils(spark: Any) -> Any:
    from pyspark.dbutils import DBUtils

    return DBUtils(spark)


def _build_openai_client(api_key: str, base_url: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key, base_url=base_url)


def _read_query_history(spark: Any, source_table: str, top_n: int) -> pd.DataFrame:
    source_columns = set(spark.table(source_table).columns)
    fetch_n = max(top_n * HISTORY_FETCH_MULTIPLIER, MIN_HISTORY_FETCH_ROWS)
    quoted_source = _quote_table_name(source_table)

    if PREAGGREGATED_HISTORY_COLUMNS.issubset(source_columns):
        query = f"""
            SELECT
                query_id,
                query_text,
                CAST(duration_ms AS BIGINT) AS duration_ms,
                CAST(bytes_scanned AS BIGINT) AS bytes_scanned,
                CAST(execution_count AS BIGINT) AS execution_count,
                user,
                warehouse_id,
                started_at
            FROM {quoted_source}
            ORDER BY CAST(duration_ms AS DOUBLE) * CAST(execution_count AS DOUBLE) DESC
            LIMIT {fetch_n}
        """
        return spark.sql(query).toPandas()

    if RAW_HISTORY_COLUMNS.issubset(source_columns) and _has_warehouse_reference(source_columns):
        warehouse_expr = _warehouse_expr(source_columns)
        query = f"""
            WITH base AS (
                SELECT
                    statement_id AS query_id,
                    statement_text AS query_text,
                    CAST(total_duration_ms AS BIGINT) AS duration_ms,
                    CAST(COALESCE(read_bytes, 0) AS BIGINT) AS bytes_scanned,
                    executed_by AS user,
                    {warehouse_expr} AS warehouse_id,
                    start_time AS started_at
                FROM {quoted_source}
                WHERE statement_text IS NOT NULL
            ),
            rolled AS (
                SELECT
                    MAX(query_id) AS query_id,
                    query_text,
                    MAX(duration_ms) AS duration_ms,
                    MAX(bytes_scanned) AS bytes_scanned,
                    CAST(COUNT(*) AS BIGINT) AS execution_count,
                    MAX(user) AS user,
                    warehouse_id,
                    MAX(started_at) AS started_at
                FROM base
                GROUP BY query_text, warehouse_id
            )
            SELECT
                query_id,
                query_text,
                duration_ms,
                bytes_scanned,
                execution_count,
                user,
                warehouse_id,
                started_at
            FROM rolled
            ORDER BY CAST(duration_ms AS DOUBLE) * CAST(execution_count AS DOUBLE) DESC
            LIMIT {fetch_n}
        """
        return spark.sql(query).toPandas()

    raise ValueError(
        f"Source table '{source_table}' does not contain the required columns "
        "for querywatch ingestion."
    )


def _build_run_query(
    spark: Any,
) -> Callable[[str], tuple[pd.DataFrame, BenchmarkMetrics]]:
    def run_query(sql_text: str) -> tuple[pd.DataFrame, BenchmarkMetrics]:
        row_count = _run_count_query(spark, sql_text)
        df = pd.DataFrame({ROW_COUNT_COLUMN: [row_count]})
        metrics = BenchmarkMetrics(duration_ms=0.0, bytes_scanned=0)
        return df, metrics

    return run_query


def _write_results(spark: Any, results_table: str, rows: list[dict[str, Any]]) -> None:
    spark.createDataFrame(rows).write.mode("append").saveAsTable(results_table)


def _calculate_improvement(original_median_ms: float, rewritten_median_ms: float) -> float:
    if original_median_ms <= 0:
        LOGGER.warning("Original median <= 0; returning 0 improvement.")
        return 0.0
    return ((original_median_ms - rewritten_median_ms) / original_median_ms) * 100.0


def _run_count_query(spark: Any, sql_text: str) -> int:
    normalized_sql = _normalize_benchmark_query(sql_text)
    count_sql = (
        f"SELECT COUNT(*) AS {ROW_COUNT_COLUMN} "
        f"FROM ({normalized_sql}) querywatch_count_subquery"
    )
    row = spark.sql(count_sql).collect()[0]
    return int(row[ROW_COUNT_COLUMN])


def _is_benchmarkable_query(sql_text: str) -> bool:
    try:
        _normalize_benchmark_query(sql_text)
    except ValueError:
        return False
    return True


def _normalize_benchmark_query(sql_text: str) -> str:
    try:
        parsed = parse_one(sql_text, read="databricks")
    except ParseError as exc:
        raise ValueError("Only query statements can be benchmarked") from exc

    if not isinstance(parsed, exp.Query):
        raise ValueError("Only query statements can be benchmarked")

    return parsed.sql(dialect="databricks")


def _quote_table_name(table_name: str) -> str:
    parts = [part.strip() for part in table_name.split(".") if part.strip()]
    if not parts:
        raise ValueError("source_table must be a non-empty table identifier")
    return ".".join(f"`{part.replace('`', '``')}`" for part in parts)


def _has_warehouse_reference(source_columns: set[str]) -> bool:
    return "warehouse_id" in source_columns or "compute" in source_columns


def _warehouse_expr(source_columns: set[str]) -> str:
    if "warehouse_id" in source_columns:
        return "warehouse_id"
    if "compute" in source_columns:
        return "compute.warehouse_id"
    raise ValueError("Source table does not include a warehouse_id reference")
