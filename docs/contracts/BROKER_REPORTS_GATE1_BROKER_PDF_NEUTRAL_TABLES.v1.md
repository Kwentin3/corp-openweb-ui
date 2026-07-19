# Broker Reports Gate 1 — Broker PDF Neutral Tables v1

Status: implemented, bounded profile; acceptance remains open until a genuine unseen positive holdout passes.

Profile identifier: `supported_broker_pdf_neutral_table_profile_v1`

This contract defines neutral structural canonicalization for one bounded broker-report PDF family. It does not claim universal broker PDF support and does not assign financial meaning.

## Ownership

Gate 1 owns bounded region identity, text/layout extraction, physical row and column topology, source order, header and span relationships, continuation lineage, provenance, uncertainty, and deterministic promotion validation.

Gate 2 owns all financial interpretation. Gate 2 may consume a PDF table only when its persisted projection has:

- `canonical_table_scope = ready_validated_projection_only`;
- `canonical_validation.validator_status = passed`;
- a matching typed source-unit anchor resolved through `ArtifactResolver`;
- a valid projection checksum and canonical integrity hash.

The region detector is proposal-only. It cannot grant canonical authority.

## Typed region decision

Schema: `broker_reports_typed_region_decision_v1`.

Allowed physical classes are:

- `canonical_table_candidate`;
- `structured_form_panel`;
- `section_heading`;
- `material_non_table_region`;
- `non_material_region`;
- `unknown_or_ambiguous`.

`canonical_table_accepted` is legal only for `canonical_table_candidate`, with `detector_authority = proposal_only` and deterministic validator `broker_pdf_neutral_table_validator_v1` as promotion authority. Malformed or model-authoritative decisions fail closed.

## Supported structural invariants

The v1 profile is selected from source structure only. Every table-candidate region in the document must satisfy all applicable invariants:

- native PDF text/layout memory exists and resolves to the candidate inventory;
- reconstruction strategy is `ruled_lines_v0`;
- geometry confidence is at least 0.95;
- no OCR, VLM, provider, or rendered-image extraction path was used;
- cell edges resolve uniquely to one ordered ruled grid within the versioned boundary tolerance;
- a local header has a complete sequential ordinal marker row `1..N`;
- a fragment without a local ordinal header is accepted only as one unambiguous continuation on the next page, with the same normalized column grid, previous region at page bottom, and fragment at page top;
- all regions in a matched document are consumed exactly once.

Filename, path, customer identity, document/region/artifact identifier, source hash, extracted customer value, and page-specific allowlists are forbidden selectors.

An unsupported or partially matching document receives no v1 promotion. Its original source units and restrictions remain intact.

## Canonical neutral table

Schema: `broker_reports_canonical_neutral_table_v1`.

Each accepted physical region persists one canonical projection and references one logical table. Multiple physical fragments may share a logical table identity. The contract records:

- deterministic canonical, logical-table, projection, row, column, cell, header, and merged-cell identities;
- source and logical-document refs;
- contributing page and region refs;
- ordered rows and columns;
- cell row/column ordinal, span, covered columns, emptiness, and source refs;
- header hierarchy and ordinal-marker ownership;
- structural total/subtotal roles;
- continuation order, root projection, shared grid, and logical page order;
- annotation and controlled source-alias relationships;
- original text/layout refs and parent/source/unit checksums;
- reconstruction and validator versions;
- explicit uncertainty ledger;
- canonical integrity hash.

Structural labels do not introduce trade, income, fee, tax, deduction, balance, or declaration semantics.

## Source ownership and aliases

Every selected region object is accounted exactly once as either a cell-owned word or an explicit line-level projection alias. A line alias must declare `lossless_line_projection_of_owned_words`; it is controlled duplication, not a second cell value.

The validator rejects missing, unexpected, or duplicated ownership, incomplete source-value checksum coverage, invalid value paths, and unresolved uncertainty. Empty cells have no source-value refs and remain distinct from non-empty values.

## Deterministic validation

Validator: `broker_pdf_neutral_table_validator_v1`.

Promotion fails on identity/provenance mismatch, row or column reordering, cell overlap or span drift, unresolved merged-cell ambiguity, invalid header-to-column mapping, missing structural totals, invalid continuation order, source loss/duplication, checksum drift, incomplete coverage, or integrity-hash mismatch.

The complete persisted projection is also validated by the maintained `TableProjectionValidator`. Validation uses bounded whole-index passes and never scans the full source-value index once per ref.

## Runtime boundary

Factories are mandatory:

- `BrokerPdfNeutralTableFactory.create` for v1 reconstruction;
- `NormalizedTableProjectionFactory.create` for maintained projection routing;
- `Gate2InputReadinessFactory.create` for Gate 2 selection;
- `Gate2TablePackageFactory.create` for canonical table packages.

Gate 2 does not import PDF parser internals or reconstruct topology. A validated PDF projection replaces only its matching source-unit anchor. Geometry-only projections remain blocked.

## Acceptance limitation

Actual-corpus closure and a negative out-of-profile holdout are proven in the 2026-07-19 implementation evidence. A previously unseen positive PDF from the same intended family was not available. Therefore profile implementation is not yet acceptance-closed and must not be generalized or deployed as a proven live profile until that holdout is obtained and passes unchanged code.
