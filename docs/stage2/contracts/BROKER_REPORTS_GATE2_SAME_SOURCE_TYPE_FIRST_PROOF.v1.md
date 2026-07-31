# Broker Reports Gate 2 Same-Source Type-First Proof v1

Status: normative inactive proof contract. Runtime activation and transport
eligibility are both false.

Machine contract:
[BROKER_REPORTS_GATE2_SAME_SOURCE_TYPE_FIRST_PROOF.v1.json](BROKER_REPORTS_GATE2_SAME_SOURCE_TYPE_FIRST_PROOF.v1.json).

## Boundary

`Gate2SameSourceTypeFirstProof` is a subordinate capability of
`current_source_fact_orchestration`. It has no product entrypoint. Product and
provider reachability are forbidden. It does not own a schema, parser,
validator, materializer, evidence store, or downstream presentation route.

The proof consumes privacy-safe structural copies of real bounded Gate 2 source
units. The source binding receipt pins the private package and unit hashes but
contains no customer values, raw refs, provider payloads, or private paths.

## Authority chain

```text
existing Gate 2 package and segmentation
-> Gate2FinancialSemanticContractFactory
-> Pack-backed opaque Type Cards
-> existing typed-option compiler
-> Gate2FinancialSemanticV6ChoiceContractFactory
-> Gate2FinancialSemanticV6DecisionExpansionFactory
-> Gate2FinancialEvidenceValidatedDecisionFactory
-> Gate2FinancialEvidenceMaterializerFactory
-> Gate2FinancialSemanticV6DecisionEvidenceFactory
-> ArtifactStoreFactory / ArtifactResolver
```

`AnswerContextSelectionFactory` remains a post-completed-Gate-2 consumer and is
not invoked by this inactive proof.

## Model-visible contract

The request schema is `broker_reports_type_first_request_v1`. It contains
bounded source units, opaque local type keys, and Pack-derived Type Cards.
Every card includes display name, definition, positive and negative signals,
competitors, counterexamples, supported source shapes, and projection version.

The request contains no canonical type IDs, source refs, prebound options,
expected answer, reason, provider metadata, or product activation signal.
Type Card order and local keys are deterministic. Synonym or header-regex
shortlists are forbidden.

## Sealed mapping and options

The private mapping binds each local type key to the existing canonical type,
Semantic Pack version, and Pack hash. Each local option key binds exactly one
existing compiler-produced typed option, its source unit, code-owned role
bindings, exact source refs, constructibility status, and integrity hash.

The model never generates values, refs, roles, field names, canonical facts, or
materialized output. Constructibility is not semantic evidence and never
reduces the visible Type Card set.

## Response and decision

The response schema is `broker_reports_type_first_response_v1`. It requires the
request key, request hash, mapping hash, Pack hash, ordered complete source-unit
coverage, and an ordered unique array of opaque plausible type keys per unit.
Empty and plural arrays are valid. Unknown keys, duplicate keys, extra fields,
missing or reordered units, canonical IDs, values, refs, reasons, and all hash
mismatches fail closed. Retry, repair, and fallback are forbidden.

Code owns the terminal reason:

- `UNIQUE_PLAUSIBLE_TYPE_AND_EXACT_OPTION`
- `MULTIPLE_PLAUSIBLE_TYPES`
- `NO_PLAUSIBLE_TYPE`
- `PLAUSIBLE_TYPE_WITHOUT_EXACT_OPTION`
- `MULTIPLE_EXACT_OPTIONS`
- `UNKNOWN_LOCAL_KEY`
- `REQUEST_HASH_MISMATCH`
- `INVALID_RESPONSE_SCHEMA`
- `UNSUPPORTED_SOURCE_SHAPE`
- `TECHNICAL_FAILURE`

Typed materialization is allowed only when one plausible type restores exactly
one prebound option and the existing canonical validator accepts it. Every
other valid semantic outcome is unclassified; every technical mismatch creates
no materialized fact.

## Evidence, replay, and totality

The existing V6 evidence owner records package, unit, Pack, projection,
request, mapping, response, restored decision, validator, materializer, and
execution hashes. Offline replay rebuilds the same authorities and fails closed
on package, Pack, request, mapping, response, local-key, source-ref, order, or
fixture mutation.

For every operation:

```text
total_units = typed + unclassified + no_fact + unsupported
              + technical_failure + excluded
```

`unaccounted_units`, provider calls, retries, repairs, fallbacks,
model-generated values, accepted unknown keys, unbound refs, duplicate facts,
product reachability changes, live changes, and canonical owner deltas must all
equal zero.
