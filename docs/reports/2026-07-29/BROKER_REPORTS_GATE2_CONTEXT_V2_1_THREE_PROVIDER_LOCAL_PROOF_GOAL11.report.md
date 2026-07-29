# Broker Reports Gate 2 — Context V2.1 three-provider local proof

## Verdict

`PASSED` for the local, non-active, zero-provider-call scope.

- OpenAI, Anthropic and Google adapter projections completed for all four governed semantic fixtures.
- Adapter extraction, V2.1 Choice parsing, local-key restoration, canonical validation/materialization, persistence, restore and exact offline replay completed.
- `choice` and `reason` enums remain present in every provider-visible schema.
- The local schema projection is bound to `broker_reports_gate2_context_v2_1_local_schema_projection_v1`; the canonical adapter versions are not relabelled.
- Each prepared request is an exact rebuild from the sealed request and repository provider profile; full request shape, schema projection, wrapper, metadata and transform count match.
- Every simulated provider response has exactly one governed terminal envelope before adapter extraction.
- The proof leaves each active V6 Choice schema/hash unchanged; Context V2.1 remains inactive and transport-ineligible.
- Provider calls, semantic repair, fallback and retry are all `0`.

## Exact transparent evidence

The exact synthetic request, system message, user content, provider-visible schema, adapter-extracted output, normalized answer, expected answer and field-level diff for each of the 12 provider/case paths are in the [transparent report](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.transparent.json).
The public case projector returns only a raw closed projection and cannot mint evidence. ProviderProofFactory creates an unissued full proof, independently recomputes it, requires exact equality, and only then invokes the private authority that issues an opaque immutable case-evidence token. Independent full-proof validation follows; the aggregate accepts only the issued token, not raw or resealed proof dictionaries, and revalidates the frozen GOAL 10 baseline plus closed projection fields.

Actual token counts, cost and latency are recorded as `null` with `NOT_APPLICABLE_NO_PROVIDER_CALL`; no live measurements are claimed.

- Transparent report SHA-256: `f77c45bf6a11de8d42546cd04ca45a2103a083825fef1b2eca80486d0845910c`
- Privacy-safe aggregate: [safe receipt](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.receipt.safe.json)
- Safe receipt integrity: `e81a6145309b0b7e11e96d55bc456683d10d875ac1ee6f172887077e309a5497`

## Boundary

All exact payloads are synthetic repository fixtures. No customer data, credentials, provider response identifiers or provider calls are present. This proof qualifies local infrastructure only; it does not qualify a model and does not authorize GOAL 12 calls until this PR is reviewed, green and merged.
