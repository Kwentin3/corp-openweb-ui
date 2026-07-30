# Broker Reports Gate 2 Context V2.1 evidence-first comparative review

Status: completed offline analytical review for exactly three synthetic cases.

This report mechanically rebuilds primary facts from immutable GOAL 12 requests and outputs, then applies the bounded GOAL 13 classifications. It makes no Prompt, Context, Semantic Pack, Choice, source-projection, expected-answer, runtime or product change. Provider calls, retries, repairs and fallbacks are `0/0/0/0`. No final refactor is selected.

Association rubric: `yes` means the exact row/value structure uniquely identifies the relevant role associations; `partial` means row grouping is visible but at least one relevant pairwise association is absent; `no` means neither is visible.

## Case 1 — `syn_successor_v2_multiple_compatible`

### A — Original source as a table

| Source field | Exact literal |
| --- | --- |
| `amount a` | `310.00` |
| `amount b` | `410.00` |
| `description` | `Possible cash` |
| `currency` | `EUR` |
| `as of date` | `2026-03-03` |
| `description 2` | `Possible total` |

`association visible: partial` — One row groups all six values, but the exact source contains no amount-to-description pair links.

Mechanical parity: rows `6`; source values `6`; exact matches `6`; missing `0`; duplicate mappings `0`; literal mismatches `0`.

### B — Exact source JSON

The block is the pretty-printed exact parsed `source` value; no field or literal is normalized.

```json
{
  "children": [
    {
      "kind": "table",
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "meaning": "amount a",
              "literal": "310.00"
            },
            {
              "meaning": "amount b",
              "literal": "410.00"
            },
            {
              "meaning": "description",
              "literal": "Possible cash"
            },
            {
              "meaning": "currency",
              "literal": "EUR"
            },
            {
              "meaning": "as of date",
              "literal": "2026-03-03"
            },
            {
              "meaning": "description 2",
              "literal": "Possible total"
            }
          ]
        }
      ]
    }
  ]
}
```

### C — Exact model task and context

Exact system message:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

Exact user semantic context (pretty-printed parsed value; the transparent artifact also preserves the exact compact serialized bytes):

```json
{
  "task": "Select one choice only when the visible source, type cards, and any shown differentiators uniquely support it; otherwise select unclassified.",
  "source": {
    "children": [
      {
        "kind": "table",
        "children": [
          {
            "kind": "row",
            "values": [
              {
                "meaning": "amount a",
                "literal": "310.00"
              },
              {
                "meaning": "amount b",
                "literal": "410.00"
              },
              {
                "meaning": "description",
                "literal": "Possible cash"
              },
              {
                "meaning": "currency",
                "literal": "EUR"
              },
              {
                "meaning": "as of date",
                "literal": "2026-03-03"
              },
              {
                "meaning": "description 2",
                "literal": "Possible total"
              }
            ]
          }
        ]
      }
    ]
  },
  "type_cards": [
    {
      "type_key": "type_1",
      "title": "Cash balance snapshot",
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "nearest_competitor": {
        "type_key": "type_2",
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
      }
    },
    {
      "type_key": "type_2",
      "title": "Printed financial metric",
      "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
      "negative_signal": "A total calculated by Gate 2 from child rows.",
      "nearest_competitor": {
        "type_key": "type_1",
        "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
      }
    }
  ],
  "choices": [],
  "unclassified_reasons": [
    {
      "code": "no_registry_type",
      "title": "No available type matches",
      "use_when": "Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning."
    },
    {
      "code": "single_registry_type_no_safe_record",
      "title": "One matching type, no safe record",
      "use_when": "Exactly one available financial type remains plausible, but the visible source does not uniquely support one complete prebound record for that type."
    },
    {
      "code": "ambiguous_registry_type",
      "title": "Multiple available types remain plausible",
      "use_when": "Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely."
    }
  ]
}
```

Exact canonical response schema:

```json
{
  "anyOf": [
    {
      "additionalProperties": false,
      "properties": {
        "choice": {
          "enum": [
            "unclassified"
          ],
          "type": "string"
        },
        "reason": {
          "enum": [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type"
          ],
          "type": "string"
        }
      },
      "required": [
        "choice",
        "reason"
      ],
      "type": "object"
    }
  ]
}
```

