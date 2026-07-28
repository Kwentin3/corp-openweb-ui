# Broker Reports Gate 2 — Nano zero-call forensic

Date: 2026-07-28

Base revision: `cabe8c6a787aa21b106e54be60a424282b25022e`

Scope: GOAL 1 only — two frozen synthetic V6 smoke cases. No provider call,
Prompt change, Semantic Pack change, packet change, option change, expected
answer change, parser change, validator change or materializer change was
performed.

## Result

Both exact Nano answers were recovered from the original private checkpoints;
neither answer was reconstructed or guessed. Each checkpoint hash, canonical
request hash and model-output hash verifies. The published post-correction
diagnostic proves exact parsing, normalization, materialization and replay
with zero provider calls.

For both cases, the field-level comparison of the Nano and Haiku canonical
request objects has exactly one difference:

```text
$.model:
  Nano  = gpt-5.4-nano-2026-03-17
  Haiku = claude-haiku-4-5-20251001
```

The system Prompt, Semantic Packet, response-format identity, frozen case,
type cards, Typed Options, unclassified choice and expected answer are exact
matches between the two executions.

The two observations support bounded diagnoses:

- typed case: `OPTION_CONFUSION`;
- unclassified case: `MODEL_IGNORED_UNCLASSIFIED`.

This two-case evidence does not establish a general model-quality rate and
does not yet justify a packet refinement. GOAL 2 remains blocked until this
forensic report is accepted and merged.

## Primary evidence provenance

| Evidence | Verification |
| --- | --- |
| Original Nano terminal safe receipt | integrity `e6e56108fd3588c12631f6c8778fbabb813adc803912d5cb0ebedef9abe69f36`, exact |
| Nano offline diagnostic | integrity `2ee7c9779cd459dfa668b3a98dd88537ca18f855d50443f431a757a8169671d3`, exact |
| Nano typed private checkpoint | private hash `89b6dbe520fd37a380c2a937968e5ca2c5c90fe731a107b44ac05c88238f80f8`, exact |
| Nano unclassified private checkpoint | private hash `d725cec9460e7090224b32733f41a48ee241127399cdee3bfd5aa11873bf98e7`, exact |
| Haiku terminal safe receipt | both private/safe hash links verified and offline replay exact |
| Provider submissions during this forensic | `0` |

Repository evidence:

- [Nano terminal receipt](../2026-07-27/BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE.receipt.safe.json);
- [Nano zero-call diagnostic](../2026-07-27/BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE_OFFLINE_DIAGNOSTIC.receipt.safe.json);
- [Nano terminal report](../2026-07-27/BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE.report.md);
- [Haiku terminal receipt](../2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.receipt.safe.json);
- [Haiku transparent report](../2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.report.md).

## Shared exact model-visible blocks

These blocks were byte-identical for both cases and both models. They are
shown once to avoid presentation-only duplication; each case below binds them
by the stated hashes.

### System instruction

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

System-message hash:
`bc77c8e1fe2b6af7b456646f7644d92b5ee6ac28101d68a0e1b6f2101dede0e0`.

### Task

```json
{
  "semantic_operation": "select_prebound_typed_option_or_unclassified",
  "ambiguity_rule": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified."
}
```

Task hash:
`4c7d5e96cda023df0f1f5e2196c6859e3daba0cfe27415d1dc39bb57d33e2f88`.

### Available financial type cards

Type-card-list hash:
`d0e716538f822bbcdc089236f91c6afabdf632df9bc32764081897da30027d5d`.

#### Card 1: `cash_balance_snapshot_v1`

- `short_meaning`: `A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.`
- `required_roles`, in order: `amount/source_decimal`; `as_of_date/source_date`; `statement_scope/source_reference`.
- `optional_roles`, in order: `balance_class/source_text`; `currency/source_currency`; `source_label/source_text`; `unit/source_unit`.
- `key_semantic_distinctions`, in order:
  - against `printed_financial_metric_v1`: `Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified.`
  - against `cash_movement`: `A movement is an event over time; this type is a state at one reporting date.`
