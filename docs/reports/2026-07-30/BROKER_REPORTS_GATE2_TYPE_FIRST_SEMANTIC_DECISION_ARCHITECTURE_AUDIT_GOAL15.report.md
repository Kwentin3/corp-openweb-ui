# Broker Reports Gate 2 — Type-First Semantic Decision Architecture Audit

Status: `COMPLETED_OFFLINE_ARCHITECTURE_AUDIT`; recommendation: `SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C`; confidence: `medium`.

Этот отчёт сравнивает три будущих варианта честно и на одной доказательной базе. Он не меняет Prompt, Context, Choice, Pack, runtime или product logic и не является разрешением на реализацию.

Machine-readable evidence: [transparent JSON](./BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.transparent.json) and [safe receipt](./BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.receipt.safe.json).

## 1. Problem statement

Текущий архитектурный вопрос состоит из двух разных решений: (1) какой финансовый тип семантически правдоподобен и (2) какую полную, уже собранную кодом запись можно безопасно принять. Constructible Typed Option не доказывает plausible financial type.

Цель — выбрать простейший профиль, который fail closed, показывает решение модели, отделяет смысл от технической сборки и не создаёт второго Packet/Pack/Choice/adapter/runtime authority.

## 2. Facts established by GOAL 14

- `multiple_compatible`: source показывает Possible cash и Possible total без явных amount-to-description связей; choices пусты; audited set = `[type_1,type_2]`.

- `detail_vs_subtotal`: source различает detail и subtotal; choices пусты; audited set = `[type_2]`.

- `no_registry_type`: source представляет связанную Broker fee detail строку; две записи технически собираемы; audited set = `[]`.

GOAL 14 доказал несовпадение constructibility и plausibility, но не доказал причинность model errors. Поэтому влияние видимых choices остаётся проверяемой гипотезой, а не установленным root cause.

## 3. Variant A

Working ID: `ONE_CALL_CHOICES_AND_PLAUSIBLE_TYPES`.

LLM decides:

- return every plausible visible type key
- select one local complete option only when one plausible type and one uniquely supported record remain

Code decides:

- validate local type and choice keys
- cross-check selected option type against singleton type
- derive canonical reason from type cardinality
- restore, validate and materialize exact code-owned option

Exact proposed Stage 1 logical request (representative `unique_cash` instance):

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "plausible_types": {
        "items": {
          "enum": [
            "type_1",
            "type_2"
          ],
          "type": "string"
        },
        "maxItems": 2,
        "type": "array",
        "uniqueItems": true
      },
      "selected_choice": {
        "enum": [
          null,
          "choice_1",
          "choice_2"
        ]
      }
    },
    "required": [
      "plausible_types",
      "selected_choice"
    ],
    "type": "object"
  },
  "user_context": {
    "complete_options": [
      {
        "choice_key": "choice_1",
        "type_key": "type_2"
      },
      {
        "choice_key": "choice_2",
        "type_key": "type_1"
      }
    ],
    "differentiators": [],
    "plausible_type_cards": [
      {
        "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
        "nearest_competitor": {
          "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
          "type_key": "type_2"
        },
        "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
        "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
        "title": "Cash balance snapshot",
        "type_key": "type_1"
      },
      {
        "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
        "nearest_competitor": {
          "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.",
          "type_key": "type_1"
        },
        "negative_signal": "A total calculated by Gate 2 from child rows.",
        "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
        "title": "Printed financial metric",
        "type_key": "type_2"
      }
    ],
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "-120.5000",
                  "meaning": "amount"
                },
                {
                  "literal": "RUB",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-01",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "Return every plausible type_key from plausible_type_cards that matches the visible source meaning, preserving card order. Judge type plausibility independently of whether complete_options can be constructed. Set selected_choice only when exactly one plausible type remains and the visible source uniquely supports one complete option of that type; otherwise set selected_choice to null."
  }
}
```

Exact Stage 1 response sketch:

```json
{
  "plausible_types": [
    "type_1"
  ],
  "selected_choice": "choice_2"
}
```

Stage 2: not applicable.

Stage 2 отсутствует. `selected_choice` нужен прежде всего для singleton-type/multiple-option состояния; при одной matching option код мог бы выбрать её сам.

Canonical backend transformation:

```json
{
  "contradiction_policy": "technical_failure_without_repair",
  "steps": [
    "validate_ordered_unique_local_type_keys",
    "derive_reason_from_distinct_plausible_type_count",
    "validate_selected_choice_membership_and_singleton_type_match",
    "restore_exact_code_owned_typed_option",
    "run_existing_validation_and_materialization",
    "persist_only_after_terminal_evidence_is_complete"
  ]
}
```

Код может проверить cardinality, membership, exact local key и совпадение типа выбранной записи с singleton plausible type. Observability высокая, а изменение относительно V2.1 ограничивается additive profiles. Главный нерешённый риск: видимые choices всё ещё участвуют в type judgment.

Strengths: one call; observable type set and record selection; can resolve a same-type multiple-option state.

Limitations: constructible choices remain visible during type judgment; type and record decisions remain coupled; larger option sets increase request surface.

## 4. Variant B

Working ID: `ONE_CALL_TYPE_FIRST_FAIL_CLOSED`.

LLM decides:

- return every plausible visible type key only

Code decides:

- derive reason from type cardinality
- filter complete options to the singleton type
- accept only exactly one matching option
- fail closed for zero or multiple matching options

Exact proposed Stage 1 logical request (representative `unique_cash` instance):

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "plausible_types": {
        "items": {
          "enum": [
            "type_1",
            "type_2"
          ],
          "type": "string"
        },
        "maxItems": 2,
        "type": "array",
        "uniqueItems": true
      }
    },
    "required": [
      "plausible_types"
    ],
    "type": "object"
  },
  "user_context": {
    "plausible_type_cards": [
      {
        "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
        "nearest_competitor": {
          "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
          "type_key": "type_2"
        },
        "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
        "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
        "title": "Cash balance snapshot",
        "type_key": "type_1"
      },
      {
        "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
        "nearest_competitor": {
          "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.",
          "type_key": "type_1"
        },
        "negative_signal": "A total calculated by Gate 2 from child rows.",
        "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
        "title": "Printed financial metric",
        "type_key": "type_2"
      }
    ],
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "-120.5000",
                  "meaning": "amount"
                },
                {
                  "literal": "RUB",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-01",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "Return every plausible type_key from plausible_type_cards that matches the visible source meaning, preserving card order. Return all plausible types, not only the best one. Judge type plausibility independently of whether any complete record can be constructed."
  }
}
```

