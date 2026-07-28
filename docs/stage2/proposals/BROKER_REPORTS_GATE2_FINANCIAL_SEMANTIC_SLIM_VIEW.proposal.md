# Broker Reports Gate 2 Financial Semantic Slim View

Status: `IMPLEMENTED_NOT_ACTIVE_GOAL1`

Date: 2026-07-28

This document originated as the model-context research design and now records
the GOAL 1 non-active implementation. It changes no runtime contract, Prompt,
Semantic Pack, Candidate Compiler, Typed Option, canonical Choice, validator,
materializer, Evidence Bundle, provider adapter or model output.

## Contract relationship

The later
[LLM Semantic Context v1](../contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the closed final boundary for the complete model-visible request.

The transition view is implemented inside the existing V6 packet owner and
remains non-active. It keeps exact canonical option IDs because the current V6
Choice requires them, so it does not claim full Context v1 conformance.
Replacing those IDs with local response aliases is a separate versioned Choice
boundary and must not be folded into the Slim View implementation.

## Purpose

Present the existing V6 semantic decision surface in a shorter human-readable
form while keeping all technical identity, provenance, binding and replay
complexity code-owned.

The model still performs one operation:

```text
select one existing exact option_id, or select unclassified
```

## Authority

The only permitted construction owner remains
`Gate2FinancialSemanticV6PacketFactory.create` in the current V6 packet
module. The GOAL 1 implementation computes the non-active candidate and alias
receipt inside that owner.

Forbidden:

- a second packet builder;
- a second Candidate Compiler;
- an alternative model-choice schema;
- provider-adapter semantic rewriting;
- model-generated refs or bindings;
- deletion of opaque IDs from the Evidence Bundle;
- runtime activation in the implementation PR.

## Implemented model-visible candidate

```json
{
  "task": "<one concise selection instruction>",
  "source": {
    "document": {
      "children": [
        {
          "alias": "t1",
          "kind": "table",
          "children": [
            {
              "alias": "r1",
              "kind": "row",
              "section_role": "<present only when non-null>",
              "row_role": "<present only when non-null>",
              "values": [
                {
                  "alias": "v1",
                  "meaning": "<column meaning or visible label or compact value type>",
                  "value": "<exact authoritative literal>",
                  "type": "<compact readable value type>",
                  "label": "<present only when non-null and distinct from meaning>"
                }
              ]
            }
          ]
        }
      ]
    }
  },
  "type_cards": [
    {
      "alias": "T1",
      "meaning": "<exact Pack-owned short_meaning>",
      "distinctions": [
        {
          "against": "<local visible type alias or readable external concept>",
          "rule": "<exact Pack-owned rule>"
        }
      ],
      "unclassified_when": "<exact Pack-owned ambiguity_rule>"
    }
  ],
  "choices": [
    {
      "alias": "A",
      "return_id": "<exact canonical option_id>",
      "type": "T1",
      "bindings": [
        "<role_id>=<value or structural alias>"
      ]
    }
  ],
  "unclassified": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

`alias` on a choice is display-only. The strict response schema continues to
require the exact `return_id` as `typed_option_id`; aliases are never accepted
as canonical Choice values.

Hierarchy levels absent from exact Evidence Bundle lineage are omitted.
Text-segment and evidence-group nodes use the same recursive structural shape.

## Representative frozen typed case

This readable projection is synthetic and repository-safe:

```json
{
  "task": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.",
  "source": {
    "document": {
      "children": [
        {
          "alias": "t1",
          "kind": "table",
          "children": [
            {
              "alias": "r1",
              "kind": "row",
              "values": [
                {
                  "alias": "v1",
                  "meaning": "amount",
                  "value": "-120.5000",
                  "type": "decimal"
                },
                {
                  "alias": "v2",
                  "meaning": "currency",
                  "value": "RUB",
                  "type": "currency"
                },
                {
                  "alias": "v3",
                  "meaning": "as_of_date",
                  "value": "2026-03-01",
                  "type": "date"
                },
                {
                  "alias": "v4",
                  "meaning": "description",
                  "value": "Cash balance",
                  "type": "text"
                }
              ],
              "row_role": "fact_candidate"
            }
          ]
        }
      ]
    }
  },
  "type_cards": [
    {
      "alias": "T1",
      "meaning": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "distinctions": [
        {
          "against": "T2",
          "rule": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
        },
        {
          "against": "cash movement",
          "rule": "A movement is an event over time; this type is a state at one reporting date."
        }
      ],
      "unclassified_when": "Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context."
    },
    {
      "alias": "T2",
      "meaning": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "distinctions": [
        {
          "against": "T1",
          "rule": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
        },
        {
          "against": "gate2 calculated aggregate",
          "rule": "This type preserves a total printed by the source; a value calculated by Gate 2 is never this type."
        }
      ],
      "unclassified_when": "Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total."
    }
  ],
  "choices": [
    {
      "alias": "A",
      "return_id": "financial-typed-option:744e3c95321e39b5f068c13cb76c72ae",
      "type": "T2",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "printed_label_evidence_ref=r1",
        "source_label=v4",
        "statement_scope=r1"
      ]
    },
    {
      "alias": "B",
      "return_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f",
      "type": "T1",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "statement_scope=r1"
      ]
    }
  ],
  "unclassified": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