- `ambiguity_rule`: `Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context.`

#### Card 2: `printed_financial_metric_v1`

- `short_meaning`: `A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.`
- `required_roles`, in order: `amount/source_decimal`; `printed_label_evidence_ref/source_reference`; `statement_scope/source_reference`.
- `optional_roles`, in order: `as_of_date/source_date`; `currency/source_currency`; `period/source_period`; `source_label/source_text`; `unit/source_unit`.
- `key_semantic_distinctions`, in order:
  - against `cash_balance_snapshot_v1`: `A printed total is not a cash balance unless ordinary cash-class state semantics are explicit.`
  - against `gate2_calculated_aggregate`: `This type preserves a total printed by the source; a value calculated by Gate 2 is never this type.`
- `ambiguity_rule`: `Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total.`

### Unclassified choice

The strict response schema offered this exact alternative in both cases:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "disposition": {
      "type": "string",
      "enum": ["unclassified_financial_input"]
    },
    "reason_code": {
      "type": "string",
      "enum": ["ambiguous_registry_type", "no_registry_type"]
    }
  },
  "required": ["disposition", "reason_code"]
}
```

## Case `syn_successor_v2_unique_cash`

### CASE PURPOSE

Verify that an unambiguous synthetic cash-balance row selects the prebound
`cash_balance_snapshot_v1` option.

### WHAT_MODEL_SAW

The exact shared Prompt, task, type cards and unclassified alternative are
shown above. Their hashes match both the Nano and Haiku checkpoints.

Exact Semantic Packet hash:
`3bcb297a62bf17d74f032b4058dc4c4f3097f33de9f89626b194d4a1600b6851`.

Exact source-context hash:
`e7ae70b30b131a669e24b7b67b28d34ff68f670ce8fbf4b4e374f695311d637c`.

#### Source values, in packet order

| `source_value_ref` | `value_type` | Exact value | Association | Exact visible context |
| --- | --- | --- | --- | --- |
| `syn_successor_v2_unique_cash:primary:value:amount` | `source_decimal` | `-120.5000` | `table_row` / `row:syn_successor_v2_unique_cash:primary` | `section_role=null; row_role=fact_candidate; column_meaning=amount; visible_label=null` |
| `syn_successor_v2_unique_cash:primary:value:currency` | `source_currency` | `RUB` | `table_row` / `row:syn_successor_v2_unique_cash:primary` | `section_role=null; row_role=fact_candidate; column_meaning=currency; visible_label=null` |
| `syn_successor_v2_unique_cash:primary:value:date` | `source_date` | `2026-03-01` | `table_row` / `row:syn_successor_v2_unique_cash:primary` | `section_role=null; row_role=fact_candidate; column_meaning=as_of_date; visible_label=null` |
| `syn_successor_v2_unique_cash:primary:value:label` | `source_text` | `Cash balance` | `table_row` / `row:syn_successor_v2_unique_cash:primary` | `section_role=null; row_role=fact_candidate; column_meaning=description; visible_label=null` |
| `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label` | `source_reference` | `row:syn_successor_v2_unique_cash:primary` | `deterministic_reference` / `row:syn_successor_v2_unique_cash:primary` | all four visible-context fields `null` |
| `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope` | `source_reference` | `row:syn_successor_v2_unique_cash:primary` | `deterministic_reference` / `row:syn_successor_v2_unique_cash:primary` | all four visible-context fields `null` |

#### Associations, in packet order

| Kind / ref | Exact source refs | Exact human summary |
| --- | --- | --- |
| `deterministic_reference` / `row:syn_successor_v2_unique_cash:primary` | `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label`; `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope` | `deterministic reference association linking 2 source values` |
| `table_row` / `row:syn_successor_v2_unique_cash:primary` | `syn_successor_v2_unique_cash:primary:value:amount`; `syn_successor_v2_unique_cash:primary:value:currency`; `syn_successor_v2_unique_cash:primary:value:date`; `syn_successor_v2_unique_cash:primary:value:label` | `table row association linking 4 source values` |

Exact Typed Options list hash:
`2b8b5f4a1aa41b100216cce2be979398da6e3a0f7b0a3aa76f2d72ad5687b6bc`.

#### Typed option 1, in packet order

`financial-typed-option:744e3c95321e39b5f068c13cb76c72ae`
(`printed_financial_metric_v1`)

| Role | Exact value | Type | Exact source ref | Visible-context values | Exact human summary |
| --- | --- | --- | --- | --- | --- |
| `amount` | `-120.5000` | `source_decimal` | `syn_successor_v2_unique_cash:primary:value:amount` | `section=null; row=fact_candidate; column=amount; label=null` | `amount is prebound to -120.5000` |
| `as_of_date` | `2026-03-01` | `source_date` | `syn_successor_v2_unique_cash:primary:value:date` | `section=null; row=fact_candidate; column=as_of_date; label=null` | `as_of_date is prebound to 2026-03-01` |
| `currency` | `RUB` | `source_currency` | `syn_successor_v2_unique_cash:primary:value:currency` | `section=null; row=fact_candidate; column=currency; label=null` | `currency is prebound to RUB` |
| `printed_label_evidence_ref` | `row:syn_successor_v2_unique_cash:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:printed-label` | all four fields `null` | `printed_label_evidence_ref is prebound to row:syn_successor_v2_unique_cash:primary` |
| `source_label` | `Cash balance` | `source_text` | `syn_successor_v2_unique_cash:primary:value:label` | `section=null; row=fact_candidate; column=description; label=null` | `source_label is prebound to Cash balance` |
| `statement_scope` | `row:syn_successor_v2_unique_cash:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope` | all four fields `null` | `statement_scope is prebound to row:syn_successor_v2_unique_cash:primary` |

#### Typed option 2, in packet order

`financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f`
(`cash_balance_snapshot_v1`)

| Role | Exact value | Type | Exact source ref | Visible-context values | Exact human summary |
| --- | --- | --- | --- | --- | --- |
| `amount` | `-120.5000` | `source_decimal` | `syn_successor_v2_unique_cash:primary:value:amount` | `section=null; row=fact_candidate; column=amount; label=null` | `amount is prebound to -120.5000` |
| `as_of_date` | `2026-03-01` | `source_date` | `syn_successor_v2_unique_cash:primary:value:date` | `section=null; row=fact_candidate; column=as_of_date; label=null` | `as_of_date is prebound to 2026-03-01` |
| `currency` | `RUB` | `source_currency` | `syn_successor_v2_unique_cash:primary:value:currency` | `section=null; row=fact_candidate; column=currency; label=null` | `currency is prebound to RUB` |
| `statement_scope` | `row:syn_successor_v2_unique_cash:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:4838449945f78fb04635e5d2:statement-scope` | all four fields `null` | `statement_scope is prebound to row:syn_successor_v2_unique_cash:primary` |

### EXPECTED_ANSWER

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

### EXACT_NANO_ANSWER

This is the exact adapter-extracted JSON object preserved by the original
checkpoint. Model-output hash:
`c6f5ffd041ea9a1c846090176d88c7dde6de8df576f1ed2fb5848c6322df5b75`.

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:744e3c95321e39b5f068c13cb76c72ae"
}
```

