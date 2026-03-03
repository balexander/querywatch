from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable

import openai
import pandas as pd

from querywatch.core.agent import analyze_and_rewrite
from querywatch.core.benchmark import benchmark_pair
from querywatch.core.ingestion import parse_query_history
from querywatch.core.models import BenchmarkMetrics, BenchmarkResult
from querywatch.core.reporter import to_delta_row
from querywatch.core.triage import score_queries
from querywatch.core.validator import check_equivalence
from querywatch.job.config import JobConfig

LOGGER = logging.getLogger(__name__)


def main() -> None:
    config = JobConfig.from_env()
    spark = _get_spark_session()
    dbutils = _resolve_dbutils(spark)
    api_key = dbutils.secrets.get(scope=config.secret_scope, key=config.secret_key)
    client = _build_openai_client(api_key=api_key, base_url=config.openrouter_base_url)

    query_history_df = _read_query_history(spark, config.source_table)
    queries = parse_query_history(query_history_df)
    candidates = score_queries(queries, top_n=config.top_n)
    run_query = _build_run_query(spark)

    results: list[BenchmarkResult] = []
    for query in candidates:
        rewrite = analyze_and_rewrite(query, client)
        comparison = benchmark_pair(
            original=query.query_text,
            rewritten=rewrite.rewritten_query,
            run_query=run_query,
            n_runs=config.n_runs,
        )
        original_result, _ = run_query(query.query_text)
        rewritten_result, _ = run_query(rewrite.rewritten_query)
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


def _read_query_history(spark: Any, source_table: str) -> pd.DataFrame:
    return spark.table(source_table).toPandas()


def _build_run_query(
    spark: Any,
) -> Callable[[str], tuple[pd.DataFrame, BenchmarkMetrics]]:
    def run_query(sql_text: str) -> tuple[pd.DataFrame, BenchmarkMetrics]:
        df = spark.sql(sql_text).toPandas()
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
