# OpenWebUI Broker Reports: аудит контрактов нормализации, контекста и агентной архитектуры

Дата: 2026-07-12
Режим: research / architecture audit only
Контрольный объект: тот же шестистраничный PDF из `case_group_002`, `source_ordinal=12`
Case: `customer_case_group_002_process_false_gate1_20260712145140`
Финальный исследованный document packet: `art_sCKVXr4llYOiuTda1OidYnfhkUBYFF_7`

В отчёте нет исходного текста, значений, имени клиентского файла, ключей или приватных путей. Production runtime, валидаторы, OpenWebUI core и live bundles в рамках аудита не менялись.

## 1. Executive verdict

Текущий пайплайн не требует замены нормализатора или немедленного перехода на «полностью агентную» оркестрацию. Gate 1 делает полезную работу: механически извлекает текст, геометрию, таблицы, стабильные source refs и полный coverage ledger. Главный доказанный источник неэффективности находится дальше — в технической форме normalized payload, доменном fan-out и повторяемой model-facing упаковке.

Рекомендуемая целевая архитектура — **гибрид D+B+E**:

1. ArtifactStore остаётся полным private system of record.
2. Каждый доменный агент получает компактную карту всей папки и право на bounded retrieval, но не всю папку в каждом prompt.
3. Детерминированный recall-first discovery строит multi-domain подсказки и candidate graph; он не имеет права окончательно скрывать evidence.
4. Coverage coordinator, а не router или отдельный агент, отвечает за то, что каждый source unit получил явный terminal state.
5. Специалисты возвращают только candidate-bound решения и доказательство просмотренного scope.
6. Отдельный reconciliation stage связывает cross-domain facts; stitcher остаётся детерминированной authority по coverage и конфликтам.
7. Monolithic pass используется как независимый recall-аудитор на контролируемых объёмах, а не как единственный production extractor.

Это рекомендация по контрактам, а не доказательство лучшей fact accuracy. Человеческого reference set для этого PDF пока нет, поэтому ни одна архитектура не доказана как победитель по recall/precision.

## 2. Метод и доказательная граница

Аудит основан на:

- production-коде Gate 1 / Gate 1.5 / Gate 2 на `a30ec5359fe978589b1e6037e7a0cf3bc43f9468`;
- versioned contracts в `docs/stage2/contracts/`;
- private ArtifactStore только через safe aggregates;
- исходном локальном PDF без вывода содержимого;
- baseline-прогоне 175 calls и повторном прогоне 46 calls;
- безопасном structural profiler текущих domain packages.

Не выполнено:

- новый provider run;
- новый runtime/refactor;
- folder-wide extraction;
- OCR/VLM, Knowledge/RAG/vector, Gate 3, tax/declaration/XLSX;
- экспертная разметка фактов.

Следовательно, размеры и текущий contract flow доказаны для одного PDF. Архитектурная сравнительная оценка является обоснованной проектной гипотезой, которую должен различить следующий эксперимент.

## 3. Текущий поток и карта контрактов

```text
source file
→ process=false private intake
→ PDF text/layout parsers
→ private normalized source payload
→ private normalized source units
→ normalized table projections
→ domain context packet / issue ledger
→ derived units + routing
→ domain extraction package
→ compact LLM context v2 + provider schema
→ provider structured output
→ candidate-binding validation/materialization
→ source-fact validation
→ deterministic stitch/coverage
→ private document extraction packet
```

### 3.1 Boundary inventory