### NORMALIZED_ANSWER

The existing Choice parser and deterministic expansion reproduced this object
without mutation:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:744e3c95321e39b5f068c13cb76c72ae"
}
```

### FIELD_LEVEL_DIFF

| Field | Expected | Nano normalized | Match |
| --- | --- | --- | --- |
| `disposition` | `"typed_input"` | `"typed_input"` | `YES` |
| `typed_option_id` | `"financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"` | `"financial-typed-option:744e3c95321e39b5f068c13cb76c72ae"` | `NO` |

Overall exact match: `NO`.

### HAIKU ANSWER ON THE SAME FROZEN CASE

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
}
```

The Nano/Haiku canonical-request diff contains only `$.model`; the Haiku
answer is an exact match to expected.

### DIAGNOSIS

`OPTION_CONFUSION`

The Nano answer selected a valid prebound option but chose the printed-metric
option instead of the cash-balance option. This is not a schema, parsing or
normalization failure: the exact object survived normalization unchanged and
the post-correction materialization/replay passed. The same exact semantic
surface led Haiku to the expected cash option. On this evidence, option choice
is the narrowest supported failure location.

This case alone cannot prove why Nano preferred the first option or establish
a general ordering bias.

## Case `syn_successor_v2_no_registry_type`

### CASE PURPOSE

