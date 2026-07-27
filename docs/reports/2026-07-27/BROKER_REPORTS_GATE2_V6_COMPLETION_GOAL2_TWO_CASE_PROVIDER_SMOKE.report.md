# Broker Reports — Gate 2 V6 completion Goal 2 provider smoke

Date: 2026-07-27

Base revision: `2a58880c8426adef48b288a1d3d268651cd3905d`

Executed implementation revision:
`7eac4b65a5f5f3d6d5afb1334a04ff79456736a3`

Execution-identity correction revision:
`75d39260bbbea670206ea2909dd88c2fd33600fb`

## Result

Goal 2 is terminal but not accepted. The two authorized exact Nano submissions
were consumed and were not retried. Both provider responses were received.
The executed revision stopped both responses at the V6 execution-identity
boundary, before semantic admission, with
`financial_semantic_v6_provider_schema_identity_mismatch`.

The failure was a harness defect, not a provider transport failure and not a
model-safety verdict. Adapter `1.1.0` correctly recorded a provider-only
root-object projection with distinct canonical/adapted schema hashes and one
schema transform. The execution-identity owner still required the obsolete
pre-projection state: equal hashes and zero transforms.

The existing execution-identity owner was corrected without a new adapter,
builder, validator or materializer. It now obtains the exact expected
projection from `Gate2ProviderAdapterFactory.create`. Exact offline processing
of both preserved provider outputs then passed schema identity, parsing,
normalization, usage normalization, materialization and zero-call evidence
replay.

The post-correction semantic observations still fail the smoke:

- the typed response had the required typed disposition but selected the wrong
  exact prebound option;
- the unclassified response did not select the required unclassified
  disposition.

No full benchmark was run.

## Acceptance

| Acceptance item | Result |
| --- | --- |
| `PROVIDER_SUBMISSIONS` | `TWO` |
| `PROVIDER_RESPONSES` | `TWO` |
| `TYPED_SMOKE` | `FAILED` |
| `UNCLASSIFIED_SMOKE` | `FAILED` |
| `USAGE_NORMALIZATION` | `PASSED_AFTER_IDENTITY_CORRECTION` |
| `OFFLINE_REPLAY` | `EXACT_AFTER_IDENTITY_CORRECTION` |
| `FALLBACK_REPAIR_RETRY` | `ZERO` |
| `MODEL_QUALIFICATION_PERFORMED` | `FALSE` |
| `MODEL_SAFETY_VERDICT` | `NONE` |
| `PRODUCTION_ADMISSIONS` | `ZERO` |
| `STAGE_MUTATIONS` | `ZERO` |
| `GOAL2` | `NOT_ACCEPTED` |
| `GOAL3` | `BLOCKED` |

The smoke does not publish precision, recall, product-gate status or a
safe/unsafe-for-shadow classification.

## Lifecycle accounting

| Boundary | Count |
| --- | ---: |
| Original local invocations | 2 |
| Original provider submissions | 2 |
| Original provider responses | 2 |
| Additional provider submissions | 0 |
| Offline diagnostic provider submissions | 0 |
| Exact offline replays after correction | 2 |
| Qualification attempts | 0 |
| Hidden retries | 0 |
| Fallbacks | 0 |
| Provider-output repairs | 0 |
| Production admissions | 0 |

The original safe receipt reports 4,984 input tokens, 118 output tokens,
7,078 ms aggregate latency and USD 0.001144300 recorded cost.

## Root-cause evidence

Both exact private checkpoints independently recorded:

- adapter version `1.1.0`;
- canonical schema hash equal to the frozen V6 Choice schema hash;
- adapted schema hash distinct from the canonical hash;
- schema transform count `1`;
- the same safe failure code
  `financial_semantic_v6_provider_schema_identity_mismatch`.

The original receipt and both private checkpoint hashes verify exactly. The
offline diagnostic rebuilt the frozen case authorities and proved:

- exact canonical request equality;
- exact response-format hash equality;
- execution identity accepted against the adapter-owned projection;
- provider content parsed and normalized without mutation;
- total materialization passed;
- exact evidence replay passed with zero provider calls;
- normalized usage arithmetic passed.

Raw provider content, response IDs, source values, credentials and private
paths remain outside Git.

## Evidence

- [Original terminal safe receipt](BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE.receipt.safe.json)
  — integrity SHA-256
  `e6e56108fd3588c12631f6c8778fbabb813adc803912d5cb0ebedef9abe69f36`.
- [Post-correction offline diagnostic](BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE_OFFLINE_DIAGNOSTIC.receipt.safe.json)
  — integrity SHA-256
  `2ee7c9779cd459dfa668b3a98dd88537ca18f855d50443f431a757a8169671d3`.

The diagnostic is supplemental evidence. It does not rewrite the original
terminal receipt or claim that the executed revision passed.

## Authority and contract impact

Affected authorities:

- `smoke_financial_semantic_v6` — bounded two-case lifecycle and safe receipt;
- `Gate2FinancialSemanticV6ExecutionIdentityFactory.create` — exact admission
  of adapter-produced execution metadata;
- `Gate2ProviderAdapterFactory.create` — reused as the sole provider projection
  authority.

Unchanged contracts:

- Financial Semantic Pack meanings;
- Prompt;
- canonical V6 Choice meaning and schema;
- Evidence Bundle;
- Candidate Compiler and Typed Options;
- deterministic expansion;
- validator and total materializer;
- Financial Domain and Query API;
- frozen benchmark cases;
- provider candidate and request profile.

The three production bundles were rebuilt from source and remained
byte-identical because qualification-only modules are not shipped in those
runtime bundles.

## Verification

```text
Zero-call runtime preflight: PASSED
Action/repository/live parity: EXACT
Adapter projection revision: openai_response_format:1.1.0
Focused smoke tests: 4 passed
Final V6 identity/smoke/evidence/adapter regression: 116 passed
Architecture + bundle precheck: 27 passed
Full service suite: 1842 passed, 20 skipped, 5 SWIG-only warnings
Targeted Ruff: PASSED
Original safe receipt integrity: EXACT
Supplemental safe receipt integrity: EXACT
Private checkpoint hash verification: 2/2 EXACT
Offline replay after correction: 2/2 EXACT, provider calls 0
```

## Continuation boundary

Goal 2 acceptance requires both semantic smoke cases to pass. They did not.
The two-call authorization is consumed and must not be reused. Goal 3 full
Nano qualification must not run. Continuing requires a new explicit policy or
candidate decision; this report does not supply that authorization.