| Boundary | Producer → consumer | Contract/version | Required core | Ownership / guarantee | Failure and retry | Facing |
|---|---|---|---|---|---|---|
| Private intake | OpenWebUI Pipe → Gate 1 | `source_file_ref_v0`; `process=false` policy | file ref, case/user/workspace scope, retention | OpenWebUI file is source; ArtifactStore stores safe ref | fail closed on scope/access; source deletion cascades; replay uses stable scope | source-facing |
| Parser text | `PypdfParserAdapter` → normalizer | `pdf_text_layer_projection_v0` | page inventory, text fragments, checksums, completeness, coverage | parser owns mechanical text/page refs; no semantic facts | parser error/partial is explicit; deterministic reparse | structural |
| Parser layout | `PdfPlumberLayoutAdapter` → normalizer | `pdfplumber_layout_policy_v0` projection | chars, words, lines, bboxes, vectors, table candidates | layout parser owns geometry refs and checksum binding | partial/rejected refs preserved; deterministic config ref | structural |
| Normalized document | `Gate1Normalizer` → source-unit builder | `private_normalized_source_payload_v0` | parser provenance, source index, coverage index, extraction-unit refs | complete mechanical evidence envelope; no domain truth | partial completeness and budgets are explicit; stable checksum/run id | source-facing |
| Normalized unit | layout-unit/source-unit factories → Gate 2 | `private_normalized_source_unit_v0` | unit id/ref, parent, selected/accounted refs, private slice, provenance | unit owns a partition of parent refs, never new evidence | no silent truncation; remainder/deferred refs explicit; idempotent checksums | structural |
| Table projection | table projection factory → Gate 2 | `broker_reports_normalized_table_projection_v0` | rows/cells/header model, source values, geometry, coverage | maps exact cells/rows to original refs; does not assert business semantics | rejection keeps fallback coverage; no fake cells | structural |
| Gate 1.5 context | handoff builder → Gate 2 | `domain_context_packet_v0`; issue ledger v0 | document refs, private artifact refs, readiness, issues | references private evidence; carries uncertainty forward | blocked/partial readiness explicit; packet does not copy raw source | product/control |
| Segmentation | segmenter → router/package builder | `broker_reports_source_unit_segmentation_plan_v0`; `broker_reports_derived_source_unit_v0` | parent refs, child refs, coverage partition, narrowed values | derived unit may narrow, not mint provenance | no remainder loss; bounded deterministic replay | structural/control |
| Routing | router → domain package builder | `broker_reports_source_unit_domain_route_v0`; policy v1 | one entry per selected ref, domain hints, coverage | suggested primary/secondary domains only; not final ownership | unknown/no-fact are explicit; current false-negative risk is semantic omission | semantic task |
| Domain package | package builder → model request builder | `broker_reports_domain_extraction_package_v0` | narrowed unit, candidates, relations, profile, issues, coverage, policies | package fixes allowed scope and candidate universe | feasibility/budget blocker before call; persisted and replayable | mixed control/model |
| LLM context | context builder → provider adapter | `broker_reports_gate2_llm_context_package_v2` | identity, target refs, local structure, domain task, candidates, relations, issues, response contract | model sees readable bounded task card, not full private artifact | hard budgets; no silent truncation | model-facing |
| Provider request | request builder/factory → selected connection | `domain_v0`; provider-specific adapted strict schema | managed prompt, compact context, strict response format, model/profile identity | provider projection may adapt syntax, not canonical semantics | no hidden failover; provider error is terminal for attempt; safe execution metadata | provider-facing |
| Candidate output | model → binding validator | `broker_reports_candidate_binding_output_v0` | exact package/candidate/relation identities; one result per target ref | model selects existing ids/roles only; cannot invent values | invalid structure/identity/role/coverage fails closed; bounded repair keeps same scope | model/evidence-binding |
| Materialized facts | materializer → source-fact validator | `broker_reports_source_facts_v0` | typed/unknown/no-fact envelope, provenance, issue impact, completeness | deterministic materializer adds known constants, never semantic choices | missing original refs, mismatch or invented values rejected | product-facing candidate |
| Stitch/coverage | stitcher → document packet | `broker_reports_source_fact_stitch_result_v0` | ownership map, accepted/rejected refs, conflicts, uncovered refs | stitcher is final unit-level ownership and coverage authority | incomplete/conflicted remains non-expandable; replay duplicates detected | product/control |
| Document packet | E2E runner → operator/Gate 3 boundary | `broker_reports_document_extraction_packet_v0` | artifact refs, metrics, coverage, restrictions, guards | safe manifest of private results; not itself proof of correctness | cannot claim ready while uncovered/conflicts remain | product-facing |

### 3.2 Общая семантика полей

Across contracts, required fields fall into five groups:

- identity/version: schema, run, document, unit, package, prompt, model and hashes;
- evidence: source refs, candidate ids, original-value refs and relation ids;
- task: domain, allowed fact types, required roles and forbidden assumptions;
- state: issues, uncertainty, completeness, coverage buckets and restrictions;
- operations: budgets, provider status, validation status, retries and retention.

Optional fields are legitimate only where source evidence may mechanically be absent: headers, table geometry, optional semantic roles, issue links and provider response identifiers. Required semantic roles are not optional merely because the model did not find them.

### 3.3 Correct boundaries

- ArtifactStore and `process=false` correctly separate private evidence from chat-visible summaries.
- Source refs originate before the LLM and remain system-owned.
- Parser/layout contracts correctly avoid claiming domain meaning.
- Table projection preserves row/cell/value provenance and retains fallback on rejection.
- Candidate binding constrains the model to existing evidence.
- Validators and stitcher correctly fail closed and distinguish accepted, unknown, no-fact, rejected, conflict and uncovered states.
- Provider adapters preserve canonical semantics and expose safe execution identity without failover.

### 3.4 Overloaded, duplicated or incomplete boundaries

1. `broker_reports_domain_extraction_package_v0` is overloaded. It is simultaneously persistence envelope, audit record, source projection, semantic task, candidate graph, provider policy and response contract. Most fields are useful to the system but are model-facing noise.
2. Routing mixes recall hints with orchestration authority. Contract text calls routing advisory, but downstream package creation can still make omission effective. There is no independent proof that every plausible domain was considered.
3. Coverage is duplicated at parser, source-unit, route, package, output and stitch levels without one folder-level coordinator state machine. The duplication is defensible for local invariants, but handoff semantics are implicit.
4. Issue context is mechanically carried forward but was repeated into every package. Relevance filtering improved in v2; the shared issue ref still appeared in all 46 calls.
5. Candidate profile and strict schema encode overlapping role constraints. This is appropriate for pre-call and post-call enforcement, but repeating the full policy in prompt/package/schema is excessive.
6. Unknown is semantically defined in prompt/profile, yet current materialization cannot satisfy the unchanged source-fact provenance requirement when the model returns zero bindings. This is an incomplete evidence-binding handoff, not a reason to weaken the validator.
7. Cross-domain relations exist only within a package candidate relation set. There is no durable event/relation contract spanning accepted facts from different agents.
8. Completion is package-local. No agent output currently declares examined folder scope, unexamined units or requests for more evidence.
9. Retry/idempotency is mostly encoded through stable ids/hashes and persistence behavior, not a single explicit attempt contract with prior-attempt lineage.