Verify that a synthetic broker-fee row unsupported by either available
financial type selects `unclassified_financial_input` with
`no_registry_type`.

### WHAT_MODEL_SAW

The exact shared Prompt, task, type cards and unclassified alternative are
shown above. Their hashes match both the Nano and Haiku checkpoints.

Exact Semantic Packet hash:
`871385de7814271f6eea35ea930be04c70f92ebc0f4c11d9d19d71f8848e25f5`.

Exact source-context hash:
`c2a0febf8cb3ad3dd76bd8fb67905dc5cfe2a5528aa7cc23b00b6afbf48febe3`.

#### Source values, in packet order

| `source_value_ref` | `value_type` | Exact value | Association | Exact visible context |
| --- | --- | --- | --- | --- |
| `syn_successor_v2_no_registry_type:primary:value:amount` | `source_decimal` | `42.25` | `table_row` / `row:syn_successor_v2_no_registry_type:primary` | `section_role=null; row_role=fact_candidate; column_meaning=amount; visible_label=null` |
| `syn_successor_v2_no_registry_type:primary:value:currency` | `source_currency` | `CHF` | `table_row` / `row:syn_successor_v2_no_registry_type:primary` | `section_role=null; row_role=fact_candidate; column_meaning=currency; visible_label=null` |
| `syn_successor_v2_no_registry_type:primary:value:date` | `source_date` | `2026-03-04` | `table_row` / `row:syn_successor_v2_no_registry_type:primary` | `section_role=null; row_role=fact_candidate; column_meaning=date; visible_label=null` |
| `syn_successor_v2_no_registry_type:primary:value:label` | `source_text` | `Broker fee detail` | `table_row` / `row:syn_successor_v2_no_registry_type:primary` | `section_role=null; row_role=fact_candidate; column_meaning=description; visible_label=null` |
| `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label` | `source_reference` | `row:syn_successor_v2_no_registry_type:primary` | `deterministic_reference` / `row:syn_successor_v2_no_registry_type:primary` | all four visible-context fields `null` |
| `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope` | `source_reference` | `row:syn_successor_v2_no_registry_type:primary` | `deterministic_reference` / `row:syn_successor_v2_no_registry_type:primary` | all four visible-context fields `null` |

#### Associations, in packet order

| Kind / ref | Exact source refs | Exact human summary |
| --- | --- | --- |
| `deterministic_reference` / `row:syn_successor_v2_no_registry_type:primary` | `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label`; `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope` | `deterministic reference association linking 2 source values` |
| `table_row` / `row:syn_successor_v2_no_registry_type:primary` | `syn_successor_v2_no_registry_type:primary:value:amount`; `syn_successor_v2_no_registry_type:primary:value:currency`; `syn_successor_v2_no_registry_type:primary:value:date`; `syn_successor_v2_no_registry_type:primary:value:label` | `table row association linking 4 source values` |

Exact Typed Options list hash:
`17d91a0ae6db15d9856b571bf77b11857cf7094d82866c8b4ac389a153e07e0e`.

#### Typed option 1, in packet order

`financial-typed-option:5dc5d8caadb90fa381f3e2b7cd42d52a`
(`printed_financial_metric_v1`)

