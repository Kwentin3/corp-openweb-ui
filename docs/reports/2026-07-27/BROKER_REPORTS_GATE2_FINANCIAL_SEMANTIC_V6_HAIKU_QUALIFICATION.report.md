# Broker Reports Gate 2 Financial Semantic V6 Haiku Qualification

Date: 2026-07-27  
Goal: 12  
Evidence status: COMPLETE  
Product gate: `MODEL_NOT_SAFE_FOR_SHADOW`

## Candidate decision

Goal 12 selected exactly one stronger candidate:
`claude-haiku-4-5-20251001` through `anthropic_claude`.

The candidate was published live and was already present in the repository
economy qualification policy. Nano was not rerun. Prompt content, Pack,
benchmark, choice schema, deterministic expansion, validator, materializer,
and evidence contracts remained frozen. The only experiment variable was the
exact model/provider candidate.

The zero-call preflight passed:

| Acceptance | Result |
| --- | --- |
| Architecture | `FROZEN` |
| One new candidate | `EXACT` |
| Model comparison | `SAME_V6_WORKLOAD` |
| Provider calls | `ZERO` |
| Production admissions | `ZERO` |

## Terminal attempt

One full-scope candidate attempt was committed and terminated. It must not be
repeated under this identity.

| Measure | Result |
| --- | ---: |
| Qualification attempts | 1 |
| Semantic provider calls | 10 |
| Technical-preclose provider calls | 0 |
| Hidden retries | 0 |
| Fallbacks | 0 |
| Repairs | 0 |
| Private case checkpoints | 10 |
| Provider metadata captures | 10 |
| Technical cases passed | 2 |
| Semantic cases admitted | 0 |

Six calls exceeded the actual 3072 input-token limit after provider
execution. The observed input sizes for those calls were 3104–3391 tokens.
Four calls stayed within that limit but failed the execution-identity gate
because the provider metadata omitted `total_tokens`.

All ten provider decisions therefore failed closed before canonical
admission. No decision was repaired, inferred, retried, or materialized as
product authority.

## Product gates

| Gate | Count |
| --- | ---: |
| Unsafe typed | 0 |
| Unclassified value loss | 0 |
| Inventions | 0 |
| Invalid or unavailable choices | 6 |
| Wrong type | 0 |
| Canonical failures | 10 |
| Materialization failures | 0 |
| Ownership gaps | 65 |
| Duplicate bindings | 0 |
| Cross-scope bindings | 0 |

Official typed precision, typed recall, and unclassified rate are zero because
no provider decision passed execution identity and canonical admission. They
must not be read as accepted model-quality measurements.

## Safe accounting reconciliation

The terminal runner receipt records usage and cost only for the four calls
whose budget receipt completed:

- input tokens: 5942;
- output tokens: 112;
- captured cost: USD 0.006502;
- elapsed latency: 35,996 ms.

Independent aggregation of all ten exact provider metadata captures gives:

- input tokens: 25,739;
- output tokens: 345;
- provider-reported duration: 35,954 ms;
- policy-tariff cost from captured usage: USD 0.027464.

The latter is the complete qualification cost. The receipt value is a lower
bound caused by the six post-response budget exceptions.

## Diagnostic-only semantic readback

No-call offline diagnostics were run against exact available private
evidence. They are not admission authority.

- Four semantic choices were preserved and parseable.
- All four selected `unclassified_financial_input`.
- Their deterministic retention and materialization checks passed.
- None of the four matched the frozen expected reason code.
- The four available cases contained no expected typed case.
- Six semantic choices were not exposed by the budget exception; the exact
  preserved object was the safe budget-failure receipt, not the model choice.

Consequently Haiku semantic precision/recall cannot be reconstructed for the
full benchmark, and the candidate remains not safe.

## Exact identity and evidence

- Pinned repository revision:
  `580dd04d22231a85cd9a9de49cc9a96769b0e998`
- Exact model: `claude-haiku-4-5-20251001`
- Provider profile: `anthropic_claude`
- Preflight integrity:
  `924ac214d45fd5dc89f7ba3cea50ee80b9f2db43fdb4195fdb9112fd04b84038`
- Terminal safe receipt integrity:
  `774b58a9c23cdcd943154cd448b44458a769dbb255d8ff05aba4738fe8a508dd`

The terminal receipt, ten private evidence hashes, ten private-to-safe links,
and ten safe case-receipt hashes were independently recomputed and verified.
The repository-safe receipt passed the privacy scan. Exact available private
evidence remains outside Git.

## Goal 12 acceptance and next gate

| Acceptance item | Result |
| --- | --- |
| `ARCHITECTURE` | `FROZEN` |
| `ONE_NEW_CANDIDATE` | `EXACT` |
| `MODEL_COMPARISON` | `SAME_V6_WORKLOAD` |
| Product gate | `MODEL_NOT_SAFE_FOR_SHADOW` |
| Production admissions | `ZERO` |

Goal 12 evidence is mergeable independently of its failed product outcome.
Goal 13 is not permitted because no exact V6 model has
`MODEL_SAFE_FOR_SHADOW`. Goal 14 may proceed as an architecture and frozen
baseline proof without activating V6 production.