### 3.5 Contracts still encoded in prompt text

The managed Prompt remains authoritative for several behaviors not fully represented as first-class fields:

- exactly one terminal result per target ref;
- use of `unknown_source_row` when semantic choice cannot be supported;
- prohibition on copying/inventing values;
- issue-limited completeness;
- compatibility behavior for legacy package shapes;
- repair behavior using the identical narrow package and schema.

`LLM context v2` now exposes most of the task card, but completion scope, evidence-request behavior and cross-agent handoff are not contracts because those stages do not yet exist.

## 4. Размер и токены: transformation chain

### 4.1 Measured values

| Representation | Count | Uncompressed size | Compressed size | Objects / arrays / strings | Notes |
|---|---:|---:|---:|---:|---|
| Source PDF | 1, 6 pages | 176,458 B | not meaningful; PDF already compressed | 24 decoded embedded images | decoded image payloads total 357,324 B; fonts/resources are also embedded |
| Extracted page text | 6 pages | 29,748 UTF-8 B; 21,536 chars | not persisted separately | 12,152 `cl100k_base` proxy tokens | tokenizer is engineering proxy, not Gemini accounting |
| PDF text+layout projection inside normalized document | 1 | 20,782,976 B | included below | 19,512 chars; 3,293 words; 274 lines; 29,638 bboxes | geometry-heavy representation |
| Full normalized source document | 1 | 22,185,599 B | 3,596,513 B gzip | 76,810 / 45,200 / 423,525 | full structural authority |
| Normalized source units | 20 | 2,121,963 B | 457,346 B gzip | 8,056 / 700 / 44,862 | selected private slices, not full parent copies |
| Unique source-unit visible text | 20 | 29,708 UTF-8 B | not separately persisted | 20 unique text values | semantic payload proxy used in ratios |
| Normalized table projections | 14 | 1,771,037 B | 326,718 B gzip | 4,495 / 3,984 / 35,664 | 96 rows, 572 cells, 1,045 source-value refs |
| Current domain packages in final packet | 192 | not all model-facing | persisted in ArtifactStore | 146 mechanically impossible | only 46 reached provider |
| Actual compact contexts for provider calls | 46 | 393,396 UTF-8 B | included below | combined with schema: 3,306 objects, 3,367 arrays, 12,700 strings | reconstructed from persisted package contracts |
| Actual strict schemas for provider calls | 46 | 129,589 UTF-8 B | included below | 46 bytewise-unique dynamic schemas | bounded enums vary by package |
| Actual context + schema | 46 | 522,985 UTF-8 B | 139,584 B gzip, per-item sum | max single call 37,264 B | excludes fixed transport framing/provider tokenization |
| Provider input | 46 | n/a | n/a | 237,725 provider-reported tokens | authoritative token total |

The 24 image objects and 357,324 decoded bytes do not mean the PDF is image-only. All six pages had usable text layer; OCR/VLM was not used.

### 4.2 Ratios

| Ratio | Result | Interpretation |
|---|---:|---|
| Text extraction: `29,748 / 176,458` | 0.169× (16.9%) | PDF bytes are not a valid semantic-size denominator by themselves |
| Unique normalization: `29,708 / 29,748` | 0.999× | normalized unit text is essentially the extracted business-visible text, not an expanded paraphrase |
| Full normalized document: `22,185,599 / 29,748` | 745.8× | almost all growth is explicit structure/provenance, not new business content |
| Structural overhead: `(22,185,599 − 171,017 text-leaf occurrence bytes) / 29,708` | 741.0× | geometry, refs, indexes, checksums and repeated structural projections dominate |
| Packaging amplification: `522,985 / 29,708` | 17.60× | actual current provider payload repeats bounded task/schema around source evidence |
| Provider token amplification: `237,725 / 12,152` | 19.56× | provider count includes prompt/schema/tokenizer effects; denominator is a proxy tokenizer |
| Source-ref repetition across actual calls: `74 / 74` | 1.00× | after refactor no target ref was sent to two successful provider calls in this run |

Baseline context component accounting across 175 calls contained approximately 11.71 million compact-JSON characters, including 5.27M schema characters and 2.94M policy/contract metadata characters. Current 46 actual calls use 522,985 UTF-8 bytes for compact context plus schema. Character and byte totals are not directly identical, but the order-of-magnitude reduction is unambiguous.

### 4.3 Where the bytes live

Inside the 20.78 MB PDF projection:

