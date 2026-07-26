# Broker Reports Gate 2 Managed Financial Domain — Goal 3 Managed OpenWebUI Asset Family

Date: 2026-07-26

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

Base revision: `bebeed378e0c2efeb9f5290ddea62526dd40293f`

Branch:
`codex/broker-reports-gate2-domain-goal3-managed-openwebui-assets`

## 1. Outcome

GOAL 3 creates a repository-managed, versioned OpenWebUI asset family:

1. Financial Domain Skill `1.0.0`;
2. Gate 2 Financial Matching Prompt `1.0.0`;
3. Financial Semantic Pack Workspace Tool `1.0.0`;
4. strict pinned asset manifest and schema.

Supporting Knowledge is intentionally empty. The family is
`target_normative_not_live`; runtime activation, stage mutation, and
production change are all false.

## 2. Managed Skill

OpenWebUI Skill ID:
`broker-reports-financial-domain-matching`

The Skill defines the stable method:

- use only the exact Semantic Pack for financial meaning;
- consider the entire supplied bounded source context;
- use only structurally eligible types and role/ref combinations;
- type only when one Pack definition is uniquely supported;
- choose first-class `unclassified_financial_input` for ambiguous
  source-stated values;
- preserve values and exact permitted refs;
- never invent or calculate missing data;
- return only the strict four-disposition decision contract.

The Skill contains zero accepted `input_type_id` strings and zero copied type
definitions.

## 3. Managed Prompt

OpenWebUI Prompt ID:
`broker-reports-gate2-financial-matching-v1`

Command: `broker_gate2_financial_match_v1`

The Prompt defines one current bounded operation and contains exactly one
input marker:
`{{financial_semantic_matching_input_json}}`.

It pins the Skill, Tool, Pack semantic version/integrity, strict
`broker_reports_gate2_financial_evidence_decision_v1` output, unclassified
safety, and no-invention/no-calculation rules. It contains no type-specific
meaning or admission branch.

## 4. Exact Semantic Pack Tool

OpenWebUI Workspace Tool ID:
`broker_reports_financial_semantic_pack`

Public method: `load_financial_semantic_pack`

Canonical repository route:

- `managed_assets/tools/broker_reports_financial_semantic_pack_tool.v1.py:82`
  — OpenWebUI `Tools` boundary;
- the same file at line 88 — sole public delivery method;
- the same file below the public method — decode, Git-blob hash, Pack
  identity, canonical semantic byte, and integrity validation.

The generated single-file Tool embeds the complete compressed Pack Git blob.
It returns the original LF repository text exactly and verifies:

- Pack Git-blob SHA-256:
  `ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f`;
