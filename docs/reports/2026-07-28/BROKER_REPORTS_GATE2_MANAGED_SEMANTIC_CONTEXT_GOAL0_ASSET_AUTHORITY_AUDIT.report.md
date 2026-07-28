# Broker Reports Gate 2 — Managed Semantic Decision Context GOAL 0 Asset Authority Audit

Date: 2026-07-28

Status: `PASSED_WITH_EXPLICIT_FAMILY_LIFECYCLE_AND_RELEASE_CONTOUR_GAPS`

Base revision: `840464bad7643e1dc9caabbf3c393d555497f487`

Branch:
`codex/broker-reports-gate2-managed-context-goal0-asset-authority-audit`

## 1. Outcome

GOAL 0 identified one existing mechanism to reuse:

`broker_reports_gate2_financial_domain_assets`

This is the existing repository-managed OpenWebUI Financial Domain asset
family. It already composes and pins:

1. one managed Financial Domain Skill;
2. one managed Financial Matching Prompt;
3. one exact Financial Semantic Pack Workspace Tool;
4. the Financial Semantic Pack and its schema;
5. strict consumer and decision-contract dependencies;
6. semantic versions, Git-blob hashes and one composition manifest.

No new GUI framework, financial type registry, Semantic Pack, packet builder or
parallel release mechanism is justified.

The audit also proved that the existing family is not yet a complete managed
publication lifecycle. Repository storage/versioning and native Workspace
surfaces exist. Native Prompt history/restore exists, but non-production
Prompt updates still overwrite current row content and are not isolated safe
drafts. The repository atomic release proves exact snapshot restoration for
all Function and Prompt fields that it mutates during rollback rehearsal, but
candidate readback is only a contracted projection and automatic failure
restoration has a known loader-replacement window. Safe draft storage and
Skill, Tool, Pack and catalog publication/retirement/rollback are not
implemented as one family.

The truthful result is therefore:

`EXISTING_ASSET_PATH_SELECTED_WITH_EXPLICIT_DRAFT_PUBLISHING_AND_RELEASE_GAPS`

## 2. Scope and hard stops

The audit covers only model-facing semantic assets inside Gate 2.

It does not:

- change the active V6 packet, Prompt, Choice or request profile;
- change financial type wording;
- add decision-reason wording;
- implement Context V2;
- change a provider adapter, validator or materializer;
- create or publish OpenWebUI resources;
- mutate stage or production;
- call a model/provider;
- advance to GOAL 1 before this GOAL is reviewed, accepted and merged.

The prior six-submission diagnostic remains terminal evidence. This audit does
not reinterpret its outputs or authorize another provider call.

## 3. Authority precedence

The repository authority order remains:

1. global gate architecture for product/gate placement;
2. versioned contracts for DTO meaning and invariants;
3. maintained factories for construction/execution;
4. compatibility wrappers for version-pinned adaptation only;
5. generated projections;
6. dated reports and receipts as historical evidence.

The exact current map is
[Broker Reports Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).
No dated report becomes a runtime or semantic authority.

## 4. Existing candidates considered

| Candidate | Useful capability | Why it is not a new sole authority |
| --- | --- | --- |
| active V6 Python Prompt | exact current instruction/hash | code-pinned current compatibility; no GUI asset lifecycle; semantic wording must not spread into Python |
| live financial evidence Registry | current runtime type declarations | migration source only; promoting/extending it would preserve duplicate type meaning |
| V6 Packet factory | sole current/candidate context assembler | renderer and evidence projection owner, not semantic asset storage or publication |
| V6 Choice | closed response codes/schema | owns codes and validation shape, not human-readable reason meaning |
| native OpenWebUI Prompt alone | history, production-version pointer, active toggle, restore | every update overwrites current row content, so it has no isolated safe draft and cannot atomically represent Skill/Tool/Pack composition |
| atomic stage release alone | guarded Prompt/Function snapshots, update, projected candidate readback and exact rehearsed snapshot restoration | currently has a loader failure-restore window, no full-row candidate equality, no Skill/Tool/Pack/catalog entries, and requires pre-existing Prompt rows |
| existing Financial Domain asset family | Pack + Skill + Prompt + Tool + schema + manifest + exact hashes | selected reuse mechanism; incomplete family lifecycle is explicit rather than hidden |