- char inventory: 7.03 MB;
- bbox inventory: 5.24 MB;
- page inventory: 2.31 MB;
- vector lines: 2.24 MB;
- words: 1.37 MB;
- table candidates: 1.07 MB;
- text fragments: 0.88 MB;
- lines and layout coverage: about 0.52 MB combined.

This is useful structural evidence: exact coordinates, word/line relations, table candidates and checksums make provenance reproducible. It is not LLM-friendly as a direct prompt and must remain behind ArtifactStore retrieval.

### 4.4 Repetition after the first refactor

Across the 46 actual calls:

- 46 local structures were unique;
- six header contexts produced 40 repeated sends; one appeared 35 times;
- one issue ref appeared 46 times;
- four domain-task shapes produced 42 repeated sends;
- all 46 schemas were bytewise unique because package-bound enums differ, while sharing the same structural skeleton;
- target source refs were not repeated across calls.

Therefore the remaining amplification is mainly task/schema/header/issue framing, not duplicate evidence ownership.

### 4.5 Classification of amplification

| Location | Verdict |
|---|---|
| Source parsing | not primary; source is small and text layer usable |
| Normalization | very large physical expansion, mostly useful audit structure |
| Structural representation | primary storage expansion: chars/bboxes/vectors/indexes |
| Context packaging | primary model-facing expansion in baseline; materially improved in v2 |
| Domain fan-out | primary baseline call amplification; currently bounded but architecture-dependent |
| Schema repetition | primary baseline token amplification; reduced but still repeated per call |
| Agent iteration | not yet present, therefore not current cause; future risk for architecture D |
| Provider adaptation | not primary size cause; important compatibility boundary |

## 5. Semantic density and LLM-friendliness

### 5.1 Current v2 task card

The current `broker_reports_gate2_llm_context_package_v2` allows a reviewer to answer:

- fragment: `target_source_refs` plus `local_structure`;
- domain: `domain_task.domain`;
- possible facts: allowed fact types and subtype values;
- candidates: compact candidate ids, kinds, roles, paths and source anchors;
- relationships: candidate relation ids;
- required roles: domain task profile;
- coverage scope: exact target refs and exactly-once policy;
- limiting issues: material issues narrowed to target refs;
- valid result: response contract plus strict schema.

This is materially better than the legacy package. The model no longer needs full parser metadata, retention policy, all artifact refs or raw coverage ledgers.

### 5.2 Residual density problems

- Candidate ids remain opaque; readable visible labels exist only indirectly through kind/path/header context. A safe, short label should be a first-class candidate field.
- Headers repeat heavily and are not referenced by shared immutable map ids.
- Every call repeats the same issue even when it is document-global and unchanged.
- Dynamic schemas remain package-bound and bytewise unique. This is safe but prevents provider-side/prompt-side reuse.
- Unknown packages may have zero candidates, leaving the agent no valid original-value binding despite exact target refs being visible.
- A domain task can request required roles that deterministic discovery cannot supply; feasibility now blocks these, but this is evidence that task selection and candidate discovery contracts are not yet aligned.
- No package provides a folder map, examined-scope ledger or evidence-request mechanism.
- Cross-domain context is intentionally absent from a domain package; cross-domain relations therefore cannot be recovered by the current per-package agent alone.

### 5.3 Safe representative inspection

| Sample | Safe shape | Verdict |
|---|---|---|
| Successful largest | `cash_movement`, table row window, 6 refs, 42 candidates, 12 relations, 1 issue, 32,231 context chars + 4,713 schema chars | semantically rich and validator-accepted; near practical bounded upper end |
| Unknown/provenance failure | `unknown_source_row`, 10 refs, 0 candidates, 0 relations, 1 issue, 9,993 + 3,075 chars | task is understandable, but output contract cannot bind provenance with zero candidates |
| Fee mismatch | `fee_commission`, 1 ref, 9 candidates, 3 relations, 1 issue, 9,301 + 2,897 chars | evidence density is adequate; failure is identity/selection-contract mismatch |
| Missing-role/relationship pre-blocked | `trade_operation`, 40 refs, 0 candidates, 0 relations, 1 issue, 11,265 + 5,148 chars | model call would be mechanically impossible; guard correctly prevents it |
| Summary pre-blocked | `document_summary_evidence`, 2 refs, 0 candidates, 0 relations, 1 issue, 2,801 + 2,491 chars | summary task has no mechanical summary candidate; correct terminal state is blocked/deferred, not invented summary |
| Mixed-domain | no current mixed-domain model package exists; 13 refs were duplicated across sibling domains in baseline, none across the 46 current calls | current design avoids duplicate calls here but cannot itself reconcile multi-domain events |

There is no separate «budget-blocked successful package»: budget or feasibility block is pre-provider by design. The largest observed pre-blocked context was the 40-ref trade package above.

## 6. Five architecture systems compared

Scores are relative design judgments: `++` strong, `+` acceptable, `0` conditional, `−` weak, `−−` high risk. They are not accuracy measurements.

