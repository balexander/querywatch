from __future__ import annotations

import logging

import pandas as pd

from querywatch.core.models import QueryRecord

LOGGER = logging.getLogger(__name__)

REQUIRED_COLUMNS: set[str] = {
    "query_id",
    "query_text",
    "duration_ms",
    "bytes_scanned",
    "execution_count",
    "user",
    "warehouse_id",
    "started_at",
}


def parse_query_history(df: pd.DataFrame) -> list[QueryRecord]:
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    records: list[QueryRecord] = []
    for idx, row in enumerate(df.to_dict(orient="records")):
        try:
            records.append(
                QueryRecord(
                    query_id=str(row["query_id"]),
                    query_text=str(row["query_text"]),
                    duration_ms=int(row["duration_ms"]),
                    bytes_scanned=int(row["bytes_scanned"]),
                    execution_count=int(row["execution_count"]),
                    user=str(row["user"]),
                    warehouse_id=str(row["warehouse_id"]),
                    started_at=pd.to_datetime(row["started_at"], utc=True).to_pydatetime(),
                )
            )
        except Exception as exc:
            LOGGER.exception("Failed to parse query history row at index %s", idx)
            raise ValueError(f"Failed to parse row at index {idx}") from exc

    return records

