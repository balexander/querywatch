# MEMORY.md

> Living state document. Update as decisions are made and questions are resolved.
> Commit alongside code.

---

## User

- Data engineer, admin access to a Unity Catalog Databricks workspace
- Comfortable with Python and SQL; learning LLM/agent patterns and Databricks job packaging by building
- Spare-time project — scope discipline matters
- Goal: portfolio piece + something genuinely useful at work

---

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Deployment | Databricks job | Admin + system tables = richer data than REST API; runs automatically |
| CLI path | v2, no refactor needed | core/job separation preserves it from day one |
| LLM | Anthropic (Sonnet + Haiku) | Sonnet for reasoning, Haiku for cheap triage passes |
| Agent framework | Raw Anthropic SDK tool use | Learning the primitives; LangChain hides the loop |
| Results | Append-only Delta table | Historical trends; never overwrite prior runs |
| Triage formula | `duration_ms × execution_count` | Biases toward recurring expensive queries, not one-off monsters |
| v1 output | Delta table only | Slack + dashboard are v2 |

---

## Open Questions

- Which catalog and schema for `optimization_results`?
- Lookback window: 7 days default, configurable via job widget?
- Top-N per run: 5 default?
- How to handle parameterized queries with redacted literals in query history?
- Cache busting on serverless vs classic warehouse — same mechanism?

---

## Interview Notes

- The core/job separation is a talking point: "the CLI is a thin wrapper over the same core, no refactor needed"
- The triage formula is intentionally simple and explainable — say that
- `equivalent=False` results are stored but flagged — shows the tool is honest about failures, not just successes
- This runs on real workspace data — not a toy benchmark
