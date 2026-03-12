from __future__ import annotations

from querywatch.core.models import QueryRecord


def score_queries(queries: list[QueryRecord], top_n: int = 10) -> list[QueryRecord]:
    if top_n <= 0:
        return []

    ranked = sorted(
        queries,
        key=lambda query: query.duration_ms * query.execution_count,
        reverse=True,
    )
    return ranked[:top_n]