| Property | Exact value |
| --- | --- |
| `choices` count | `0` |
| typed response branch present | `no` |
| unclassified branch present | `yes` |
| allowed reason codes | `["no_registry_type","single_registry_type_no_safe_record","ambiguous_registry_type"]` |

> **Typed output was unavailable:** `choices=[]`, and the canonical schema permits only the unclassified branch.

### D — Provider differences

The system message, complete user semantic context and canonical response schema are byte/structurally identical across providers. Exact user-content UTF-8 SHA-256: `4dd76de2e81a18d12af9c9a96702f975602fc1bece7ddaccc93aabef769984c2`. Sealed model-visible request SHA-256: `303681e6f94e012ba6891950fde6128dd533e23c5783f25a33b4e14efa54a161`.

| Wrapper fact | OpenAI Nano | Anthropic Haiku |
| --- | --- | --- |
| top-level fields | `["max_completion_tokens","messages","model","response_format","stream"]` | `["max_tokens","messages","model","output_config","system"]` |
| model | `gpt-5.4-nano-2026-03-17` | `claude-haiku-4-5-20251001` |
| provider request wrapper | `openai_response_format` | `anthropic_native_messages` |
| system location | `messages[0].content` | `system` |
| user location | `messages[1].content` | `messages[0].content` |
| token cap | `max_completion_tokens=640` | `max_tokens=640` |
| schema location | `response_format.json_schema.schema` | `output_config.format.schema` |
| provider-visible schema shape | canonical schema under `properties.broker_reports_gate2_choice` | direct canonical schema |
| schema metadata | `name=broker_reports_gate2_choice`, `strict=true` | absent |
| schema transformation count | `1` | `0` |
| stream field | `stream=false` | absent |

No other semantic-context field delta exists in the stored exact requests.

### E — Exact model outputs

| Model | Stored adapter value type | Exact adapter-extracted value |
| --- | --- | --- |
| Nano | `object` | `{"choice":"unclassified","reason":"single_registry_type_no_safe_record"}` |
| Haiku | `string` | `{"choice": "unclassified", "reason": "ambiguous_registry_type"}` |

### F — Expected answer and mechanical diff

| Field | Expected | Nano | Haiku |
| --- | --- | --- | --- |
| `disposition` | `unclassified_financial_input` | `unclassified_financial_input` | `unclassified_financial_input` |
| `reason_code` | `ambiguous_registry_type` | `single_registry_type_no_safe_record` | `ambiguous_registry_type` |

Independently audited plausible local type set: `[type_1, type_2]`.

- Nano field-level diff: `$.reason_code` expected `ambiguous_registry_type`, actual `single_registry_type_no_safe_record`.
- Haiku field-level diff: `none`.

### G — Facts before interpretation

