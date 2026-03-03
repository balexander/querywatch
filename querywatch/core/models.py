from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class QueryRecord(BaseModel):
    query_id: str
    query_text: str
    duration_ms: int
    bytes_scanned: int
    execution_count: int
    user: str
    warehouse_id: str
    started_at: datetime


class RewriteResult(BaseModel):
    original_query: str
    rewritten_query: str
    reasoning: str
    hypothesized_issue: str
    confidence: Literal["high", "medium", "low"]

    @field_validator("reasoning", "hypothesized_issue")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must be non-empty")
        return value


class BenchmarkMetrics(BaseModel):
    duration_ms: float
    bytes_scanned: int


class BenchmarkComparison(BaseModel):
    original_runs: list[BenchmarkMetrics]
    rewritten_runs: list[BenchmarkMetrics]
    original_median_ms: float
    rewritten_median_ms: float
    original_bytes_scanned: int
    rewritten_bytes_scanned: int


class BenchmarkResult(BaseModel):
    query_record: QueryRecord
    rewrite_result: RewriteResult
    original_median_ms: float
    rewritten_median_ms: float
    original_bytes_scanned: int
    rewritten_bytes_scanned: int
    improvement_pct: float | None
    equivalent: bool
    run_count: int
    timestamp: datetime

    @model_validator(mode="after")
    def _validate_improvement(self) -> "BenchmarkResult":
        if not self.equivalent and self.improvement_pct is not None:
            raise ValueError("improvement_pct must be None when equivalent=False")
        return self

