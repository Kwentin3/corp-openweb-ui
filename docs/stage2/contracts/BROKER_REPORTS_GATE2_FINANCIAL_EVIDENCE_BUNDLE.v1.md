# Broker Reports Gate 2 Financial Evidence Bundle v1

Status: authoritative V6 pre-semantic boundary contract

Schema identity:
`broker_reports_gate2_financial_evidence_bundle_v1`

## Purpose

The Evidence Bundle is the complete code-owned representation of one
financial semantic scope after deterministic technical preclose and before
typed-option compilation.

Gate 1 remains the authority for normalized source evidence and provenance.
The Evidence Bundle seals that evidence for V6 without assigning a financial
meaning.

## Construction authority

`Gate2FinancialEvidenceBundleFactory.create()` is the only bundle
construction entrypoint.

It accepts:

- one integrity-validated
  `Gate2FinancialEvidenceSourcePackage`;
- the Gate 1 packages that contain the visible source projection for the
  scope.

It performs no provider call and accepts no model output, Semantic Pack,
Registry, expected answer, type ID or role binding.

## Bundle fields

The bundle contains:

- an opaque, content-derived `bundle_id`;
- schema and policy identities;
- source-package identity and integrity hash;
- normalization run, document, scope and source-family identities;
- completeness, restrictions and issue references;
- every authoritative source value exactly once;
- each exact literal and technical value type;
- visible row, segment, column and label context where Gate 1 provides it;
- deterministic source associations;
- source evidence refs and exact lineage;
- the complete provenance-ref union;
- a code-owned `retention_set`;
- an integrity hash over the complete private bundle.

`source_reference` values remain authoritative values. They retain their
exact literal and provenance and use their source lineage as a deterministic
association. They are not omitted merely because the model-facing context
would normally hide their literal.

## Exactly-once and retention invariants

The following sets are identical:

- source value refs in the source package;
- source value refs stored in `source_values`;
- source value refs accounted by `source_associations`;
- source value refs in `retention_set`.

Every set is sorted and duplicate-free. Any missing, extra, duplicate,
cross-document or integrity-mismatched value fails closed.

The later `unclassified_financial_input` expansion must copy the complete
`retention_set`; a model never enumerates or narrows it.

## Forbidden semantic authority

The bundle must not contain or derive:

- a financial `input_type_id`;
- Financial Semantic Pack meanings;
- an expected answer;
- model output;
- typed role bindings;
- Gate 3 methodology.

Python construction must not inspect financial words or introduce
type-specific branches. Technical value types and Gate 1 structural
associations are allowed because they describe source structure, not
financial meaning.

## Privacy

`to_private_dict()` contains exact literals, source refs and provenance and
must remain in private artifact storage.

`safe_summary()` contains only hashes, counts and boolean invariant results.
It contains no source literal, source-value ref, document ref, provenance ref
or model output.

## Acceptance

- `SOURCE_VALUES: COMPLETE_AND_EXACTLY_ONCE`
- `FINANCIAL_TYPE_MEANING: ABSENT`
- `PROVENANCE: COMPLETE`
- `UNCLASSIFIED_RETENTION_SET: CODE_OWNED`
