from __future__ import annotations

from datetime import datetime, timezone

import pytest

from querywatch.core.agent import analyze_and_rewrite
from querywatch.core.models import QueryRecord


def _query_record() -> QueryRecord:
    return QueryRecord(
        query_id="q-123",
        query_text="select * from sales",
        duration_ms=1200,
        bytes_scanned=10_000,
        execution_count=5,
        user="alice",
        warehouse_id="wh-1",
        started_at=datetime.now(timezone.utc),
    )


def _response_with_content(mocker, content: str):
    message = mocker.Mock(content=content)
    choice = mocker.Mock(message=message)
    return mocker.Mock(choices=[choice])


def test_analyze_and_rewrite_returns_rewrite_result_and_builds_prompt(mocker) -> None:
    query = _query_record()
    client = mocker.Mock()
    client.chat.completions.create.return_value = _response_with_content(
        mocker,
        """
        {
          "rewritten_query": "select * from sales where ds >= current_date() - interval 7 day",
          "reasoning": "Adds partition pruning.",
          "hypothesized_issue": "Missing date filter led to full scan.",
          "confidence": "high"
        }
        """,
    )

    result = analyze_and_rewrite(query, client)

    assert result.original_query == query.query_text
    assert "partition pruning" in result.reasoning.lower()
    assert result.confidence == "high"

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"]
    prompt = kwargs["messages"][1]["content"]
    assert query.query_text in prompt
    assert str(query.execution_count) in prompt
    assert str(query.duration_ms) in prompt


def test_analyze_and_rewrite_rejects_missing_reasoning_or_issue(mocker) -> None:
    query = _query_record()
    client = mocker.Mock()
    client.chat.completions.create.return_value = _response_with_content(
        mocker,
        """
        {
          "rewritten_query": "select 1",
          "confidence": "low"
        }
        """,
    )

    with pytest.raises(Exception):
        analyze_and_rewrite(query, client)


def test_analyze_and_rewrite_logs_and_reraises_api_errors(mocker, caplog) -> None:
    query = _query_record()
    client = mocker.Mock()
    client.chat.completions.create.side_effect = RuntimeError("openrouter unavailable")

    with pytest.raises(RuntimeError):
        analyze_and_rewrite(query, client)

    assert "Failed to analyze and rewrite query_id=q-123" in caplog.text