- Pack ID and semantic version `1.0.0`;
- inactive target status;
- canonical semantic bytes `9404`;
- semantic integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`.

The Tool uses standard-library `base64`, `hashlib`, `json`, `typing`, and
`zlib` only. It has no runtime filesystem path, environment read, network
call, OpenWebUI-internal import, workspace/sibling import, RAG, or Knowledge
dependency. Tampered embedded bytes fail closed.

## 5. Factory and closed-world evidence

The Tool contains both mandatory anti-drift anchors:

- `FACTORY_REQUIRED`: `Tools.load_financial_semantic_pack` is the only managed
  delivery entrypoint;
- `FORBIDDEN`: no runtime filesystem, network/RAG, partial Pack, or semantic
  reinterpretation.

`test_workspace_tool_returns_exact_complete_pack_and_fails_closed` imports the
actual generated single-file Tool, constructs `Tools`, calls the public
method, proves exact Pack-blob parity, and exercises terminal tamper failure.

`test_workspace_tool_is_closed_world_single_file_python` parses the actual
Tool AST, proves the single public method and standard-library-only imports,
and rejects filesystem, environment, network, and OpenWebUI-internal access.

Control-check, UI-action, and smoke parity are not applicable in this GOAL:
the asset is not live and no execution path was activated. Live installation,
binding, smoke, independent readback, and rollback belong to the release
GOAL.

## 6. Pinned manifest

Manifest schema:
`broker_reports_financial_domain_managed_asset_manifest_v1`

Manifest Git-blob SHA-256:
`2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315`

Manifest canonical integrity SHA-256:
`b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59`

The manifest pins:

- three asset identities, versions, paths, media types, Git-blob hashes, and
  OpenWebUI API forms;
- OpenWebUI target/tag `0.9.6` / `v0.9.6`;
- `/api/v1/skills`, `/api/v1/prompts`, and `/api/v1/tools`;
- Pack, Pack schema, consumer schema, and current decision-contract source;
- exact Skill → Prompt → Tool → Pack → strict-output composition;
- `hash_boundary=git_blob_bytes`;
- empty supporting Knowledge;
- all duplicate semantic-authority flags false.

All asset and dependency hashes were verified from staged Git objects, not
Windows working-tree bytes.

## 7. Deterministic build

`scripts/build_openwebui_managed_financial_assets.py`:

- normalizes source text to portable LF Git-blob bytes;
- validates Pack identity and semantic integrity;
- generates the single-file Tool;
- generates the pinned manifest;
- emits no timestamp or environment-specific path;
- supports read-only `--check`.

The generated Tool and manifest matched `--check` exactly:

```text
tool_git_blob_sha256=e7c1a49cc8988e88a16a0696c03ec7469c961a838fd22dd315257e50815ffaee
manifest_git_blob_sha256=2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315
```

## 8. Semantic authority boundary

The manifest enforces:

```text
financial_semantic_authority=semantic_pack_only
full_pack_required=true
rag_only_authority_allowed=false
knowledge_authority_allowed=false
python_type_meanings_allowed=false
prompt_type_meanings_allowed=false
```

Schema-negative probes reject enabling RAG-only authority or adding a
supporting Knowledge item to this v1 family.

## 9. Explicit non-goals

This GOAL adds no:

- live OpenWebUI install, activation, owner, tenant, group, or access grant;
- current production Pipe/Function update;
- type-specific deterministic scope removal (GOAL 4);
- final model-input assembly (GOAL 5);
- validator/materializer change (GOAL 6);
- query/catalog API (GOAL 7);
- provider qualification or model call;
- Gate 3 tax/declaration/ledger methodology.

## 10. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- managed asset tests: `8 passed in 0.89s`;
- focused asset/Pack/consumer/decision tests:
  `45 passed in 1.37s`;
- full Broker Reports suite:
  `1545 passed, 20 skipped, 5 warnings in 114.90s`;
- repository privacy guard: `3 passed in 0.86s`;
- JSON Schema meta/instance validation: passed;
- manifest integrity and every staged Git-blob pin: passed;
- exact Tool/Pack blob and semantic-integrity parity: passed;
- tamper terminal: failed closed;
- deterministic build `--check`: passed;
- closed-world import check: passed;
- anti-drift anchors: enforced;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

## 11. Deliverables

1. asset-family contract;
2. managed Skill;
3. managed Prompt;
4. exact Semantic Pack Workspace Tool;
5. strict manifest and manifest schema;
6. deterministic builder;
7. contract/integrity/closed-world/anti-drift tests;
8. this safe report;
9. repository-safe receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL3_MANAGED_OPENWEBUI_ASSET_FAMILY.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL3_MANAGED_OPENWEBUI_ASSET_FAMILY.receipt.safe.json)
   - Git-blob SHA-256:
     `9759d3a0c208d3be70be92d1846b09f4ae2ad83572adaf2a18e38f79b113c255`

## 12. Acceptance markers

```text
MANAGED_SKILL: VERSIONED
MANAGED_PROMPT: VERSIONED
SEMANTIC_PACK_FUNCTION: EXACT
ASSET_MANIFEST: PINNED
RAG_ONLY_AUTHORITY: FORBIDDEN
RUNTIME_ACTIVATION: FALSE
NEXT_PERMITTED_GOAL: GOAL_4_AFTER_GOAL_3_REVIEW_ACCEPTANCE_AND_MERGE
```
