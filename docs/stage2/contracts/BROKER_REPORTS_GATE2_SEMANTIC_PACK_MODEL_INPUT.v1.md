# Broker Reports Gate 2 Semantic Pack Model Input v1

Status: historical version-pinned full-Pack candidate; repository-managed;
not live-activated; not the future Minimal Model Surface.

## 1. Purpose

This contract defines the bounded historical V4 model-input candidate that
joins a deterministic financial scope, visible Gate 1 source context, the
complete compact Financial Semantic Pack, and exact managed OpenWebUI asset
identities.

The Pack alone owns financial meaning. Deterministic code owns only structural
eligibility, package membership, bounded projection, and validation.

## 2. Versioned identities

- model input:
  `broker_reports_gate2_financial_evidence_successor_model_input_v4`;
- result:
  `broker_reports_gate2_financial_evidence_successor_result_v4`;
- Prompt contract:
  `broker_reports_gate2_financial_evidence_managed_prompt_v1`;
- managed model-asset projection:
  `broker_reports_gate2_financial_semantic_model_assets_v1`;
- request profile:
  `financial_evidence_successor_qualification_v3`;
- strict decision:
  `broker_reports_gate2_financial_evidence_decision_v1`;
- Pack:
  `broker_reports_managed_financial_semantic_pack@1.0.0`;
- Pack integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- hash boundary for managed source assets: Git blob bytes.

V1-V3 successor inputs and Prompts remain frozen compatibility contracts.

## 3. Exact model-input shape

The V4 input has exactly four top-level members:

```text
managed_assets
semantic_pack
structural_scope
source_groups
```

`managed_assets` contains exact manifest-derived Skill and Prompt identities:
asset ID, kind, semantic version, Git-blob SHA-256, and OpenWebUI API identity.
It contains no repository path.

`semantic_pack` contains the exact Pack identity and the complete,
order-preserving `full_compact_snapshot`. No type, field, example,
counterexample, distinction, synonym, ambiguity rule, or model guidance entry
may be removed or rewritten.

`structural_scope` contains only:

- every structurally eligible type ID from the deterministic decision
  contract;
- every package candidate ref and its exact allowed role set.

`source_groups` contains every bounded visible or deterministic-reference
value from the validated Gate 1 source context. Allowed roles are removed from
the groups because `structural_scope` is their single authority.

## 4. Source context

Visible source groups preserve:

- group kind;
- row and section role;
- package-bound `source_value_ref`;
- value type;
- exact associated literal;
- column meaning;
- visible label.

Deterministic-reference groups preserve their package-bound ref and value type
but carry no invented literal, label, or column meaning.

Every scope value must occur exactly once. Context groups and literals remain
bounded by the existing source-context limits and validator.

## 5. Forbidden model metadata

The model input must not contain:

- document, file, page, table, row, cell, segment, or filesystem path IDs;
- internal relation, candidate, lineage, or provenance graphs;
- package, source-scope, normalization-run, or audit metadata;
- confidence, completeness, ownership, restrictions, or uncertainty state;
- expected answers or raw model output;
- Gate 3 methodology.

Opaque package-bound `source_value_ref` values are required decision inputs
and are not source-locator or filesystem references.

## 6. One semantic authority

The V4 input must not contain the former Registry `eligible_types` projection
or any other definition, synonym, counterexample, semantic distinction, or
ambiguity-guidance block outside `semantic_pack`.

The managed Prompt defines procedure and output discipline but no financial
type meaning. Skill and Prompt are represented in the input by identity, not
by a copied semantic dictionary. Therefore:

```text
semantic authorities total = 1
duplicate semantic authorities total = 0
```

The existing four-disposition strict decision contract is reused unchanged.

## 7. Closed-world projection

`build_gate2_financial_semantic_model_assets.py` generates the runtime
projection from the repository Pack, managed Prompt, and managed asset
manifest. The generated module embeds compressed exact bytes and verifies:

- Pack Git-blob hash, identity, canonical semantic size, and integrity;
- exact Prompt Git-blob hash and input marker;
- canonical manifest-derived Skill and Prompt identities.

It performs no runtime filesystem, network, Knowledge, RAG, embedding, vector,
or provider access. The official OpenWebUI bundle builder includes this module
before the successor module.

## 8. Validation and failure behavior

The V4 validator fails closed unless:

1. the four-part shape is exact;
2. Pack identity and the complete compact snapshot equal the generated
   projection;
3. exact managed identities equal the manifest-derived projection;
4. structurally eligible IDs are Pack members;
5. allowed role/ref combinations equal the deterministic decision contract;
6. source groups exactly cover the validated source context;
7. no forbidden system field or second semantic authority is present.

There is no fallback, response repair, semantic Python predicate, or validator
bypass.

## 9. Economy and activation boundary

The full V4 request is larger than the historical 3,072-token financial
evidence cap. Historical Semantic Pack Model Input GOAL 5 did not widen that
cap, call a provider, qualify a model, or activate a production route. That
completed historical program goal is distinct from current Minimal Model
Surface GOAL 5. The existing budget guard therefore continues to reject such
calls before provider authorization until a separately authorized
qualification/admission goal establishes a new measured policy.

## 9.1 Current minimal-surface routing

The complete `full_compact_snapshot` and every identity above remain exact
historical V4 contract data. They are not evidence that every full-Pack field
is eligible for a future model view and are not rewritten by the
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md).
The separate implemented non-active
[Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md) likewise
remains exact version-pinned historical completeness evidence.

GOAL 5 defines the field boundary and GOAL 6 audits the outcome taxonomy and
count-one stop. GOAL 7 implements one versioned minimal projection through
the existing managed projection owner using only the exact GOAL 5 selections:
Pack `examples[0]`, `counterexamples[0]`, the unique direct rule against the
only other current visible type, and the exact first sentence of catalog
`meaning`. Those strings already exist; GOAL 7 does not author markers or
reason wording. GOAL 8 implements only one non-active
[PacketFactory V2.1 candidate plus private receipt](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
**STOP before GOAL 9:** a separately
authorized/versioned V2.1 response profile must first exist in the Choice
authority, or the program must be amended. GOAL 9 only consumes that schema
while linting P01-P18; it cannot invent or build it. This contract adds no
new semantic authority, request, provider or runtime activation.

## 10. Explicit non-goals

This contract does not:

- change Pack contents or managed Skill/Prompt bytes;
- make validator/materializer type-independent (historical Semantic Pack
  program GOAL 6);
- add persistence or Gate 3 query interfaces;
- perform a customer, provider, or model call;
- mutate OpenWebUI stage or production;
- admit any model or workload to production.