Exact Stage 1 response sketch:

```json
{
  "plausible_types": [
    "type_1"
  ]
}
```

Stage 2: not applicable.

Stage 2 отсутствует. При двух complete options одного типа код намеренно завершает `single_registry_type_no_safe_record`.

Canonical backend transformation:

```json
{
  "same_type_multiple_option_policy": "single_registry_type_no_safe_record",
  "steps": [
    "validate_ordered_unique_local_type_keys",
    "derive_reason_from_distinct_plausible_type_count",
    "filter_complete_options_to_singleton_type",
    "accept_only_when_matching_option_count_equals_one",
    "restore_exact_code_owned_typed_option",
    "run_existing_validation_and_materialization",
    "persist_only_after_terminal_evidence_is_complete"
  ]
}
```

На текущих fixtures B автоматически типизирует четыре случая: `unique_cash`, `unique_printed_total`, `optional_missing`, `forbidden_neighbour`. В остальных случаях он выводит корректный code-owned reason. Безопасная недотипизация возникает только в не представленном governed evidence состоянии с несколькими same-type options. Это разумный MVP-компромисс, но не доказанная долгосрочная полнота.

Strengths: cleanest separation between meaning and construction; one call and smallest governed request; simple replay, accounting and rollback boundary.

Limitations: deliberately under-types singleton-type cases with multiple complete options; false singleton risk remains.

## 5. Variant C

Working ID: `TYPE_FIRST_THEN_RECORD_SELECTION`.

LLM decides:

- Stage 1 returns plausible type keys only
- Stage 2 selects among complete options of one already-fixed type or returns null

Code decides:

- derive Stage 1 route and filter options
- invoke Stage 2 only for two or more same-type options
- bind both stages to one operation and replay ledger
- restore and validate one exact option

