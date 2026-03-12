from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from querywatch.core.models import BenchmarkResult, QueryRecord, RewriteResult


def _query_record() -> QueryRecord:
    return QueryRecord(
        query_id="q-1",
        query_text="select 1",
        duration_ms=1000,
        bytes_scanned=1024,
        execution_count=5,
        user="alice",
        warehouse_id="wh-1",
        started_at=datetime.now(timezone.utc),
    )


def _rewrite_result() -> RewriteResult:
    return RewriteResult(
        original_query="select 1",
        rewritten_query="select 1",
        reasoning="No-op rewrite for baseline.",
        hypothesized_issue="None",
        confidence="high",
    )


def test_rewrite_result_requires_non_empty_reasoning() -> None:
    with pytest.raises(ValidationError):
        RewriteResult(
            original_query="select 1",
            rewritten_query="select 1",
            reasoning="   ",
            hypothesized_issue="Missing partition filter.",
            confidence="medium",
        )


def test_rewrite_result_requires_non_empty_hypothesized_issue() -> None:
    with pytest.raises(ValidationError):
        RewriteResult(
            original_query="select 1",
            rewritten_query="select 1",
            reasoning="Added filter.",
            hypothesized_issue="",
            confidence="medium",
        )


def test_benchmark_result_requires_none_improvement_when_not_equivalent() -> None:
    with pytest.raises(ValidationError):
        BenchmarkResult(
            query_record=_query_record(),
            rewrite_result=_rewrite_result(),
            original_median_ms=1000.0,
            rewritten_median_ms=900.0,
            original_bytes_scanned=1024,
            rewritten_bytes_scanned=1024,
            improvement_pct=10.0,
            equivalent=False,
            run_count=3,
            timestamp=datetime.now(timezone.utc),
        )


def test_benchmark_result_allows_improvement_when_equivalent() -> None:
    result = BenchmarkResult(
        query_record=_query_record(),
        rewrite_result=_rewrite_result(),
        original_median_ms=1000.0,
        rewritten_median_ms=900.0,
        original_bytes_scanned=1024,
        rewritten_bytes_scanned=800,
        improvement_pct=10.0,
        equivalent=True,
        run_count=3,
        timestamp=datetime.now(timezone.utc),
    )

    assert result.improvement_pct == 10.0
