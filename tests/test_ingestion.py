from __future__ import annotations

import pandas as pd
import pytest

from querywatch.core.ingestion import parse_query_history
from tests.fixtures.query_history_rows import VALID_QUERY_HISTORY_ROWS


def test_parse_query_history_maps_dataframe_to_query_records() -> None:
    df = pd.DataFrame(VALID_QUERY_HISTORY_ROWS)

    records = parse_query_history(df)

    assert len(records) == 2
    assert records[0].query_id == "q-100"
    assert records[0].duration_ms == 1200
    assert records[0].bytes_scanned == 8192
    assert records[0].execution_count == 3
    assert records[0].started_at.tzinfo is not None


def test_parse_query_history_raises_for_missing_columns() -> None:
    df = pd.DataFrame(
        [
            {
                "query_id": "q-1",
                "query_text": "select 1",
            }
        ]
    )

    with pytest.raises(ValueError):
        parse_query_history(df)


def test_parse_query_history_raises_for_malformed_rows() -> None:
    df = pd.DataFrame(
        [
            {
                "query_id": "q-1",
                "query_text": "select 1",
                "duration_ms": "not-a-number",
                "bytes_scanned": 1024,
                "execution_count": 2,
                "user": "alice",
                "warehouse_id": "wh-1",
                "started_at": "2026-03-01T00:00:00Z",
            }
        ]
    )

    with pytest.raises(ValueError):
        parse_query_history(df)