Exact proposed Stage 1 logical request (representative `unique_cash` instance):

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "plausible_types": {
        "items": {
          "enum": [
            "type_1",
            "type_2"
          ],
          "type": "string"
        },
        "maxItems": 2,
        "type": "array",
        "uniqueItems": true
      }
    },
    "required": [
      "plausible_types"
    ],
    "type": "object"
  },
  "user_context": {
    "plausible_type_cards": [
      {
        "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
        "nearest_competitor": {
          "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
          "type_key": "type_2"
        },
        "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
        "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
        "title": "Cash balance snapshot",
        "type_key": "type_1"
      },
      {
        "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
        "nearest_competitor": {
          "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.",
          "type_key": "type_1"
        },
        "negative_signal": "A total calculated by Gate 2 from child rows.",
        "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
        "title": "Printed financial metric",
        "type_key": "type_2"
      }
    ],
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "-120.5000",
                  "meaning": "amount"
                },
                {
                  "literal": "RUB",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-01",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "Return every plausible type_key from plausible_type_cards that matches the visible source meaning, preserving card order. Return all plausible types, not only the best one. Judge type plausibility independently of whether any complete record can be constructed."
  }
}
```

Exact Stage 1 response sketch:

```json
{
  "plausible_types": [
    "type_1"
  ]
}
```

Exact proposed Stage 2 logical request (documentation-only same-type scenario):

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "selected_choice": {
        "enum": [
          null,
          "choice_1",
          "choice_2"
        ]
      }
    },
    "required": [
      "selected_choice"
    ],
    "type": "object"
  },
  "user_context": {
    "complete_options": [
      {
        "choice_key": "choice_1",
        "type_key": "type_1"
      },
      {
        "choice_key": "choice_2",
        "type_key": "type_1"
      }
    ],
    "differentiators": [
      {
        "choice_key": "choice_1",
        "values": [
          {
            "literal": "2026-03-31",
            "meaning": "as of date"
          },
          {
            "literal": "Cash balance",
            "meaning": "description"
          }
        ]
      },
      {
        "choice_key": "choice_2",
        "values": [
          {
            "literal": "2025-12-31",
            "meaning": "as of date"
          },
          {
            "literal": "Cash balance comparative",
            "meaning": "description"
          }
        ]
      }
    ],
    "selected_type_card": {
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "nearest_competitor": {
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
        "type_key": "type_2"
      },
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "title": "Cash balance snapshot",
      "type_key": "type_1"
    },
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "100.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            },
            {
              "kind": "row",
              "values": [
                {
                  "literal": "90.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2025-12-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance comparative",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "The financial type is fixed by Stage 1. Do not reconsider or return a type. Select one choice_key only when the visible source uniquely supports one complete option of selected_type_card; otherwise return selected_choice as null."
  }
}
```

Exact Stage 2 response sketch:

```json
{
  "selected_choice": "choice_1"
}
```

Stage 2 получает ровно одну уже выбранную type card, только complete options этого типа и минимальные differentiators. Schema не содержит поля типа или reason, поэтому тип нельзя переопределить.

Canonical backend transformation:

```json
{
  "stage2_null_policy": "single_registry_type_no_safe_record",
  "steps": [
    "validate_ordered_unique_local_type_keys",
    "derive_reason_from_distinct_plausible_type_count",
    "filter_complete_options_to_singleton_type",
    "skip_stage2_for_zero_or_one_matching_option",
    "invoke_stage2_only_for_two_or_more_matching_options",
    "validate_stage2_choice_against_fixed_type_option_set",
    "restore_exact_code_owned_typed_option",
    "run_existing_validation_and_materialization",
    "persist_only_after_terminal_evidence_is_complete"
  ],
  "technical_failure_policy": "abort_without_semantic_relabeling"
}
```

На десяти governed fixtures Stage 2 требуется `0/10` раз. Будущий C должен остаться внутри существующего production orchestration owner, связать оба вызова одной operation identity, сохранить оба sealed requests/outputs и учитывать каждый фактический call. Технический Stage 2 failure прерывает операцию до ArtifactStore writes; выполненный call не откатывается. Текущий one-call economy limit потребует versioned behavior change в существующем owner.

Strengths: preserves type-first separation; can recover completeness in same-type multiple-option state; Stage 2 cannot reclassify the financial type.

Limitations: zero Stage 2 triggers in the ten governed fixtures; requires future two-call policy and multi-stage replay profile; adds latency and a record-level model error surface.

## 6. Four-case simulation

Каждый ответ ниже — детерминированная симуляция, которая подставляет frozen audited plausible set. Это не наблюдавшийся ответ новой модели. Полные exact logical request objects находятся в transparent JSON.

### `syn_successor_v2_unique_cash`

Exact source summary:

```json
{
  "children": [
    {
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "literal": "-120.5000",
              "meaning": "amount"
            },
            {
              "literal": "RUB",
              "meaning": "currency"
            },
            {
              "literal": "2026-03-01",
              "meaning": "as of date"
            },
            {
              "literal": "Cash balance",
              "meaning": "description"
            }
          ]
        }
      ],
      "kind": "table"
    }
  ]
}
```

Audited plausible set: `["type_1"]`; Compiler options by type: `{"type_1":1,"type_2":1}`.

