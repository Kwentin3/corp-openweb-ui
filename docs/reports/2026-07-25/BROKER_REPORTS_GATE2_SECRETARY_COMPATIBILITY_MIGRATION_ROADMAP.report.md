# Broker Reports — Gate 2 Compatibility And Migration Roadmap

Дата: 2026-07-25  
Статус: `GOAL_9_MIGRATION_BLUEPRINT: COMPLETED`

## Политика перехода

```text
read: legacy + successor
write: legacy сейчас → shadow dual-write evidence → successor single-write после admission
rewrite persisted legacy: никогда
rollback: route future runs back to legacy; persisted artifacts immutable
```

Нельзя менять смысл существующей schema под прежней version. Deterministic scope, successor run/receipt и compatibility projection получают новые explicit versions.

## Независимые implementation slices

### Slice 1 — contract-only deterministic scope

- Новый factory строит financial source scopes напрямую из Gate 1/domain package inputs существующими deterministic rules.
- Никаких provider calls и runtime routing changes.
- Доказательства: schema, integrity, complete ref/value/lineage reproduction, tests.
- Stop: любой ref/literal/provenance gap.

### Slice 2 — successor benchmark/comparator

- Product invariants вместо exact candidate graph.
- Value-free mismatch paths и failure layers обязательны.
- Legacy benchmark остаётся неизменным и запускается как historical evidence.
- Stop: comparator допускает out-of-package refs, duplicate/cross-row или literal loss.

### Slice 3 — synthetic model qualification

- Exact existing financial contract, published GPT-5.4 Nano identity.
- Provider schema probe и bounded synthetic cases.
- Никаких customer data/stage changes.
- Stop: schema/canonical/cost gate failure.

### Slice 4 — bounded actual-corpus shadow

- Read-only authorized non-customer/bounded actual corpus.
- Legacy и successor artifacts сохраняются раздельно.
- Сравниваются product invariants, не serialized shape.
- Stop: coverage, literal, provenance, unclassified или context regression.

### Slice 5 — full-scope shadow

- Полный frozen Gate 2 scope, без Gate 3.
- Successor пока не customer-facing authority.
- Доказать terminal ref ownership и baseline parity.

### Slice 6 — successor single-write admission

- Только после отдельного release approval.
- New runs пишут successor artifacts; readers остаются dual-read.
- Legacy source/domain LLM route остаётся rollback path ограниченное время.

### Slice 7 — legacy call retirement

- После observation window и clean rollback drill.
- Удаление только runtime calls, не persisted readers/artifacts.

## Compatibility table

| Artifact/consumer | Во время миграции |
|---|---|
| legacy source facts | immutable, legacy reader сохраняется |
| domain packages | сохраняются; successor scope ссылается на их source authority либо на новый эквивалент |
| financial evidence inputs | current schema/reader остаётся основной semantic target |
| financial context | current v1 authority сохраняется, если invariants идентичны |
| receipts | отдельные schema IDs; нельзя смешивать revision/corpus/mode |
| full-scope evidence | legacy baseline pinned, successor comparison отдельный |
| future Gate 3 | читает stable context boundary; Gate 3 вне implementation scope |

## Dual-read / single-write

Reader определяет schema version, затем вызывает только соответствующий canonical validator. Он не делает silent upcast. Unified context assembler может принимать оба validated artifact families, но receipt обязан фиксировать source schema и projector identity.

После admission writer создаёт только successor artifact family. Legacy projection допустима только как явно помеченный compatibility view и не должна храниться под legacy model-output schema.

## Rollback

Rollback меняет только routing feature flag для будущих runs:

- successor artifacts не удаляются и не переписываются;
- legacy artifacts не модифицируются;
- Registry/context schemas не откатываются;
- qualification receipts остаются привязаны к exact revision;
- незавершённые successor runs получают terminal blocked/failed status.

## Stop conditions

- silent conversion обнаружен;
- legacy reader перестал воспроизводить исторический artifact;
- source values или provenance различаются;
- unclassified value loss > 0;
- selected refs не имеют terminal ownership;
- context consumer требует new Registry expansion;
- fallback/repair/free JSON появился;
- full-scope baseline хуже.

## Acceptance

- `LEGACY_READ: PRESERVED`
- `SILENT_REWRITE: ZERO`
- `SUCCESSOR_SCHEMA: EXPLICIT`
- `IMPLEMENTATION_SLICES: SEVEN_INDEPENDENT_GATES`
- `ROLLBACK_BOUNDARY: FUTURE_ROUTING_ONLY`
- `PERSISTED_ARTIFACT_MUTATION: ZERO`