| Criterion | A Monolithic | B Router + specialists | C Full folder per specialist | D Map + agent retrieval | E Hybrid recommendation |
|---|---:|---:|---:|---:|---:|
| Theoretical completeness | + | + | ++ | ++ | ++ |
| False-negative routing risk | + | − | ++ | 0 | + |
| Attention/context quality | − | ++ | −− | ++ | ++ |
| Provenance enforceability | 0 | ++ | + | ++ | ++ |
| Terminal coverage proof | − | ++ | 0 | + | ++ |
| Cross-domain recovery | ++ | − | + | + | ++ |
| Token amplification | + for small doc, −− for folder | + | −− | + | 0/+ |
| Failure isolation | −− | ++ | + | ++ | ++ |
| Repeatability | 0 | ++ | 0 | 0/+ | + |
| Auditability | 0 | ++ | 0 | + | ++ |
| Contract complexity | + | + | + | − | − |
| Operational complexity | + | + | + | −− | − |

### 6.1 Architecture A — monolithic one-pass

**Input:** complete document/folder, global evidence index, one global output schema.
**Task:** find all domains, facts and relationships and account for all refs.
**Output:** facts grouped by domain, relation graph and complete coverage ledger.
**Handoff:** one result to validator/stitcher.
**Failure:** oversized context/output, partial invalid object or forgotten small facts invalidates a broad scope.
**Completion:** only when every source ref has a terminal state and every section of the output validates.

Serious advantages:

- one model sees the whole narrative and can connect trade, fee, cash, FX and tax;
- no central router false negative;
- simple orchestration for a six-page document;
- one independent pass is valuable for recall auditing.

Serious limits:

- a global candidate-bound schema grows with all refs/domains and may repeat the baseline schema failure at larger scale;
- small facts can disappear in attention competition;
- one invalid sub-tree complicates repair and idempotency;
- complete source-ref ownership is a large output obligation;
- full folders can exceed input or output budgets even when the model context window accepts input.

Staged section output can reduce repair blast radius, but then the design becomes hierarchical/map-reduce rather than truly one-pass. Architecture A remains a valid comparator and likely a useful independent auditor for small documents.

### 6.2 Architecture B — central router plus specialists

**Input:** router receives source-unit map; specialists receive selected bounded fragments.
**Task:** router assigns one or more domain hypotheses; specialist binds one domain.
**Output:** per-domain candidate selections plus explicit unknown/no-fact.
**Handoff:** route must include all considered domains, evidence refs, rule signals and reason codes.
**Failure:** `not_relevant`, `uncertain`, `mechanically_impossible` and provider failure must remain distinct.
**Completion:** router covers every unit; every routed domain package reaches terminal state.

Current pipeline is closest to B. It gives compact contexts, deterministic operation and good failure isolation. Its central weakness is false-negative routing. «Suggested route» is insufficient if omitted evidence never reaches a specialist.

Required correction is contractual, not necessarily agentic: routing must be recall-first, multi-label, auditable and non-terminal. Uncertain units must reach unknown review or broad audit; a route cannot silently mean «not examined».

### 6.3 Architecture C — full folder to every domain specialist

**Input:** identical full normalized folder for each domain.
**Task:** independently find all evidence for one domain.
**Output:** domain facts plus full-folder examined-scope ledger.
**Handoff:** result states every document/unit inspected and all possible-domain candidates.
**Failure:** context too large or incomplete scan must produce `partial_scope`, never `complete`.
**Completion:** agent proves full-folder examination, not merely that it found one fact.

The user hypothesis has real merit: it removes a central router as a single evidence gate and exposes cross-document context. It may improve domain recall for moderately sized folders.

But «full access» and «embedding everything» are not equivalent. Repeating the current 22.19 MB normalized source document, much less a client folder, for six specialists would be structurally wasteful and attention-hostile. Even a compact visible-text folder repeated six times duplicates business evidence, schemas and issue context. Independent agents can also disagree without a shared relation/coverage contract.

Architecture C should be tested using a compact folder evidence view, not raw normalized JSON. It is a fair comparator for small folders, but not the production default until maximum context, scan proof and reconciliation are demonstrated.

### 6.4 Architecture D — full access through map and retrieval

**Input:** compact immutable folder map, source-unit summaries, document/section graph and broad candidate hints.
**Task:** one domain agent requests bounded evidence, binds facts, reports uncertainty and may request more.
**Output:** facts, examined refs, skipped/deferred refs, unresolved candidates and optional further evidence requests.
**Handoff:** every request/response is persisted with map version, scope and budget.
**Failure:** wrong retrieval, exploration-budget exhaustion or partial inspection are explicit terminal states.
**Completion:** required exploration policy has been satisfied and all plausible-domain candidates are terminally accounted.

Advantages:

- full logical access without repeating full evidence;
- private evidence remains in ArtifactStore;
- context stays semantically dense;
- iterative uncertainty can be handled explicitly;
- failure is isolated to a domain/request.

Risks:

- the agent can retrieve the wrong fragment or stop early;
- tool iteration increases latency and nondeterminism;
- coverage proof requires a coordinator and deterministic broad hints;
- uncontrolled semantic search would recreate RAG and violate current boundaries.

