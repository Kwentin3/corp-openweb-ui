# Broker Reports PDF Dual-Oracle Consensus v1

> **Superseded active-runtime semantics.** Use
> `BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_CONSENSUS.v2.md` for current terminals,
> supplied-hypothesis scope and acceptance rules. Names such as
> `accepted_unique_consensus`, `uniqueness_proven` and
> `solver_search_complete` below are retained only to explain immutable
> historical v1 artifacts. They must not be used to claim global uniqueness or
> complete enumeration in the repaired runtime.

Status: obsolete research baseline retained only for legacy replay interpretation. Production Gate 2 selection and OpenWebUI core are unchanged.

## Purpose

Historically, this vertical asked whether one bounded PDF table topology was simultaneously compatible with two observations:

1. parser physical evidence: immutable words, exact values, source identities, checksums and PDF coordinates;
2. VLM visual evidence: candidate-id-only rows, columns, empties, headers, spans, geometry and continuation hypotheses.

Neither oracle was preferred. The old acceptance wording below applied only to the supplied v1 evidence set; it did not prove global structural uniqueness. Current runtime semantics are defined by v2.

## Domain boundaries

| Domain | Owns | Must not own |
|---|---|---|
| Parser observation | exact word atoms, candidate identities, values, refs, bboxes, ordering evidence, duplicate-value ambiguity | rows, columns, headers or table meaning |
| VLM topology | rectangular candidate-id placement, explicit empties, headers, hierarchy, spans, proposed normalized geometry, alternatives, uncertainty | free financial values, source refs, business facts or reference answers |
| Consensus | deterministic constraint checks, alternative enumeration, uniqueness, explanation and terminal mapping | scoring, oracle ranking, repair or provider calls |
| Continuation | ordered fragment set, shared column count, repeated-header, subtotal and duplicate policies, fragment acceptance | hiding a failed fragment behind a passing fragment |
| Replay evidence | strict legacy journal/package integrity and repeat history | reference scoring or production authority |
| Diagnostic scoring | post-terminal parser/VLM/consensus comparison with a provisional reference | changing a solver terminal |

The generic v1 contracts are reused by the v2 Gate 1 shadow and its closed-world bundle. The legacy replay path remains isolated, and no v1 result changes Gate 2 selection or authority.

## Parser observation contract

Schemas:

- `broker_reports_pdf_parser_observation_v1`;
- policy `pdf_dual_oracle_contract_policy_v1`.

Every candidate resolves exactly to owned word atoms. The validator recomputes candidate value, value checksum, bbox union, source refs, bbox refs, text checksum refs, order, duplicate groups and source accounting from the word records. Word, line, candidate and envelope checksums are verified. Coordinates must be finite PDF points inside the declared table scope.

Two construction lineages are explicit:

- `raw_word_atoms`: topology-neutral and eligible for automatic consensus;
- `legacy_compact_ledger_candidate_groups`: derived from the current parser cell inventory and therefore never sufficient for automatic consensus.

The second mode exists only to replay current shadow evidence honestly. Removing row/column fields from a parser-derived grouping does not make that grouping independent.

## VLM topology hypothesis contract

Schemas:

- `broker_reports_pdf_vlm_topology_hypothesis_v1`;
- `broker_reports_pdf_vlm_topology_hypothesis_set_v1`.

Each bound or ambiguous hypothesis contains:

- positive row and column counts;
- every rectangular position, including empty lists;
- exactly-once ownership of all candidate ids;
- header rows and hierarchy;
- non-overlapping merged/spanning relations with one non-empty anchor and empty covered positions;
- normalized row/column boundaries or an explicit `not_observed` state;
- continuation metadata;
- uncertainty codes and package/model evidence lineage.

Unknown fields and free/source values are rejected. Invalid alternatives remain explicit rejected evidence; one valid hypothesis cannot erase them.

The closed schema applies recursively to rows, geometry axes, continuation, uncertainty, evidence packages and rejected reason codes. Hypothesis lineage must contain non-empty typed attempt, provider, model, configuration and package identities. Provider/model/configuration are cross-checked against the set-level model context; authority flags are exact booleans and cannot be self-promoted by recomputing a checksum.

Three hashes have separate meanings:

| Hash | Projection |
|---|---|
| canonical grid | shape, rows/cells, headers, hierarchy and spans |
| topology | canonical grid plus proposed geometry and continuation |
| hypothesis | topology plus uncertainty and model/package evidence |

Thus two geometry revisions of the same grid are not misreported as two distinct grids.

Independence is derived from sealed lineage fields, not from a caller's `independent=true` boolean. The accepted path requires a visual crop without a parser grid, VLM-observed dimensions, bounded explicit alternative generation, prompt/crop manifest hashes and all context guards.

## Deterministic consensus model

The selected model is bounded finite-domain constraint evaluation over the explicit VLM hypothesis set. It has no optimizer, score or tie-breaker.

For every hypothesis the runtime checks:

- complete candidate and source accounting;
- rectangular shape and explicit empties;
- candidate-to-row and candidate-to-column compatibility;
- row bands, column boundaries and stable order;
- empty regions against parser candidate coordinates;
- merged/header span anchors and hierarchy;
- exact parser provenance;
- duplicate-value physical identity;
- uncertainty and evidence lineage.

When VLM boundaries are absent, joint bands may be calculated only to explain a conflict. Such geometry receives `pdf_dual_oracle_vlm_geometry_independence_not_proven` and cannot auto-accept.

