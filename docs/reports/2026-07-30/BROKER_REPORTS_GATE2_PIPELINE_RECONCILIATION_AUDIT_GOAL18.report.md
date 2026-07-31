# Broker Reports GOAL 18 — Gate 2 Pipeline Reconciliation Audit

Date: 2026-07-30
Status: `AUDIT_COMPLETE_WITH_LIVE_BUNDLE_DRIFT`
Scope: repository and saved-evidence reconciliation only
Provider calls during audit: `0`

## 1. Executive summary

The semantic visual-table input path is real, released, and represented by maintained production owners. It sends one immutable table crop—not the whole PDF—to Gemini as the master VLM, accepts only `description + rows`, then deterministically creates the semantic envelope, logical table, normalized projection, ArtifactStore record, and Gate 2 package. Saved historical evidence proves this chain on customer-shaped inputs. The current live valves remain enabled, but a fresh read-only parity check failed because all three live Function bundle hashes differ from `main`; therefore the route is operationally enabled but not currently parity-confirmed against this repository snapshot.

The presumed “old production `source_fact_selection_v2`” is not a current production route. The repository contains `broker_reports_source_fact_selection_v3`; it ran historically at commit `ba1eb13475fa9a31488fb54ea764db8e1aba4947`, then commit `d14bb70045954947c6bf7fe812a93418258dcff8` deliberately contained it as regressive. Current `main` hard-wires its source-Pipe containment guard to `False`, and the current domain runtime no longer imports the selection contract. Product extraction currently uses the broader canonical `broker_reports_source_facts_v0` response plus deterministic validation.

The old selection contract did not expose the global nine-type enum uniformly. Across 35 exact saved `v3` requests, 26 schemas exposed only `unknown_source_row`; nine exposed exactly `document_summary_evidence + unknown_source_row`. Package-level `position_snapshot`, `fee_commission`, and `income` were removed by the capability/required-field projection. The exact traced requests carried no rich per-type definitions: the model saw enum names, a narrow domain prompt, the source package, and dynamically bounded value-binding refs.

GOAL 17 adds genuinely useful semantics: versioned rich type cards, local opaque type keys, plural `plausible_types`, code-owned reasons, exact option restoration, a sealed request, exact replay, and explicit false-singleton observability. It does not add visual reading. Its proof uses three synthetic benchmark fixtures through `Gate2DeterministicFinancialScopeFromGate1V2Factory`; it does not consume the existing historical semantic-visual Gate 2 package, and it is inactive with zero provider evidence. Its additive Packet/Choice/Context-Linter/Expansion path overlaps the old selection route’s classification, schema, parser, and deterministic materialization responsibilities.

Preferred convergence is **Option A**: preserve the existing visual input, Gate 2 package, segmentation, ArtifactStore, validators, and materializer; bring the useful Type-First contract into the existing source-fact owner rather than activating a second V6 semantic route. Option B is the reserve only if the program explicitly proves that V6 Financial Semantic classification is a different domain decision from source-fact typing. PR #232 should not be merged as-is before that architectural direction is approved.

## 2. Verified Git snapshots

### 2.1 Local and remote snapshot

| Item | Verified value |
| --- | --- |
| Original worktree branch | `feat/broker-reports-goal-17-type-first-inactive` |
| Original worktree HEAD | `d6954f401ae4734fc1573c7560c981cf084c278c` |
| Original untracked files | Three pre-existing GOAL 17-adjacent reports; untouched |
| `origin/main` at audit start | `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614` |
| Audit base | Exact `origin/main` above |
| Audit branch | `audit/broker-reports-goal-18-gate2-reconciliation` |
| Historical detached snapshot | `ba1eb13475fa9a31488fb54ea764db8e1aba4947` |
| GOAL 17 comparison head | `d6954f401ae4734fc1573c7560c981cf084c278c` |

The audit was performed in a separate worktree. The original GOAL 17 worktree and its untracked user files were not modified.

### 2.2 PR #232