Therefore retrieval must be ref-addressed and map-constrained: list/get by authorized artifact, document, section, unit and source refs; fixed page sizes; persisted queries; no vector similarity; no open-ended filesystem/network access; maximum requests/bytes/units; immutable response hashes.

### 6.5 Architecture E — stronger variants

The strongest additional variant is not another agent swarm but a **shared evidence graph with dual-pass verification**:

```text
normalized folder map + source-unit graph
→ deterministic broad candidate discovery and domain subscriptions
→ bounded specialist extraction with agent-directed retrieval
→ deterministic validation/stitch
→ cross-domain event reconciliation
→ independent monolithic/challenge recall audit on compact evidence
→ terminal coverage result
```

Useful subordinate variants:

- hierarchical section agents for very large documents;
- map-reduce extraction when sections have strong structural boundaries;
- challenge agent only for uncovered/ambiguous/conflicting regions;
- independent monolithic audit sampled by risk, not on every folder;
- deterministic candidate discovery plus semantic binding, already partly implemented and worth preserving.

An ensemble of identical prompts is not recommended: it multiplies disagreement without creating a better coverage contract.

## 7. Cross-domain event contract

For a business event such as:

```text
trade + commission + cash movement + currency conversion + withholding tax
```

one source row may support several valid facts. Source-ref ownership must therefore be split into two concepts:

- **evidence usage:** non-exclusive; many facts/domains may cite the same ref;
- **coverage disposition:** exactly one terminal accounting record per `(source_ref, analysis_scope)` that lists all accepted uses, unknown/no-fact state, conflicts and unexamined status.

Exclusive row ownership is incorrect for multi-domain events. The current stitcher's single typed-owner conflict rule is safe for avoiding duplication within its package model, but insufficient as a folder-wide business-event model.

Recommended additions:

- `event_candidate_id`: deterministic source-structure group, not a business conclusion;
- `fact_relation_id`: accepted relation between validated fact ids;
- relation kinds such as `same_source_event`, `fee_for_trade`, `cash_settlement_for_trade`, `tax_for_income`, `fx_for_cash_movement`;
- relation provenance: exact shared/source refs and relation decision origin;
- reconciliation statuses: `accepted`, `ambiguous`, `conflicting`, `insufficient_evidence`;
- duplicate key based on fact type, normalized core values and evidence set, while preserving separate facts across documents.

The reconciliation stage may propose links but cannot change accepted source values or validator outcomes. Conflicting interpretations remain represented, not silently merged.

## 8. Coverage and anti-loss contract

Coverage must be architecture-independent and folder-level.

### 8.1 Required state machine

Every `(document_ref, source_unit_ref, source_ref)` starts as `registered` and must finish in exactly one terminal disposition:

- `typed_fact`: one or more validated facts use the ref;
- `unknown`: inspected but domain/fact unresolved with provenance;
- `no_fact`: inspected and mechanically/semantically no fact under stated scope;
- `rejected`: inspected, output failed validation;
- `deferred`: intentionally not inspected yet with reason and next owner;
- `blocked`: mechanically impossible or required evidence absent;
- `provider_failed`: request made but provider did not return usable output;
- `unexamined`: terminal only for a partial run, never compatible with `complete`.

`uncovered` is an aggregate defect, not a satisfactory terminal explanation.

### 8.2 Responsibility by architecture

| Architecture | Completeness owner | Silent-loss path | Required guard |
|---|---|---|---|
| A | monolithic task coordinator | model forgets small fact/ref | exact ref ledger in output + challenge pass |
| B | routing/coverage coordinator | false-negative route | multi-label recall route, unknown review, route recall metric |
| C | each domain agent + folder coordinator | agent claims full scan without evidence | examined-unit ledger and unexamined prohibition |
| D | retrieval coordinator + domain agent | wrong/insufficient retrieval | deterministic broad hints, exploration budget and request ledger |
| E | folder coverage coordinator | disagreement between passes | reconciliation and terminal precedence rules |

### 8.3 Completion claim

A domain agent may return `complete` only with:

- map/folder version and domain scope;
- documents and units examined;
- exact source refs examined;
- units not examined and reason;
- accepted fact refs, unknown/no-fact refs and rejected refs;
- unresolved possible-domain candidates;
- evidence requests issued and exhausted;
- issue links and completeness limits;
- validator state;
- zero unexplained refs in its assigned/claimed scope.

Finding one fact is not completion.

## 9. Conceptual target contracts v1

These are blueprint contracts, not implemented schemas.

### 9.1 `broker_reports_normalized_folder_map_v1`

Required:

- folder/case id, map version/hash and ArtifactStore scope;
- document entries with type/readiness/issues;
- ordered section/unit graph;
- source-ref counts and coverage-registration refs;
- safe readable labels and structural summaries;
- broad deterministic domain hints and candidate counts;
- private detail artifact refs;
- budgets and forbidden access paths.

Guarantee: every eligible private source unit appears exactly once in the map. The map contains navigation metadata, not full raw content.

