# Broker Reports OpenWebUI Financial Domain Asset Family v1

Status: target normative contract, repository-managed, not live

Version: `1.0.0`

Manifest schema:
`broker_reports_financial_domain_managed_asset_manifest_v1`

Family ID: `broker_reports_gate2_financial_domain_assets`

## 1. Purpose

This contract defines the managed OpenWebUI asset family used to make one
bounded Gate 2 Financial Domain semantic decision:

1. Financial Domain Skill — stable method;
2. Gate 2 Financial Matching Prompt — current operation;
3. Financial Semantic Pack Workspace Tool — exact Pack delivery;
4. pinned asset manifest.

Supporting Knowledge is optional by program contract and is intentionally
absent from v1. Financial semantics do not depend on RAG, Knowledge,
embeddings, vector search, or native OpenWebUI document processing.

GOAL 3 creates repository assets only. It does not install, activate, bind, or
publish them in a live OpenWebUI instance. Release and live readback belong to
the later release GOAL.

## 2. OpenWebUI compatibility

The repository pins OpenWebUI `v0.9.6`. The manifest therefore pins:

- Skill API root: `/api/v1/skills`;
- Prompt API root: `/api/v1/prompts`;
- Workspace Tool API root: `/api/v1/tools`;
- Tool module form: Python `class Tools` with a typed, documented public
  method.

These shapes match the official OpenWebUI `v0.9.6` source:

- <https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py>
- <https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py>
- <https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/tools.py>

The repository manifest contains complete API identities but no owner,
tenant, group, or access grants. Those are environment-specific release
inputs and must be applied and independently read back during the release
GOAL.

## 3. Single semantic authority

Only dependency
`broker_reports_managed_financial_semantic_pack@1.0.0` defines financial type
meaning.

Pinned semantic identity:

- Pack ID: `broker_reports_managed_financial_semantic_pack`;
- semantic version: `1.0.0`;
- repository Git-blob SHA-256:
  `ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f`;
- semantic integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- canonical semantic bytes: `9404`.

The Skill defines method, not type meaning. The Prompt defines one operation,
not type meaning. The Tool returns Pack bytes, not a reduced interpretation.
The manifest explicitly sets all of the following to false:

- `rag_only_authority_allowed`;
- `knowledge_authority_allowed`;
- `python_type_meanings_allowed`;
- `prompt_type_meanings_allowed`.

## 4. Managed Skill

OpenWebUI Skill ID:
`broker-reports-financial-domain-matching`

Semantic version: `1.0.0`

The Skill requires:

- full exact Pack loading;
- exact Pack identity verification;
- the whole supplied bounded source context;
- only structurally eligible types and allowed role/ref combinations;
- typed selection only when Pack meaning is unique and required roles are
  explicit;
- first-class unclassified output when safe typing is not possible;
- no invention, calculation, normalization, repair, or missing-data fill;
- one strict
  `broker_reports_gate2_financial_evidence_decision_v1` object.

The Skill contains no accepted `input_type_id` and no copied type definition.

## 5. Managed Prompt

OpenWebUI Prompt ID:
`broker-reports-gate2-financial-matching-v1`

Command: `broker_gate2_financial_match_v1`

Semantic/version ID: `1.0.0`

The Prompt performs one current operation. It has exactly one bounded-input
placeholder:

`{{financial_semantic_matching_input_json}}`

The Prompt pins the Skill, Tool, Pack version/integrity, four-disposition
decision contract, Pack-only semantic authority, safe unclassified behavior,
and the ban on invented or calculated values. It contains no financial type
definition or type-specific admission instruction.

## 6. Exact Semantic Pack Tool

OpenWebUI Workspace Tool ID:
`broker_reports_financial_semantic_pack`

Public method: `load_financial_semantic_pack`

The generated Tool embeds a compressed copy of the complete repository Pack
Git blob. At construction it:

1. decodes and decompresses the embedded bytes;
2. verifies the Pack Git-blob SHA-256;
3. parses one JSON object;
4. verifies Pack ID, semantic version, and inactive target status;
5. removes only `integrity_sha256` from hash material;
6. canonicalizes with UTF-8, lexicographic object keys, preserved array order,
   and no whitespace;
7. verifies canonical byte count, semantic SHA-256, and supplied integrity;
8. returns the original repository Pack Git-blob text unchanged.

