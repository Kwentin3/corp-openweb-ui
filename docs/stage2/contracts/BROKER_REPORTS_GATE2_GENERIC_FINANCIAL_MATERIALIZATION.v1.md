# Broker Reports Gate 2 Generic Financial Materialization

Status: target contract.

Version: `1.0.0`.

Date: 2026-07-26.

## 1. Purpose

This contract makes financial-evidence validation, deterministic
materialization, and model-facing context projection independent of concrete
financial type IDs and source vocabulary.

The managed Financial Semantic Pack and the active Registry remain the only
type and role authorities. Provider output is a proposal and cannot mint
canonical IDs, normalized values, ownership, provenance, coverage, validation
state, compatibility state, or integrity.

## 2. Versioned records

New canonical writes use:

```text
validated_decision=broker_reports_financial_evidence_validated_decision_v2
financial_inputs=broker_reports_financial_evidence_inputs_v2
materialization_policy=broker_reports_financial_evidence_materialization_v2
financial_context=broker_reports_gate2_financial_context_v2
context_projection_policy=broker_reports_gate2_financial_context_projection_v2
semantic_runtime_contract=broker_reports_gate2_financial_semantic_runtime_contract_v1
```

The v1 financial-input and context records remain accepted by their frozen
read validators. They are not canonical write contracts.

## 3. Pack and Registry authority

The runtime contract factory loads the exact closed-world managed Pack
projection and fails closed unless:

- Pack type membership equals the active Registry type membership;
- every title, lifecycle, semantic class, compatible source family, role,
  value type, cardinality, dimension requirement, sign policy, identity role,
  and operational profile equals the Registry declaration;
- identity includes source scope and evidence refs;
- the Pack type and role projections contain no duplicates.

The Pack identity is:

```text
pack_id=broker_reports_managed_financial_semantic_pack
semantic_version=1.0.0
integrity_sha256=ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8
```

Every new root artifact carries the complete identity. Every new typed or
unclassified terminal record carries
`semantic_pack_integrity_sha256`. The Pack hash also participates in terminal
IDs, root artifact IDs, and integrity hashes.

## 4. Generic validator

The validator derives type and role rules only from the runtime Pack contract.
It validates:

- exact Pack and Registry identities;
- one of the four terminal dispositions;
- type membership and active lifecycle;
- role membership, required-role completeness, value type, and cardinality;
- date/period and currency/unit requirements;
- source-package projection and, on the canonical factory path, exact package
  ref membership;
- unique ordered bindings and terminal ownership;
- exact source scope, package, normalization run, document, evidence, and
  lineage when the authoritative Source Package is supplied;
- code-derived comparison values, dimensions, source sign, coverage,
  provenance, IDs, and integrity;
- absence of Gate 3 or provider-owned fields.

The materializer always calls the validator with the authoritative Source
Package. Read compatibility may validate a frozen artifact without loading
private package content, but cannot turn that structural validation into a new
write.

## 5. Generic materializer

The factory-managed path deterministically builds:

- typed or unclassified terminal IDs;
- literal-preserving values and comparison projections;
- date/period and currency/unit dimensions;
- evidence and lineage provenance;
- source ownership;
- scope coverage and terminal closure;
- completeness, restrictions, and issues;
- validation execution refs;
- root and nested integrity hashes;
- the dual-read compatibility surface.

No model, Prompt, Skill, provider adapter, or caller can bypass the factory to
mint these fields.

## 6. Aggregate semantics

The former concrete branch
`printed_financial_metric_v1 -> source_printed` is removed.

Context projection now uses one schema rule over the Pack-owned
`semantic_class`:

```text
aggregate -> source_printed
state | event | attribute -> not_aggregate
```

This is a schema-level distinction between a source-stated aggregate and a
Gate 2 calculated aggregate. The generic runtime contains no concrete
financial type ID. An unsupported semantic class fails closed.

## 7. Compatibility and stage boundary

- v2 is the only production write target in repository code.
- v1 and v2 financial-input records are dual-read.
- v1 context remains read-valid for frozen artifacts.
- historical v1 qualification hashes may be reconstructed only by the
  value-free audit replay helper; that helper does not persist a v1 record.
- no stage or production migration is performed by this contract.
- live stage verifiers continue to report the actually deployed version until
  a later atomic activation goal supplies a terminal receipt and rollback
  proof.

## 8. Closed-world and privacy rules

The runtime uses only bundled repository modules and standard-library
operations. It performs no filesystem lookup, Knowledge/RAG call,
vectorization, direct provider call, or network lookup.

Repository tests and safe evidence must not contain customer/private values,
raw provider output, secrets, or private paths.

## 9. Acceptance

```text
VALIDATOR_FINANCIAL_LANGUAGE_KNOWLEDGE=ZERO
MATERIALIZER_TYPE_BRANCHES=ZERO_OR_SCHEMA_JUSTIFIED
PACK_HASH_ON_RECORD=REQUIRED
```

The proof must include an AST/source invariant for zero concrete type IDs, a
Pack/Registry drift rejection, typed and unclassified Pack-hash checks,
role/value and authoritative package-binding rejection, v1 read compatibility,
closed-world bundle load, focused and full test results, privacy checks, and
deterministic bundle rebuild.
