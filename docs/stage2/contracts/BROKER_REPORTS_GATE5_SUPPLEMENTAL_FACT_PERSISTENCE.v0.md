# Broker Reports Gate 5 Supplemental Fact Persistence v0

Status: `EXPERIMENTAL_G5_3_CONTRACT`

Goal status: `G5.3_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract defines one minimal persistence proof for a structured fact that
is absent from the immutable Gate 4 Financial Case and supplied separately by
an authenticated user.

```text
closed supplemental input
-> Gate5SupplementalFactRuntimeFactory.create
-> existing ArtifactStore
-> new runtime/store instance
-> same structured supplemental fact
```

It is not a Tax Case, Tax Model, generic fact store or methodology lifecycle.

## Ownership

| Concern | Owner |
| --- | --- |
| authenticated user/case/run/workspace scope | existing `ArtifactAccessContext` |
| durable payload, retention and purge lifecycle | existing `ArtifactStoreFactory.create` storage |
| access-checked read | existing `ArtifactResolver.resolve` |
| closed supplemental contract and write/read projection | `Gate5SupplementalFactRuntimeFactory.create` |
| Gate 4 facts | unchanged `Gate4FinancialCaseRuntimeFactory.create` |

The supplemental boundary does not write `Gate4FinancialCaseFactV1`, Gate 4
SQL, Gate 3 annotations or `CanonicalArtifactV1`.

## Trusted context

The caller supplies an existing `ArtifactAccessContext`. The runtime requires:

- non-empty authenticated `user_id`;
- non-empty `case_id`;
- non-empty `normalization_run_id`;
- `allow_private=True`;
- the existing optional `workspace_model_id` binding.

The contract input cannot supply or override user, case, run or workspace
identity. Scope is copied only from the trusted context into the persisted
fact, while the ArtifactStore record retains the authenticated user binding.

## Minimal input

The input is a closed JSON-compatible object:

```json
{
  "schema_version": "broker_reports_gate5_supplemental_fact_input_v0",
  "requirement_ref": "acquisition-cost-required",
  "subject_ref": "security-disposal-1",
  "fact_key": "acquisition_cost",
  "value": {
    "kind": "money",
    "amount": "70000.00",
    "currency": "RUB"
  }
}
```

Rules:

- the top-level and `value` keys are exact;
- refs are bounded opaque identifiers, not tenant or case identifiers;
- `fact_key` is a bounded lower-case machine identifier;
- this proof accepts only canonical non-negative money strings with at most
  two fractional digits and an upper-case three-letter currency code;
- extra keys, empty strings and malformed values fail before persistence.

The boundary intentionally does not infer values from free text.

## Persisted fact

The runtime generates an opaque ArtifactStore reference and persists this
private payload:

```json
{
  "schema_version": "broker_reports_gate5_supplemental_fact_v0",
  "supplemental_fact_ref": "art_<opaque>",
  "requirement_ref": "acquisition-cost-required",
  "subject_ref": "security-disposal-1",
  "fact_key": "acquisition_cost",
  "value": {
    "kind": "money",
    "amount": "70000.00",
    "currency": "RUB"
  },
  "scope_binding": {
    "scope_kind": "case",
    "case_id": "<trusted context case>",
    "normalization_run_id": "<trusted context run>",
    "workspace_model_id": "<trusted context workspace or null>"
  },
  "provenance": {
    "source_kind": "user_provided_supplemental",
    "provided_by": "authenticated_user",
    "gate4_derived": false,
    "captured_via": "gate5_supplemental_fact_boundary_v0"
  }
}
```

The private payload uses `project_artifact_payload`, the supplied existing
retention policy and normal ArtifactStore lifecycle. It is not stored in chat,
Knowledge/RAG or a new database.

## Write and read output

Write returns:

```json
{
  "schema_version": "broker_reports_gate5_supplemental_fact_result_v0",
  "status": "stored",
  "supplemental_fact_ref": "art_<opaque>",
  "fact": { "schema_version": "broker_reports_gate5_supplemental_fact_v0" }
}
```

An authorized read through a new runtime/store instance returns the same
envelope with `status: found` and the complete same `fact` payload.

An absent well-formed ref returns `status: missing` and `fact: null`. It must
not synthesize a value. A ref that exists in another trusted scope fails with
the existing ArtifactStore access error rather than being hidden as missing.

## Fail-closed boundary

The runtime rejects untrusted/incomplete context, malformed input, unsupported
schema, foreign-scope access, wrong artifact type, corrupt payload, expired or
purged records. Validation completes before the irreversible `put_record`
boundary.

## Representative acceptance

The proof must demonstrate all of the following using the real ArtifactStore:

1. Gate 4 has a disposal fact without `acquisition_cost`.
2. `70000.00 RUB` is persisted through the supplemental boundary.
3. A new ArtifactStore and runtime instance reads the identical fact and
   provenance from the same trusted context.
4. Gate 4 before and after is byte-for-byte structurally equal.
5. A foreign trusted scope cannot read the fact.
6. Invalid input leaves no stored supplemental artifact.
7. A missing ref returns no invented fact.

## KISS and stop condition

This proof may add one artifact type, one small factory-backed module, one
closed contract and focused tests. It must not add a TaxCaseRepository,
SupplementalFactEngine, registry, evidence graph, workflow manager, new DB,
query merge, LLM call, tax calculation or later Gate 5 slice.

The representative persistence and isolation proof passed, so `G5.3_CLOSED`.
This contract authorizes no subsequent slice.
