from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "querywatch" / "core"


def test_core_has_no_databricks_runtime_imports() -> None:
    forbidden_terms = ["databricks.sdk", "pyspark", "from databricks", "import pyspark"]
    violations: list[str] = []

    for path in CORE_DIR.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        if any(term in content for term in forbidden_terms):
            violations.append(path.name)

    assert not violations, f"Forbidden imports found in core modules: {violations}"


def test_openai_usage_lives_only_in_core_agent() -> None:
    violations: list[str] = []
    for path in CORE_DIR.glob("*.py"):
        if path.name == "agent.py":
            continue
        content = path.read_text(encoding="utf-8")
        if "openai" in content:
            violations.append(path.name)

    assert not violations, f"OpenAI references outside agent.py: {violations}"
