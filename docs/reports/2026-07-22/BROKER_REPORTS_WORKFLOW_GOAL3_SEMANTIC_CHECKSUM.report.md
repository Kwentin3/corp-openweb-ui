# Broker Reports Workflow Goal 3 — Semantic Checksum

Date: 2026-07-22

Branch: `codex/broker-reports-goal3-semantic-checksum-v1`

Reviewer status:

- `reviewer_kind: delegated_agent`
- `human_reviewed: false`
- `customer_accepted: false`

Status: PASSED

## Executed boundary

The answer model was called through the native OpenWebUI
`/api/chat/completions` route. Its only document evidence was the assembled
private answer context. The answering model had no raw PDF, crop, source file,
sealed reference, Knowledge/RAG or vector access.

Authoritative answer run:

- model: `models/gemini-3.5-flash`;
- Gate 2 run: `art_TnEoBnCY04zQWaBHoXABfd4IAZHQJnNF`;
- answer context: `answerctx_9c3d061c120cb6e4ad76c3f6`;
- context integrity hash:
  `b422b312b6f7f3de2c6911c17f83a7b6af2c62a62549f10a65eb55a00fafeef8`;
- canonical context SHA-256:
  `819b995323a07f3bd2e641abda4241a5a59017460ebe79afa3478e1c07552788`.

## Result

The model returned a compact Markdown table. Deterministic comparison against
the sealed three-metric control vector produced:

| Check | Result |
|---|---:|
| Control metrics | 3 |
| Source labels | 3/3 |
| Amounts | 3/3 |
| Currency or unit | 3/3 |
| Signs | 3/3 |
| Periods | 3/3 |
| Source page/reference | 3/3 |
| Arithmetic reconciliation | 1/1 |
| Semantic-table focused follow-up | passed |
| Duplicate counting findings | 0 |
| Invented control metrics | 0 |
| Technical JSON/internal IDs in chat | 0 |
| Knowledge/RAG/vector delta | 0 |

Private authoritative receipt SHA-256:
`9fd71077755df65450bb8c5dff163bc9736242d8485d8a5fa11b7dce1dbc1084`.

All three metrics had unique resolved context bindings and source references.
One resolved through owner-filtered validated Gate 2 facts; two resolved through
the semantic visual logical-table representation. The focused follow-up used a
semantic-table metric and answered from the same assembled context.

## Comparator history

The first model attempt returned the labels, values and signs but was not
accepted as the authoritative checksum: its periods were incomplete, and a
provider quota error prevented a clean retry. No such response was promoted.

The authoritative Gemini response populated every period and source page. Its
initial receipt still read `failed` because the comparator accepted only exact
literal/ISO periods and exact opaque source refs. A fresh deterministic rescore
accepted only presentation-equivalent forms:

- decimal formatting for amounts;
- unambiguous currency code or symbol;
- literal, ISO, numeric or unambiguous word-month date;
- exact context source ref or exact human-readable page number.

The rescore changed neither the answer nor the sealed reference. It also
corrected the follow-up checker to inspect the complete focused multiline
answer rather than only its heading line.

## Acceptance

| Invariant | Result |
|---|---|
| `BROKER_REPORT_CONTROL_VECTOR` | `THREE_OF_THREE` |
| `SEMANTIC_TABLE_CONTEXT` | `PROVEN` |
| `DOUBLE_COUNTING` | `ZERO` |
| `ANSWER_REPAIR_PERFORMED` | `FALSE` |
| `REFERENCE_MUTATED` | `FALSE` |
| `KNOWLEDGE_RAG_VECTOR_DELTAS` | `ZERO` |

No private label, amount or source content is included in this report.