This implemented candidate is 2,653 minified UTF-8 bytes versus 9,638 bytes for
the current packet. With the unchanged Prompt and response format, the
repository estimator is 1,047 versus 2,937 tokens.

## Private alias receipt

The alias receipt is never part of the model message:

```json
{
  "schema_version": "broker_reports_gate2_financial_semantic_slim_alias_receipt_v1",
  "policy_version": "broker_reports_gate2_llm_semantic_context_transition_v1",
  "context_contract_identity": "broker_reports_gate2_llm_semantic_context_v1",
  "active_packet_hash": "<exact current packet hash>",
  "slim_view_hash": "<hash of exact model-visible Slim View>",
  "value_aliases": {
    "v1": "<exact source_value_ref>"
  },
  "structural_aliases": {
    "t1": {
      "kind": "table",
      "association_ref": null,
      "page_ref": null,
      "table_ref": "<exact table_ref>",
      "row_ref": null,
      "cell_ref": null,
      "text_segment_ref": null
    },
    "r1": {
      "kind": "row",
      "association_ref": "<exact association_ref>",
      "page_ref": null,
      "table_ref": "<exact table_ref>",
      "row_ref": "<exact row_ref>",
      "cell_ref": null,
      "text_segment_ref": null
    }
  },
  "type_aliases": {
    "T1": "<exact input_type_id>"
  },
  "choice_aliases": {
    "A": "<exact option_id>"
  },
  "evidence_only_source_refs": [
    "<omitted deterministic reference refs>"
  ],
  "evidence_only_aliases": {
    "<exact deterministic reference ref>": "r1"
  },
  "choice_role_bindings": {
    "A": [
      {
        "role_id": "<exact role_id>",
        "source_value_ref": "<exact source_value_ref>"
      }
    ]
  },
  "provider_calls_total": 0,
  "integrity_hash": "<hash of all preceding fields>"
}
```

The current synthetic example produces:

- Slim View hash
  `f4b285a4d9e6f474dd0c4eec25bd8bd86784984d9f4167ae5092e4f201e4ed1c`;
- alias-receipt integrity
  `ab0603213864a3395f96958017af0146e39a1abb325eae78d8216f1e9aaf156f`.

## Deterministic construction rules

1. Build and validate the current full packet exactly as today.
2. Assign aliases in canonical source/card/option order.
3. Group values only by existing Evidence Bundle association and lineage.
4. Never infer a missing hierarchy level or semantic label.
5. Omit a visible-context key only when the authoritative value is null.
6. Display each non-deterministic authoritative literal exactly once.
7. Keep a compact readable value type beside each literal.
8. Render deterministic-reference binding targets as the resolved structural
   alias; retain each exact ref in the Typed Option and role-specific receipt.
