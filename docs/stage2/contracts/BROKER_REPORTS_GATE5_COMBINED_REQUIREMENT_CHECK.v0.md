# Broker Reports Gate 5 Combined Requirement Check v0

Status: `EXPERIMENTAL_G5_4_CONTRACT`

Goal status: `G5.4_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract defines one minimal read-only check across the already proven
G5.2 Financial Case selection and G5.3 persistent Supplemental Fact read.

```text
external requirement
-> G5.2 Financial Case selection
   + G5.3 access-checked supplemental reads
-> satisfied / missing with one source-tagged provenance
```

The check does not create a Tax Case, unified fact store, query language or
new persistence layer.

## Ownership

| Concern | Owner |
| --- | --- |
| current Financial Case lookup | unchanged `Gate5MethodologySelectionRuntimeFactory.create` -> Gate 4 |
| persistent supplemental write/read and scope | unchanged `Gate5SupplementalFactRuntimeFactory.create` |
| combined presence decision and tagged output | `Gate5CombinedRequirementCheckRuntimeFactory.create` |
| tax calculation and methodology lifecycle | out of scope |

Gate 4 and G5.3 storage are unchanged. The combined runtime is read-only.

## Minimal methodology input

```json
{
  "schema_version": "broker_reports_gate5_combined_requirements_v0",
  "requirements": [
    {
      "requirement_id": "acquisition-cost-required",
      "financial_type": "SECURITY_DISPOSAL",
      "value_key": "acquisition_cost",
      "subject_ref": "security-disposal-1"
    }
  ]
}
```

The top level and every requirement are closed objects. Requirements are a
non-empty ordered list with unique opaque `requirement_id` values.

`financial_type` and `value_key` are projected mechanically into one G5.2
requirement:

```json
{
  "requirement_id": "acquisition-cost-required",
  "financial_type": "SECURITY_DISPOSAL",
  "roles": ["acquisition_cost"]
}
```

The same `value_key`, plus `requirement_id` and `subject_ref`, is used only to
match an already resolved G5.3 Supplemental Fact. There is no scenario table
or tax-specific runtime branch.

## Supplemental refs input

The `check` call receives a separate ordered `supplemental_fact_refs` list.
This list may be empty. It contains opaque refs returned by G5.3 persistence;
it is not part of Tax Methodology and carries no tenant/case identity.

Every ref is read through `Gate5SupplementalFactRuntime.get` with the same
trusted `ArtifactAccessContext`. Missing refs remain absent. Foreign-scope,
expired, purged, corrupt or wrong-type refs fail through the existing G5.3 and
ArtifactResolver boundary.

The runtime does not discover, list, rebind or migrate supplemental facts.

## Decision rule

For each requirement:

1. G5.2 checks `financial_type + value_key` against the Financial Case.
2. If G5.2 reports `found`, the requirement is `satisfied` from
   `financial_case`; supplemental values are not selected.
3. Otherwise, resolved supplemental facts are matched exactly by
   `requirement_ref == requirement_id`, `subject_ref` and `fact_key ==
   value_key`.
4. Exactly one matching supplemental fact makes the requirement `satisfied`
   from `supplemental_fact`.
5. No match leaves the requirement `missing`.
6. More than one matching supplemental fact fails closed; conflict resolution
   is not part of G5.4.

Values from the two sources are never merged into one untagged value.

## Minimal output

Supplemental satisfaction:

```json
{
  "schema_version": "broker_reports_gate5_combined_requirement_check_result_v0",
  "requirements": [
    {
      "requirement_id": "acquisition-cost-required",
      "financial_type": "SECURITY_DISPOSAL",
      "value_key": "acquisition_cost",
      "subject_ref": "security-disposal-1",
      "status": "satisfied",
      "checks": {
        "financial_case": "partial",
        "supplemental_facts": "found"
      },
      "source": {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": "art_<opaque>",
        "value": {
          "kind": "money",
          "amount": "70000.00",
          "currency": "RUB"
        },
        "scope_binding": {},
        "provenance": {}
      }
    }
  ],
  "summary": {
    "requirements_total": 1,
    "satisfied": 1,
    "missing": 0
  }
}
```

Financial Case satisfaction uses a tagged source with exact `fact_id`, `role`
and value matches. Missing uses `source: null` and explicit check statuses.

## Trusted run binding

The representative proof reopens the ArtifactStore/runtime but preserves the
same trusted `ArtifactAccessContext`, including `normalization_run_id`. This is
the G5.3 contract already proved and is sufficient for G5.4.

Cross-run rebinding, discovery and migration are not required and must not be
implemented unless a later representative case proves that gap.

## Fail-closed boundary

The runtime rejects unsupported schema versions, extra/missing keys, empty or
duplicate requirement IDs, invalid refs, foreign scope and multiple eligible
supplemental matches. Existing Gate 4 freshness/read errors and G5.3
access/lifecycle errors pass through unchanged.

## Representative acceptance

The real-boundary proof must show:

1. the Financial Case disposal lacks `acquisition_cost`;
2. with no supplemental ref the requirement is `missing`;
3. G5.3 persists `70000.00 RUB` for the same requirement/subject;
4. a new store/runtime instance sees the requirement as `satisfied`;
5. source is exactly `supplemental_fact` with value and provenance;
6. an ordinary existing Financial Case role is tagged `financial_case`;
7. Gate 4 before and after is structurally equal;
8. no new write, DB, table, registry or Tax Case is created by G5.4.

## KISS and stop condition

G5.4 may add one read-only factory-backed adapter, one closed input/output and
focused tests. It must not add a unified query engine, Tax Case, repository,
generic join, conflict solver, workflow, LLM, tax calculation, cross-run
framework or subsequent Gate 5 slice.

The representative proof passed, so `G5.4_CLOSED`. This contract authorizes
no subsequent slice.