At audit time PR [#232](https://github.com/Kwentin3/corp-openweb-ui/pull/232) was:

| Field | Value |
| --- | --- |
| State | Open Draft |
| Base | `main` at `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614` |
| Head | `feat/broker-reports-goal-17-type-first-inactive` at `d6954f401ae4734fc1573c7560c981cf084c278c` |
| Changed files | 27 |
| Commits | 5 |
| Merge status | `MERGEABLE` / `CLEAN` |
| Check | `broker-reports-ci`: `SUCCESS` |
| Merge action | Not performed |

GitHub’s combined commit-status collection was empty, while the PR CheckRun collection contained the successful workflow. This audit treats the CheckRun as the check evidence and does not equate mergeability with product acceptance.

## 3. Historical evolution

| PR | Merge commit | Verified contribution | Current disposition |
| --- | --- | --- | --- |
| [#12](https://github.com/Kwentin3/corp-openweb-ui/pull/12) | `c568bc5e…` | Semantic visual-table `description + rows` contract | Maintained |
| [#13](https://github.com/Kwentin3/corp-openweb-ui/pull/13) | `c30f50b7…` | Gemini runtime/factory boundary | Maintained |
| [#16](https://github.com/Kwentin3/corp-openweb-ui/pull/16) | `3ccfde4c…` | Three-table VLM qualification | Historical qualification evidence |
| [#18](https://github.com/Kwentin3/corp-openweb-ui/pull/18) | `9f050fe5…` | Downstream migration to logical table/Gate 2 projection | Maintained |
| [#19](https://github.com/Kwentin3/corp-openweb-ui/pull/19) | `e8c75cdf…` | Atomic default-on release | Maintained policy; live parity presently failed |
| [#23](https://github.com/Kwentin3/corp-openweb-ui/pull/23) | `a68ac222…` | Post-Gate-2 deterministic answer-context selection | Maintained |
| [#35](https://github.com/Kwentin3/corp-openweb-ui/pull/35) | `df22db91…` | Reduced source-fact provider response | Historical route |
| [#40](https://github.com/Kwentin3/corp-openweb-ui/pull/40) | `75a30d0e…` | Capability-aware semantic selection | Historical; later contained |
| [#231](https://github.com/Kwentin3/corp-openweb-ui/pull/231) | `9a4cc2c9…` | Type-First fail-closed contract | Contract on `main`, inactive |
| [#232](https://github.com/Kwentin3/corp-openweb-ui/pull/232) | Not merged | Type-First inactive implementation/proof | Draft experimental implementation |

The important post-#40 history is:

1. `ba1eb134…` added domain semantic selection and produced the exact historical traces used here.
2. `d14bb700…` contained the route as regressive.
3. `main` preserves the code/contracts for evidence readability but prevents product reachability.

## 4. Current visual-table route

### 4.1 Exact owner chain

| Step | Current owner and symbol | Input → output | Status / consumer |
| --- | --- | --- | --- |
| PDF intake/detection | `pdf_table_intake_runtime.py:66` — `PdfTableIntakeRuntimeFactory` | PDF bytes → bounded page/candidate inventory and PNG crop manifest | Maintained; called by Gate 1 Pipe |
| Crop/VLM orchestration | `pdf_dual_vlm_runtime.py:131` — `PdfDualVlmRuntimeFactory.create_for_openwebui`; `:244` — `PdfDualVlmRuntime.run` | Immutable crop candidates → provider decision/private evidence | Maintained; Gate 1 Pipe `:890-947` |
| VLM contract | `semantic_visual_table_contracts.py:59` and `:84` | Crop → exact `{description, rows}` schema | Maintained normative contract |
| Deterministic envelope/logical table | `semantic_visual_table_materialization.py:77` — `SemanticVisualTableMaterializationFactory`; `:104` — `materialize` | Valid transcription + lineage → semantic envelope + logical table + projection | Maintained |
| Downstream admission | `semantic_visual_table_migration.py:77` — `SemanticVisualTableMigrationFactory`; `:111` — `migrate` | Decisions/evidence → admitted projections or fail-closed dispositions | Maintained |
| Artifact persistence | Gate 1 Pipe + `ArtifactStoreFactory` | Private envelope/projection → immutable ArtifactStore records | Maintained private boundary |
| Gate 2 package | `gate2_table_packages.py:37` — `Gate2TablePackageFactory`; `:52` — `build` | Valid projection → bounded Gate 2 table package | Maintained |
| Gate 2 readiness/orchestration | `gate2_input_readiness.py:111` — `Gate2InputReadinessFactory`; `:142` — `audit_and_build` | DCP + ArtifactStore projections → Gate 2 source packages | Maintained |

Gate 1 product order is explicit in `openwebui_actions/broker_reports_gate1_pipe.py:607-637`: table intake, dual VLM, semantic migration, then private envelopes/projections.

### 4.2 Provider boundary

`architecture_policy.py:31-53` fixes the boundary:

- provider input scope is `declared_page` or `table_crop`;
- whole-document provider upload is forbidden;
- local OCR production is forbidden;
- Gemini (`google_gemini`) is master;
- OpenAI is optional control or explicit fallback;
- provider authority is transcription only;
- Gate 2 owns financial interpretation.

The exact response schema is `broker_reports_semantic_table_transcription_v1`. The only root fields are:

```text
description: string
rows: array<array<string|null>>
```

The provider does not return document IDs, crop IDs, indexes, spans, geometry, hashes, canonical facts, or financial classifications. Deterministic code supplies those fields.

### 4.3 Supported and fail-closed inputs

The released downstream profile is deliberately narrower than the VLM’s absolute contract bounds. `SemanticVisualTableMigrationConfig` admits at most:

- 64 rows;
- 4 columns;
- 256 characters per cell.

Admission additionally requires:

- terminal valid semantic transcription;
- no review requirement;
- valid selected-provider contract;
- no provider merge;
- no provider-created canonical table;
- at least one visible amount and one visible label;
- no visual-uncertainty signal in `description`.

Out-of-bounds, visually uncertain, missing-label, missing-amount, invalid-schema, review-required, or non-terminal cases are not promoted and finish with a typed disposition.

### 4.4 Execution evidence and live parity

ArtifactStore’s read-only inventory contained:

- 30 semantic visual envelopes;
- 64 migration-policy artifacts;
- 88 PDF candidates;
- 120 detection attempts;
- 72 intake runs.

Trace A and B each join a persisted Gemini crop transcription to a logical projection and historical Gate 2 request. Both VLM steps passed the exact contract.

The 2026-07-30 read-only live verifier reported:

- table intake valve: enabled;
- dual-VLM valve: enabled;
- semantic downstream valve: enabled;
- Gemini model configured;
- PyMuPDF `1.26.5`;
- all 12 managed Prompt contracts match the repository;
- all three live Function bundle hashes differ from `main`;
- repository factory-boundary aggregate failed because `provider_adapters_stay_inside_openwebui=false`.

| Function | Live SHA-256 | Repository SHA-256 | Parity |
| --- | --- | --- | --- |
| Gate 1 | `a042ff14…f70519` | `a685e1c9…e836af` | Failed |
| Gate 2 source | `d3ba38ed…83d503` | `aa49f3be…07eef8` | Failed |
| Gate 2 domain | `4f5424f2…3bb0d5` | `21ab2062…629ace` | Failed |

Conclusion: visual reading is implemented and historically executed; live valves are on; exact current repository/live parity is **failed**, so “current runtime equals `main`” is not proven.

## 5. Current and historical source-fact routes

### 5.1 Current `main`

The source Pipe defines `semantic_selection_enabled`, but `openwebui_actions/broker_reports_gate2_source_fact_pipe.py:60-63` returns `False` from `_semantic_selection_containment_guard`, and `:260-262` passes only that result to runtime. The valve cannot activate the route. Current domain runtime has no semantic-selection branch.

Current product behavior is:

```text
Gate 2 package
→ broad broker_reports_source_facts_v0 structured response
→ Gate2SourceFactValidatorFactory
→ canonical source facts / fail closed
```

The following audited route is therefore historical:

```text
Gate 2 package
→ broker_reports_source_fact_selection_v3
→ decision_type + value_bindings
→ deterministic materialization
→ canonical broker_reports_source_facts_v0
```

The task calls it `v2`; current code and saved validations identify the final form as `v3`.

### 5.2 Exact historical model-visible projection

Exact historical requests were rebuilt with the exact deployed-era owner code at `ba1eb134…`, exact persisted package, exact managed Prompt snapshot, and exact dynamic response schema. No provider call was made.

The model-visible material consisted of:

1. system message: narrow managed domain Prompt with the complete private package replacing `{{source_fact_package_json}}`;
2. user message:
   - `task=extract_broker_reports_domain_source_facts_v0`;
   - `extractor_domain`;
   - package ref;
   - package `allowed_fact_types`;
   - exact return instruction;
3. strict `response_format`:
   - one `decisions` array;
   - exact decision count equal to selected source refs;
   - `decision_type` enum containing package/capability-surviving fact types plus code-owned no-fact reasons;
   - `value_bindings` variants containing exact field constants and exact permitted opaque source-value refs.

The model did **not** create:

- canonical `fact_id`;
- final package/fact/validation ArtifactRecord metadata;
- storage, visibility, retention, lifecycle, or access policy;
- final downstream-use permissions;
- final normalized canonical shell;
- validation error codes;
- provider-execution receipt;
- deterministic reason for the final canonical disposition.

Those are application-owned.

Because exact source literals and refs are private, the complete messages, schema, package, and historical response are only in the ignored private pack. Public evidence records only hashes, type names, counts, and byte sizes.

### 5.3 Exact traced contexts

| Context | Package types | Actual schema fact types | Binding fields | Decisions | Exact model-visible bytes | Post-hoc repository token estimate | Result |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Trace A | `document_summary_evidence`, `unknown_source_row` | Same two | `identifier`, `label`; 3 exact refs each | 1 | 27,744 | 7,000 | Passed; 1 document-summary fact |
| Trace B | `unknown_source_row` | `unknown_source_row` | `amount`, `converted_amount`, `identifier`, `label`, `quantity`, `rate`; exact bounded refs | 4 | 39,160 | 9,854 | Failed; 4 forbidden unknown bindings |

The token estimate uses `compact_request_utf8_bytes_div_4_plus_64_v1` after the fact. Historical provider usage did not record a tokenizer count for the complete Gate 2 request, so it would be misleading to label this an exact provider-token count.

### 5.4 Thirty-five-request matrix

| Package-level types | Actual schema types | Requests | Explanation |
| --- | --- | ---: | --- |
| `unknown_source_row` | `unknown_source_row` | 6 | Global fallback |
| `document_summary_evidence + unknown_source_row` | Same two | 9 | Required `label`/`identifier` capability survived |
| `position_snapshot + unknown_source_row` | `unknown_source_row` | 12 | Position required fields absent from exact reproducible projection |
| `fee_commission + unknown_source_row` | `unknown_source_row` | 6 | Fee required fields absent |
| `income + unknown_source_row` | `unknown_source_row` | 2 | Income required fields absent |

Totals:

- 35 exact contexts;
- 18 passed, 17 failed;
- exact model-visible size range: 24,434–46,276 UTF-8 bytes;
- estimator range: 6,173–11,633 tokens;
- 26 requests exposed one fact type;
- 9 requests exposed two fact types;
- zero requests in this saved run exposed trade, tax, fee, income, cash, FX, or position as an actual schema choice.

### 5.5 Historical schema-hash defect

The old `source_fact_selection_schema_hash` called `stable_digest` with a dictionary. `stable_digest` iterated the dictionary’s root keys, so 34 distinct canonical response schemas in this sample shared one legacy owner hash. The exact rebuilt owner hash matches the persisted receipt, but that match proves historical owner behavior—not content equality.

GOAL 18 separately computed canonical sorted compact JSON SHA-256 and found 34 distinct schema hashes. This defect is audit evidence only; no runtime fix is included.

## 6. GOAL 17 Type-First route

### 6.1 Exact proof path

PR #232’s support builder uses:

```text
synthetic benchmark fixture
→ Gate2DeterministicFinancialScopeFromGate1V2Factory
→ Financial Evidence source package and bundle
→ Candidate Compiler
→ existing V6 Packet
→ additive create_type_first_candidate
→ additive Choice response profile
→ additive Context Linter seal
→ existing request builder / OpenAI adapter preparation
→ one simulated terminal envelope
→ additive parser and Expansion
→ existing canonical validator/materializer
→ Financial Domain persistence
→ additive evidence/replay/comparator
```

The concrete construction is in `scripts/build_type_first_zero_call_e2e_evidence.py:565-750`. The three fixture identities are synthetic benchmark cases. The builder does not load a saved semantic visual envelope or the historical `broker_reports_source_fact_package_v0` used by Trace A/B.

### 6.2 Exact model-visible contract

The exact simulated contexts have:

- root fields: `task`, `source`, `type_cards`;
- exactly two cards:
  - local `type_1`: Cash balance snapshot;
  - local `type_2`: Printed financial metric;
- each card has title, definition, positive signal, negative signal, nearest competitor;
- response schema: exactly `{plausible_types: [...]}`;
- enum: `type_1`, `type_2`;
- no canonical type IDs, choices, bindings, reasons, refs, or materialization fields in the response.

The Trace C logical request is 2,113 UTF-8 bytes and 685 estimator tokens. The response is simulated and explicitly marked `SIMULATED_NOT_PROVIDER_EVIDENCE`.

### 6.3 What is new and what overlaps

New, worth preserving:

- versioned semantic definitions rather than enum-only labels;
- local opaque type keys;
- plural plausible set rather than forced singleton;
- explicit empty/multiple/singleton code-owned policy;
- exact unchanged option restoration;
- sealed request and mapping receipt;
- independent oracle comparator;
- explicit false-empty, false-singleton, false-superset, and wrong-singleton counters;
- exact private evidence, safe receipt, and zero-call replay.

Overlapping with the historical source-selection route:

- model-facing type classification;
- dynamically bounded response enum;
- response parser/schema;
- code-owned canonical choice;
- deterministic value/fact restoration;
- canonical materialization;
- validation/evidence persistence;
- provider request-builder and adapter use.

It is inaccurate to call every additive GOAL 17 method a separate domain owner: the implementation intentionally extends existing V6 owner classes. It nevertheless creates a second semantic route beside the source-fact route, with its own Packet candidate, Choice profile, linter/seal, Expansion, evidence branch, and orchestration proof.

### 6.4 Side-by-side comparison

| Criterion | Historical source selection v3 | GOAL 17 Type-First |
| --- | --- | --- |
| Status | Historical/contained; not product-reachable on `main` | Draft, inactive, transport-ineligible |
| Input | Real Gate 2 source/domain package | Synthetic Financial Evidence source package |
| Visual logical table | Yes; proven in Trace A/B | No direct use in GOAL 17 proof |
| Model-visible type authority | Python global/domain allowlists + capability schema | Semantic Pack projection/type cards |
| Actual types inspected | 1 or 2 per request | Exactly 2 local cards |
| Rich definitions | No in exact domain traces | Yes |
| Response | `decision_type + value_bindings` per source ref | Ordered set `plausible_types` |
| Value bindings | Model selects exact bounded refs | Model sees no bindings; Compiler options prebind values |
| Code-owned fields | Canonical shell, IDs, validation, permissions | Canonical mapping, reason, option restoration |
| Reason ownership | Mixed no-fact enum + backend validation | Backend policy |
| Materialization | Deterministic source-fact materializer | Existing Financial Evidence materializer |
| Evidence/replay | ArtifactStore evidence; no equivalent false-singleton comparator | Exact serialized replay and comparator |
| False-singleton visibility | No explicit oracle counter | Explicit; Trace D proves unsafe typed outcome |
| Product integration | Route retained but contained; broad source-fact route remains active | None |

## 7. Exact context-window findings

The old global `FACT_TYPES` list is not a statement of what the model saw. Exact evidence shows:

- the global code universe had nine fact types;
- domain routing first reduced it;
- required-field/capability logic reduced it again;
- the dynamic JSON Schema was the actual authority visible to the model;
- value bindings were exact enum refs, not open strings.

GOAL 17 is substantially smaller in the inspected synthetic success:

| Route | Type choices | Exact bytes | Estimated tokens | Source basis |
| --- | ---: | ---: | ---: | --- |
| Old Trace A | 2 | 27,744 | 7,000 | Real persisted visual table package |
| Old Trace B | 1 | 39,160 | 9,854 | Real persisted visual table package |
| GOAL 17 Trace C | 2 | 2,113 | 685 | Synthetic Financial Evidence package |

This is not an apples-to-apples compression result: GOAL 17’s source is a different precompiled synthetic representation. Trace E could not be produced without a new adapter.

## 8. Dictionary and type exposure findings

### 8.1 Enum is not a Semantic Pack

For the old nine types:

| Old type | Name/enum | Definition | Positive signal | Negative signal | Nearest competitor | Counterexample | Exact traced LLM visibility |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `trade_operation` | Yes | No rich definition | One legacy label-mapping sentence | No | No | No | 0/35 |
| `income` | Yes | No rich definition | Same | No | No | No | 0/35; package-only in 2 |
| `withholding_tax` | Yes | No rich definition | Same | No | No | No | 0/35 |
| `fee_commission` | Yes | No rich definition | Same | No | No | No | 0/35; package-only in 6 |
| `cash_movement` | Yes | No rich definition | Same | No | No | No | 0/35 |
| `currency_fx` | Yes | No rich definition | Same | No | No | No | 0/35 |
| `position_snapshot` | Yes | No rich definition | Same | No | No | No | 0/35; package-only in 12 |
| `document_summary_evidence` | Yes | No rich definition | Same | No | No | No | 9/35 |
| `unknown_source_row` | Yes | Fallback behavior | Four literal unknown labels | N/A | N/A | No | 35/35 |

The current source Prompt contract contains one conservative mapping paragraph for legacy compatibility. The exact domain prompts used by Trace A/B expose the domain and allowed type names plus generic instructions; they do not expose rich per-type definitions.

GOAL 17’s Pack contains two different semantic types:

| Type | Versioned definition | Positive | Negative | Nearest | Counterexamples/synonyms in Pack |
| --- | --- | --- | --- | --- | --- |
| `cash_balance_snapshot_v1` | Yes | Yes | Yes | Yes | Yes |
| `printed_financial_metric_v1` | Yes | Yes | Yes | Yes | Yes |

These are not automatically equivalent to the old `document_summary_evidence` or `position_snapshot`.

### 8.2 Can an asset-only change expose a new type?

No.

For the old route, a new term requires synchronized changes to at least:

1. `FACT_TYPES` in `gate2_source_fact_contracts.py`;
2. domain allowlists/routing in `gate2_domain_contracts.py` and package builder profiles;
3. `_REQUIRED_ANY_FIELDS_BY_FACT_TYPE`;
4. `_FIELD_BY_HEADER_LABEL` or another deterministic field capability source when the type requires new fields;
5. model-facing schema generation;
6. Prompt registration/metadata for a new domain;
7. deterministic finalizer/materializer/validator branches;
8. tests, generated bundles, and release/parity evidence.

For GOAL 17, Pack changes still require registry/managed-projection/card mapping, Compiler option support, validator/materializer compatibility, tests, and a new immutable authority hash. Neither contour supports “edit one managed dictionary entry and it automatically appears safely.”

## 9. Regex, capability, and filtering

| Mechanism | File/symbol | What it filters | Semantic or mechanical | Can hide a new type | Visible to LLM |
| --- | --- | --- | --- | --- | --- |
| Semantic regex shortlist | None found in old type exposure | N/A | N/A | No mechanism | No |
| Synonym map for type exposure | None found | N/A | N/A | No mechanism | No |
| Header-label map | `gate2_source_fact_selection.py:_FIELD_BY_HEADER_LABEL` | Exact normalized headers → reproducible fields | Mechanical/lexical | Yes, indirectly | Only result |
| Required-field map | `_REQUIRED_ANY_FIELDS_BY_FACT_TYPE` | Type allowed only if required fields exist | Mechanical capability | Yes | Only surviving enum |
| Domain routing | `Gate2SourceUnitRouterFactory`; domain package builder | Candidate refs → domain package | Semantic proposal plus deterministic allowlist | Yes | Domain/result |
| Package allowlist | `allowed_fact_types` | Global types → domain types | Policy | Yes | Yes, in package/user message |
| Capability filter | `_provider_allowed_fact_types` | Package types ∩ reproducible fields | Mechanical | Yes | Only surviving enum |
| Source-shape projection | `_reproducible_value_refs_by_field` | Rows/segments/candidates → exact fields/refs | Mechanical | Yes | Resulting refs |
| Managed Prompt selection | domain Prompt resolver | One domain instruction asset | Policy | Yes by routing | Yes |
| Dynamic JSON Schema | `source_fact_selection_provider_json_schema` | Types, bindings, decision count | Mechanical final model contract | Yes | Yes |
| Type-specific Prompt | One Prompt per domain | Domain name and compatibility rules | Semantic instruction | Yes | Yes |

Regexes do exist elsewhere for mechanical decimal/date/amount validation and visual admission, but no regex or synonym engine selects old `fact_type` semantics. The hardcoded header map and required-field map are the important hiding mechanisms.

## 10. Human-reviewable traces

### Trace A — successful visual table

Safe chain:

```text
one-table crop hash
→ Gemini 3.5 Flash, exact prompt/schema
→ 16 rows, 3 logical columns
→ validated semantic envelope
→ normalized table projection
→ Gate 2 document-summary package
→ exact 2-type schema
→ historical document_summary_evidence response
→ 1 validated canonical source fact
```

Evidence:

- VLM input/output tokens: 1,428 / 448;
- provider status: completed;
- schema and semantic validators: passed;
- crop bytes: not retained in the available ArtifactStore evidence; immutable crop SHA-256 and geometry are retained;
- exact private values/request/response: private pack only.

### Trace B — old Gate 2 semantic failure

Safe chain:

```text
one-table crop hash
→ Gemini 3.5 Flash, exact prompt/schema
→ 5 rows, 2 logical columns
→ validated semantic envelope
→ normalized table projection
→ Gate 2 unknown-source package
→ exact 1-type schema
→ 4 unknown_source_row decisions with bindings
→ 4 × source_fact_selection_unknown_binding_forbidden
→ no canonical fact
```

The visual table was read successfully. Failure occurred at the old model-facing/source-selection contract: only the unknown type survived, but the schema still allowed mechanical binding variants; the provider supplied those bindings, and deterministic validation correctly rejected them.

### Trace C — GOAL 17 success

`SIMULATED_NOT_PROVIDER_EVIDENCE`

```text
synthetic source summary
→ 2 rich type cards
→ simulated ["type_1"]
→ typed_input
→ exactly 1 matching prebound option
→ materialized Financial Evidence record
→ exact replay
```

No provider submission, response, retry, repair, fallback, or transport invocation occurred.

### Trace D — GOAL 17 false singleton

`SIMULATED_NOT_PROVIDER_EVIDENCE`

```text
oracle ["type_1", "type_2"]
→ simulated ["type_1"]
→ exactly 1 matching prebound option
→ structurally valid typed_input
→ materialized record
→ comparator: false_singleton=1, false_singleton_typed=1, unsafe_typed=1
```

This proves an important limit: exact option restoration prevents value drift, but it cannot make a semantically wrong singleton safe. The comparator is genuinely new and should be preserved.

### Trace E — same source through both routes

Not technically possible without implementation.

The historical visual route produces `broker_reports_source_fact_package_v0` / domain packages with row refs and source-value refs. GOAL 17’s builder consumes a `Gate2FinancialEvidenceSourcePackage` created by `Gate2DeterministicFinancialScopeFromGate1V2Factory` from benchmark fixture shapes, then a Financial Evidence Bundle and Candidate Compilation. No existing audited entrypoint converts the saved semantic visual Gate 2 package into the exact GOAL 17 authority set. Creating that adapter would be the next implementation, not a read-only audit operation.

## 11. Duplication map

| Component | Disposition | Basis |
| --- | --- | --- |
| PDF crop | `REUSE_AS_IS` | Released visual input |
| VLM provider/runtime | `REUSE_AS_IS` | Gemini master; GOAL 17 does not replace it |
| Semantic table contract | `REUSE_AS_IS` | Exact content-only boundary |
| Logical table materialization | `REUSE_AS_IS` | Deterministic and evidenced |
| Table projection | `REUSE_AS_IS` | Existing Gate 2 handoff |
| ArtifactStore envelope | `REUSE_AS_IS` | Existing private immutable authority |
| Gate 2 package | `REUSE_AS_IS` | Existing product package should remain convergence input |
| Source segmentation | `REUSE_AS_IS` | Existing bounded runtime |
| Old enum/dictionary | `REPLACE` | Enum/prompt fragments are not a maintainable Semantic Pack |
| GOAL 17 type cards | `EXTEND` | Preserve projection/card contract; adapt to source-fact domain |
| Old per-request filtering | `REPLACE` | Regressed; hides types mechanically |
| GOAL 17 card projection | `EXTEND` | Useful, but must consume existing package |
| Old response schema/parser | `DUPLICATE` | Same classification boundary as Type-First Choice |
| GOAL 17 Choice/parser | `EXTEND` | Prefer as convergence response contract |
| Old value bindings | `REPLACE` | Model selected refs; GOAL 17 safely prebinds options |
| Exact value restoration | `REUSE_AS_IS` | Existing deterministic materializer plus GOAL 17 exact option check |
| Reason derivation | `EXTEND` | Preserve code-owned GOAL 17 policy |
| Canonical fact materialization | `REUSE_AS_IS` | Do not create a second materializer |
| Evidence/replay | `EXTEND` | Add GOAL 17 comparator/replay to existing evidence |
| Product orchestration | `DUPLICATE` | GOAL 17 proof is a second inactive semantic orchestration |
| Answer-context selection | `REUSE_AS_IS` | Separate downstream answer-model concern |
| Historical `source_fact_selection_v3` | `HISTORICAL_ONLY` | Contained on `main` |

## 12. Reuse map and AnswerContext

`AnswerContextSelectionFactory` is not a financial-LLM input builder.

`gate2_domain_runtime.py:597-654` schedules it only after a terminal completed Gate 2 extraction run has been persisted. `answer_context_selection.py:92-107` rejects non-completed runs. It then:

- groups semantic visual packages by projection;
- makes the semantic visual logical table the one interpretation-bearing representation;
- records Gate 2 facts and retained source evidence only as provenance links;
- for non-visual sources, compacts canonical facts;
- forbids Knowledge/RAG, vectorization, ordinary upload, and document-store writes;
- validates exactly one interpretation-bearing representation per evidence group.

Its consumer contract is `resolve_for_answer`, i.e. a subsequent answer model. It prevents the answer model from seeing crop/rows/facts as competing interpretations, but it does not select input for the Gate 2 financial model and cannot replace GOAL 17’s Packet/Context Linter.

It is applicable after any future converged Gate 2 run without modification, provided the run persists the existing source-fact/projection authorities.

## 13. Architecture options

| Criterion | A — evolve existing source-fact owner to Type-First | B — connect visual package to GOAL 17 V6 route | C — keep old product route; close GOAL 17 | D — retain both |
| --- | --- | --- | --- | --- |
| Owner count | Lowest if old Choice path is replaced | Adds adapter and keeps V6 semantic route | Lowest short-term | Highest |
| Migration risk | Medium; contained route must stay inactive until requalified | Medium-high; new package/domain bridge | Low immediate, high semantic debt | High |
| Reuse production evidence | Highest | Visual evidence reused, source-fact evidence partly bypassed | Highest existing only | Split |
| OpenWebUI impact | Can be zero until activation | New inactive route first; later integration | Zero | Larger |
| Pack updatability | Good if Pack becomes one authority | Good inside V6 only | Poor | Two authorities drift |
| False-singleton risk | Observable via GOAL 17 comparator | Observable | Unobserved | Observable only on one route |
| Value correctness | Prebound options + existing materializer | Prebound options, but adapter must reproduce source refs | Existing binding risks | Two policies |
| Replay | Extend existing evidence | GOAL 17 strong replay | Existing only | Duplicated |
| Rollback | Existing valve/route boundary | New route rollback required | Existing | Complex |
| Context size | Likely reduced; must prove on same source | GOAL 17 small synthetic result, real size unknown | Large old packages | Largest operational surface |
| New adapter | Minimal package→card/option projection | Required visual/source package→V6 authorities | None | Required |
| Technical debt | Lowest after convergence | Moderate | Leaves semantic debt | Highest |

### Preferred: Option A

Use the existing source-fact product boundary as the single orchestration owner, but replace the contained model-selection semantics with the useful Type-First contract:

- existing semantic visual projection and Gate 2 package remain input;
- existing segmentation, ArtifactStore, provider factory, validator, and canonical materializer remain;
- Pack/type cards become the type authority;
- response becomes plural plausible types with local keys;
- values are prebound by deterministic code;
- reasons and exact restoration remain code-owned;
- comparator/replay are retained;
- route remains inactive until same-source and live qualification pass.

This is not “turn `semantic_selection_enabled` back on.” The historical route was contained for good reason and must not be reactivated unchanged.

### Reserve: Option B

Choose B only if an explicit domain decision proves that V6 Financial Semantic classification is materially different from source-fact typing. In that case, add one bounded existing-package adapter, retain one canonical materializer, and prohibit parallel type dictionaries.

### Rejected

- C discards the rich card contract, plural choice, exact replay, and false-singleton comparator—the strongest new work in GOAL 17.
- D has no demonstrated distinct-task justification and institutionalizes two dictionaries, two model choices, and two semantic orchestration paths.

## 14. Recommended convergence

The convergence boundary should be:

```text
existing PDF/crop/VLM/logical table
→ existing Gate 2 package and segmentation
→ one Pack-backed type-card projection
→ plausible type set
→ code-owned reason and exact prebound option restoration
→ existing canonical source-fact validator/materializer
→ existing ArtifactStore and AnswerContext
→ extended exact replay + false-singleton comparator
```

The VLM remains a transcription service. The financial model never receives crop bytes. The answer model continues to receive exactly one interpretation-bearing representation per evidence group.

PR #232 should not be merged as-is. Its useful changes should be retargeted or superseded after the convergence contract is approved; merging first would make a synthetic parallel route part of `main` before its product boundary is chosen.

## 15. Exactly one minimal next implementation GOAL

**GOAL 19 — Inactive same-source converged Type-First adapter proof.**

Create one inactive, offline-only projection inside the existing source-fact owner that consumes an already validated current Gate 2 package—including `semantic_visual_logical_table` packages—and produces GOAL 17-compatible type cards plus deterministically prebound options. Run the same saved source through historical reconstruction and the new inactive projection, prove exact value restoration, plural-choice/false-singleton counters, privacy-safe replay, and no second materializer. Provider calls, product imports, valves, admissions, and runtime activation remain zero.

No other implementation GOAL should start from this audit.

## 16. Open questions

1. Why do all three live Function bundles differ from `main`, and which deployed commit is the intended runtime authority?
2. Is `provider_adapters_stay_inside_openwebui=false` a verifier false positive or a real closed-world boundary regression?
3. Does the program intend `cash_balance_snapshot_v1` / `printed_financial_metric_v1` to replace source-fact types or represent a separate later financial domain?
4. Can the original crop bytes for Trace A/B be recovered from an approved private backup? The available ArtifactStore retains crop hashes/geometry, exact provider response, and exact logical output, but not crop bytes.
5. Should the historical schema-hash defect be corrected in a separate maintenance task even though the route is contained?

## 17. Evidence index

### Public, committed

- This report.
- `BROKER_REPORTS_GATE2_PIPELINE_RECONCILIATION_AUDIT_GOAL18.receipt.safe.json`.
- `BROKER_REPORTS_GATE2_PIPELINE_RECONCILIATION_DECISION_BRIEF.md`.

### Private, ignored

Location:

```text
local/goal18-private/BROKER_REPORTS_GATE2_RECONCILIATION_PRIVATE_EVIDENCE/
```

Contents:

- exact historical ArtifactStore/Prompt window;
- exact 35-context matrix;
- Trace A/B exact VLM contract, response, logical projection, Gate 2 package, model request/schema, historical response, backend result;
- Trace C/D exact simulated GOAL 17 request, response, decision, option/materialization, comparator, and replay;
- four Markdown human-review forms;
- extractor summary.

The pack is ignored by `.gitignore` through `local/`. It contains private customer-derived values and refs and must not be committed or attached to a public PR.

### Audit extractor justification

One stdlib-only local extractor was necessary because exact historical requests are split across immutable ArtifactStore payload files, SQLite metadata, managed Prompt snapshots, and the deployed-era factory code. It:

- opens the remote databases in SQLite URI `mode=ro`;
- invokes no provider;
- performs no runtime write;
- rebuilds requests through the historical factory;
- runs GOAL 17 with its existing transport-forbidden context manager;
- writes only under ignored `local/`;
- is not imported by runtime and is not committed.

### Scope closure

| Counter | Value |
| --- | ---: |
| Provider calls | 0 |
| Runtime changes | 0 |
| Product logic changes | 0 |
| OpenWebUI core changes | 0 |
| Feature-valve changes | 0 |
| Production-admission changes | 0 |
| Semantic Pack changes | 0 |
| Historical evidence rewrites | 0 |