| Variant | What LLM sees | Stage 1 JSON | Code decision | Stage 2 | Stage 2 JSON | Final | Calls | Possible failure |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `Variant A` | `task,source_summary,plausible_type_cards,complete_options,differentiators` | `{"plausible_types":["type_1"],"selected_choice":"choice_2"}` | Filter to one complete matching option, restore the exact code-owned Typed Option, validate and materialize. | `false` | `null` | `{"disposition":"typed_input","typed_option":{"choice_key":"choice_2","local_type_key":"type_1","restoration":"exact_code_owned_typed_option"}}` | 1 | Visible constructible choices may anchor or distort the plausible-type cardinality judgment. |
| `Variant B` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_1"]}` | Filter to one complete matching option, restore the exact code-owned Typed Option, validate and materialize. | `false` | `null` | `{"disposition":"typed_input","typed_option":{"choice_key":"choice_2","local_type_key":"type_1","restoration":"exact_code_owned_typed_option"}}` | 1 | A true singleton type with multiple safe options is deliberately under-typed. |
| `Variant C` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_1"]}` | Filter to one complete matching option, restore the exact code-owned Typed Option, validate and materialize. | `false` | `null` | `{"disposition":"typed_input","typed_option":{"choice_key":"choice_2","local_type_key":"type_1","restoration":"exact_code_owned_typed_option"}}` | 1 | A future same-type Stage 2 can choose the wrong record even though it cannot change the financial type. |

### `syn_successor_v2_no_registry_type`

Exact source summary:

```json
{
  "children": [
    {
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "literal": "42.25",
              "meaning": "amount"
            },
            {
              "literal": "CHF",
              "meaning": "currency"
            },
            {
              "literal": "2026-03-04",
              "meaning": "date"
            },
            {
              "literal": "Broker fee detail",
              "meaning": "description"
            }
          ]
        }
      ],
      "kind": "table"
    }
  ]
}
```

Audited plausible set: `[]`; Compiler options by type: `{"type_1":1,"type_2":1}`.

| Variant | What LLM sees | Stage 1 JSON | Code decision | Stage 2 | Stage 2 JSON | Final | Calls | Possible failure |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `Variant A` | `task,source_summary,plausible_type_cards,complete_options,differentiators` | `{"plausible_types":[],"selected_choice":null}` | Derive no_registry_type from distinct plausible count 0. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` | 1 | Visible constructible choices may anchor or distort the plausible-type cardinality judgment. |
| `Variant B` | `task,source_summary,plausible_type_cards` | `{"plausible_types":[]}` | Derive no_registry_type from distinct plausible count 0. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` | 1 | A true singleton type with multiple safe options is deliberately under-typed. |
| `Variant C` | `task,source_summary,plausible_type_cards` | `{"plausible_types":[]}` | Derive no_registry_type from distinct plausible count 0. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` | 1 | A future same-type Stage 2 can choose the wrong record even though it cannot change the financial type. |

### `syn_successor_v2_multiple_compatible`

Exact source summary:

```json
{
  "children": [
    {
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "literal": "310.00",
              "meaning": "amount a"
            },
            {
              "literal": "410.00",
              "meaning": "amount b"
            },
            {
              "literal": "Possible cash",
              "meaning": "description"
            },
            {
              "literal": "EUR",
              "meaning": "currency"
            },
            {
              "literal": "2026-03-03",
              "meaning": "as of date"
            },
            {
              "literal": "Possible total",
              "meaning": "description 2"
            }
          ]
        }
      ],
      "kind": "table"
    }
  ]
}
```

Audited plausible set: `["type_1","type_2"]`; Compiler options by type: `{"type_1":0,"type_2":0}`.

| Variant | What LLM sees | Stage 1 JSON | Code decision | Stage 2 | Stage 2 JSON | Final | Calls | Possible failure |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `Variant A` | `task,source_summary,plausible_type_cards,complete_options,differentiators` | `{"plausible_types":["type_1","type_2"],"selected_choice":null}` | Derive ambiguous_registry_type from distinct plausible count 2+. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` | 1 | Visible constructible choices may anchor or distort the plausible-type cardinality judgment. |
| `Variant B` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_1","type_2"]}` | Derive ambiguous_registry_type from distinct plausible count 2+. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` | 1 | A true singleton type with multiple safe options is deliberately under-typed. |
| `Variant C` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_1","type_2"]}` | Derive ambiguous_registry_type from distinct plausible count 2+. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` | 1 | A future same-type Stage 2 can choose the wrong record even though it cannot change the financial type. |