### 9.2 `broker_reports_agent_evidence_request_v1`

Required:

- agent/task id, domain, map hash;
- requested document/unit/source refs;
- reason: `initial_scan`, `uncertainty`, `cross_domain_link`, `challenge`;
- requested view: rows, cells, text window, headers, candidate graph, issues;
- remaining request/byte/unit budget;
- prior examined refs.

Failure: out-of-scope ref, stale map, budget exceeded or unavailable evidence returns a typed denial, never empty-success.

### 9.3 `broker_reports_agent_task_package_v1`

Required:

- immutable task/scope identity;
- domain and allowed fact types;
- evidence response refs and hashes;
- exact target refs;
- readable local structure;
- candidate graph and required roles;
- material issues;
- prior validated facts only when explicitly allowed;
- coverage obligation and response schema;
- forbidden assumptions and completion criteria.

This replaces the model-facing role of the overloaded domain package. The persisted orchestration envelope may remain broader.

### 9.4 `broker_reports_domain_result_v1`

Required:

- candidate-bound fact selections;
- examined, skipped, unresolved and requested-more refs;
- unknown/no-fact decisions;
- issue links, confidence and completeness;
- task/map/evidence hashes;
- `complete|partial|blocked|failed` with machine-checkable reason;
- no direct invented source values.

### 9.5 `broker_reports_coverage_result_v1`

Required:

- one row per registered source ref;
- evidence uses by fact/domain;
- terminal disposition and responsible stage;
- inspected/unexamined distinction;
- provider/validation/blocker lineage;
- conflicts and duplicate uses;
- folder/domain/document aggregates;
- `complete` only when no `registered`, unexplained `uncovered` or `unexamined` remains.

### 9.6 `broker_reports_cross_agent_reconciliation_v1`

Required:

- validated fact ids only;
- proposed event/relation ids and kinds;
- supporting refs;
- duplicate/conflict groups;
- decisions and unresolved questions;
- no mutation of source facts;
- deterministic accepted/rejected/ambiguous status.

### 9.7 `broker_reports_terminal_document_result_v1`

Required:

- normalized folder map hash;
- all task/result/evidence-request refs;
- accepted fact and relation refs;
- terminal coverage result;
- issues/restrictions;
- provider/validator summaries;
- partial-failure isolation;
- explicit Gate 3 readiness flag derived only from validators and coverage.

## 10. Failure contracts

| Failure | Required behavior |
|---|---|
| Context too large | pre-call `blocked_context_budget`, scope and requested size persisted; deterministic split/retrieval allowed, silent truncation forbidden |
| Required evidence absent | `blocked_evidence_absent` with missing role/ref kind; unknown only when source evidence exists and provenance can be bound |
| Provider rejects schema | provider attempt failed; canonical/adapted schema hashes preserved; no hidden failover |
| Invalid model structure | fail closed; optional repair uses same evidence/task/schema and explicit attempt lineage |
| Relevance uncertain | route/domain state `uncertain`, not `not_relevant`; send to unknown/challenge or request evidence |
| Agents conflict | retain both validated claims, create reconciliation conflict; no last-writer-wins |
| Agent fails midway | examined refs remain recorded; unexamined scope returns to coordinator; task is partial |
| Folder partly examined | terminal document state `partial`; unexamined units visible to operator |
| Retrieval budget exhausted | `partial_exploration_budget_exhausted` plus remaining plausible candidates |
| Retry/replay | stable task/input hashes; exact duplicates idempotent; changed evidence creates new task version |

## 11. Ground truth and fair evaluation

Current token/coverage improvements do not prove fact accuracy. The next experiment needs a human-reviewed reference set for this PDF, and preferably a small multi-document folder.

Reference set must contain:

- known facts by domain and exact source refs;
- all valid evidence uses when one ref supports several facts;
- expected cross-domain relations;
- valid no-fact units;
- genuinely ambiguous/unknown units;
- document-summary evidence;
- route labels: relevant domains, including multi-label rows;
- explicit unresolvable evidence gaps.

### 11.1 Metrics

Primary:

- fact recall/precision;
- provenance accuracy;
- source-ref terminal coverage;
- false-negative routing;
- cross-domain relation recall/precision;
- unknown and no-fact correctness;
- validator acceptance without weakening;
- conflict rate and false merge rate.

Engineering:

- context bytes/tokens, maximum single call, calls, wall time;
- repeatability over at least three runs;
- failure isolation and recoverability;
- number of unexamined/deferred refs;
- audit and implementation complexity.

Cost is recorded but is not the primary decision criterion.

### 11.2 Experimental controls

- same normalized artifacts and map hash;
- same provider/model profile where architecture permits;
- same canonical fact and coverage validators;
- same maximum total evidence bytes and output budget, plus a separately reported unconstrained arm;
- no hidden failover or repair-policy differences;
- blind human adjudication of disagreements;
- raw customer data remains private; reports expose only counts/hashes/codes.

## 12. Recommended smallest experiment

Do not rebuild production orchestration. Add an isolated research harness over immutable ArtifactStore artifacts for the same PDF.

### Arm A — monolithic audit