| Role | Exact value | Type | Exact source ref | Visible-context values | Exact human summary |
| --- | --- | --- | --- | --- | --- |
| `amount` | `42.25` | `source_decimal` | `syn_successor_v2_no_registry_type:primary:value:amount` | `section=null; row=fact_candidate; column=amount; label=null` | `amount is prebound to 42.25` |
| `as_of_date` | `2026-03-04` | `source_date` | `syn_successor_v2_no_registry_type:primary:value:date` | `section=null; row=fact_candidate; column=date; label=null` | `as_of_date is prebound to 2026-03-04` |
| `currency` | `CHF` | `source_currency` | `syn_successor_v2_no_registry_type:primary:value:currency` | `section=null; row=fact_candidate; column=currency; label=null` | `currency is prebound to CHF` |
| `printed_label_evidence_ref` | `row:syn_successor_v2_no_registry_type:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:printed-label` | all four fields `null` | `printed_label_evidence_ref is prebound to row:syn_successor_v2_no_registry_type:primary` |
| `source_label` | `Broker fee detail` | `source_text` | `syn_successor_v2_no_registry_type:primary:value:label` | `section=null; row=fact_candidate; column=description; label=null` | `source_label is prebound to Broker fee detail` |
| `statement_scope` | `row:syn_successor_v2_no_registry_type:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope` | all four fields `null` | `statement_scope is prebound to row:syn_successor_v2_no_registry_type:primary` |

#### Typed option 2, in packet order

`financial-typed-option:c123e84fef9c627b68c06341410c35a7`
(`cash_balance_snapshot_v1`)

| Role | Exact value | Type | Exact source ref | Visible-context values | Exact human summary |
| --- | --- | --- | --- | --- | --- |
| `amount` | `42.25` | `source_decimal` | `syn_successor_v2_no_registry_type:primary:value:amount` | `section=null; row=fact_candidate; column=amount; label=null` | `amount is prebound to 42.25` |
| `as_of_date` | `2026-03-04` | `source_date` | `syn_successor_v2_no_registry_type:primary:value:date` | `section=null; row=fact_candidate; column=date; label=null` | `as_of_date is prebound to 2026-03-04` |
| `currency` | `CHF` | `source_currency` | `syn_successor_v2_no_registry_type:primary:value:currency` | `section=null; row=fact_candidate; column=currency; label=null` | `currency is prebound to CHF` |
| `statement_scope` | `row:syn_successor_v2_no_registry_type:primary` | `source_reference` | `value:scope:gate2:deterministic-financial:46624096caaccdbd55cf2be0:statement-scope` | all four fields `null` | `statement_scope is prebound to row:syn_successor_v2_no_registry_type:primary` |

### EXPECTED_ANSWER

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

### EXACT_NANO_ANSWER

This is the exact adapter-extracted JSON object preserved by the original
checkpoint. Model-output hash:
`0c82d7ea2d741c26c55952723970dd37397c0458c297f8701294fffac4e06f39`.

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:5dc5d8caadb90fa381f3e2b7cd42d52a"
}
```

### NORMALIZED_ANSWER

The existing Choice parser and deterministic expansion reproduced this object
without mutation:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "financial-typed-option:5dc5d8caadb90fa381f3e2b7cd42d52a"
}
```

### FIELD_LEVEL_DIFF

| Field | Expected | Nano normalized | Match |
| --- | --- | --- | --- |
| `disposition` | `"unclassified_financial_input"` | `"typed_input"` | `NO` |
| `reason_code` | `"no_registry_type"` | absent | `NO` |
| `typed_option_id` | absent | `"financial-typed-option:5dc5d8caadb90fa381f3e2b7cd42d52a"` | `NO` |

Overall exact match: `NO`.