### `syn_successor_v2_detail_vs_subtotal`

Exact source summary:

```json
{
  "children": [
    {
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "literal": "USD",
              "meaning": "currency"
            },
            {
              "literal": "2026-03-06",
              "meaning": "date"
            },
            {
              "literal": "25.00",
              "meaning": "detail amount"
            },
            {
              "literal": "Fee detail and subtotal",
              "meaning": "description"
            },
            {
              "literal": "125.00",
              "meaning": "subtotal amount"
            }
          ]
        }
      ],
      "kind": "table"
    }
  ]
}
```

Audited plausible set: `["type_2"]`; Compiler options by type: `{"type_1":0,"type_2":0}`.

| Variant | What LLM sees | Stage 1 JSON | Code decision | Stage 2 | Stage 2 JSON | Final | Calls | Possible failure |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `Variant A` | `task,source_summary,plausible_type_cards,complete_options,differentiators` | `{"plausible_types":["type_2"],"selected_choice":null}` | Filter Compiler options to the singleton type; zero remain, so derive single_registry_type_no_safe_record. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | 1 | Visible constructible choices may anchor or distort the plausible-type cardinality judgment. |
| `Variant B` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_2"]}` | Filter Compiler options to the singleton type; zero remain, so derive single_registry_type_no_safe_record. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | 1 | A true singleton type with multiple safe options is deliberately under-typed. |
| `Variant C` | `task,source_summary,plausible_type_cards` | `{"plausible_types":["type_2"]}` | Filter Compiler options to the singleton type; zero remain, so derive single_registry_type_no_safe_record. | `false` | `null` | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | 1 | A future same-type Stage 2 can choose the wrong record even though it cannot change the financial type. |

## 7. Ten-case mechanical simulation

`NEEDS_SEMANTIC_AUDIT = 0`: corrected outcome audit закрепляет plausible set для всех десяти semantic-model fixtures. `repeated_header` и `unsupported_shape` — technical preclose и в эту десятку не входят.

| Case | Semantic state | Plausible/count | Options t1/t2 | A route/calls | B route/calls | C route/calls | Expected final | Completeness loss | Unproved assumption |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `syn_successor_v2_unique_cash` | `typed_safe_1` | `["type_1"]` / 1 | 1/1 | `one_call_joint_type_and_choice` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `{"disposition":"typed_input","reason_code":"typed_supported"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_unique_printed_total` | `typed_safe_1` | `["type_2"]` / 1 | 1/1 | `one_call_joint_type_and_choice` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `{"disposition":"typed_input","reason_code":"typed_supported"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_multiple_compatible` | `ambiguous_type_2plus` | `["type_1","type_2"]` / 2 | 0/0 | `fail_closed_ambiguous_registry_type` / 1 | `fail_closed_ambiguous_registry_type` / 1 | `fail_closed_ambiguous_registry_type` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_no_registry_type` | `no_type_0` | `[]` / 0 | 1/1 | `fail_closed_no_registry_type` / 1 | `fail_closed_no_registry_type` / 1 | `fail_closed_no_registry_type` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_missing_discriminator` | `ambiguous_type_2plus` | `["type_1","type_2"]` / 2 | 1/1 | `fail_closed_ambiguous_registry_type` / 1 | `fail_closed_ambiguous_registry_type` / 1 | `fail_closed_ambiguous_registry_type` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_detail_vs_subtotal` | `single_type_no_safe_record` | `["type_2"]` / 1 | 0/0 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_adjacent_equal` | `single_type_no_safe_record` | `["type_1"]` / 1 | 0/0 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_adjacent_fx` | `single_type_no_safe_record` | `["type_1"]` / 1 | 0/0 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `fail_closed_single_registry_type_no_safe_record` / 1 | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_optional_missing` | `typed_safe_1` | `["type_1"]` / 1 | 1/1 | `one_call_joint_type_and_choice` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `{"disposition":"typed_input","reason_code":"typed_supported"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |
| `syn_successor_v2_forbidden_neighbour` | `typed_safe_1` | `["type_1"]` / 1 | 1/1 | `one_call_joint_type_and_choice` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `type_first_auto_accept_single_matching_option` / 1 | `{"disposition":"typed_input","reason_code":"typed_supported"}` | none in governed fixture | `proposed_stage1_returns_frozen_audited_plausible_set`; A additionally assumes no choice-induced distortion |

B и C механически совпадают на `10/10` случаях; C Stage 2 = `0/10`. Для A также получается corrected expected answer, но симуляция не доказывает, что видимые choices не изменят фактический type judgment.

## 8. Same-type multi-option scenario

В governed ten-case set не найдено состояния «один plausible type, больше одной complete option этого типа». Поэтому ниже только documentation-only thought experiment: не benchmark fixture, не product case и не frequency evidence.

Две complete cash-записи относятся к текущей и сравнительной датам. Stipulated plausible set = `[type_1]`; option counts = `{"type_1":2,"type_2":0}`.

Exact Stage 1 logical request:

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "plausible_types": {
        "items": {
          "enum": [
            "type_1",
            "type_2"
          ],
          "type": "string"
        },
        "maxItems": 2,
        "type": "array",
        "uniqueItems": true
      }
    },
    "required": [
      "plausible_types"
    ],
    "type": "object"
  },
  "user_context": {
    "plausible_type_cards": [
      {
        "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
        "nearest_competitor": {
          "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
          "type_key": "type_2"
        },
        "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
        "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
        "title": "Cash balance snapshot",
        "type_key": "type_1"
      },
      {
        "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
        "nearest_competitor": {
          "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.",
          "type_key": "type_1"
        },
        "negative_signal": "A total calculated by Gate 2 from child rows.",
        "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
        "title": "Printed financial metric",
        "type_key": "type_2"
      }
    ],
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "100.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            },
            {
              "kind": "row",
              "values": [
                {
                  "literal": "90.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2025-12-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance comparative",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "Return every plausible type_key from plausible_type_cards that matches the visible source meaning, preserving card order. Return all plausible types, not only the best one. Judge type plausibility independently of whether any complete record can be constructed."
  }
}
```

