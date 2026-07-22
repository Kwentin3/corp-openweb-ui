# Broker Reports Workflow Goal 5G — Gate 2 Semantic Selection Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5g-gate2-source-provider-projection-v1`

Correction family: Gate 2 source-fact model-facing contract and deterministic
materialization boundary

Implementation status: PASSED

Live Gate 2 reproof: PENDING AFTER MERGE

## Trigger

The preceding live audit processed ten source packages through twenty strict
provider calls, but every canonical candidate failed deterministic validation.
The dominant findings concerned application-owned provenance, coverage and
mechanical fields. The provider had been required to reproduce the canonical
source-of-record object instead of returning only semantic decisions.

## Narrow correction

The canonical `broker_reports_source_facts_v0` artifact, its validator and its
legacy readability remain unchanged. The maintained customer source Function
now gives the provider a versioned compact projection:

- root fields: `facts` and `no_fact_results` only;
- each fact: source ownership, fact type/subtype, source-value bindings,
  confidence, completeness and uncertainty codes only;
- no model-produced ids, hashes, audit objects, provenance arrays, normalized
  values, issue policy, downstream policy, coverage scaffold or validation
  state;
- mandatory package-known no-fact rows remain application-owned.

The deterministic materializer verifies exact source coverage, source-ref and
value-ref ownership, allowed type/subtype combinations and minimum typed-value
requirements. It reproduces normalized values from retained source evidence,
adds canonical scope/provenance/audit/issue fields, and then invokes the
existing canonical validator before persistence.

The production valve defaults to semantic selection. The runtime default
remains the legacy path for explicit compatibility callers and historical
synthetic tests. Both paths use the existing OpenWebUI provider connection,
ArtifactStore, resolver and factory-owned runtime.

## Contract reduction

For the representative synthetic package used by the regression suite:

- provider schema root fields: 14 to 2;
- provider fact fields: 25 to 7;
- compact serialized provider schema: 93,801 to 13,490 bytes;
- canonical persisted schema fields removed: zero.

This is a provider projection, not a Markdown runtime contract and not a new
storage model. The model makes semantic choices; code owns deterministic
mechanics.

## Failure semantics

The selection validator fails closed before canonical output when it sees:

- incomplete or duplicate source ownership;
- a value ref owned by another row or text segment;
- forbidden fact types, subtypes or fields;
- unreproducible values;
- missing minimum values for typed facts;
- system-owned metadata in model output.

An `unknown_source_row` may carry source-location and evidence provenance
without an invented normalized value. It remains low-confidence,
uncertain/blocked and unusable downstream.

## Preserved boundaries

- Gemini-master visual-table semantic JSON and prompt are unchanged;
- crop discovery, image processing and provider selection are unchanged;
- private intake and WorkloadAuthority ownership are unchanged;
- canonical Gate 2 source-fact schema and final validator remain authoritative;
- legacy artifact readability is preserved;
- no Knowledge, RAG, embeddings, vectorization, PaddleOCR or local OCR was
  added;
- no direct provider API path was added.

## Verification

Terminal local results:

- focused semantic-selection and canonical-materialization tests: 20 passed;
- full affected Gate 2, bundle, architecture, release and ArtifactStore
  regression: 124 passed;
- strict selection coverage, typed value materialization, cross-row ref
  rejection and system-metadata rejection: passed;
- Ruff on changed production/test surfaces with repository baseline import
  exceptions: passed;
- compile check: passed;
- deterministic bundle regeneration: passed;
- `git diff --check`: passed;
- boundary-aware scan of sealed private labels and values: zero findings.

Source and bundle SHA-256 identities:

- Gate 1 bundle: `b49c444952e522317eab961def29c01ec78127ab2b67b94fa58cae4cb25c3439`;
- Gate 2 source Function source: `f27d3ed4128c394605cf5d2aadd4536597a434a7903795cba90271be24a76c28`;
- Gate 2 source bundle: `084dfcead9a77319f3611c7358c48b089ee2debc152f3e2e6bd0fa8d56085857`;
- Gate 2 domain bundle: `f3fff42dd7cf59d4bc587068dc214ffcc23d48406e4d5ea84a358d094909b0d4`.

## Acceptance disposition

- PROVEN_SOURCE_CONTRACT_DEFECT: YES
- PROVIDER_ROOT_FIELDS: TWO
- PROVIDER_FACT_FIELDS: SEVEN
- SYSTEM_METADATA_MODEL_OWNERSHIP: ZERO
- MODEL_PRODUCED_NORMALIZED_VALUES: ZERO
- CROSS_ROW_VALUE_BINDING: REJECTED
- CANONICAL_SOURCE_FACT_SCHEMA_CHANGED: NO
- CANONICAL_VALIDATOR_BYPASSED: NO
- LEGACY_READABILITY: PRESERVED
- SEMANTIC_VLM_CONTRACT_OR_PROMPT_CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5G implementation is complete. Goal 2 remains pending for a fresh native
Gate 2 source run after merge and atomic release.
