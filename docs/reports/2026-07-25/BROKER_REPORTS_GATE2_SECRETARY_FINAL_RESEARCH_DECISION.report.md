# Broker Reports — Gate 2 Source/Domain Secretary: Final Research Decision

Дата: 2026-07-25  
Статус: `GOAL_11_FINAL_DECISION: COMPLETED_WITH_EXPLICIT_GAPS`

## Рекомендуемая цель

Убрать source/domain LLM как отдельные semantic authorities. Оставить:

```text
Gate 1 evidence
  → deterministic segmentation/router/scopes
  → existing four-disposition Financial Evidence decision
  → deterministic materialization
  → current source-bound financial context
```

Модель возвращает только disposition, eligible Registry `input_type_id`, role-to-source-value bindings и bounded reason. Все graph/relation/path/ownership/completeness/provenance/audit structures принадлежат коду.

## Ответы на финальные вопросы

### 1. Почему source/domain не прошли qualification?

Потому что qualification contracts требовали exact воспроизведения внутренней структуры, а не только product semantics. Source дополнительно просил code-owned schema echo через provider projection, которая сняла `const`. Domain требовал paths, relation cardinality, subtype и diagnostic metadata; три из пяти результатов при этом прошли canonical materialization.

### 2. Чья это проблема?

Основная причина — распределение ответственности и stage architecture. Дополнительные причины:

- contract/schema перегружены;
- provider projection ослабляет некоторые canonical constraints;
- comparator переоценивает serialized exactness;
- benchmark taxonomy частично расходится с production;
- source diagnostics не сохранили mismatch paths.

`MODEL_WRONG` не доказан ни для одного case. Prompt следует перегруженному контракту и потому не является самостоятельным корнем.

### 3. Что убрать из LLM output?

Все system IDs/hashes, literals, normalized structures, provenance/evidence objects, fact paths, candidate/relation graph, subtype, confidence, completeness, uncertainty strings, ownership, coverage, issue/restriction fields, audit и downstream hints.

### 4. Что передать коду?

Scope/package identity, eligible Registry projection, path/relation/ownership construction, completeness, restrictions, issue linkage, provenance, audit, integrity, validation, coverage и compatibility projection.

### 5. Нужен ли source LLM?

Нет. Gate 1 уже даёт neutral authoritative values/refs/provenance; source LLM не добавляет уникальной нужной financial-context способности.

### 6. Нужен ли domain LLM?

Нет. Deterministic router уже ограничивает candidates, а semantic type/role binding выполняет financial-evidence decision. Отдельный domain call дублирует его.

### 7. Минимальный contract?

Существующий `broker_reports_gate2_financial_evidence_decision_v1`: branch-specific четыре dispositions, package-bound refs, Registry-bound IDs/roles, bounded reasons, strict canonical validation.

### 8. Рекомендуемая architecture?

Option D — deterministic preparation плюс один existing financial decision call. Option C — резерв только при доказанном capability gap. A/B отклонены как target.

### 9. Как мигрировать?

Новая explicit deterministic package/run schema; legacy+successor dual-read; shadow evidence; после admission successor single-write; persisted legacy не переписывать; rollback только future routing.

### 10. Самый узкий следующий implementation slice?

Contract-only `DeterministicFinancialScopeFromGate1Factory`:

- переиспользовать существующие segmentation/router/package rules;
- построить exact `FinancialEvidenceDecisionPackage` и authoritative source package без source/domain model call;
- доказать ref/value/lineage/coverage identity deterministic tests;
- не менять production route;
- не делать provider call.

Только после этого — successor invariant comparator. Это два независимых PR, а не один большой refactor.

## Exact ownership table

| Data | Authority |
|---|---|
| literals, labels, source refs, provenance | Gate 1 / authoritative package |
| type definitions, roles, compatibility | Financial Evidence Registry |
| disposition, type selection, role/ref selection, bounded reason | LLM |
| IDs, paths, relations, ownership, completeness, restrictions, issues, audit, hashes, coverage | deterministic code |
| admission | canonical validator |
| customer-facing Gate 2 structure | financial materializer/context factory |

