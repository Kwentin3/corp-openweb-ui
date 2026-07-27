# Broker Reports Gate 2 Financial Semantic V6 Nano Qualification

Date: 2026-07-27  
Goal: 11B  
Evidence status: COMPLETE  
Product gate: `MODEL_NOT_SAFE_FOR_SHADOW`

## Terminal disposition

The one authorized full-scope V6 qualification attempt was committed and
terminated. It must not be repeated.

All ten semantic model-client invocations failed at the local canonical
request-builder boundary with
`gate2_financial_semantic_v6_prompt_contract_mismatch`. The completion
boundary was not reached: no provider output, provider execution metadata,
tokens, or cost were returned.

This is a harness contract defect, not a Nano semantic decision. Therefore
the run cannot establish Nano typed precision, typed recall, or semantic
fitness. The product gate fails closed as `MODEL_NOT_SAFE_FOR_SHADOW`.

## Attempt accounting

| Measure | Result |
| --- | ---: |
| Full-scope qualification attempts | 1 |
| Semantic model-client invocations | 10 |
| Provider transport submissions | 0 |
| Technical-preclose provider calls | 0 |
| Hidden retries | 0 |
| Fallbacks | 0 |
| Repairs | 0 |
| Private case checkpoints | 10 |
| Cases passed by technical preclose | 2 |
| Semantic cases failed before transport | 10 |

The safe receipt's `provider_calls_total=10` counts the ten consumed semantic
model-client slots. Exact private evidence proves that each stopped before
provider transport.

## Hard gates

| Gate | Count |
| --- | ---: |
| Unsafe typed | 0 |
| Unclassified value loss | 0 |
| Inventions | 0 |
| Invalid or absent choices | 10 |
| Wrong type | 0 |
| Canonical failures | 10 |
| Materialization failures | 0 |
| Ownership gaps | 65 |
| Duplicate bindings | 0 |
| Cross-scope bindings | 0 |

Typed precision and recall are both recorded as zero because no model choice
was returned. These values are non-measurements caused by the pre-transport
harness failure, not observed Nano quality.

Provider cost is zero. The recorded 37 ms total latency is local failure
latency and is not provider latency.

## Exact identity and evidence

- Pinned repository revision:
  `43e7cfb838741eadd4ac1beb713c25a7fc51493a`
- Exact model: `gpt-5.4-nano-2026-03-17`
- Provider profile: `openai_gpt`
- Request profile: `financial_semantic_v6_qualification_v1`
- Exact identity hash:
  `7010ab05d3e8f8d4acd86b90fcdd66c9f1db1914711fc0855bedde955769ff4e`
- Terminal safe receipt integrity:
  `c263b2dca517a7b9fbcab100bcadf7331739d7f349bc009601a625a1e651a640`

The terminal receipt, all ten private evidence hashes, all ten
private-to-safe links, and every safe failure receipt hash were independently
recomputed and verified. The safe receipt privacy scan passed. Exact private
evidence remains outside Git.

## Acceptance

| Acceptance item | Result |
| --- | --- |
| `PROVIDER_ATTEMPTS` | `EXACTLY_ONE` |
| `HIDDEN_RETRY` | `ZERO` |
| `EXACT_EVIDENCE` | `PRESERVED` |
| `PRODUCT_GATE` | `MODEL_NOT_SAFE_FOR_SHADOW` |
| Production admissions | `ZERO` |

Goal 11B evidence is complete and mergeable regardless of the failed product
gate. Any later experiment must be a separate program and PR. It must first
correct the prompt-object/request-builder seam without changing Prompt
content, Pack, benchmark, or V6 architecture; this Nano attempt remains
consumed and is not rerun.
