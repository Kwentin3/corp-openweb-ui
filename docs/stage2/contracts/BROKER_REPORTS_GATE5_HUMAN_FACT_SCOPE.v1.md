# Broker Reports Gate 5 Human Fact Scope v1

Status: `CURRENT SUPPORTING CONTRACT`

Issue: `#299`

Date: 2026-08-23

## Boundary and owner

`Gate5HumanGapClosureRuntimeFactory.create` remains the sole owner of Human
Adapter request meaning, authenticated-answer normalization and typed
user/case fact publication. The v1 boundary is:

```text
ArtifactAccessContext + bounded taxpayer slot + tax period
-> owner-built request
-> owner-published private request artifact
-> authenticated answer
-> owner-published private typed fact
-> owner validation under the consuming context/scope
```

The implementation reuses the existing `ArtifactStorePort` and
`ArtifactResolver`; it introduces no identity authority, registry, workflow,
receipt engine or persistence platform. `ArtifactResolver.resolve_case` is the
minimal public access seam used for an immutable same-case artifact across
normalization runs.

## Identities and scope

The immutable semantic fact scope contains exactly:

- `authenticated_user_ref` from trusted `ArtifactAccessContext.user_id`;
- `case_id` from trusted `ArtifactAccessContext.case_id`;
- independent opaque `taxpayer_scope_ref`;
- four-digit `tax_period`;
- canonical `scope_binding_sha256`.

`gate5_case_taxpayer_scope_ref` owns the bounded one-taxpayer case slot used by
the existing preparation composition when no prior taxpayer ref exists. The
slot is derived from the case identity under the Human owner and differs from
the authenticated user, raw case ID and any operation subject. It is a stable
scope handle only; it does not assert a person's identity, representation,
residency or tax status. The authenticated answer supplies or confirms the
allowed factual/elective meaning for that slot.

The public boundary still receives `taxpayer_scope_ref` so composition must
show the binding it intends to consume, but the Human owner recomputes the only
valid bounded slot from the trusted case context and rejects any unequal value.
The caller therefore cannot mint an authoritative taxpayer scope string.

`normalization_run_id` is deliberately excluded from immutable fact scope. A
valid fact may replay in a later run for the same user, case, taxpayer and tax
period. `workspace_model_id` is also excluded from semantic scope, but remains
an ArtifactStore access-control boundary: cross-workspace reads fail closed.

## Request origin and staleness

`broker_reports_gate5_gap_request_v1` includes the exact scope binding, stable
`request_id`, full canonical `request_sha256` and deterministic private
`request_ref`. Only `publish_requests` may publish requests; it rebuilds them
from the Human owner's actual intake, scope activation, client review, known
facts and residency classification. It never accepts a caller-authored request
for publication.

`normalize_answer` resolves the exact stored request through the existing
artifact owner and rejects a missing, changed, foreign or superseded request.
A later owner-published request for the same semantic key and scope makes the
older request stale. The answer cannot select or replace `fact_key`; that key
comes only from the stored request.

## Typed fact publication and validation

`broker_reports_gate5_user_case_fact_v1` contains:

- deterministic `user_case_fact_ref` and `fact_sha256`;
- the closed current `fact_key` and normalized value;
- the exact immutable scope binding;
- exact request artifact/id/hash binding;
- authenticated-user provenance with both calculation and document-source
  authority false.

The fact is accepted only when the Human owner can resolve an exact matching
private fact artifact and its exact request artifact, both under the consuming
context, and both scope bindings equal the requested taxpayer and tax period.
Caller-recomputed hashes prove only bytes: they cannot create matching owner
artifacts. Missing fields, foreign scope, payload/store disagreement, schema
downgrade and any duplicate semantic key fail closed. Duplicate equal facts
and conflicting facts are both rejected; there is no last-write-wins rule.

## Fact classes and authority ceiling

V1 scopes all five existing Human Adapter fact keys:

```text
taxpayer_identity_confirmed
filing_instance_identity
signer_and_representation
budget_disposition
residency_evidence
```

This issue adds no structured identity, filing, signer, settlement or
completeness variants because no newly activated typed consumer is authorized.
It first closes the common publication boundary for the existing facts.

A Human answer may provide a raw circumstance or explicit election. It cannot
publish residency/tax status, source classification, deductibility,
settlement, KBK, OKTMO, destination authority, external reference or broker
source fact. Residency answers remain raw interval evidence interpreted only
by `Gate5ResidencyEvidenceRuntimeFactory.create`. Additional documents return
`NORMALIZATION_REQUIRED`; external-authority and methodology requests cannot
be normalized into Human facts. Runtime provider/LLM calls are zero.

## Compatibility and activation

`broker_reports_gate5_user_case_fact_v0` is historical-readable evidence only.
It lacks user, case, taxpayer, tax-period and stored-request proof and is
therefore explicitly rejected by the v1 publication/validation route. No
silent migration or reinterpretation exists.

`Gate5DeclarationPreparationRuntimeFactory.create` accepts only v1 facts on its
updated `broker_reports_gate5_declaration_preparation_v1` boundary and requires
an explicit taxpayer scope ref. This closes preparation replay only; it does
not activate Declaration Scope/Package, XML, filing or submission.

## Required fail-closed proof

Executable tests use real owner-published request/fact artifacts for synthetic
personas A and B and prove deterministic same-scope acceptance, independent
foreign user/case/workspace/taxpayer/period rejection, allowed cross-run replay,
stale and changed request rejection, resealed A/B mix rejection, duplicate and
conflict rejection, v0 downgrade rejection, document/external routing and zero
provider imports/calls.