9. Preserve exact Pack meanings, distinctions and ambiguity rules.
10. Preserve each exact option ID and the current unclassified reasons.
11. Hash the candidate view and alias receipt.
12. Fail closed on any non-bijective value/type/choice/structural mapping,
    missing role target, duplicate alias or tampered content.

## Mapping invariants

```text
displayed value alias
  ↔ one exact Evidence Bundle source value

displayed structural alias
  ↔ one exact association/lineage group

code-only deterministic reference
  → one displayed structural alias
  + exact role/source-ref binding in the private receipt

displayed type alias
  ↔ one exact Pack input_type_id

displayed return_id
  = one exact compiled typed_option_id
  → exact original role bindings
  → unchanged expansion/validation/materialization

unclassified reason
  → unchanged canonical unclassified Choice
  → complete Evidence Bundle retention
```

## Explicitly retained outside the model view

- global source/package/document/scope refs;
- exact page/table/row/cell/text-segment refs;
- provenance and evidence refs;
- deterministic reference source values;
- complete required/optional role schemas;
- compilation and materializability receipts;
- Pack/Registry identities and hashes;
- packet/view/alias hashes;
- expected answers;
- provider metadata;
- exact replay artifacts.

## GOAL 1 implementation evidence

The non-active implementation proves:

- all 10 frozen current packet hashes and byte counts remain exact;
- aliases are deterministic and value/type/choice/structural mappings are
  bijective;
- every semantic literal and available non-null metadata is preserved once;
- every displayed binding resolves to the exact compiled option binding;
- candidate and receipt tampering fail closed;
- repository-safe rendering contains counts and hashes only;
- active request construction still consumes only `packet.payload`;
- provider calls and stage mutations are zero;
- no second builder, Slim module or alternative Choice schema exists.

| Case | Current bytes | Implemented Slim bytes | Current estimator | Slim estimator |
| --- | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 9,638 | 2,653 | 2,937 | 1,047 |
| `syn_successor_v2_unique_printed_total` | 9,905 | 2,651 | 3,004 | 1,047 |
| `syn_successor_v2_multiple_compatible` | 4,246 | 816 | 1,393 | 488 |
| `syn_successor_v2_no_registry_type` | 9,770 | 2,648 | 2,970 | 1,046 |
| `syn_successor_v2_missing_discriminator` | 9,145 | 2,549 | 2,797 | 1,017 |
| `syn_successor_v2_detail_vs_subtotal` | 3,822 | 751 | 1,278 | 468 |
| `syn_successor_v2_adjacent_equal` | 3,724 | 747 | 1,253 | 467 |
| `syn_successor_v2_adjacent_fx` | 4,066 | 820 | 1,348 | 489 |
| `syn_successor_v2_optional_missing` | 9,779 | 2,651 | 2,973 | 1,047 |
| `syn_successor_v2_forbidden_neighbour` | 9,875 | 2,652 | 2,997 | 1,047 |
| **Total** | **73,970** | **18,938** | **22,950** | **8,163** |

The view-byte reduction is 74.4%. The analysis-only repository-estimator
reduction is 64.4%; Prompt, model and current Choice are exact-equal, and only
the user-message view changes.

Validation receipt:

- focused packet, architecture, qualification and evidence tests:
  `59 passed in 62.02s`;
- full service suite: `1853 passed, 20 skipped, 5 warnings in 416.77s`;
- focused Ruff validation: passed;
- 10 JSON examples parsed, 61 relative documentation links resolved and
  repository-safe privacy scan returned zero findings;
- `git diff --check`: passed.

Semantic sufficiency cannot be proven by unit tests. A later separately
authorized provider qualification must pass two-case smoke before the full
benchmark, and runtime activation remains a separate decision.

The immediate next GOAL is not provider qualification. GOAL 2 must first
create and prove the separate non-active local-alias Choice candidate so the
complete model-visible request can remove exact `return_id`.

## Research evidence

See the
[field-by-field redundancy audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_SEMANTIC_PACKET_REDUNDANCY_AUDIT.report.md)
for classifications, risk ownership and all 10 per-case size measurements.
