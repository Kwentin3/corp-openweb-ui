# Broker Reports Gate 5 Human Fact Scope v1

Status: `CURRENT SUPPORTING CONTRACT; INACTIVE, TAXPAYER BINDING BLOCKED`

Issues: `#299`, review follow-up `#301`

Date: 2026-08-23

## Boundary and owner

`Gate5HumanGapClosureRuntimeFactory.create` is the single owner of Human
request meaning, authenticated-answer normalization, typed fact publication,
current-request publication, conflict detection and fact validation:

```text
authenticated context + externally supplied taxpayer scope + tax period
-> owner request content + owner current-publication chain
-> authenticated answer
-> owner-published typed fact
-> exact owner validation
```

The implementation reuses `ArtifactStorePort` and `ArtifactResolver`. It adds
no registry, workflow/event engine, identity authority, receipt engine or
provider/LLM path.

## Scope and the unresolved taxpayer binding

The immutable fact scope contains authenticated user, case, independent
`taxpayer_scope_ref`, four-digit tax period and a canonical scope hash. Run ID
is deliberately excluded so a valid fact can replay in a later run. Workspace
ID remains an ArtifactStore ACL boundary, not fact meaning.

The Human owner validates mechanical equality of the supplied taxpayer scope
across request, fact and consumer. Two distinct synthetic taxpayer refs in the
same user/case remain independently representable and cross-use fails closed.
This does **not** prove where either ref came from.

Repository investigation found no pre-existing owner-produced authenticated
case-to-taxpayer binding and no trusted exactly-one-taxpayer-per-case invariant.
The historical operation/category binding is caller-supplied
`user_verified_fact` for one operation subject; it does not authenticate the
taxpayer to the user/case and cannot be promoted into that missing relation.

The former `gate5_case_taxpayer_scope_ref` case hash is removed. Hashing a case
ID only obfuscated the case and silently invented a one-taxpayer invariant.
The current product composition now fails closed with
`ndfl_trusted_taxpayer_scope_binding_required` instead of manufacturing a
scope. Positive tests use explicit synthetic refs and prove mechanics only.

Smallest missing upstream contract: an owner-produced, owner-verifiable
authenticated taxpayer-case binding containing at least authenticated user,
case, independent taxpayer scope and explicit origin/provenance, with cardinality
able to represent more than one taxpayer per case. Authentication/case identity
must own it; the Human Adapter must only consume it.

Issue-level terminal: `HUMAN_FACT_TAXPAYER_SCOPE_BLOCKER_PROVEN`.

## Current request publication

Request content remains content-addressed. A separate immutable
`broker_reports_gate5_gap_request_publication_v1` records, for one semantic
request lane:

- exact request content binding;
- exact Human scope, fact key and closure type;
- predecessor publication ref;
- canonical publication hash/ref.

The owner accepts exactly one complete root-to-tip chain. Missing predecessors,
branches, multiple roots/tips or cycles fail closed. `A -> A` reuses the current
publication; `A -> B -> A` creates three publications and makes the final A
current even though request content A is reused. Selection uses neither record
timestamps, insertion/list order nor artifact-ref lexical order. Old requests
and facts bind the old publication ref and become stale.

## Unambiguous facts

Each fact binds the exact request content and exact request publication. Before
acceptance, the Human owner scans all genuine owner-visible facts for the same
scope, semantic key and request publication. More than one distinct fact hash
is an unresolved conflict, so A alone, B alone, both orders and caller omission
all fail closed. Repeating the same byte-equal answer reuses one artifact and
does not create a false conflict. No timestamp or caller list order chooses a
winner.

## Authority ceiling

The closed Human fact keys remain:

```text
taxpayer_identity_confirmed
filing_instance_identity
signer_and_representation
budget_disposition
residency_evidence
```

`filing_instance_identity` is now only the closed election
`INITIAL | CORRECTION`. Destination/inspection is a separate required
`EXTERNAL_AUTHORITY` gap. Free text cannot smuggle inspection, KBK, OKTMO,
residency/tax status, source classification, deductibility or settlement into
the filing fact. Declaration Preparation consumes only readiness and does not
reinterpret the election as destination or target data.

Residency remains raw interval evidence interpreted by
`Gate5ResidencyEvidenceRuntimeFactory.create`. Additional documents return
`NORMALIZATION_REQUIRED`; external/methodology actions cannot become Human
facts. Runtime provider/LLM calls remain zero.

## Compatibility and activation

`broker_reports_gate5_user_case_fact_v0` is historical-readable only and is
rejected on this v1 boundary. There is no silent migration. Declaration/XML,
filing and submission are not activated. Until the missing taxpayer binding is
owned upstream, this contract is an inactive synthetic proof and PR #300 must
not be merged.