- The exact source contains 6 values in one row.
- The exact visible source literals, in model order, are ["310.00","410.00","Possible cash","EUR","2026-03-03","Possible total"].
- Association visibility is partial: One row groups all six values, but the exact source contains no amount-to-description pair links.
- The exact choices array contains 0 entries.
- The canonical schema contains no typed branch.
- The canonical schema contains the unclassified branch.
- Both exact outputs contain choice=unclassified.
- The independently audited plausible local type set is [type_1, type_2].
- The independently audited plausible type count is 2.
- The independently audited expected canonical answer is {"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}.
- The exact expected reason is ambiguous_registry_type; Nano returned single_registry_type_no_safe_record; Haiku returned ambiguous_registry_type.

### H — Bounded interpretation

| Layer | Evidence strength | Bounded finding |
| --- | --- | --- |
| `source_projection` | `supported` | Every literal survives, but amount-to-description pairing is absent. Causation is not established. |
| `type_glossary` | `hypothesis` | Both relevant cards and their reciprocal distinction are visible; no causal glossary defect is proven. |
| `choices_presentation` | `supported` | Zero choices and an unclassified-only schema are directly present. |
| `reason_contract` | `proven` | The proven mismatch locus is plausible-type cardinality 2+ to 1; that does not prove the contract caused it. |
| `model_capability` | `hypothesis` | One exact response cannot isolate capability from presentation. |
| `expected_answer_defect` | `not supported` | Independent revalidation reproduces the expected answer and records expected_answer_defect_supported=false. |

No row above establishes a causal root.

## Case 2 — `syn_successor_v2_detail_vs_subtotal`

### A — Original source as a table

| Source field | Exact literal |
| --- | --- |
| `currency` | `USD` |
| `date` | `2026-03-06` |
| `detail amount` | `25.00` |
| `description` | `Fee detail and subtotal` |
| `subtotal amount` | `125.00` |

`association visible: partial` — The exact meanings distinguish detail amount from subtotal amount, but the flat row contains no explicit pair or relationship binding.

Mechanical parity: rows `5`; source values `5`; exact matches `5`; missing `0`; duplicate mappings `0`; literal mismatches `0`.

### B — Exact source JSON

The block is the pretty-printed exact parsed `source` value; no field or literal is normalized.

```json
{
  "children": [
    {
      "kind": "table",
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "meaning": "currency",
              "literal": "USD"
            },
            {
              "meaning": "date",
              "literal": "2026-03-06"
            },
            {
              "meaning": "detail amount",
              "literal": "25.00"
            },
            {
              "meaning": "description",
              "literal": "Fee detail and subtotal"
            },
            {
              "meaning": "subtotal amount",
              "literal": "125.00"
            }
          ]
        }
      ]
    }
  ]
}
```

### C — Exact model task and context

Exact system message:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

Exact user semantic context (pretty-printed parsed value; the transparent artifact also preserves the exact compact serialized bytes):

```json
{
  "task": "Select one choice only when the visible source, type cards, and any shown differentiators uniquely support it; otherwise select unclassified.",
  "source": {
    "children": [
      {
        "kind": "table",
        "children": [
          {
            "kind": "row",
            "values": [
              {
                "meaning": "currency",
                "literal": "USD"
              },
              {
                "meaning": "date",
                "literal": "2026-03-06"
              },
              {
                "meaning": "detail amount",
                "literal": "25.00"
              },
              {
                "meaning": "description",
                "literal": "Fee detail and subtotal"
              },
              {
                "meaning": "subtotal amount",
                "literal": "125.00"
              }
            ]
          }
        ]
      }
    ]
  },
  "type_cards": [
    {
      "type_key": "type_1",
      "title": "Cash balance snapshot",
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "nearest_competitor": {
        "type_key": "type_2",
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
      }
    },
    {
      "type_key": "type_2",
      "title": "Printed financial metric",
      "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
      "negative_signal": "A total calculated by Gate 2 from child rows.",
      "nearest_competitor": {
        "type_key": "type_1",
        "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
      }
    }
  ],
  "choices": [],
  "unclassified_reasons": [
    {
      "code": "no_registry_type",
      "title": "No available type matches",
      "use_when": "Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning."
    },
    {
      "code": "single_registry_type_no_safe_record",
      "title": "One matching type, no safe record",
      "use_when": "Exactly one available financial type remains plausible, but the visible source does not uniquely support one complete prebound record for that type."
    },
    {
      "code": "ambiguous_registry_type",
      "title": "Multiple available types remain plausible",
      "use_when": "Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely."
    }
  ]
}
```

Exact canonical response schema:

```json
{
  "anyOf": [
    {
      "additionalProperties": false,
      "properties": {
        "choice": {
          "enum": [
            "unclassified"
          ],
          "type": "string"
        },
        "reason": {
          "enum": [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type"
          ],
          "type": "string"
        }
      },
      "required": [
        "choice",
        "reason"
      ],
      "type": "object"
    }
  ]
}
```

| Property | Exact value |
| --- | --- |
| `choices` count | `0` |
| typed response branch present | `no` |
| unclassified branch present | `yes` |
| allowed reason codes | `["no_registry_type","single_registry_type_no_safe_record","ambiguous_registry_type"]` |

> **Typed output was unavailable:** `choices=[]`, and the canonical schema permits only the unclassified branch.

### D — Provider differences

The system message, complete user semantic context and canonical response schema are byte/structurally identical across providers. Exact user-content UTF-8 SHA-256: `bfbe343eff9f269cdbe87b677cd8a1657c75c4d7d4fb199c6edb83a79020eba0`. Sealed model-visible request SHA-256: `c6f53bdf45df0ccbc26b67c71f48cc9b638d70132ed0f4f156b6e994c6a72116`.

| Wrapper fact | OpenAI Nano | Anthropic Haiku |
| --- | --- | --- |
| top-level fields | `["max_completion_tokens","messages","model","response_format","stream"]` | `["max_tokens","messages","model","output_config","system"]` |
| model | `gpt-5.4-nano-2026-03-17` | `claude-haiku-4-5-20251001` |
| provider request wrapper | `openai_response_format` | `anthropic_native_messages` |
| system location | `messages[0].content` | `system` |
| user location | `messages[1].content` | `messages[0].content` |
| token cap | `max_completion_tokens=640` | `max_tokens=640` |
| schema location | `response_format.json_schema.schema` | `output_config.format.schema` |
| provider-visible schema shape | canonical schema under `properties.broker_reports_gate2_choice` | direct canonical schema |
| schema metadata | `name=broker_reports_gate2_choice`, `strict=true` | absent |
| schema transformation count | `1` | `0` |
| stream field | `stream=false` | absent |

No other semantic-context field delta exists in the stored exact requests.

### E — Exact model outputs

| Model | Stored adapter value type | Exact adapter-extracted value |
| --- | --- | --- |
| Nano | `object` | `{"choice":"unclassified","reason":"no_registry_type"}` |
| Haiku | `string` | `{"choice": "unclassified", "reason": "single_registry_type_no_safe_record"}` |

### F — Expected answer and mechanical diff

| Field | Expected | Nano | Haiku |
| --- | --- | --- | --- |
| `disposition` | `unclassified_financial_input` | `unclassified_financial_input` | `unclassified_financial_input` |
| `reason_code` | `single_registry_type_no_safe_record` | `no_registry_type` | `single_registry_type_no_safe_record` |

Independently audited plausible local type set: `[type_2]`.

- Nano field-level diff: `$.reason_code` expected `single_registry_type_no_safe_record`, actual `no_registry_type`.
- Haiku field-level diff: `none`.

### G — Facts before interpretation

- The exact source contains 5 values in one row.
- The exact visible source literals, in model order, are ["USD","2026-03-06","25.00","Fee detail and subtotal","125.00"].
- Association visibility is partial: The exact meanings distinguish detail amount from subtotal amount, but the flat row contains no explicit pair or relationship binding.
- The exact choices array contains 0 entries.
- The canonical schema contains no typed branch.
- The canonical schema contains the unclassified branch.
- Both exact outputs contain choice=unclassified.
- The independently audited plausible local type set is [type_2].
- The independently audited plausible type count is 1.
- The independently audited expected canonical answer is {"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}.
- The exact expected reason is single_registry_type_no_safe_record; Nano returned no_registry_type; Haiku returned single_registry_type_no_safe_record.

### H — Bounded interpretation

| Layer | Evidence strength | Bounded finding |
| --- | --- | --- |
| `source_projection` | `hypothesis` | No literal or amount role is lost; the flat row remains an unproved contributor. |
| `type_glossary` | `hypothesis` | The visible printed-metric card covers a labelled source total; no concrete glossary defect is shown. |
| `choices_presentation` | `supported` | choices=[] establishes zero safe prebound records, not zero plausible types. |
| `reason_contract` | `proven` | The proven mismatch locus is plausible-type cardinality 1 to 0; causal responsibility is not proven. |
| `model_capability` | `hypothesis` | The exact response cannot isolate model capability. |
| `expected_answer_defect` | `not supported` | Independent revalidation reproduces the corrected expected answer and records expected_answer_defect_supported=false. |

No row above establishes a causal root.

## Case 3 — `syn_successor_v2_no_registry_type`

### A — Original source as a table

| Source field | Exact literal |
| --- | --- |
| `amount` | `42.25` |
| `currency` | `CHF` |
| `date` | `2026-03-04` |
| `description` | `Broker fee detail` |

`association visible: yes` — One amount, currency, date and description are grouped in one row with no competing value pair.

Mechanical parity: rows `4`; source values `4`; exact matches `4`; missing `0`; duplicate mappings `0`; literal mismatches `0`.

### B — Exact source JSON

The block is the pretty-printed exact parsed `source` value; no field or literal is normalized.

```json
{
  "children": [
    {
      "kind": "table",
      "children": [
        {
          "kind": "row",
          "values": [
            {
              "meaning": "amount",
              "literal": "42.25"
            },
            {
              "meaning": "currency",
              "literal": "CHF"
            },
            {
              "meaning": "date",
              "literal": "2026-03-04"
            },
            {
              "meaning": "description",
              "literal": "Broker fee detail"
            }
          ]
        }
      ]
    }
  ]
}
```

### C — Exact model task and context

Exact system message:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

Exact user semantic context (pretty-printed parsed value; the transparent artifact also preserves the exact compact serialized bytes):

```json
{
  "task": "Select one choice only when the visible source, type cards, and any shown differentiators uniquely support it; otherwise select unclassified.",
  "source": {
    "children": [
      {
        "kind": "table",
        "children": [
          {
            "kind": "row",
            "values": [
              {
                "meaning": "amount",
                "literal": "42.25"
              },
              {
                "meaning": "currency",
                "literal": "CHF"
              },
              {
                "meaning": "date",
                "literal": "2026-03-04"
              },
              {
                "meaning": "description",
                "literal": "Broker fee detail"
              }
            ]
          }
        ]
      }
    ]
  },
  "type_cards": [
    {
      "type_key": "type_1",
      "title": "Cash balance snapshot",
      "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
      "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
      "nearest_competitor": {
        "type_key": "type_2",
        "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
      }
    },
    {
      "type_key": "type_2",
      "title": "Printed financial metric",
      "definition": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "positive_signal": "A synthetic statement prints a labelled total for an explicit period and statement scope.",
      "negative_signal": "A total calculated by Gate 2 from child rows.",
      "nearest_competitor": {
        "type_key": "type_1",
        "distinction": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
      }
    }
  ],
  "choices": [
    {
      "choice_key": "choice_1",
      "title": "Printed financial metric"
    },
    {
      "choice_key": "choice_2",
      "title": "Cash balance snapshot"
    }
  ],
  "unclassified_reasons": [
    {
      "code": "no_registry_type",
      "title": "No available type matches",
      "use_when": "Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning."
    },
    {
      "code": "single_registry_type_no_safe_record",
      "title": "One matching type, no safe record",
      "use_when": "Exactly one available financial type remains plausible, but the visible source does not uniquely support one complete prebound record for that type."
    },
    {
      "code": "ambiguous_registry_type",
      "title": "Multiple available types remain plausible",
      "use_when": "Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely."
    }
  ]
}
```

Exact canonical response schema:

```json
{
  "anyOf": [
    {
      "additionalProperties": false,
      "properties": {
        "choice": {
          "enum": [
            "choice_1",
            "choice_2"
          ],
          "type": "string"
        }
      },
      "required": [
        "choice"
      ],
      "type": "object"
    },
    {
      "additionalProperties": false,
      "properties": {
        "choice": {
          "enum": [
            "unclassified"
          ],
          "type": "string"
        },
        "reason": {
          "enum": [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type"
          ],
          "type": "string"
        }
      },
      "required": [
        "choice",
        "reason"
      ],
      "type": "object"
    }
  ]
}
```

| Property | Exact value |
| --- | --- |
| `choices` count | `2` |
| typed response branch present | `yes` |
| unclassified branch present | `yes` |
| allowed reason codes | `["no_registry_type","single_registry_type_no_safe_record","ambiguous_registry_type"]` |

> Typed output was available: the exact choices and both typed and unclassified schema branches were visible.

### D — Provider differences

The system message, complete user semantic context and canonical response schema are byte/structurally identical across providers. Exact user-content UTF-8 SHA-256: `8475b9ce840a4801b4792a347306a5ba85a40a8d10e08e9cfcd80d5b914b1007`. Sealed model-visible request SHA-256: `b2edde39e5ae1b9f1a871db49bdfb619dc5f7c719169ccd42231187cc0963a6a`.

| Wrapper fact | OpenAI Nano | Anthropic Haiku |
| --- | --- | --- |
| top-level fields | `["max_completion_tokens","messages","model","response_format","stream"]` | `["max_tokens","messages","model","output_config","system"]` |
| model | `gpt-5.4-nano-2026-03-17` | `claude-haiku-4-5-20251001` |
| provider request wrapper | `openai_response_format` | `anthropic_native_messages` |
| system location | `messages[0].content` | `system` |
| user location | `messages[1].content` | `messages[0].content` |
| token cap | `max_completion_tokens=640` | `max_tokens=640` |
| schema location | `response_format.json_schema.schema` | `output_config.format.schema` |
| provider-visible schema shape | canonical schema under `properties.broker_reports_gate2_choice` | direct canonical schema |
| schema metadata | `name=broker_reports_gate2_choice`, `strict=true` | absent |
| schema transformation count | `1` | `0` |
| stream field | `stream=false` | absent |

No other semantic-context field delta exists in the stored exact requests.

### E — Exact model outputs

| Model | Stored adapter value type | Exact adapter-extracted value |
| --- | --- | --- |
| Nano | `object` | `{"choice":"unclassified","reason":"no_registry_type"}` |
| Haiku | `string` | `{"choice":"unclassified","reason":"ambiguous_registry_type"}` |

### F — Expected answer and mechanical diff

| Field | Expected | Nano | Haiku |
| --- | --- | --- | --- |
| `disposition` | `unclassified_financial_input` | `unclassified_financial_input` | `unclassified_financial_input` |
| `reason_code` | `no_registry_type` | `no_registry_type` | `ambiguous_registry_type` |

Independently audited plausible local type set: `[]`.

- Nano field-level diff: `none`.
- Haiku field-level diff: `$.reason_code` expected `no_registry_type`, actual `ambiguous_registry_type`.

### G — Facts before interpretation

- The exact source contains 4 values in one row.
- The exact visible source literals, in model order, are ["42.25","CHF","2026-03-04","Broker fee detail"].
- Association visibility is yes: One amount, currency, date and description are grouped in one row with no competing value pair.
- The exact choices array contains 2 entries.
- The canonical schema contains a typed branch.
- The canonical schema contains the unclassified branch.
- Both exact outputs contain choice=unclassified.
- The independently audited plausible local type set is [].
- The independently audited plausible type count is 0.
- The independently audited expected canonical answer is {"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}.
- The exact expected reason is no_registry_type; Nano returned no_registry_type; Haiku returned ambiguous_registry_type.

### H — Bounded interpretation

| Layer | Evidence strength | Bounded finding |
| --- | --- | --- |
| `source_projection` | `hypothesis` | All four values survive in one simple row; no projection defect creating two meanings is shown. |
| `type_glossary` | `supported` | The full Pack detail-row exclusion is absent from the minimal visible card; its causal effect is unobserved. |
| `choices_presentation` | `supported` | Two structural choices are visible while the audited plausible type set is empty. |
| `reason_contract` | `proven` | The proven mismatch locus is plausible-type cardinality 0 to 2+; the contract is not thereby proven causal. |
| `model_capability` | `hypothesis` | Capability cannot be separated from the supported presentation risks. |
| `expected_answer_defect` | `not supported` | Pack, reason catalog and corrected audit reproduce zero plausible types; expected_answer_defect_supported=false. |

No row above establishes a causal root.

## Review boundary

The comparison proves exact inputs, outputs, expected answers, mechanical differences and bounded evidence strengths. It does not prove a causal root, qualify either model, authorize activation or select a corrective implementation.