Canonical grids that satisfy every physical constraint are deduplicated. The solver then returns exactly one terminal:

| Condition | Terminal |
|---|---|
| one valid grid, complete independent search, no review code or historical conflict | `accepted_unique_consensus` |
| more than one distinct valid grid | `ambiguous_multiple_consensus` |
| well-formed VLM topology contradicts parser geometry/accounting | `parser_vlm_conflict` |
| contracts or all alternatives are invalid | `no_valid_consensus` |
| one compatible grid exists but independence, completeness, lineage, repeatability or ambiguity remains unproven | `human_review_required` |
| bounded representation is unavailable or exceeds an explicit limit | `unsupported` |

`uniqueness_proven=true` is legal only for `accepted_unique_consensus`. `solver_search_complete=true` additionally requires raw word atoms, independently observed VLM topology, a complete alternative set, a passing context manifest and zero rejected evidence.

## Explainability

Every result records:

- every submitted or rejected alternative;
- each constraint and its pass/fail reasons;
- row/column compatibility for every candidate id;
- explicit-empty checks;
- distinct valid canonical grid hashes;
- witness hypothesis ids;
- review and historical conflict codes;
- evidence required to resolve the block.

Numeric scoring, majority voting, repair, reference answers and oracle preference are fixed to false in the result contract.

Before downstream materialization, the runtime recomputes the result from the parser observation, hypothesis set and repeat history. It then verifies the result checksum, the constraint-valid witness set and package/crop/dictionary identities. The private candidate dictionary hash is recomputed and every value, source ref, word ref, bbox, checksum ref and source order is compared with the sealed parser observation. A forged accepted dictionary, a stale hash, an invalid same-grid witness or a package from another table cannot cross this boundary.

## Context contract

The VLM side is restricted to one table or deterministic row window, one crop, table-local candidate ids, shared topology context and a narrow output schema. The evidence manifest must prove:

- exact provider token accounting before generation;
- bounded candidates, image and output;
- exactly-once candidate ownership;
- no silent truncation;
- no column splitting;
- no hidden retry or provider failover.

Image/output budget evidence is numeric: observed and maximum image bytes plus observed and maximum output tokens. The attestation is derived from those values and is false when they are absent, invalid or over limit. A caller cannot promote the derived flags by editing them and recomputing the envelope checksum. The prototype does not yet bind those maxima to immutable provider configuration or independently reconstruct pre-call versus actual token counts, so real context-guard readiness is not claimed.

The solver consumes compact JSON only and makes no model call. Whole-PDF input, raw forensic payloads, unrelated pages, business prompts, OCR, Knowledge/RAG/vector and duplicated dictionaries are outside the contract.

## Continuation contract

A continuation group has unique ordered fragments, increasing page numbers, one shared column count, valid repeated-header policies and explicit subtotal/duplicate policies. The supplied result set must match the fragment set exactly; duplicates, omissions and extras block.

Every supplied fragment envelope is checked for exact result schema, checksum and accepted state. Fragment identity, set membership, order, page order, coverage flags, shared columns and policies are validated. The joined terminal can be accepted only when every supplied required fragment says `accepted_unique_consensus`; a page-local success cannot hide a failed sibling.

This prototype does not yet re-solve each fragment from its parser/VLM evidence, materialize joined rows or prove subtotal/duplicate-row semantics from source observations. Therefore the continuation contract is useful as a fragment-set gate, but not yet as an independent continuation integrity boundary; real dual-oracle continuation readiness is not claimed.

## Repeatability

For identical parser evidence, VLM evidence, model/configuration and solver version, two runs must produce the same result and canonical checksum. `broker_reports_pdf_dual_oracle_repeatability_record_v2` groups hypotheses by `(attempt_number, attempt_id)`: alternatives inside one provider response form one order-independent alternative set and never count as repeat attempts. At least two contiguous distinct attempts must have one evidence identity, unique alternatives, identical alternative-set checksums and exactly one identical constraint-valid canonical grid per attempt. The record is bound to parser/hypothesis checksums, provider/model/configuration, crop manifest, packages and solver version; caller `passed=true` booleans are insufficient. A different supplied attempt set sets `ever_conflicted=true`, and later agreement in that same supplied history does not clear it. DPI changes and retries remain separate through crop-manifest, package and attempt identities.

The v2 field `supplied_history_structurally_complete` means only that the attempts supplied in the current hypothesis set are distinct and contiguous. It cannot prove that an older attempt was not omitted or renumbered, and it is not yet backed by a durable append-only history authority. The legacy real journal is still represented by its older repeat summary. That summary remains diagnostic, but it does not satisfy the v2 acceptance record. Real repeatability readiness is therefore withheld.

## Safe integration and non-goals

The only allowed bridge to existing materialization and validation is an accepted result whose full identity is revalidated. Existing materializer and validators are not weakened.

This v1 does not:

- migrate PDF tables to CSV in production;
- transcribe free-form values through the VLM;
- perform OCR, business extraction, Gate 3, tax/declaration or XLSX work;
- activate cleanup or remove forensic artifacts;
- make any shadow result authoritative;
- change production Gate 2 selection.

The current legacy six-table journal proves replay, typed conflict handling and integration, but not an independent visual-topology oracle. A new bounded topology task over raw-word candidate ids is required before real-table automatic acceptance can be claimed.
