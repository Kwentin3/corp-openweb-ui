# Broker Reports Gate 2 Universal Structural Scope v1

Status: target normative, repository-managed, not live-activated.

## 1. Purpose

This contract defines the deterministic boundary between a bounded Gate 1
source scope and the set of Financial Semantic Pack types that may be shown to
the Gate 2 semantic model.

Deterministic code owns structural eligibility only. The LLM owns financial
semantic selection.

## 2. Versioned identities

- structural-filter schema:
  `broker_reports_gate2_financial_typed_admission_v2`;
- structural-filter policy:
  `gate2_financial_generic_structural_filter_v1`;
- enclosing scope:
  `broker_reports_gate2_deterministic_financial_scope_package_v2`;
- hash boundary for repository evidence: Git blob bytes.

The historical `typed_admission` payload and Python factory names remain as
compatibility surfaces. In schema v2, `admitted_type_ids` means only
structurally eligible type IDs passed through to the strict decision contract.
It is not a deterministic semantic classification.

## 3. Structural eligibility

A Semantic Pack type is structurally eligible only when all of these generic
conditions hold:

1. its Registry lifecycle is `active`;
2. the bounded source family is a member of its compatible source families;
3. every required role has at least one package candidate with the Registry
   role specification's value type;
4. source-value and candidate identities match;
5. ordinary source values belong to the bounded Gate 1 package;
6. deterministic source-reference values point to an allowed evidence ref;
7. the surrounding source package, Registry identity, decision contract, scope
   coverage, and integrity hashes remain valid.

More than one candidate value for a required role is structurally feasible.
Ambiguity is presented to the LLM; deterministic code must not resolve it by
financial meaning.

Every type satisfying these conditions is passed to the strict decision
contract. A generic failed condition may exclude a type. No concrete type ID
may have a dedicated admission branch.

## 4. Forbidden deterministic inputs

The structural filter must not use any of these to include or exclude a type:

- financial words in literals;
- visible labels or headings;
- column meaning;
- row role or row-kind semantics;
- cash, total, subtotal, summary, or equivalent-language regexes;
- a type-specific positive discriminator;
- a type-specific conflict rule;
- expected benchmark answers.

Changing financial words while preserving the same structural value types,
roles, package membership, and scope integrity must not change the eligible
type set.

## 5. LLM-owned semantic decision

The bounded semantic model, not Python, decides whether the source meaning
supports:

- one structurally eligible typed input;
- `unclassified_financial_input`;
- `no_financial_input`;
- `unsupported`.

The existence of a typed branch is not an instruction to select it. The model
must use the versioned Semantic Pack and visible bounded source context. The
exact Pack/model-input assembly is owned by GOAL 5 and is not implemented by
this contract.

## 6. Safe receipt fields

The structural-filter receipt is value-free and includes:

- candidate and structurally eligible type IDs;
- generic reason codes;
- counts for source values, candidate values, package-member values, evaluated
  required roles, and infeasible required roles;
- `filter_kind=generic_structural`;
- `semantic_selection_owner=llm`;
- `financial_language_predicates_total=0`;
- `type_specific_admission_branches_total=0`;
- provider calls and post-response conversions, both zero;
- an integrity hash.

It must not contain source literals or source-value refs.

## 7. Factory and runtime boundary

`Gate2FinancialEvidenceTypedAdmissionFactory.create` remains the single
structural-filter factory entrypoint. The maintained source and generated
OpenWebUI Gate 2 domain bundle must contain the same implementation.

No provider, persistence adapter, production router, benchmark expectation, or
response repair path may mint or widen this filter.

## 8. Explicit non-goals

This contract does not:

- assemble the complete Semantic Pack model input;
- change generic response validation or materialization;
- activate a provider/model or production route;
- mutate OpenWebUI stage assets;
- qualify a model;
- add Gate 3 methodology.
