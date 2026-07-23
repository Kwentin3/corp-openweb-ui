# Broker Reports — Gate 2: migration и implementation roadmap

Дата: 2026-07-23  
Статус: `GOAL_7_MIGRATION_PLAN: COMPLETED`

## Решение по текущему stage

Рекомендация: выполнить отдельной операционной процедурой атомарный rollback semantic-selection release к доказанным предыдущим Gate 2 Function identities, затем держать semantic selection выключенным до corpus-qualified registry contract.

Этот research PR rollback не выполняет и stage не меняет.

### Основание

| Метрика | До semantic selection | Released semantic selection |
|---|---:|---:|
| accepted packages | 35/41 | 21/41 |
| rejected packages | 6/41 | 20/41 |
| uncovered refs | 7 | 42 |
| strict schema provider outputs | не целевая метрика baseline | 41/41 |
| fallback/repair | — | 0/0 |

Новая форма технически стабильна, но семантически регрессивна. 27 ошибок возникли из-за bindings при `unknown`, ещё 10 — при no-fact.

Released revision:

- source revision: `97c70340501725fc7dd2d0e4f5bc0dc977946989`;
- release ID: `broker-reports-97c703405017`;
- rollback identity SHA-256: `a31fa3da4b6ba946d52f951aac438610b90cd7a167d069b8cdd23dcd9ff8b485`;
- scope: ровно две Gate 2 Functions;
- rollback proof и independent verifier ранее прошли.

Перед реальным rollback оператор обязан read-only проверить, что live identities всё ещё соответствуют этому release и rollback artifact не устарел. Если stage изменился, старый artifact применять вслепую нельзя: сначала нужен новый bounded release plan.

### Оценка вариантов

| Вариант | Риск | Решение |
|---|---|---|
| атомарный rollback | medium: возвращает менее удобный контракт и baseline gaps, но известное лучшее покрытие | `RECOMMENDED` |
| только disable semantic-selection default | medium-high: существующая workload/config override может снова включить регрессивный path | дополнительный предохранитель после rollback |
| быстрый prompt/`if` mitigation | high: не устраняет смешение taxonomy и schema states | отклонён |
| оставить released revision | critical: доказанная потеря покрытия | отклонён |

Rollback не закрывает Gate 2: baseline также имел 6 rejects и 7 uncovered refs. Он только снижает текущий production risk до реализации принятого blueprint.

## Migration boundary

Переход добавляет новую registry-driven линию рядом со старой, затем переключает создание новых artifacts. Он не переписывает:

- persisted `broker_reports_source_facts_v0`;
- legacy domain facts и validation artifacts;
- FNS 2-NDFL artifacts;
- Gate 1 semantic JSON;
- исторические manifests и answer contexts.

Artifact всегда читается по собственным `schema_version`, registry/schema hash и pinned validator revision.

## Независимые implementation slices

### Slice 0 — operational containment

Scope: отдельная ops branch/approval.

- read-only live identity verification;
- atomic rollback двух Gate 2 Functions;
- semantic-selection disabled guard;
- exact verifier, workload quiescence и control run.

Terminal gate: accepted/uncovered не хуже pre-release control.  
Rollback: повторное применение предыдущего candidate запрещено без нового qualification.

### Slice 1 — registry authority и consistency factory

Scope:

- pure declarations schema;
- `Gate2FactRegistryFactory`;
- lifecycle/version/hash;
- consistency validator;
- два самых узких experimental candidates: `cash_balance_snapshot_v1` и `printed_financial_metric_v1`.

Не подключать runtime/provider.

Tests:

- duplicate/role/lifecycle/alias failures;
- deterministic snapshot hash;
- examples/counterexamples present;
- no customer data;
- no imports из runtime/provider/ArtifactStore.

Terminal gate: registry can be built and rejected deterministically in isolation.

### Slice 2 — decision contract factory

Scope:

- canonical four-disposition schema;
- OpenAI projection;
- Gemini projection capability fixture;
- package-bound type/role/source-ref constraints;
- no production switch.

Tests:

- contradictory states rejected structurally;
- root is object;
- OpenAI strict requirements;
- Gemini adapted schema keeps `disposition`, `fact_type` enums and branches;
- schema budget and deterministic hashes.

Terminal gate: provider schemas build and validate synthetic fixtures; no live corpus claim.

### Slice 3 — deterministic materialization и validation profile

Scope:

- materialize v1 decision into existing canonical fact envelope or explicitly versioned successor;
- registry-required roles;
- `unclassified_fact` preservation;
- no-fact/unsupported coverage;
- unchanged Gate 3 forbidden fields.

Tests:

- accepted typed fact has deterministic ID;
- unclassified retains evidence but publishes no fact;
- legacy unknown remains readable;
- no value loss;
- tampered refs/roles fail closed.

Terminal gate: local end-to-end synthetic run, no provider dependency.

### Slice 4 — compatibility adapter

Scope:

- version-aware read mapping for seven financial legacy IDs;
- `document_summary_evidence` to evidence kind;
- `unknown_source_row` to legacy disposition;
- FNS path explicitly left separate;
- no stored artifact rewrite.

Tests:

- replay old fixtures byte-for-byte;
- ambiguous mappings remain `unmapped`;
- alias cycles/improper automatic aliases fail.

Terminal gate: every persisted schema family is either mapped, preserved as legacy, or explicitly unsupported.

### Slice 5 — shadow corpus qualification

Scope:

- authorized actual corpus;
- new decision path shadow-only;
- compare accepted/rejected/unclassified/no-fact/unsupported and uncovered refs;
- registry-gap report;
- OpenAI and Gemini provider-specific evidence where quota permits.

Promotion gates:

- no coverage regression versus rollback baseline;
- zero contradictory schema states;
- zero fallback/repair unless separately approved;
- all unclassified values retained;
- safe receipts only in Git.

Terminal gate: explicit `QUALIFIED` or `NOT_QUALIFIED`; HTTP success is insufficient.

### Slice 6 — projection layer

Scope:

- one profile first: `balance_snapshot_view_v1`;
- registry-driven mapping;
- deterministic projection ID/rule hash;
- replay and lineage;
- no ledger/posting.

Tests:

- projection never changes fact identity;
- incompatible fact types rejected;
- printed and calculated aggregates remain separate.

Terminal gate: one bounded consumer proves value; no speculative profiles.

### Slice 7 — controlled production migration

Scope:

- new schema/version and config flag;
- dual-read, single-write to new path;
- atomic two-Function release only if scope remains exact;
- rollback artifact;
- live control and independent verifier.

Release gate:

- accepted blueprint;
- slices 1–6 terminally passed;
- actual-corpus qualification;
- no Gate 1/provider policy change;
- exact privacy guard;
- rollback verified before candidate remains live.

## Dependency order

```text
containment
    ↓
registry authority
    ↓
decision factory ──→ provider capability
    ↓
materialization
    ↓
compatibility
    ↓
shadow qualification
    ↓
one projection
    ↓
production migration
```

Slice 4 может разрабатываться параллельно slice 2/3 после заморозки registry schema, но production merge должен видеть единый compatibility decision.

## Изменения по существующим поверхностям

| Surface | Migration |
|---|---|
| legacy fact IDs | read-only identities; explicit mapping status |
| persisted artifacts | no rewrite; version-aware readers |
| source facts | envelope reuse только если semantics совместима, иначе successor schema |
| domain facts | router domain отделяется от fact type |
| prompts | descriptions generated from registry snapshot |
| provider schemas | generated projections, canonical/adapted hashes |
| canonical validator | registry profile добавляется после отдельного review; Gate 3 guard сохраняется |
| materializers | model output сокращается до decision/bindings |
| register projections | один bounded profile после fact qualification |
| tests | unit → contract → corpus shadow → live control |
| Gate 3 manifest | dual-read fact identity/version; no tax semantics |
| release | atomic, exact scope, independently verified |

## Stop conditions

Работа останавливается без rollout, если:

- provider projection теряет disposition enum;
- schema complexity вынуждает свободный JSON;
- actual-corpus coverage хуже rollback baseline;
- unclassified evidence теряется;
- новый type не имеет counterexample/evidence;
- compatibility требует переписать persisted artifacts;
- projection требует Gate 3 methodology;
- rollback artifact не соответствует live state.

## Acceptance

`MIGRATION_BOUNDARY: EXPLICIT`  
`LEGACY_ARTIFACTS: PRESERVED`  
`IMPLEMENTATION_SLICES: INDEPENDENT`  
`CURRENT_STAGE_RISK: CRITICAL_UNTIL_CONTAINED`  
`ROLLBACK_OR_MITIGATION: ATOMIC_ROLLBACK_RECOMMENDED`