## 5. Selected mechanism and exact evidence

### 5.1 Repository system of record

The pinned
[asset manifest](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v1.manifest.json)
declares:

- family ID and semantic version;
- `target_normative_not_live`;
- `runtime_activation=false`;
- OpenWebUI `v0.9.6` Skill, Prompt and Tool API roots;
- all three managed assets with exact repository paths and Git-blob hashes;
- the exact Pack, Pack schema, consumer schema and decision contract;
- Skill → Prompt → Tool → Pack composition;
- Pack-only type-semantic authority;
- no Knowledge/RAG authority.

The
[asset-family contract](../../stage2/contracts/BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v1.md)
already states that the family is repository-managed and not live. Its
deterministic builder is
[`build_openwebui_managed_financial_assets.py`](../../../services/broker-reports-gate1-proof/scripts/build_openwebui_managed_financial_assets.py).

Generated closed-world Tool/model projections are exact hash-checked copies.
They do not become independent semantic authorities.

### 5.2 Native OpenWebUI Workspace surface

The manifest pins OpenWebUI `v0.9.6`. Primary upstream source proves:

- Prompt has `is_active`, a production history `version_id`, commit messages
  and an `is_production` update flag:
  [Prompt model/form](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L23-L93);
- A full-form Prompt update always writes current row fields and creates a
  history entry only when its `content_changed` predicate is true; a selected
  history entry can restore content, and `is_production` only controls whether
  a newly created entry becomes `version_id`:
  [Prompt update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L481-L554)
  and [selected-version restoration](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L585-L622);
- Prompt exposes history, version-selection and active-toggle endpoints:
  [version-selection](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L360-L397),
  [active-toggle](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L454-L492)
  and [history reads](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L533-L616);