The runtime Tool uses only Python standard-library modules already present in
the OpenWebUI image. It uses no filesystem path, environment variable,
network request, OpenWebUI-internal import, RAG, Knowledge, or sibling-service
source import.

The Tool exposes the anti-drift anchors `FACTORY_REQUIRED` and `FORBIDDEN`.
Any byte, identity, or semantic-integrity mismatch fails closed.

## 7. Manifest and deterministic build

All content hashes use `hash_boundary=git_blob_bytes`; working-tree newline
expansion is not evidence. Canonical manifest integrity is SHA-256 over
canonical JSON after omitting only top-level `manifest_sha256`.

The manifest pins:

- all three asset IDs, versions, repository paths, media types, and Git-blob
  hashes;
- exact OpenWebUI API identities;
- Pack, Pack schema, consumer schema, and current strict decision-contract
  source Git-blob hashes;
- composition links between Skill, Prompt, Tool, Pack, bounded input, and
  output contract;
- empty supporting Knowledge;
- inactive repository-only status.

`scripts/build_openwebui_managed_financial_assets.py` deterministically builds
the Tool and manifest from LF-normalized repository text. `--check` performs
no write and compares the generated Git-blob text, independent of checkout
newline policy.

## 8. Boundary to later GOALs

This asset family does not:

- remove current type-specific deterministic scope behavior (GOAL 4);
- assemble the final bounded Pack-visible model input (GOAL 5);
- change validation or materialization (GOAL 6);
- implement catalog/query APIs (GOAL 7);
- qualify a provider/model;
- mutate stage or production;
- add Gate 3 methodology.

Later GOALs may update pinned dependency hashes or issue a new asset semantic
version. They must not silently edit a live asset or treat a stale manifest as
current authority.

## 9. Managed Semantic Decision Context lifecycle audit

The Managed Semantic Decision Context GOAL 0 audit selects this existing asset
family as the sole reuse path. No second semantic registry, Semantic Pack,
packet builder, parallel asset-family/manifest authority or GUI framework is
permitted. Additional immutable version manifests inside this selected family
are allowed.

The ownership split is:

- financial type meaning remains in the Financial Semantic Pack;
- the closed decision-reason code set and response shape remain in the current
  Choice/decision contracts;
- human-readable decision-reason meaning belongs in one separately versioned
  catalog dependency inside this same asset family;
- authorable model-visible presentation belongs in the managed Skill/Prompt,
  while the existing V6 packet factory remains the sole context assembler;
- exact refs, provenance, aliases, bindings, retention and materialization
  remain backend-only.

The existing family proves repository storage, semantic versioning, immutable
hash identity, deterministic composition and an OpenWebUI Workspace GUI/API
surface. It does not yet prove a complete family-level publish lifecycle.
OpenWebUI `v0.9.6` has native Prompt history, a production-version pointer,
active toggling and restore. However every Prompt update overwrites current row
content even when `is_production=false`; the flag only controls whether the
production-version pointer moves. This is not isolated runtime-safe draft
storage. Skill has update plus active toggling but no version history. Tool has
overwrite update but no history or active-version selector.

The repository atomic stage release proves snapshot, exact readback and
rollback for Functions plus already-existing Prompt rows. It does not publish
or restore this Skill/Tool/Pack family, and its direct Prompt-row update does
not create native Prompt history.

Therefore isolated `draft` storage, validation, active selection, retirement
and rollback for the complete family are an explicit later implementation gap.
They must be added by extending this manifest/release contour. The OpenWebUI
Workspace surface may be reused for authoring and inspection only behind that
guarded lifecycle: direct GUI edits overwrite managed rows and are not
publication or safe drafts. Until that boundary exists, this family remains
repository-managed and non-active.

## 10. Acceptance

```text
MANAGED_SKILL: VERSIONED
MANAGED_PROMPT: VERSIONED
SEMANTIC_PACK_FUNCTION: EXACT
ASSET_MANIFEST: PINNED
RAG_ONLY_AUTHORITY: FORBIDDEN
RUNTIME_ACTIVATION: FALSE
MANAGED_CONTEXT_REUSE_PATH: THIS_ASSET_FAMILY
COMPLETE_FAMILY_LIFECYCLE: EXPLICIT_GAP
```
