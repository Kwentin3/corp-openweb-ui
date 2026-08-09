# Broker Reports Gate 5 — Supplemental Fact Persistence (G5.3)

Status: `FINAL`

Goal status: `G5.3_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Итог

Утверждение G5.3 доказано:

> Gate 5 может иметь минимальное persistent состояние для данных, которых нет
> в Financial Case, не сохраняя их в LLM context, не изменяя Gate 4 и не
> создавая отдельную Tax Case платформу.

Найденный минимальный seam:

```text
closed supplemental input
-> Gate5SupplementalFactRuntimeFactory(...).create()
-> existing ArtifactStore private payload
-> new ArtifactStore/runtime instance
-> ArtifactResolver access-checked read
-> identical structured fact or explicit missing
```

Новая БД, таблица, ACL, case registry, Repository и lifecycle не понадобились.

## Проверяемый сценарий

Representative Financial Case содержит один `SECURITY_DISPOSAL`. В его ролях
нет `acquisition_cost`.

Отдельно через G5.3 boundary передан синтетический structured input:

```json
{
  "schema_version": "broker_reports_gate5_supplemental_fact_input_v0",
  "requirement_ref": "acquisition-cost-required",
  "subject_ref": "security-disposal-1",
  "fact_key": "acquisition_cost",
  "value": {
    "kind": "money",
    "amount": "70000.00",
    "currency": "RUB"
  }
}
```

`requirement_ref` связывает факт с потребностью, `subject_ref` — с объектом,
для которого он предоставлен. User/case/run/workspace identity в input нет.

Полный закрытый контракт: [BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md](../../stage2/contracts/BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md).

## Trusted scope

Boundary принимает существующий `ArtifactAccessContext` и требует:

- authenticated `user_id`;
- `case_id`;
- `normalization_run_id`;
- private access permission;
- существующий optional `workspace_model_id` binding.

Идентичность берётся только из trusted context. Передать или переопределить
scope через supplemental input нельзя: extra scope field делает вход
невалидным до persistence boundary.

Это сохраняет текущую access-модель ArtifactStore и не создаёт параллельный
tenant/ACL механизм.

## Что сохранено

Boundary генерирует opaque `art_...` reference и сохраняет один отдельный
artifact type `broker_reports_gate5_supplemental_fact_v0`.

Payload содержит исходные structured fields, trusted scope binding и
boundary-owned provenance:

```json
{
  "schema_version": "broker_reports_gate5_supplemental_fact_v0",
  "supplemental_fact_ref": "art_<opaque>",
  "requirement_ref": "acquisition-cost-required",
  "subject_ref": "security-disposal-1",
  "fact_key": "acquisition_cost",
  "value": {
    "kind": "money",
    "amount": "70000.00",
    "currency": "RUB"
  },
  "scope_binding": {
    "scope_kind": "case",
    "case_id": "g5-supplemental-case",
    "normalization_run_id": "g5-supplemental-run-1",
    "workspace_model_id": "broker-reports-ndfl"
  },
  "provenance": {
    "source_kind": "user_provided_supplemental",
    "provided_by": "authenticated_user",
    "gate4_derived": false,
    "captured_via": "gate5_supplemental_fact_boundary_v0"
  }
}
```

Значение хранится как `private_case` в существующем
`project_artifact_payload`. Retention и purge остаются у существующего
ArtifactStore lifecycle. Safe metadata не содержит сумму, currency, case или
user identity.

## Persistence proof

Наблюдаемая цепочка теста:

1. Реальный Gate 4 runtime собрал representative case.
2. Test подтвердил отсутствие роли `acquisition_cost`.
3. G5.3 runtime записал supplemental artifact.
4. Stored record оказался private external payload с user/case binding.
5. Создан новый `ArtifactStoreFactory(config).create()` adapter.
6. Создан новый `Gate5SupplementalFactRuntimeFactory(...).create()` runtime.
7. Новый runtime прочитал artifact через `ArtifactResolver`.
8. Прочитанный `fact` структурно равен результату записи, включая value,
   scope и provenance.
9. Gate 4 fact после supplemental write/read структурно равен снимку до
   записи и по-прежнему не содержит `acquisition_cost`.

Следовательно, результат зависит от durable ArtifactStore state, а не от
памяти объекта runtime, LLM context или текста диалога.

## Fail-closed proof

| Проверка | Наблюдаемый результат |
| --- | --- |
| input содержит caller-controlled `case_id` | validation error до записи; supplemental records остаются пустыми |
| тот же ref читается с другим `user_id` | `artifact_access_denied` |
| тот же ref читается с другим `case_id` | `artifact_access_denied` |
| well-formed ref отсутствует | `status: missing`, `fact: null` |
| ref указывает на другой artifact type | contract error, payload не принимается как supplemental fact |
| private permission/context отсутствует | trusted-context/access error |

`missing` не подменяет foreign-scope denial и не создаёт придуманное значение.

## Архитектурная граница

Новый runtime:

- не импортирует и не вызывает Gate 4 runtime;
- не меняет `Gate4FinancialCaseFactV1` или Gate 4 SQL;
- не читает broker reports, CanonicalArtifact или Gate 3 annotations;
- не использует `sqlite3` или `SqliteArtifactStoreAdapter` напрямую;
- не принимает tenant/case identity из DTO;
- не вызывает LLM, chat, Knowledge/RAG или workflow;
- не объединяет supplemental и financial facts в query model.

Factory получает существующий store, созданный через
`ArtifactStoreFactory.create`, и создаёт существующий `ArtifactResolver` для
read/access/lifecycle enforcement.

Authority routing зафиксирован в
[BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).

## KISS-проверка

Для G5.3 добавлены только:

- один разрешённый ArtifactStore artifact type;
- один маленький factory-backed module;
- один закрытый money input и один result envelope;
- три focused теста;
- экспериментальный контракт и этот отчёт.

Не добавлены `TaxCaseRepository`, `SupplementalFactEngine`, `TaxInputRegistry`,
`TaxEvidenceGraph`, `Generic Fact Store`, `Workflow Manager`, новая БД,
таблица, migration, Tax Model, methodology extension или generic query engine.

## Evidence

Основные артефакты:

- [gate5_supplemental_fact.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact.py) — write/read factory boundary;
- [test_broker_reports_gate5_supplemental_fact.py](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_supplemental_fact.py) — reopen, Gate 4 immutability, scope isolation, invalid/no-write и missing proof;
- [artifact_models.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/artifact_models.py) — единственное расширение существующего artifact type catalog.

Focused proof:

```text
3 passed
```

Финальный exact-tree набор ArtifactStore/lifecycle/architecture/Gate 4/G5.2/
G5.3/generated bundles/privacy после детерминированной bundle regeneration:

```text
103 passed
```

Все десять managed-generator `--check` прошли. Source-authority hash изменён
через существующий authorized-successor pin. Generated bundle parity восстановлен
детерминированным builder; runtime logic вручную в bundles не редактировалась.

## Обнаруженные gaps и ограничения

Для representative case существующая инфраструктура оказалась достаточной;
upstream gap не обнаружен.

Доказан один money-shaped supplemental fact в одном trusted case/run scope.
Не доказаны cross-run rebinding, изменение/отзыв факта, несколько значений,
conflict resolution, Tax Case, вопросы пользователю, Tax Methodology lifecycle,
объединённая выборка и расчёт налога.

Эти ограничения не входят в G5.3.

## Stop condition

`G5.3_CLOSED`, результат `PROVEN`, product status `INACTIVE`.

Следующий Gate 5 slice этим отчётом не начинается и не авторизуется.