### HAIKU ANSWER ON THE SAME FROZEN CASE

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "no_registry_type"
}
```

The Nano/Haiku canonical-request diff contains only `$.model`; the Haiku
answer is an exact match to expected.

### DIAGNOSIS

`MODEL_IGNORED_UNCLASSIFIED`

The strict schema visibly offered unclassified with `no_registry_type`, and
the source label was `Broker fee detail`, while neither available type card
describes a fee. Nano nevertheless selected the first typed option. The exact
object survived normalization unchanged and the post-correction
materialization/replay passed, excluding a technical normalization error.
Haiku selected the expected unclassified answer on the otherwise exact same
canonical request.

The two observations are consistent with a preference for a structurally
complete typed option, but two cases are insufficient to prove a general
first-option or typed-default mechanism.

## Mechanical cross-model comparison

| Boundary | Typed case | Unclassified case |
| --- | --- | --- |
| Canonical request diff paths | `$.model` only | `$.model` only |
| System Prompt equal | `YES` | `YES` |
| Semantic Packet equal | `YES` | `YES` |
| Response-format hash equal | `YES` | `YES` |
| Expected answer equal | `YES` | `YES` |
| Nano exact vs normalized | `EXACT` | `EXACT` |
| Nano expected match | `NO` | `NO` |
| Haiku expected match | `YES` | `YES` |
| Offline provider calls | `0` | `0` |

## Diagnosis exclusions

- `SOURCE_CONTEXT_INSUFFICIENT`: not supported for these frozen cases; the
  same exact context led Haiku to both expected choices.
- `TYPE_CARD_AMBIGUOUS`: not supported by this two-case differential; Nano's
  wrong choices do not identify a contradictory or missing card field.
- `EXPECTED_ANSWER_QUESTIONABLE`: not supported; both expected choices follow
  the frozen benchmark and were independently selected by Haiku.
- `TECHNICAL_NORMALIZATION_ERROR`: excluded by exact output-to-normalized
  equality and exact post-correction replay.
- `EVIDENCE_INSUFFICIENT`: excluded for identifying the observed field
  mismatches and bounded diagnoses; evidence remains insufficient for a
  general causal theory or a packet-refinement decision.

## Acceptance

| Item | Result |
| --- | --- |
| `PROVIDER_CALLS` | `ZERO` |
| `NANO_INPUT_VISIBLE` | `YES` |
| `NANO_EXACT_OUTPUT_VISIBLE` | `YES` |
| `NANO_OUTPUT_RECOVERED_NOT_GUESSED` | `YES` |
| `NORMALIZED_ANSWER_VISIBLE` | `YES` |
| `EXPECTED_VS_ACTUAL_DIFF` | `EXPLICIT` |
| `HAIKU_SAME_FROZEN_WORKLOAD` | `PROVEN; ONLY $.model DIFFERS` |
| `PRIMARY_EVIDENCE_BEFORE_INTERPRETATION` | `YES` |
| `PROMPT_OR_PACK_CHANGE` | `ZERO` |
| `RUNTIME_CHANGE` | `ZERO` |
| `FALLBACK_REPAIR_HIDDEN_RETRY` | `ZERO` |
| `GOAL_1` | `COMPLETE_FOR_REVIEW` |
| `GOAL_2` | `BLOCKED_UNTIL_GOAL_1_MERGED` |

## Verification

```text
Nano private checkpoint integrity: 2/2 EXACT
Nano canonical request hash: 2/2 EXACT
Nano model-output hash: 2/2 EXACT
Published safe receipt integrity: 2/2 EXACT
Current factory packet vs Nano checkpoint: 2/2 EXACT
Nano packet vs Haiku packet: 2/2 EXACT
Nano request vs Haiku request diff: $.model ONLY, 2/2
Response-format hash equality: 2/2 EXACT
Report packet string-leaf coverage: 0 missing
Offline provider calls: 0
Privacy scan: PASSED
Markdown relative links: 9 checked, 0 broken
Focused evidence/qualification/architecture regression: 57 passed
Full service suite: 1846 passed, 20 skipped, 5 SWIG-only warnings
git diff --check: PASSED
```

## Authority and privacy boundary

Affected authority: V6 exact decision evidence and transparent synthetic
reporting documentation. No execution authority changed.

The report uses only allowlisted synthetic values and exact semantic JSON.
It contains no credential, provider response ID, raw provider envelope,
hidden reasoning, private filesystem path or customer value. Private
checkpoints remain outside Git and are connected to repository evidence only
through hashes.

No second packet builder, projector, adapter, parser, validator or
materializer was introduced.
