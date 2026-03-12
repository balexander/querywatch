from __future__ import annotations


VALID_QUERY_HISTORY_ROWS: list[dict[str, object]] = [
    {
        "query_id": "q-100",
        "query_text": "select * from sales",
        "duration_ms": "1200",
        "bytes_scanned": "8192",
        "execution_count": "3",
        "user": "alice",
        "warehouse_id": "wh-123",
        "started_at": "2026-03-01T12:00:00Z",
    },
    {
        "query_id": "q-200",
        "query_text": "select count(*) from sales",
        "duration_ms": 300,
        "bytes_scanned": 1024,
        "execution_count": 7,
        "user": "bob",
        "warehouse_id": "wh-123",
        "started_at": "2026-03-02T08:15:00Z",
    },
]

