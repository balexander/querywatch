from __future__ import annotations

from datetime import datetime, timezone

from querywatch.core.models import BenchmarkResult, QueryRecord, RewriteResult
from querywatch.core.reporter import to_delta_row, to_slack_message


def _benchmark_result() -> BenchmarkResult:
    return BenchmarkResult(
        query_record=QueryRecord(
            query_id="q-1",
            query_text="select * from t",
            duration_ms=1500,
            bytes_scanned=4096,
            execution_count=4,
            user="alice",
            warehouse_id="wh-1",
            started_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        ),
        rewrite_result=RewriteResult(
            original_query="select * from t",
            rewritten_query="select * from t where ds >= current_date() - interval 7 day",
            reasoning="Adds partition pruning.",
            hypothesized_issue="Missing date predicate caused full table scan.",
            confidence="high",
        ),
        original_median_ms=1500.0,
        rewritten_median_ms=900.0,
        original_bytes_scanned=4096,
        rewritten_bytes_scanned=2048,
        improvement_pct=40.0,
        equivalent=True,
        run_count=3,
        timestamp=datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc),
    )


def test_to_delta_row_returns_expected_fields() -> None:
    row = to_delta_row(_benchmark_result())

    assert row["query_id"] == "q-1"
    assert row["original_query"] == "select * from t"
    assert row["rewritten_query"].startswith("select * from t where")
    assert row["reasoning"] == "Adds partition pruning."
    assert row["hypothesized_issue"].startswith("Missing date predicate")
    assert row["equivalent"] is True
    assert row["run_count"] == 3
    assert row["improvement_pct"] == 40.0
    assert row["timestamp"] == "2026-03-03T12:00:00+00:00"


def test_to_slack_message_is_v1_stub() -> None:
    message = to_slack_message([_benchmark_result()])
    assert message == "Slack reporting not implemented in v1."
