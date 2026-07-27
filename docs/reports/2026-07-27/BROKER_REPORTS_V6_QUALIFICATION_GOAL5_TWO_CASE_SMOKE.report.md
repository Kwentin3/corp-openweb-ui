# Broker Reports — V6 qualification Goal 5 two-case provider smoke

Date: 2026-07-27

Base revision: `4bcb986dfa1a8ce362e6d4c0ec35888fc549de4e`

Executed implementation revision: `f8ee9fa4723640f988df3f62341ca9c71151e35c`

## Result

| Acceptance item | Result |
| --- | --- |
| `PROVIDER_SUBMISSIONS` | `TWO` |
| `TYPED_SMOKE` | `FAILED` |
| `UNCLASSIFIED_SMOKE` | `FAILED` |
| `USAGE_NORMALIZATION` | `FAILED` |
| `OFFLINE_REPLAY` | `FAILED` |
| Terminal class | `PROVIDER_RESPONSE_INVALID` |
| Model qualification performed | `FALSE` |
| Production admissions | `ZERO` |
| Stage mutations | `ZERO` |

The exact Nano candidate was submitted once for the typed smoke case and once
for the unclassified smoke case. Both submissions reached the provider
transport and both returned a provider response. Both responses failed at the
provider response-format boundary with the safe failure code
`gate2_model_schema_response_format_rejected`.

No model semantic choice crossed the parsing boundary. This is not a model
semantic failure and does not classify Nano as either safe or unsafe for
shadow.

## Lifecycle accounting

| Boundary | Count |
| --- | ---: |
| Local invocations | 2 |
| Provider submissions | 2 |
| Provider responses | 2 |
| Technically admitted semantic decisions | 0 |
| Product-admitted decisions | 0 |
| Offline exact replays | 0 |
| Qualification attempts | 0 |
| Hidden retries | 0 |
| Fallbacks | 0 |
| Repairs | 0 |

The smoke is deliberately not a qualification, so it does not publish
precision, recall, quality or a product gate. It consumed the two authorized
provider submissions and was not repeated.

## Smoke boundary results

| Required boundary | Result |
| --- | --- |
| Request actually sent | Passed for both cases |
| Provider response received | Passed for both cases |
| Usage normalized | Failed; no valid model response metadata was admitted |
| Semantic choice parsed | Not reached |
| Deterministic expansion | Not reached |
| Product validation | Not reached |
| Product materialization | Not reached |
| Evidence replay | Not reached |

The safe receipt accounts zero input tokens, zero output tokens and
`0` USD because neither rejected response supplied admissible usage/cost
metadata. It does not make a claim about provider billing outside the recorded
response contract.

## Reused authorities

The smoke reuses the accepted V6 qualification fixture and exact execution
identity, canonical Prompt/request builder and response format, canonical
model-client factory and lifecycle counters, Evidence Bundle, Candidate
Compiler, Typed Options, deterministic expansion, generic
validator/materializer and evidence replay implementation.

The only new evidence contract is
`broker_reports_gate2_financial_semantic_v6_provider_smoke_v1`. A separate
safe smoke receipt is necessary because reusing the full qualification receipt
would falsely imply a benchmark, precision/recall publication and product-gate
decision. This is an evidence-only distinction; no product semantic contract
or architecture was added.

## Evidence and privacy

Canonical safe receipt:
`BROKER_REPORTS_V6_QUALIFICATION_GOAL5_TWO_CASE_SMOKE.receipt.safe.json`

Receipt integrity verification: `EXACT`

Receipt integrity SHA-256:
`7b5e38c9fe157eaecfae972b17f07b3151f7163d6ca455a661941a5937f69a97`

Two non-empty exact evidence checkpoints were written outside Git. Their
private paths, raw provider payloads, exact model values, credentials and
customer bytes are absent from this report and the safe receipt.

## Verification

```text
Goal 5 runner tests: 17 passed
All V6 tests: 122 passed
Full service suite: 1827 passed, 20 skipped
Targeted Ruff: All checks passed
Live smoke CLI import/help: passed
Safe receipt integrity: EXACT
Private evidence checkpoints: 2 non-empty files outside Git
```

The implementation was committed and the worktree was clean before the live
smoke. The safe receipt identifies that exact implementation revision. The
only subsequent changes are this report and the canonical safe receipt.

## Unchanged contracts

Semantic Pack, compact projection, four-block packet, minimal choice,
deterministic expansion, generic validator/materializer, Managed Domain,
Domain API, qualification scorer, provider selection, stage Action and
production admissions remain unchanged. No financial-semantic regex,
fallback, repair or hidden retry was added.

## Review and continuation

Goal 5 acceptance is not met. Goal 6 requires a passed Goal 5 and therefore
must not run. Goal 7 is permitted only after an actual Nano semantic-unsafe
verdict; this run produced no semantic verdict, so Goal 7 must not run either.
Goals 8–10 consequently remain blocked.

Continuation requires an explicit new provider-schema policy or candidate
decision. It must not reuse these consumed smoke paths or silently retry either
submission.