- Skill supports managed update and active toggling, but its model has no
  version/history identity:
  [Skill model](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/skills.py#L20-L52),
  [Skill update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L253-L320)
  and [Skill toggle](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L376-L410);
- Tool exposes managed content and an overwrite update, but its model has
  neither version history nor an active-version selector:
  [Tool model](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L20-L52) and
  [Tool update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L291-L304).

Therefore the existing GUI/API is a selected authoring and inspection surface,
not a safe draft store or publisher by itself. Direct GUI edits overwrite
managed rows and must not be treated as drafts or bypass manifest validation,
qualification, atomic publication, exact readback and rollback.

### 5.3 Existing release/rollback contour

The current atomic stage release already provides a valuable but partial
control plane:

- exact Prompt identity, version, content, metadata and hash in its manifest;
- validation before mutation;
- private snapshots of all release-mutated Function and Prompt fields plus
  loader bytes;
- stopped-runtime guarded replacement;
- one SQLite transaction for Function and Prompt rows;
- candidate readback of the contracted Function/Prompt/loader projection;
- rollback rehearsal with exact equality for all snapshotted release-mutated
  Function/Prompt fields and prior loader identity, followed by candidate
  reapplication and projected verification;
- a safe receipt containing only rollback identity, not rollback content.

But it is bounded:

- only Functions, declared already-existing Prompts and the loader participate;
- missing Prompt rows fail closed;
- preflight requires the declared Prompt set and a valid current loader, not
  candidate Prompt/loader parity;
- Prompt rows are directly updated and forced active;
- direct row updates do not create native Prompt history;
- candidate readback omits Function `updated_at` and undeclared
  `meta`/`valves`, plus Prompt `updated_at` and undeclared `meta` keys;
- if loader replacement succeeds but its verification raises before the caller
  sets `modified=true`, automatic failure handling may restart without
  restoring the previous loader;
- Skill, Tool, Pack and reason-catalog resources are absent.

The canonical
[Atomic Stage Release runbook](../../stage2/operations/BROKER_REPORTS_ATOMIC_STAGE_RELEASE.v1.md)
was corrected in this PR to match the current schema-v3 implementation and to
state this family gap explicitly.

## 6. Concern ownership fixed by GOAL 0

| Concern | Sole owner/placement | Explicit non-owner |
| --- | --- | --- |
| financial type semantics | existing versioned Financial Semantic Pack | reason catalog, Prompt, packet, adapter, runner |
| closed decision-reason codes and response shape | existing Choice/decision contracts | Pack and provider adapter |
| human-readable decision-reason semantics | one new versioned catalog dependency inside the existing managed asset family | Python strings, Prompt copy, report code, second Pack/Registry |
| model-visible semantic presentation | managed Skill/Prompt authoring plus deterministic projection by the existing V6 Packet/LLM Context owner | provider adapter and runner |
| exact refs, provenance and evidence bindings | Evidence Bundle and existing backend authorities | managed semantic assets and model |
| local aliases and exact reverse mapping | existing packet/Choice candidate and private receipt authorities | provider adapter |
| retention, validation and materialization | existing backend validators/materializer | model, catalog and GUI |
| future asset-version lifecycle and active pointer | planned extension of the selected family version manifest plus release receipt/control plane; absent today | direct GUI mutation and runtime Python constants |

This split keeps semantic content data-driven without allowing the model or GUI
to own exact backend records.

## 7. Type, reason and publication lifecycles are different

Three lifecycle concepts must not be conflated:

1. Type lifecycle already exists in the Pack:
   `experimental / active / deprecated / retired`.
2. Tenant overlay lifecycle already exists:
   `draft / qualified / retired`.
3. Managed asset-family publication lifecycle does not yet exist end to end.

The presence of type or overlay lifecycle fields is not evidence that a Pack,
Prompt, reason catalog or Context version can be atomically published and
rolled back.

The required future asset-version state machine is:

```text
draft
  -> validated
  -> benchmark-previewed
  -> active
  -> retired

active --rollback--> prior validated immutable version
```

GOAL 0 assigns this state to the existing family manifest/release layer. It
does not implement the transitions.

## 8. Current capability matrix

| Capability | Current status | Evidence/limit |
| --- | --- | --- |
| repository storage | present | Pack, Skill, Prompt, Tool, schemas and manifest are committed assets |
| semantic versioning | present | family/assets/dependencies pin semantic versions and exact hashes |
| deterministic build | present | Tool and manifest rebuild exactly from repository Git-blob text |
| native Prompt history/restore | partial | present, but non-production update still overwrites current row content; no isolated safe draft |
| native Skill active toggle | present | no Skill history/restore |
| native Tool managed update | present | no Tool version/active selector |
| Prompt/Function snapshots and rollback rehearsal | present | exact equality for all snapshotted release-mutated fields; requires pre-existing Prompt rows |
| candidate Function/Prompt readback | partial | contracted safe projection, not full mutated-field equality |
| automatic loader failure restoration | partial | uncovered post-replace/pre-`modified` window |
| full Skill/Prompt/Tool/Pack/catalog publication | missing | no family release manifest entries |
| family retirement and rollback | missing | no active family pointer or exact family restore |
| live managed financial family | absent | manifest and Pack remain non-active |

## 9. Decision-reason gap

The current reason codes are:

- `no_registry_type`;
- `ambiguous_registry_type`.

Choice/decision code validates the closed set. The current packet/Slim view
exposes bare labels. The Context Linter proves code-set equality, but no
versioned authority defines the human distinction.

Type-specific Pack ambiguity guidance is not a substitute:

- `no_registry_type` means no available type matches the source;
- `ambiguous_registry_type` means two or more available types remain plausible
  and one cannot be selected safely.

Today this distinction appears only in diagnostic/report interpretation. Dated
evidence is not a semantic authority. GOAL 1 may create exactly one catalog in
the selected asset family; it must not change type meanings or the active
runtime.

## 10. Duplicate and drift audit

### Proven existing migration debt

- the current runtime Registry and target Pack both carry type declarations;
- the runtime semantic contract validates their exact membership and
  operational parity;
- the Registry remains a migration source, not a second target authority.

### Reason-code duplication

The same two bare codes appear in decision/Choice and packet code. The linter
detects set divergence, but neither copy supplies human meaning. GOAL 1 must
leave code validation in Choice/decision code while sourcing visible wording
from one catalog.

### Generated projections

The Workspace Tool and closed-world model-assets module embed exact generated
Pack copies. Hash/integrity checks make them projections, not authorities. Any
future semantic revision must regenerate and repin them as one family.

### Forbidden corrective patterns

- reason definitions hardcoded in provider adapters;
- type definitions copied into a reason catalog;
- a second packet/context builder;
- a new GUI or semantic registry;
- a Prompt that silently becomes type authority;
- a direct live GUI edit treated as publication;
- an atomic release claim that omits Skill/Tool/Pack rollback;
- a provider call used to debug local asset/lifecycle plumbing.

Duplicate registries created by GOAL 0: `0`.

## 11. Canonical documentation updated

This PR updates:

- global Gate architecture component map;
- Broker Reports architecture authority map;
- OpenWebUI Financial Domain asset-family contract;
- LLM Semantic Context ownership;
- V6 Choice reason-meaning boundary;
- Atomic Stage Release runbook;
- Stage 2 Context Index;
- this dated evidence report and safe receipt.

No existing document/report was moved, so no redirect entry is required.

Repository-safe machine receipt:
[BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL0_ASSET_AUTHORITY_AUDIT.receipt.safe.json](./BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL0_ASSET_AUTHORITY_AUDIT.receipt.safe.json)

Canonical receipt integrity SHA-256 after omitting only top-level
`integrity_sha256`:
`c964c2f9402426f08d6886e38ad05e709d0508de81fa2e022e357f75a5fc46b4`.

## 12. Verification boundary

Accepted shell: PowerShell.

Working directory for service checks:
`services/broker-reports-gate1-proof`.

Validation required for this documentation-only GOAL:

- JSON parse and canonical integrity of the existing managed asset manifest;
- deterministic managed-asset builder `--check`;
- focused managed-asset tests;
- architecture authority tests;
- documentation link/path checks;
- repository privacy guard;
- `git diff --check`;
- fresh review of the actual GitHub diff.

Executed local results:

- deterministic managed-asset builder: `PASSED`;
- manifest SHA-256:
  `2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315`;
- generated Tool SHA-256:
  `e7c1a49cc8988e88a16a0696c03ec7469c961a838fd22dd315257e50815ffaee`;
- focused managed-asset, architecture, release and privacy tests:
  `62 passed`;
- full service suite:
  `1873 passed, 20 skipped`;
- missing local documentation links: `0`;
- `git diff --check`: `PASSED`.

The fresh review of the actual GitHub diff remains a remote merge gate. Local
results do not substitute for it.

There is no handler, asynchronous protocol, provider transport, database
mutation or irreversible runtime boundary in this GOAL. The observable result
is the exact canonical documentation/evidence package and unchanged runtime
source tree.

## 13. Acceptance

```text
SOLE_AUTHORITY_IDENTIFIED: YES
SELECTED_MECHANISM: broker_reports_gate2_financial_domain_assets
EXISTING_GUI_ASSET_PATH: REUSE_SELECTED_WITH_SAFE_DRAFT_GAP
EXISTING_PUBLICATION_ROLLBACK_CONTOUR: REUSE_SELECTED_WITH_KNOWN_GAPS
COMPLETE_FAMILY_LIFECYCLE: EXPLICIT_GAP_PROVEN
FINANCIAL_TYPE_AUTHORITY: FINANCIAL_SEMANTIC_PACK
DECISION_REASON_CODE_AUTHORITY: CHOICE_DECISION_CONTRACTS
DECISION_REASON_MEANING_AUTHORITY: GOAL1_CATALOG_IN_EXISTING_FAMILY
MODEL_VISIBLE_CONTEXT_OWNER: GATE2_FINANCIAL_SEMANTIC_V6_PACKET_FACTORY
DUPLICATE_REGISTRY: ZERO
NEW_GUI_FRAMEWORK: ZERO
RUNTIME_CHANGES: ZERO
STAGE_MUTATIONS: ZERO
PROVIDER_CALLS: ZERO
DOCUMENTATION: UPDATED_IN_SAME_PR
GOAL0: PASSED_WITH_EXPLICIT_LIFECYCLE_AND_RELEASE_CONTOUR_GAPS
NEXT_GOAL: GOAL1_ONLY_AFTER_APPROVED_GREEN_MERGE
```