B фильтрует две matching options и безопасно завершает `single_registry_type_no_safe_record`. C запускает Stage 2.

Exact C Stage 2 logical request:

```json
{
  "response_schema": {
    "additionalProperties": false,
    "properties": {
      "selected_choice": {
        "enum": [
          null,
          "choice_1",
          "choice_2"
        ]
      }
    },
    "required": [
      "selected_choice"
    ],
    "type": "object"
  },
  "user_context": {
    "complete_options": [
      {
        "choice_key": "choice_1",
        "type_key": "type_1"
      },
      {
        "choice_key": "choice_2",
        "type_key": "type_1"
      }
    ],
    "differentiators": [
      {
        "choice_key": "choice_1",
        "values": [
          {
            "literal": "2026-03-31",
            "meaning": "as of date"
          },
          {
            "literal": "Cash balance",
            "meaning": "description"
          }
        ]
      },
      {
        "choice_key": "choice_2",
        "values": [
          {
            "literal": "2025-12-31",
            "meaning": "as of date"
          },
          {
            "literal": "Cash balance comparative",
            "meaning": "description"
          }
        ]
      }
    ],
    "selected_type_card": {
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "nearest_competitor": {
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.",
        "type_key": "type_2"
      },
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "title": "Cash balance snapshot",
      "type_key": "type_1"
    },
    "source_summary": {
      "children": [
        {
          "children": [
            {
              "kind": "row",
              "values": [
                {
                  "literal": "100.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2026-03-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance",
                  "meaning": "description"
                }
              ]
            },
            {
              "kind": "row",
              "values": [
                {
                  "literal": "90.00",
                  "meaning": "amount"
                },
                {
                  "literal": "USD",
                  "meaning": "currency"
                },
                {
                  "literal": "2025-12-31",
                  "meaning": "as of date"
                },
                {
                  "literal": "Cash balance comparative",
                  "meaning": "description"
                }
              ]
            }
          ],
          "kind": "table"
        }
      ]
    },
    "task": "The financial type is fixed by Stage 1. Do not reconsider or return a type. Select one choice_key only when the visible source uniquely supports one complete option of selected_type_card; otherwise return selected_choice as null."
  }
}
```

Stage 2 response sketches:

```json
{
  "closed_refusal": {
    "selected_choice": null
  },
  "selected": {
    "selected_choice": "choice_1"
  }
}
```

Residual risk: Stage 2 может неверно связать current и comparative row. Код доказывает fixed type и membership, но не семантическую правильность выбранной записи.

## 9. Authority/change-surface matrix

`new owner required = 0` для A, B и C. `additive_profile` означает versioned profile внутри названного owner, а не новую factory или параллельный route.

