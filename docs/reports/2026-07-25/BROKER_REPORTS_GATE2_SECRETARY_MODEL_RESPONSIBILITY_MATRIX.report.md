# Broker Reports — Gate 2 Source/Domain Model Responsibility Matrix

Дата: 2026-07-25  
Статус: `GOAL_2_FIELD_OWNERSHIP: COMPLETED`

## Вывод

В successor path модели нужны только четыре решения:

1. terminal disposition;
2. один допустимый Registry `input_type_id` для typed branch;
3. связь разрешённых `role_id` с package-bound `source_value_ref`;
4. branch-specific bounded `reason_code`.

Остальные текущие поля уже даны Gate 1/package/Registry либо однозначно строятся кодом. Отдельный machine-readable реестр: `BROKER_REPORTS_GATE2_SECRETARY_FIELD_OWNERSHIP.inventory.safe.json`.

## Нормативные классы

| Класс | Нормативный владелец | Может быть в target model output |
|---|---|---|
| `SOURCE_PROVIDED` | Gate 1 / source package | нет |
| `REGISTRY_PROVIDED` | Financial Evidence Registry | нет |
| `CODE_DERIVABLE` | deterministic factories/materializer/validator | нет |
| `MODEL_SEMANTIC_DECISION` | bounded LLM choice | да |
| `OBSERVABILITY_ONLY` | runtime/provider instrumentation | нет |
| `LEGACY_ONLY` | compatibility reader/projection либо удаление | нет |

## Критические поля

| Текущее поле | Класс | Почему не должно возвращаться моделью |
|---|---|---|
| `fact_field_path` | `REGISTRY_PROVIDED` | role spec уже задаёт destination; domain comparator доказал, что path может отличаться при тех же candidate/role |
| `subtype` | `LEGACY_ONLY` | current financial context не требует legacy subtype; при необходимости он выводится из `input_type_id` |
| relation objects / count | `CODE_DERIVABLE` | graph построен kernel; selected roles/refs определяют полезные relations |
| `confidence` | `OBSERVABILITY_ONLY` | не является source fact и не участвует в accepted financial decision |
| `completeness` | `CODE_DERIVABLE` | required roles, source membership и issue restrictions известны validator |
| `uncertainty_codes` | `LEGACY_ONLY` | current domain schema допускает free strings; target использует bounded reason enum |
| ownership graph | `CODE_DERIVABLE` | package scope + source ref + validated bindings дают одного владельца |
| candidate IDs | `LEGACY_ONLY` | технические гипотезы kernel; target связывает semantic role прямо с authoritative ref |
| evidence refs | `SOURCE_PROVIDED` | package allowlist и lineage |
| source-value refs | `MODEL_SEMANTIC_DECISION` только как выбор | сами refs созданы Gate 1/code; модель выбирает только из enum |
| normalized values | `SOURCE_PROVIDED` | literal не создаётся моделью и копируется по binding |
| issue/restriction fields | `CODE_DERIVABLE` | issue ledger и policy |
| IDs/hashes/schema versions | `CODE_DERIVABLE` | contract/package/artifact factories |
| audit/provider metadata | `OBSERVABILITY_ONLY` | runtime знает точные execution facts |

## Что действительно требует семантики

`input_type_id` нельзя всегда вывести из видимой формы значения: одна сумма может быть dividend, fee, tax, cash movement или unclassified. `role_id ↔ source_value_ref` также требует ограниченного смыслового сопоставления, когда несколько совместимых значений находятся в одном scope.

Это единственные доказанные model responsibilities. Даже здесь модель не создаёт ID и refs: она выбирает из package-specific enum. Если required role не имеет явного значения, результат обязан быть `unclassified_financial_input`, а не догадка.

## Source legacy burden

Legacy source schema (`gate2_source_fact_contracts.py:331-538`) просит модель вернуть 14 root fields, 26 fact fields и вложенные технические объекты. Нормативная раскладка:

- identity, status, coverage, IDs, hashes: code;
- literals, lineage, source refs: Gate 1/package;
- paths, restrictions, issue linkage: Registry/policy/code;
- audit: observability;
- fact type и bindings: bounded semantics;
- subtype/candidate decorations: legacy only.

Таким образом, массив `facts` является compatibility representation, а не минимальным model contract.

## Domain candidate-binding burden

Schema `gate2_candidate_binding_runtime.py:70-201` одновременно просит:

```text
candidate_id + semantic_role + fact_field_path + relation_ids
```

Но candidate graph строится в `gate2_candidate_binding.py`, а allowed paths уже приложены к candidate. Три поля описывают один выбор на разных внутренних уровнях. Domain qualification показала path/relation mismatches без forbidden/invented refs; следовательно, exact equality этих полей не является самостоятельной product ability.

## Target responsibility

Рекомендуемый target — существующий `broker_reports_gate2_financial_evidence_decision_v1`:

```json
{
  "decision": {
    "disposition": "typed_input",
    "input_type_id": "package_registry_enum",
    "value_bindings": {
      "registry_role_id": "package_source_value_ref"
    },
    "reason_code": "typed_supported"
  }
}
```

Другие branches имеют отдельные shapes и не могут содержать `input_type_id`, если disposition этого не допускает (`gate2_financial_evidence_decision.py:210-372,452-574`).

## Acceptance

- `EVERY_FIELD: HAS_ONE_OWNER_CLASS`
- `MODEL_SEMANTIC_FIELDS: MINIMALLY_JUSTIFIED`
- `CODE_DERIVABLE_FIELDS_RETURNED_BY_MODEL: ZERO_IN_TARGET_BLUEPRINT`
- `TARGET_SYSTEM_OWNED_FIELDS: ZERO`
