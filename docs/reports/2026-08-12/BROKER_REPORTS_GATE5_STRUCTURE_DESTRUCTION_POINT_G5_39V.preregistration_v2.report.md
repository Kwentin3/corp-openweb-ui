# G5.39V blind-probe preregistration v2

Status: `FROZEN_BEFORE_PROVIDER_SUBMISSION`
Date: `2026-08-12`
Scope: provider-profile correction only; corpus, facts, oracle, representations,
adjudication and production freeze remain as preregistered in v1.

## Superseded provider profile

The v1 preregistration SHA-256 is
`05a55e4d0759969c4f4264a322b3586cd627efd5ca921d82bf3122b6d13ab6cc`.
Its `gpt-5.4-mini-2026-03-17` profile could not reach inference: the exact model
is neither admitted by the current `openai_gpt` factory profile nor published
by the live OpenWebUI model registry. The current admitted OpenAI models are
also absent from that registry. No provider submission occurred during this
preflight.

The corrected clean diagnostic uses the same provider/model route as the
available current Gate 3 proof path:

```text
Gate2StructuredModelClientFactory.create.label_gate3_once
provider profile: google_gemini
model: models/gemini-3.5-flash
temperature parameter sent: false (the exact Gate 3 sealed request forbids it)
retry: 0
repair: 0
best-of-N: false
answer merge: false
maximum submissions: 7
```

This is a fail-closed correction to a non-executable setup, not model selection
after observing semantic output.

## Frozen input plan

- Factory-derived trace SHA-256:
  `18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766`.
- Probe code SHA-256:
  `9096cb229762ea8828c5600e3e488b8fc813528d9b69e78d5f19e45b78256261`.
- Probe plan SHA-256:
  `fa638947c745f10fd32cba1a2808ef8f8c36d2d07d9e5952086e21d12a425441`.
- Neutral task SHA-256:
  `1cdec72f4aa19276f81328f9c94c05b6f1df042d81bfee9748a7edc8b15e524b`.
- Closed response schema SHA-256:
  `35479d6ed2d0b1d981f2a18399a84ade4cd1128221b95a1a32723a031366c3f9`.

| Slot | Stage | Chars | UTF-8 bytes |
|---|---|---:|---:|
| DEV before | C rich tables | 29,244 | 31,130 |
| HOLDOUT before | C rich table | 107,472 | 119,757 |
| LARGE before | C three full reviewed tables | 48,630 | 54,656 |
| DEV after | exact E chunk | 8,036 | 12,379 |
| HOLDOUT after | exact E chunk | 30,537 | 38,749 |
| LARGE after | exact E page-54 chunk | 3,779 | 3,946 |
| A/B negative | C two complete tables | 2,173 | 2,173 |

For LARGE, the after-representation is one actual chunk, not a hand-merged
three-page context. Reviewed location selects the chunk but supplies no target
role values. The before-representation contains complete selected tables, not
oracle-filtered rows.

Each slot is permanently claimed before its sole call. A claimed slot is never
resubmitted. Raw requests, responses and readable representations remain only
under ignored `local/`; public evidence retains hashes and aggregate outcomes.