| Concern | Existing sole owner | A | B | C | New owner |
| --- | --- | --- | --- | --- | ---: |
| Packet construction / semantic instruction | `Gate2FinancialSemanticV6PacketFactory.create + financial_semantic_v6_prompt` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py:107,4765,5065; services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_prompt.py:13,32`) | `additive_profile` | `additive_profile` | `additive_profile` | 0 |
| Semantic Pack/type projection | `Gate2FinancialSemanticV5ProjectionFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v5_projection.py:126,199`) | `unchanged` | `unchanged` | `unchanged` | 0 |
| Candidate Compilation | `Gate2FinancialCandidateCompilerFactory.create` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py:42,130,271`) | `unchanged` | `unchanged` | `unchanged` | 0 |
| Choice contract | `Gate2FinancialSemanticV6ChoiceContractFactory.create` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py:80,249,531`) | `additive_profile` | `additive_profile` | `additive_profile` | 0 |
| Context Linter | `Gate2FinancialSemanticV6ContextLinterFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py:82,362,596`) | `additive_profile` | `additive_profile` | `additive_profile` | 0 |
| request builder | `Gate2OpenWebUIRequestBuilder` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py:210,227,358`) | `additive_profile` | `additive_profile` | `additive_profile` | 0 |
| provider adapters | `Gate2ProviderAdapterFactory.create` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py:39,547,908`) | `unchanged` | `unchanged` | `unchanged` | 0 |
| expansion | `Gate2FinancialSemanticV6DecisionExpansionFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py:54,120,219`) | `behavior_change_later_required` | `behavior_change_later_required` | `behavior_change_later_required` | 0 |
| validation | `Gate2FinancialEvidenceValidatedDecisionFactory.create` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py:89`) | `unchanged` | `unchanged` | `unchanged` | 0 |
| materialization | `Gate2FinancialEvidenceMaterializerFactory.create` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py:145`) | `unchanged` | `unchanged` | `unchanged` | 0 |
| persistence/replay | `Gate2FinancialSemanticV6DecisionEvidenceFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py:115,450,1156`) | `additive_profile` | `additive_profile` | `additive_profile` | 0 |
| operation/economy accounting | `Gate2EconomyBudgetSessionFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_budget.py:44,131,305`) | `additive_profile` | `additive_profile` | `behavior_change_later_required` | 0 |

Для C orchestration остаётся в `Gate2FinancialEvidenceProductionRuntime._decide`; Decision Evidence сохраняет обе стадии и deterministic branch; EconomyBudget считает только реально выполненные calls. Qualification coordinator GOAL 12 не становится product owner.

## 10. Byte/call estimates

Измеряется exact provider-neutral logical object `{response_schema,user_context}` как minified sorted UTF-8 JSON. Estimator `compact_request_utf8_bytes_div_4_plus_64_v1` = `ceil(bytes/4)+64`; это planning estimate, не provider tokenizer и не wire request.

| Case | A bytes/tokens | B bytes/tokens | C1 bytes/tokens | C2 calls |
| --- | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 2444 / 675 | 2111 / 592 | 2111 / 592 | 0 |
| `syn_successor_v2_unique_printed_total` | 2442 / 675 | 2109 / 592 | 2109 / 592 | 0 |
| `syn_successor_v2_multiple_compatible` | 2428 / 671 | 2208 / 616 | 2208 / 616 | 0 |
| `syn_successor_v2_no_registry_type` | 2439 / 674 | 2106 / 591 | 2106 / 591 | 0 |
| `syn_successor_v2_missing_discriminator` | 2383 / 660 | 2050 / 577 | 2050 / 577 | 0 |
| `syn_successor_v2_detail_vs_subtotal` | 2388 / 661 | 2168 / 606 | 2168 / 606 | 0 |
| `syn_successor_v2_adjacent_equal` | 2384 / 660 | 2164 / 605 | 2164 / 605 | 0 |
| `syn_successor_v2_adjacent_fx` | 2428 / 671 | 2208 / 616 | 2208 / 616 | 0 |
| `syn_successor_v2_optional_missing` | 2442 / 675 | 2109 / 592 | 2109 / 592 | 0 |
| `syn_successor_v2_forbidden_neighbour` | 2443 / 675 | 2110 / 592 | 2110 / 592 | 0 |

A total/max: `24221 bytes / 6697 tokens`; max `2444 / 675`.

B and current C total/max: `21343 bytes / 5979 tokens`; max `2208 / 616`.

Governed aggregate calls: A=`10`, B=`10`, C=`10` (Stage 1=`10`, Stage 2=`0`). Architectural worst per operation: A/B=`1`, C=`2`; generic ten-operation ceiling for C=`20`.

Thought experiment C Stage 2: `2073 bytes / 583 estimated tokens`; both stages: `2 calls / 1228 estimated input tokens`.

Pinned economy policy `broker_reports_economy_model_policy_v1` v1.5.0 currently permits exactly one call per financial operation. No current price is claimed as provider truth.

## 11. Comparison matrix

Scores are a transparent 1–5 decision rubric, not measured model quality. Higher is better. Safety, responsibility separation and freedom from choice influence have higher weights than byte/token cost.

| Criterion | Weight | A | B | C |
| --- | ---: | ---: | ---: | ---: |
| Domain safety | 3 | 3 | 4 | 4 |
| typed accuracy potential | 2 | 4 | 3 | 5 |
| under-typing risk | 2 | 4 | 2 | 5 |
| separation of semantic and code responsibilities | 3 | 2 | 5 | 5 |
| influence of constructible choices on type judgment | 3 | 1 | 5 | 5 |
| observability of model decision | 1 | 5 | 4 | 5 |
| deterministic reason derivation | 2 | 4 | 5 | 5 |
| request size | 1 | 3 | 5 | 4 |
| expected token cost | 1 | 4 | 5 | 3 |
| latency | 1 | 5 | 5 | 3 |
| number of provider calls | 1 | 5 | 5 | 3 |
| implementation complexity | 1 | 3 | 5 | 2 |
| test complexity | 1 | 3 | 5 | 2 |
| persistence/replay complexity | 1 | 4 | 5 | 2 |
| provider portability | 1 | 4 | 5 | 4 |
| rollback simplicity | 1 | 4 | 5 | 3 |
| compatibility with current two-type Pack | 1 | 5 | 5 | 5 |
| scaling to larger managed ontology | 2 | 2 | 3 | 3 |
| compatibility with future type shortlisting | 2 | 2 | 5 | 5 |
| usefulness for MVP | 2 | 3 | 5 | 3 |

Weighted totals: A=`101/160` (63.1%); B=`142/160` (88.8%); C=`130/160` (81.2%).

## 12. Recommendation

Recommendation: **`SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C`**.

Confidence: **`medium`**.

B — минимальный вариант, который убирает constructible choices из type judgment, делает plausible set наблюдаемым и выводит reason в коде. Он точно воспроизводит corrected route всех десяти fixtures с одним плановым call.

A отклонён как MVP: он сохраняет нерешённое влияние choices и смешивает type/record decisions, хотя даёт one-call same-type selection. C пока отложен: Stage 2 нужен `0/10` раз и добавляет недоказанную полноту ценой двухвызовной orchestration, policy, replay и failure accounting.

Phased strategy не является четвёртой архитектурой: сначала B; C рассматривается только после accepted-corpus evidence материальной частоты singleton-type/multiple-option state и bounded Stage 2 qualification с безопасным net gain.

Evidence present: frozen audited sets, exact option counts, exact logical request budgets, zero current Stage 2 triggers and existing-owner map. Missing evidence перечислено далее.

## 13. Unresolved questions

1. `type_first_contract_unqualified` — Will an eligible model reproduce the audited plausible-type sets under the proposed type-first prompt and schema?

   Missing: No live or offline model qualification of this contract.

2. `false_singleton_risk` — How often can a false singleton type judgment combine with one complete matching option and yield unsafe typed output?

   Missing: No accepted-corpus error-rate evidence.

3. `synthetic_two_type_scope` — Do the conclusions generalize beyond synthetic fixtures and the current two-type managed Pack?

   Missing: No representative accepted-corpus generalization proof.

4. `same_type_multi_option_frequency` — Does singleton-type/multiple-complete-option state occur often enough to justify Stage 2?

   Missing: No governed fixture or frequency evidence.

5. `stage2_safety_and_value` — Can a bounded Stage 2 select the right same-type record with a safe net completeness gain?

   Missing: No Stage 2 qualification or outcome evidence.

6. `larger_ontology_behavior` — When does a larger ontology require deterministic type shortlisting before the model?

   Missing: No larger managed ontology benchmark.

7. `future_product_entrypoint` — Which versioned inactive profile and policy change will be authorized inside the existing production orchestration owner?

   Missing: No implementation authorization or two-call policy.

## 14. Decision boundary

GOAL 15 заканчивается архитектурной рекомендацией. Implementation changes, runtime activation, model qualification и production admission равны нулю. Context V2.1 по-прежнему не имеет доказанного eligible model.

Program owner отдельно утверждает A, B, C, phased B→C или дополнительную диагностику. До такого решения нельзя изменять Prompt/Context/Choice/Pack, runtime, provider policy или начинать следующий implementation GOAL.

**STOP AFTER GOAL 15.**
