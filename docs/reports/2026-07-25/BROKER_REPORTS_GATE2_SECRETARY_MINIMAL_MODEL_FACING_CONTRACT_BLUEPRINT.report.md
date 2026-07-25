# Broker Reports — Gate 2 Minimal Model-Facing Contract Blueprint

Дата: 2026-07-25  
Статус: `GOAL_6_MINIMAL_CONTRACT: COMPLETED`

## Решение

Не вводить новый source/domain semantic schema. Минимальный target уже реализован как `broker_reports_gate2_financial_evidence_decision_v1` (`gate2_financial_evidence_decision.py:17-168`).

Новый deterministic source-to-financial package seam при реализации должен получить новую schema version. Но model-facing output остаётся существующим financial decision contract; это сохраняет принятую authority и исключает перевод между двумя наборами dispositions.

## Root и branch shapes

Root всегда:

```json
{
  "decision": {}
}
```

Typed:

```json
{
  "decision": {
    "disposition": "typed_input",
    "input_type_id": "eligible_registry_enum",
    "value_bindings": {
      "required_or_optional_role_id": "package_source_value_ref_or_null_for_optional"
    },
    "reason_code": "typed_supported"
  }
}
```

Unclassified:

```json
{
  "decision": {
    "disposition": "unclassified_financial_input",
    "value_bindings": [
      {
        "role_id": "package_allowed_role_enum",
        "source_value_ref": "package_source_value_ref"
      }
    ],
    "reason_code": "ambiguous_registry_type"
  }
}
```

No financial / unsupported:

```json
{
  "decision": {
    "disposition": "no_financial_input",
    "reason_code": "non_financial_content"
  }
}
```

## Структурные гарантии

| Branch | `input_type_id` | bindings | reason |
|---|---|---|---|
| typed | required, eligible Registry enum | object со всеми declared roles; required не null | singleton `typed_supported` |
| unclassified | structurally absent | non-empty list, unique source refs, package compatible | `ambiguous_registry_type` или `no_registry_type` |
| no financial | absent | absent | bounded no-financial enum |
| unsupported | absent | absent | bounded unsupported enum |

Противоречивые состояния не представимы за счёт `anyOf` branch schemas и `additionalProperties:false`. Parser повторно проверяет точный set fields и membership (`gate2_financial_evidence_decision.py:210-372`).

## Enum sources

- disposition/reason: frozen code enums;
- type: `eligible_type_ids` из frozen Registry snapshot и package source family;
- typed role keys: Registry declaration;
- source refs: только candidates текущего package;
- unclassified pairs: декартово множество только разрешённых `role_id/source_value_ref`;
- optional null: только для Registry optional roles.

## Поля, которых нет

Target не содержит:

- schema version echo;
- package/run/document/system IDs;
- source literals;
- normalized values;
- `fact_field_path`;
- candidate/relation graph и cardinality;
- subtype;
- confidence/completeness/uncertainty;
- ownership;
- provenance/evidence objects;
- issue/restriction/audit/downstream metadata;
- free-form JSON.

## Provider projections

Canonical schema остаётся единственной semantic authority.

- OpenAI: удалить только неподдерживаемый `uniqueItems`, сохранить enums/branches; после ответа canonical parse (`:174-184,623-631`).
- Gemini: `const → singleton enum`, удалить `$schema/maxItems/minItems/uniqueItems`; после ответа canonical parse восстанавливает cardinality/uniqueness guarantees (`:186-205,610-620`).
- Anthropic: передать canonical object union через structural projection native messages adapter; после ответа применить тот же canonical parser. Provider projection не может менять dispositions, eligible IDs или refs.

Любая projection обязана сохранять canonical hash, adapted hash и transform ledger. Transport/schema acceptance не заменяет canonical validation.

## Почему гипотеза с `matched|unclassified|no_match|no_financial_data` не принята буквально

Она семантически верна, но создала бы новый vocabulary и conversion layer. Existing four dispositions уже различают:

- безопасно typed;
- финансовое, но unclassified;
- не финансовое;
- unsupported contract/system shape.

`no_match` — reason внутри unclassified, а не отдельный state. Так данные не теряются.

## Validator order

1. strict JSON/root/branch shape;
2. disposition/reason enum;
3. type eligibility;
4. exact Registry role set;
5. package ref membership;
6. role/value-type compatibility;
7. required-role completeness;
8. duplicate ref prohibition;
9. deterministic materialization validation.

## Acceptance

- `MODEL_OUTPUT_FIELDS: MINIMAL`
- `SYSTEM_OWNED_FIELDS: ZERO`
- `PACKAGE_BOUND_REFS: ONLY`
- `REGISTRY_BOUND_IDS: ONLY`
- `CONTRADICTORY_STATES: UNREPRESENTABLE`
- `NEW_SEMANTIC_AUTHORITY: ZERO`
