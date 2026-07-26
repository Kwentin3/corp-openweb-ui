# Broker Reports Gate 2 Domain — GOAL 5 Semantic Pack Model Input

Date: 2026-07-26.

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Base revision: `f16ae47e107f9a08f82b1bbef6cbaddc6248633f`.

Branch:
`codex/broker-reports-gate2-domain-goal5-bounded-input`

## 1. Objective

Build one bounded Pack-authoritative model input from deterministic scope,
visible Gate 1 groups, the complete compact Semantic Pack, structurally
eligible types, exact role/ref combinations, and exact managed Skill/Prompt
identities.

## 2. Contract

New target contract:
[`BROKER_REPORTS_GATE2_SEMANTIC_PACK_MODEL_INPUT.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_SEMANTIC_PACK_MODEL_INPUT.v1.md).

Versioned target identities:

```text
model_input=broker_reports_gate2_financial_evidence_successor_model_input_v4
result=broker_reports_gate2_financial_evidence_successor_result_v4
prompt=broker_reports_gate2_financial_evidence_managed_prompt_v1
request_profile=financial_evidence_successor_qualification_v3
asset_projection=broker_reports_gate2_financial_semantic_model_assets_v1
decision=broker_reports_gate2_financial_evidence_decision_v1
```

The previous V1-V3 contracts remain frozen.

## 3. Complete Pack visibility

The model input contains the exact Pack identity and every entry in
`full_compact_snapshot`, in normative order. The runtime projection verifies:

```text
pack_id=broker_reports_managed_financial_semantic_pack
semantic_version=1.0.0
integrity_sha256=ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8
compact_types_total=2
```

Tests compare the projected snapshot by deep equality with the repository
Pack. Removing one entry fails closed with
`financial_evidence_successor_semantic_pack_incomplete`.

## 4. Exact managed identities and Prompt

Skill and Prompt identities are generated from the accepted managed asset
manifest without repository paths. The successor uses the exact managed
Prompt bytes:

```text
prompt_ref=openwebui:broker-reports-gate2-financial-matching-v1@1.0.0
prompt_git_blob_sha256=3f169c79a9bf6f0eb1b476853ed1ace50cca9b2f7fd2d2fe3394f2ab3f6d5a2e
```

The request builder replaces the exact managed
`{{financial_semantic_matching_input_json}}` marker once and retains
`knowledge_rag_used=false` and `vectorization_performed=false`.

## 5. Bounded source and structural scope

The input contains all validated source groups with their group kind, row and
section role, exact associated literal, column meaning, visible label, value
type, and opaque package-bound source-value ref.

Structural eligibility is represented only by:

- the decision contract's complete eligible type ID list;
- one exact allowed-role list for every package candidate ref.

Allowed roles are removed from `source_groups`, so there is one structural
role/ref authority. The existing source-context validator still proves exact
coverage before the projection is built.

## 6. Duplicate-authority and metadata proof

The former V3 Registry definition/counterexample projection is absent. All
definitions, synonyms, examples, counterexamples, distinctions, ambiguity
guidance, and model guidance occur only under `semantic_pack`.

Negative tests reject:

- incomplete Pack contents;
- drifted Prompt identity;
- injected document IDs;
- forbidden system fields;
- semantic guidance outside the Pack.

The V4 input contains no document/path IDs, internal/provenance graph, source
scope, audit, expected answer, raw provider output, or Gate 3 methodology.

## 7. Closed-world bundle

The new runtime asset projection is generated deterministically from the Pack,
managed Prompt, and manifest. It uses only Python standard-library in-memory
decoding and validation and performs no runtime filesystem or network access.

It is included in the official Gate 2 domain single-file bundle before the
successor. Rebuilding the bundle twice is byte-exact.

```text
runtime_projection_sha256=e6fcaab0c323dcc88959bcccbb16a6d4b40986f9308e2ecbd65dd1a09a85dd75
bundle_sha256=6fddac7bc9ccccc315c5877d309f9a246fa8e6912d5a326139a87e504305069c
bundle_rebuild=exact
```

No live OpenWebUI asset was installed or changed.

## 8. Terminal-path proof

A focused test executes the V4 successor through:

1. deterministic scope and source-context validation;
2. exact model-input construction;
3. the existing provider response-format projection;
4. one fake transport response;
5. the real strict decision validator;
6. the real materializer;
7. terminal `unclassified_financial_input`.

The fake transport is used only to avoid a provider call; terminal validation
and materialization are real. Fallback and repair remain zero.

## 9. Honest budget boundary

The complete V4 dry-build across the current 11 synthetic cases estimates
3,902–5,358 input tokens. The existing financial-evidence cap remains 3,072,
so the budget guard rejects V4 before provider authorization.

GOAL 5 does not widen the cap because provider qualification and workload
admission belong to later goals. No earlier qualification receipt is current
for this new Prompt/input/schema identity. The exact old Haiku candidate was
not rerun.

## 10. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- initial focused Pack/input/successor/bundle tests:
  `43 passed in 4.15s`;
- focused successor/artifact/budget regressions:
  `74 passed in 10.86s`;
- final focused tests: `117 passed in 14.80s`;
- full Broker Reports suite:
  `1554 passed, 20 skipped, 5 warnings in 123.62s`;
- generated runtime projection rebuild: exact;
- generated domain bundle rebuild: exact;
- targeted Ruff: passed;
- package-facade Ruff: passed with historical `F401` excluded;
- targeted compileall: passed;
- `git diff --check`: passed;
- repository privacy guard: `3 passed in 0.83s`;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

## 11. Explicit unchanged boundaries

This GOAL does not:

- change Semantic Pack, managed Skill, or managed Prompt bytes;
- change the four-disposition decision contract;
- claim generic validator/materializer closure owned by GOAL 6;
- add persistence, domain query APIs, or Gate 3 tooling;
- change production allowlists or workload admissions;
- perform a provider/customer call;
- write customer/private values, raw provider output, secrets, or local paths
  to Git.

## 12. Acceptance markers

```text
SEMANTIC_PACK_VISIBLE=COMPLETE
SOURCE_CONTEXT=BOUNDED_AND_SUFFICIENT
SYSTEM_METADATA=ABSENT
DUPLICATE_SEMANTIC_AUTHORITY=ZERO
```

Authoring status:
`IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

Next permitted goal:
`GOAL_6_AFTER_GOAL_5_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.

## 13. Safe receipt

Repository-safe receipt:
[`BROKER_REPORTS_GATE2_DOMAIN_GOAL5_SEMANTIC_PACK_MODEL_INPUT.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL5_SEMANTIC_PACK_MODEL_INPUT.receipt.safe.json)

Its exact Git-blob SHA-256 is recorded here after committed-object
finalization:

`9c4642032c057bbbe070f8d4d55ae858911937f606446f7e20005028e8167472`
