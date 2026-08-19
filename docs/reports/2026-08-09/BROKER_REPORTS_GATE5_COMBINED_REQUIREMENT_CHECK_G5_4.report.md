# Broker Reports Gate 5 — Combined Requirement Check (G5.4)

Status: `FINAL`

Goal status: `G5.4_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Ответ на финальный вопрос

Да.

> Gate 5 может проверять достаточность данных по совокупности Financial Case и
> persistent Supplemental Facts без создания отдельной Tax Case платформы.

Минимальный найденный seam:

```text
closed combined requirement
-> Gate5CombinedRequirementCheckRuntimeFactory.create
   -> Gate5MethodologySelectionRuntimeFactory.create
   -> Gate5SupplementalFactRuntimeFactory.create
-> satisfied / missing with one tagged source
```

G5.4 не создаёт и не сохраняет объединённую копию данных. Он только проверяет
наличие и возвращает provenance-tagged result.

## Representative requirement

Машиночитаемое требование:

```json
{
  "schema_version": "broker_reports_gate5_combined_requirements_v0",
  "requirements": [
    {
      "requirement_id": "acquisition-cost-required",
      "financial_type": "SECURITY_DISPOSAL",
      "value_key": "acquisition_cost",
      "subject_ref": "security-disposal-1"
    }
  ]
}
```

Полный контракт: [BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md](../../stage2/contracts/BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md).

`financial_type + value_key` механически передаются в G5.2. Те же
`requirement_id + subject_ref + value_key` используются для точного сравнения
с уже разрешённым через G5.3 persistent fact.

В runtime нет литералов representative tax scenario.

## Контроль: Financial Case + no Supplemental Fact

Реальный Gate 4 case содержит один `SECURITY_DISPOSAL`, но его роли не содержат
`acquisition_cost`.

При пустом `supplemental_fact_refs` результат:

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

Отсутствие в обоих источниках не превращается в значение.

## Persistent Supplemental Fact

Через неизменённую G5.3 boundary сохранён:

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

После записи создан новый `ArtifactStoreFactory(config).create()` adapter и
новый combined runtime. Использован тот же trusted `ArtifactAccessContext`.

Повторная проверка вернула:

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

Таким образом, persistent Supplemental Fact реально участвует в проверке
достаточности, а не существует отдельно от машинного требования.

## Financial Case provenance

Тем же runtime проверено обычное требование `amount`, которое уже доступно в
Financial Case. Оно возвращено как:

```json
{
  "status": "satisfied",
  "checks": {
    "financial_case": "found",
    "supplemental_facts": "not_needed"
  },
  "source": {
    "source_kind": "financial_case",
    "matches": [
      {
        "fact_id": "g4fact_<exact-id>",
        "role": "amount",
        "value": "60.00"
      }
    ]
  }
}
```

Financial Case и Supplemental Fact используют разные tagged source shapes.
Значения и provenance не сливаются в одну недоказуемую цифру.

## Decision rule

Для каждого требования adapter делает только следующее:

1. вызывает G5.2 с `financial_type` и одной ролью `value_key`;
2. при G5.2 `found` возвращает tagged Financial Case source;
3. иначе ищет среди access-checked G5.3 reads точное совпадение
   `requirement_ref + subject_ref + fact_key`;
4. одно совпадение даёт tagged Supplemental Fact source;
5. отсутствие совпадения оставляет `missing`;
6. несколько совпадений отклоняются как ambiguous без conflict resolution.

Это linear adapter для доказанного примера, не generic join/query framework.

## Trusted scope и normalization run

Opaque supplemental refs передаются отдельно от Tax Methodology. Они не несут
`user_id`, `case_id`, `normalization_run_id` или workspace identity.

Каждый ref разрешается через G5.3 `get` с trusted `ArtifactAccessContext`.
Foreign-user ref возвращает `artifact_access_denied`.

G5.3 binding к `normalization_run_id` не помешал representative proof: новый
store/runtime был открыт с тем же trusted calculation context. Cross-run
rebinding/migration не потребовался и не реализован.

## Gate 4 immutability

Gate 4 Financial Case снят до supplemental write и после combined check.
Структуры равны. Роль `acquisition_cost` в Gate 4 не появилась.

G5.4 module:

- не импортирует `Gate4FinancialCaseRuntimeFactory`;
- не вызывает ArtifactResolver или ArtifactStore напрямую;
- не читает SQL, broker reports, CanonicalArtifact или Gate 3;
- не пишет supplemental facts;
- не создаёт persistence state.

## Fail-closed proof

| Проверка | Результат |
| --- | --- |
| нет supplemental ref | `missing`, `source: null` |
| ref существует, но `subject_ref` другой | не удовлетворяет requirement |
| ref принадлежит другому user scope | `artifact_access_denied` |
| два подходящих persistent facts | explicit ambiguous error |
| methodology содержит caller `user_id` | closed-contract error |
| Gate 4 cache/upstream stale | существующая G5.2/Gate 4 ошибка проходит наружу |

Runtime не решает conflicts и не скрывает access errors как отсутствие.

## KISS-проверка

Для G5.4 добавлены:

- один read-only factory-backed adapter;
- один закрытый requirement/result contract;
- три focused behavior/anti-drift теста;
- authority routing и этот отчёт.

Не добавлены новая БД, таблица, migration, Repository, `TaxCaseRepository`,
`UnifiedFactStore`, `TaxDataGraph`, `TaxInputEngine`, workflow, Tax Model,
generic join/query framework, LLM или relation layer.

## Evidence

Основные артефакты:

- [gate5_combined_requirement_check.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_combined_requirement_check.py) — read-only composition;
- [test_broker_reports_gate5_combined_requirement_check.py](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_combined_requirement_check.py) — missing/satisfied, two provenance paths, bindings, scope, ambiguity и Gate 4 immutability;
- [BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md) — единственный G5.4 owner и запрещённые обходы.

Focused proof:

```text
3 passed
```

Расширенный ArtifactStore/lifecycle/architecture/Gate 4/G5.2/G5.3/G5.4/privacy
набор:

```text
106 passed
```

Authority successor hash обновлён штатным fail-closed механизмом; связанные
managed-generator checks прошли.

## Ограничения и gaps

Доказан один `financial_type + value_key` requirement и явный список opaque
supplemental refs в одном trusted run context.

Не реализованы discovery/listing, cross-run rebinding, lifecycle методологии,
conflict resolution, универсальная объединённая выборка, Tax Case и расчёт.

Для representative G5.4 case конкретный infrastructure gap не обнаружен.

## Stop condition

`G5.4_CLOSED`, результат `PROVEN`, product status `INACTIVE`.

Следующий Gate 5 slice этим отчётом не начинается и не авторизуется.
