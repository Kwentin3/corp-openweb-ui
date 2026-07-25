# Broker Reports — Gate 2 Deterministic Completion Blueprint

Дата: 2026-07-25  
Статус: `GOAL_7_DETERMINISTIC_COMPLETION: COMPLETED`

## Целевая функция

```text
(validated financial decision,
 authoritative source package,
 frozen Registry snapshot,
 execution metadata)
    → deterministic financial inputs
    → deterministic source-bound financial context
```

Модель не является authority ни для одного metadata field. Основа уже реализована в `Gate2FinancialEvidenceMaterializerFactory`; successor work должен подключить к нему deterministic scopes, а не писать второй materializer.

## Sources для удалённых model fields

| Удалённое поле/семейство | Deterministic source |
|---|---|
| schema/package/run/artifact IDs | contract/package/artifact factory + stable digest |
| fact/input path | selected Registry declaration и role spec |
| source ownership | scope + validated package-bound ref |
| candidate/relation graph | не сохранять как product authority; при диагностике воспроизводить kernel |
| relation cardinality | selected bindings + Registry rules |
| subtype | Registry input type; если mapping отсутствует — не создавать legacy subtype |
| confidence | observability, не semantic artifact |
| completeness | required roles + package integrity + issue checks |
| uncertainty | bounded disposition/reason; free strings удалить |
| normalized values | authoritative Gate 1 value по `source_value_ref` |
| evidence/provenance | source package lineage/evidence allowlist |
| restrictions/issues | issue ledger + policy validator |
| audit/provider execution | runtime metadata после ответа |
| coverage | selected scope refs минус terminally accounted refs |
| validation refs/status | canonical validator и artifact store |
| context/checksum hashes | canonical serialization |
| compatibility metadata | explicit reader/writer schema versions |

## Materialization algorithm

1. Проверить source package integrity до model call.
2. Создать package-specific canonical decision contract из frozen Registry.
3. После ответа выполнить canonical parse; provider acceptance не учитывать как terminal result.
4. Для `typed_input`:
   - разрешить declaration по `input_type_id`;
   - проверить все required/optional roles;
   - получить authoritative value и lineage для каждого ref;
   - создать canonical input ID и role bindings;
   - вычислить completeness и restrictions кодом.
5. Для `unclassified_financial_input`:
   - сохранить каждый связанный source value без назначения свободного типа;
   - сохранить lineage и bounded reason;
   - fail closed, если value потерян.
6. Для terminal no-financial/unsupported:
   - зафиксировать reason и ownership scope;
   - не создавать fake empty financial input.
7. Построить source-bound financial context единственным factory.
8. Посчитать integrity hashes по canonical serialization.
9. Persist artifact/receipt с model output только как evidence, не metadata authority.

## Legacy compatibility projection

Если downstream временно требует `source_facts_v0`, compatibility projector может построить только те поля, которые имеют однозначный mapping. Он обязан:

- выставить новую projector identity;
- ссылаться на successor financial input;
- не выдавать projection за legacy model exact-selection;
- не выдумывать subtype/confidence;
- сохранять original legacy artifacts отдельно.

Если поле неоднозначно и не нужно current financial context, оно остаётся отсутствующим в successor, а не возвращается модели.

## Неразрешённая недетерминированность

Два типа ambiguity остаются terminal semantics, а не repair:

- несколько Registry types подходят одинаково → `unclassified_financial_input/ambiguous_registry_type`;
- финансовые значения не соответствуют Registry → `unclassified_financial_input/no_registry_type`.

Если role binding неоднозначен, модель может выбрать только при достаточном source context; иначе unclassified. Код не угадывает.

## Запрещённые shortcuts

- heuristic post-hoc repair model decision;
- default type только ради coverage;
- silent drop source value;
- derived literal, которого нет в Gate 1;
- model-authored provenance/audit/completeness;
- legacy field stuffing под старой schema version.

## Acceptance

- `FULL_ARTIFACT_FROM_MINIMAL_DECISION: DETERMINISTIC`
- `MODEL_METADATA_AUTHORITY: ZERO`
- `UNRESOLVED_NONDETERMINISM: EXPLICIT_UNCLASSIFIED`
- `HIDDEN_REPAIR: ZERO`
- `LITERAL_AND_PROVENANCE_AUTHORITY: GATE1_PACKAGE`