Полный field inventory находится в `BROKER_REPORTS_GATE2_SECRETARY_FIELD_OWNERSHIP.inventory.safe.json`; machine diff — в `BROKER_REPORTS_GATE2_SECRETARY_CURRENT_VS_TARGET_CONTRACT_DIFF.safe.json`.

## Rejected alternatives

- Возобновить `source_fact_selection_v3`: отклонено из-за доказанной coverage regression и positional ownership.
- Продвинуть `candidate_binding_output_v0`: отклонено из-за технического candidate graph и overconstrained comparator.
- Создать новый secretary semantic authority сразу: отклонено как duplicate существующего qualified financial contract.
- Ослабить validator/fixtures: запрещено и не устраняет ownership defect.
- Подобрать другую модель: запрещено программой и не нужно до contract correction.

## Implementation sequence

1. deterministic scope factory;
2. product-invariant comparator с mismatch paths;
3. compatibility readers/projections;
4. Q0/Q1 local proof;
5. exact-model schema/synthetic qualification;
6. bounded actual shadow;
7. full-scope shadow;
8. separate production admission and rollback drill.

## Риски

- current domain package creation слишком сцеплена с runtime persistence;
- candidate source family inference может скрывать heuristic ownership;
- legacy consumers могут неявно зависеть от subtype/confidence;
- financial scope grouping может отличаться от legacy row ownership;
- actual-corpus evidence может выявить Registry coverage gap.

Каждый риск имеет stop boundary: никакого silent fallback, Registry expansion или context regression внутри migration.

## Explicit gaps

1. В четырёх source cases нет value-free mismatch paths, поэтому exact failure ownership остаётся `UNKNOWN`.
2. В domain multiple-hypotheses один expected candidate отличается; реальная product data loss не доказана и не опровергнута.

Эти gaps требуют diagnostic observability в будущем, но не меняют decision: fields, в которых возникло расхождение, не должны быть model-owned target metadata.

## Terminal statuses

- `GOAL_0_EVIDENCE_FREEZE: COMPLETED`
- `GOAL_1_ARCHAEOLOGY: COMPLETED`
- `GOAL_2_FIELD_OWNERSHIP: COMPLETED`
- `GOAL_3_STAGE_NECESSITY: COMPLETED`
- `GOAL_4_BENCHMARK_VALIDITY: COMPLETED_WITH_GAPS`
- `GOAL_5_SECRETARY_TASK: COMPLETED`
- `GOAL_6_MINIMAL_CONTRACT: COMPLETED`
- `GOAL_7_DETERMINISTIC_COMPLETION: COMPLETED`
- `GOAL_8_ARCHITECTURE_OPTIONS: COMPLETED`
- `GOAL_9_MIGRATION_BLUEPRINT: COMPLETED`
- `GOAL_10_QUALIFICATION_PLAN: COMPLETED`
- `GOAL_11_FINAL_DECISION: COMPLETED_WITH_EXPLICIT_GAPS`
- `RESEARCH_PROGRAM: COMPLETED_WITH_EXPLICIT_GAPS`

## Delivery verification

- delivery PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/125`
- required deliverables: 11 reports + 2 safe JSON
- focused tests: `145 passed in 20.20s`
- full suite: `1400 passed, 20 skipped, 5 warnings in 94.31s`
- report encoding: 11/11 UTF-8 BOM
- safe JSON: 2/2 valid, 2/2 without BOM
- logical research commits before delivery proof: 6

## Program boundary proof

- production code changes: 0
- provider calls: 0
- customer corpus calls: 0
- stage/browser/Gate 3 work: 0
- Registry expansion: 0
- validator/fixture weakening: 0
- free JSON/repair/fallback: 0
