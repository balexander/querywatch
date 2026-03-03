from datetime import datetime, timezone

from querywatch.core.models import QueryRecord
from querywatch.core.triage import score_queries


def _query(query_id: str, duration_ms: int, execution_count: int) -> QueryRecord:
    return QueryRecord(
        query_id=query_id,
        query_text=f"select {query_id}",
        duration_ms=duration_ms,
        bytes_scanned=1000,
        execution_count=execution_count,
        user="alice",
        warehouse_id="wh-1",
        started_at=datetime.now(timezone.utc),
    )


def test_score_queries_sorts_by_duration_times_execution_count_desc() -> None:
    queries = [
        _query("low", duration_ms=100, execution_count=1),   # 100
        _query("mid", duration_ms=200, execution_count=3),   # 600
        _query("high", duration_ms=1000, execution_count=5), # 5000
    ]

    ranked = score_queries(queries, top_n=3)

    assert [q.query_id for q in ranked] == ["high", "mid", "low"]


def test_score_queries_limits_to_top_n() -> None:
    queries = [
        _query("a", duration_ms=100, execution_count=1),
        _query("b", duration_ms=200, execution_count=1),
        _query("c", duration_ms=300, execution_count=1),
    ]

    ranked = score_queries(queries, top_n=2)

    assert len(ranked) == 2
    assert [q.query_id for q in ranked] == ["c", "b"]


def test_score_queries_returns_empty_for_non_positive_top_n() -> None:
    queries = [_query("a", duration_ms=100, execution_count=1)]
    assert score_queries(queries, top_n=0) == []
