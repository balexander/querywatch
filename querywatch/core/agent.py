from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import openai

from querywatch.core.models import QueryRecord, RewriteResult

LOGGER = logging.getLogger(__name__)

DEFAULT_REASONING_MODEL = "anthropic/claude-sonnet-4.5"


def analyze_and_rewrite(query: QueryRecord, client: openai.OpenAI) -> RewriteResult:
    model = os.getenv("QUERYWATCH_REASONING_MODEL", DEFAULT_REASONING_MODEL)
    prompt = _build_prompt(query)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a SQL performance expert. Return valid JSON with keys: "
                        "rewritten_query, reasoning, hypothesized_issue, confidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = _normalize_content(response.choices[0].message.content)
        if not content:
            raise ValueError("Model returned empty content")

        payload = _normalize_payload(_extract_json_object(content))
        payload["original_query"] = query.query_text
        return RewriteResult(**payload)
    except Exception:
        LOGGER.exception("Failed to analyze and rewrite query_id=%s", query.query_id)
        raise


def _build_prompt(query: QueryRecord) -> str:
    return (
        "Analyze this slow query and propose a faster equivalent rewrite.\n\n"
        f"query_id: {query.query_id}\n"
        f"query_text:\n{query.query_text}\n\n"
        f"duration_ms: {query.duration_ms}\n"
        f"bytes_scanned: {query.bytes_scanned}\n"
        f"execution_count: {query.execution_count}\n"
        f"user: {query.user}\n"
        f"warehouse_id: {query.warehouse_id}\n"
        f"started_at: {query.started_at.isoformat()}\n"
    )


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_json_object(content: str) -> dict[str, Any]:
    candidates: list[str] = []

    stripped = content.strip()
    if stripped:
        candidates.append(stripped)

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL):
        block = match.group(1).strip()
        if block:
            candidates.append(block)

    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if 0 <= first_brace < last_brace:
        candidates.append(content[first_brace : last_brace + 1].strip())

    seen: set[str] = set()
    deduped = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)

    for candidate in deduped:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    snippet = stripped[:200].replace("\n", " ")
    raise ValueError(f"Model response did not contain valid JSON object. Snippet: {snippet}")


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["confidence"] = _normalize_confidence(payload.get("confidence"))
    return normalized


def _normalize_confidence(raw_confidence: Any) -> str:
    if isinstance(raw_confidence, str):
        candidate = raw_confidence.strip().lower()
        if candidate in {"high", "medium", "low"}:
            return candidate
        if "high" in candidate:
            return "high"
        if "medium" in candidate or "med" in candidate:
            return "medium"
        if "low" in candidate:
            return "low"
        try:
            numeric = float(candidate)
        except ValueError:
            return "medium"
        return _confidence_from_numeric(numeric)

    if isinstance(raw_confidence, (int, float)):
        return _confidence_from_numeric(float(raw_confidence))

    return "medium"


def _confidence_from_numeric(value: float) -> str:
    normalized = value
    if normalized > 1.0 and normalized <= 100.0:
        normalized = normalized / 100.0

    if normalized >= 0.8:
        return "high"
    if normalized >= 0.5:
        return "medium"
    return "low"
