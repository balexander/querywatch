from __future__ import annotations

import json
import logging
import os

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
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Model returned empty content")

        payload = json.loads(_strip_json_fence(content))
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


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1])
    return stripped