- compact document map + all visible source-unit text/table views;
- staged global output by domain plus one coverage ledger;
- one model profile;
- validate with unchanged candidate/provenance rules.

### Arm B — current routed specialists

- current v2 packages;
- record route ground-truth recall and terminal coverage;
- no runtime changes.

### Arm C — full compact document per specialist

- every specialist receives the same compact document evidence view, not 22 MB normalized JSON;
- requires examined-unit ledger;
- six core domains only.

### Arm D — map + bounded retrieval

- one compact map for every specialist;
- deterministic get-by-ref tool with at most three retrieval rounds and explicit byte/unit budget;
- broad candidate hints visible from the start;
- every request persisted.

### Shared challenge/reconciliation

- run only on disagreements, uncovered refs and cross-domain event candidates;
- compare whether it adds recall without inventing evidence.

Stop after this single PDF unless the reference set and validators show a meaningful distinction. Advance to one small folder only if at least two leading arms are operationally valid and no arm relies on validator exceptions.

Decision thresholds should be defined before the run. A reasonable initial rule is: no architecture advances if it lowers provenance accuracy or terminal coverage; among remaining options, prefer higher fact/relationship recall, then lower false-negative routing, then lower complexity/token amplification.

## 13. Migration boundary

### Keep unchanged

- `process=false` intake and ArtifactStore access/retention;
- PDF text/layout parsing and current normalized source contracts;
- normalized table projection and fallback coverage;
- source refs, source-value candidates and candidate-binding kernel;
- strict structured output, provider factory and no-failover behavior;
- source-fact validator, issue carry-forward and deterministic stitch principles;
- OpenWebUI core boundary and no Knowledge/RAG/vector path.

### Revise if experiment supports the hybrid

- split persisted orchestration envelope from model-facing task package;
- make router advisory/recall-first and add folder coverage coordinator;
- add folder map and ref-addressed evidence request contracts;
- add examined/unexamined/deferred states;
- permit non-exclusive evidence usage while keeping exact coverage accounting;
- add cross-domain reconciliation contract;
- resolve unknown provenance by providing real evidence candidates or a separately valid provenance-bearing unknown contract, never by invention.

### Deprecate later, not now

- legacy model-facing full `broker_reports_domain_extraction_package_v0` shape;
- implicit completion in prompt-only language;
- package-local coverage as a substitute for folder completeness;
- exclusive typed ownership where one source ref legitimately supports several domains.

### Gate impact

Gate 1 does not require a semantic rewrite. At most it needs a compact folder-map projection built from existing refs and structural summaries. The main change, if proven, is Gate 2 orchestration and handoff contracts. Gate 3 remains out of scope.

## 14. Evidence anchors in the repository

- `services/broker-reports-gate1-proof/broker_reports_gate1/pdf_text_layer.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/pdf_layout.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/pdf_layout_units.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/table_projection.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_unit_segmentation.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_routing.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_packages.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_llm_context.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_candidate_binding.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_candidate_binding_runtime.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_validation.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_stitching.py`
- `services/broker-reports-gate1-proof/scripts/live_gate2_context_composition_profile.py`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_UNIT_ROUTING.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_VALUE_CANDIDATES.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_CANDIDATE_BINDING_OUTPUT.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_STITCHING.v0.md`

## 15. Final statuses

Proven for the controlled PDF and current repository contracts:

- `BROKER_REPORTS_NORMALIZATION_CONTRACT_AUDIT_READY`
- `BROKER_REPORTS_CONTEXT_PACKAGING_AUDIT_READY`
- `BROKER_REPORTS_SIZE_AMPLIFICATION_CHAIN_PROVEN`
- `BROKER_REPORTS_AGENT_ARCHITECTURE_OPTIONS_COMPARED`
- `BROKER_REPORTS_MONOLITHIC_OPTION_ASSESSED`
- `BROKER_REPORTS_ROUTED_AGENT_OPTION_ASSESSED`
- `BROKER_REPORTS_FULL_FOLDER_AGENT_OPTION_ASSESSED`
- `BROKER_REPORTS_AGENT_DIRECTED_CONTEXT_OPTION_ASSESSED`
- `BROKER_REPORTS_CROSS_DOMAIN_CONTRACT_AUDITED`
- `BROKER_REPORTS_COVERAGE_CONTRACT_AUDITED`
- `BROKER_REPORTS_TARGET_ARCHITECTURE_RECOMMENDATION_READY`
- `BROKER_REPORTS_NEXT_EXPERIMENT_PLAN_READY`

Not proven:

- superiority of any architecture by fact recall/precision;
- whole-folder scalability;
- complete coverage of the current PDF;
- readiness for multi-document production processing.

Terminal research verdict:

```text
CURRENT NORMALIZATION: structurally useful, storage-heavy, not suitable as direct LLM context
CURRENT PACKAGING V2: materially improved and bounded, still package-local
TARGET HYPOTHESIS: hybrid map + recall-first hints + bounded specialists + reconciliation + independent audit
NEXT ACTION: controlled four-arm experiment with human ground truth and unchanged validators
```
