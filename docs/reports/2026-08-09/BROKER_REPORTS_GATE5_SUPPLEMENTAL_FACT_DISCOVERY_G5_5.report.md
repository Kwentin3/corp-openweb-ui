# Broker Reports Gate 5 — Supplemental Fact Discovery (G5.5)

Status: `FINAL`

Goal status: `G5.5_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Ответ на финальный вопрос

Да — для supplemental state, доступного в текущем trusted run context.

> Gate 5 может самостоятельно восстановить доступное supplemental state
> текущего trusted case без памяти LLM и без передачи opaque artifact refs
> caller'ом.

Минимальный найденный seam:

```text
methodology + trusted ArtifactAccessContext
-> Gate5SupplementalFactDiscoveryRuntimeFactory.create
   -> ArtifactResolver.catalog_case
   -> same-run G5.3 artifact refs selected internally
   -> Gate5CombinedRequirementCheckRuntimeFactory.create
-> satisfied / missing with unchanged provenance
```

Caller не передаёт `supplemental_fact_refs` и не хранит `art_...` IDs.

## Repository truth

Новая storage infrastructure не потребовалась.

Существующий `ArtifactResolver.catalog_case(context)` уже получает metadata
артефактов одного authenticated user/case/workspace через текущий
ArtifactStore owner. Payload в catalog не выдаётся.

G5.3 по-прежнему является owner полного чтения: каждый выбранный ref повторно
разрешается через `Gate5SupplementalFactRuntime.get`, где проверяются access,
lifecycle, artifact type и payload contract.

G5.4 остаётся owner решения `Financial Case + Supplemental Fact`.

## Contract input

Новый runtime вызывается так:

```python
runtime.check(
    methodology=methodology,
    context=trusted_artifact_access_context,
)
```

В signature отсутствуют:

- `supplemental_fact_refs`;
- отдельные `user_id` или `case_id`;
- отдельные workspace или `normalization_run_id` authority-параметры.

Полный контракт: [BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_DISCOVERY.v0.md](../../stage2/contracts/BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_DISCOVERY.v0.md).

## Representative proof

Реальный Gate 4 case содержит один `SECURITY_DISPOSAL`, но не содержит роль
`acquisition_cost`.

До сохранения подходящего supplemental fact новый discovery runtime вернул:

```json
{
  "status": "missing",
  "checks": {
    "financial_case": "partial",
    "supplemental_facts": "missing"
  },
  "source": null
}
```

Через неизменённую G5.3 boundary был заранее сохранён:

```json
{
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

Затем созданы новый `ArtifactStoreFactory(config).create()` adapter и новый
G5.5 runtime. Caller передал только methodology и тот же trusted context.

Runtime сам обнаружил ref и вернул:

```json
{
  "status": "satisfied",
  "checks": {
    "financial_case": "partial",
    "supplemental_facts": "found"
  },
  "source": {
    "source_kind": "supplemental_fact",
    "supplemental_fact_ref": "art_<opaque>",
    "value": {
      "kind": "money",
      "amount": "70000.00",
      "currency": "RUB"
    },
    "scope_binding": {
      "scope_kind": "case"
    },
    "provenance": {
      "source_kind": "user_provided_supplemental",
      "provided_by": "authenticated_user",
      "gate4_derived": false,
      "captured_via": "gate5_supplemental_fact_boundary_v0"
    }
  }
}
```

Значение и provenance прошли через существующие G5.3/G5.4 contracts без
преобразования или объединения в untagged value.

## Discovery rule

G5.5 делает только четыре операции:

1. получает case metadata через `ArtifactResolver.catalog_case(context)`;
2. оставляет точный G5.3 supplemental artifact type;
3. оставляет текущий trusted `normalization_run_id`;
4. передаёт найденные refs внутрь неизменённого G5.4 runtime.

Это закрытый adapter, а не generic discovery/filter API.

## Trusted-scope proof

В storage были отдельно сохранены matching facts для:

- другого user в том же case/run;
- другого case того же user/run;
- другого workspace;
- другого `normalization_run_id` того же user/case;
- того же scope/run, но другого `subject_ref`.

При отсутствии eligible current-scope/current-run fact requirement остался
`missing`. Ни одно foreign или mismatched значение не попало в source.

Scope identity получена только из `ArtifactAccessContext`.

## normalization_run_id

Новый runtime с тем же trusted run context успешно восстановил fact. Поэтому
G5.3 run binding не заблокировал representative G5.5 proof.

Отдельно доказано: fact другого run в том же logical case не используется и
оставляет requirement `missing`. Это ожидаемая текущая lifecycle boundary, а
не скрытый fallback.

Cross-run discovery/rebinding/migration не реализованы. Если будущий сценарий
потребует открыть case с новым run identity и использовать старое supplemental
state, это будет отдельный конкретный lifecycle gap.

## Gate 4 immutability

Financial Case прочитан до supplemental persistence и после discovery check.
Структуры равны; роль `acquisition_cost` в Gate 4 не появилась.

G5.5 module:

- не изменяет Gate 4 или G5.4;
- не читает broker reports, CanonicalArtifact, Gate 3 или SQL;
- не читает ArtifactStore payload напрямую;
- не создаёт Supplemental Fact;
- не создаёт persistence state.

## KISS-проверка

Для G5.5 добавлены:

- один read-only factory-backed adapter;
- один закрытый контракт;
- три focused behavior/anti-drift теста;
- authority routing, CI inclusion и этот отчёт.

Не добавлены `SupplementalFactRegistry`, `TaxCaseRepository`,
`FactDiscoveryEngine`, `GenericFactQuery`, `UnifiedFactStore`, новая БД,
таблица, индекс, workflow, relation layer, Tax Case, LLM или semantic matching.

## Evidence

Основные артефакты:

- [gate5_supplemental_fact_discovery.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact_discovery.py) — discovery и делегирование;
- [test_broker_reports_gate5_supplemental_fact_discovery.py](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_supplemental_fact_discovery.py) — reopen, missing, scope/run isolation, provenance и Gate 4 immutability;
- [BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md) — единственный G5.5 owner и запрещённые обходы.

Focused proof:

```text
3 passed
```

Расширенный ArtifactStore/lifecycle/generated bundles/architecture/Gate
4/G5.2/G5.3/G5.4/G5.5/privacy набор:

```text
109 passed
```

Authority successor hash обновлён штатным fail-closed механизмом; связанные
managed-generator checks прошли.

## Ограничения и gap boundary

Доказано automatic discovery для exact G5.3 artifact type в одном trusted
case и текущем trusted run.

Не реализованы cross-run reuse, listing API для caller, discovery по смыслу,
conflict resolution, Tax Case, methodology lifecycle или расчёт.

Для representative same-run reopen case infrastructure gap не обнаружен.
Different-run reuse остаётся явно доказанной lifecycle boundary и не маскируется
как найденный факт.

## Stop condition

`G5.5_CLOSED`, результат `PROVEN`, product status `INACTIVE`.

Следующий Gate 5 slice этим отчётом не начинается и не авторизуется.
