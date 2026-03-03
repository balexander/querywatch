from __future__ import annotations

from querywatch.core.models import BenchmarkResult


def to_delta_row(result: BenchmarkResult) -> dict:
    return {
        "query_id": result.query_record.query_id,
        "query_text": result.query_record.query_text,
        "original_query": result.rewrite_result.original_query,
        "rewritten_query": result.rewrite_result.rewritten_query,
        "reasoning": result.rewrite_result.reasoning,
        "hypothesized_issue": result.rewrite_result.hypothesized_issue,
        "confidence": result.rewrite_result.confidence,
        "original_median_ms": result.original_median_ms,
        "rewritten_median_ms": result.rewritten_median_ms,
        "original_bytes_scanned": result.original_bytes_scanned,
        "rewritten_bytes_scanned": result.rewritten_bytes_scanned,
        "improvement_pct": result.improvement_pct,
        "equivalent": result.equivalent,
        "run_count": result.run_count,
        "timestamp": result.timestamp.isoformat(),
    }


def to_slack_message(results: list[BenchmarkResult]) -> str:
    _ = results
    return "Slack reporting not implemented in v1."

