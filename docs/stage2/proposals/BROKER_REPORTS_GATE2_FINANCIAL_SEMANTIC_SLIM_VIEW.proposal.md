# Broker Reports Gate 2 Financial Semantic Slim View

Status: `PROPOSED_NOT_IMPLEMENTED_NOT_ACTIVE`

Date: 2026-07-28

This proposal is the GOAL 2 design output. It changes no runtime contract,
Prompt, Semantic Pack, Candidate Compiler, Typed Option, canonical Choice,
validator, materializer, Evidence Bundle, provider adapter or model output.

## Contract relationship

The later
[LLM Semantic Context v1](../contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the closed final boundary for the complete model-visible request.

This proposal remains the transition design for a first non-active view. It
keeps exact canonical option IDs because the current V6 Choice requires them,
so it does not claim full Context v1 conformance. Replacing those IDs with
local response aliases is a separate versioned Choice boundary and must not be
folded into the Slim View implementation.

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
module. A future implementation may compute a non-active candidate and alias
receipt inside that owner.

Forbidden:

- a second packet builder;
- a second Candidate Compiler;
- an alternative model-choice schema;
- provider-adapter semantic rewriting;
- model-generated refs or bindings;
- deletion of opaque IDs from the Evidence Bundle;
- runtime activation in the implementation PR.

## Proposed model-visible contract

```json
{
  "task": "<one concise selection instruction>",
  "source": {
    "document": "current document",
    "groups": [
      {
        "alias": "g1",
        "kind": "table row | text segment | other readable existing kind",
        "location": {
          "page": "<local alias, only when present>",
          "table": "<local alias, only when present>",
          "row": "<local alias, only when present>",
          "text_segment": "<local alias, only when present>"
        },
        "section_role": "<present only when non-null>",
        "row_role": "<present only when non-null>",
        "values": [
          {
            "alias": "v1",
            "meaning": "<column meaning or visible label or compact value type>",
            "value": "<exact authoritative literal>",
            "type": "<compact readable value type>",
            "label": "<present only when non-null>"
          }
        ]
      }
    ]
  },
  "type_cards": [
    {
      "alias": "type1",
      "name": "<exact input_type_id>",
      "meaning": "<exact Pack-owned short_meaning>",
      "distinctions": [
        {
          "against": "<local visible type alias or exact external type name>",
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
      "type": "type1",
      "bindings": [
        "<role_id>=<value or group alias>"
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

## Representative frozen typed case

This readable projection is synthetic and repository-safe:

```json
{
  "task": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.",
  "source": {
    "document": "current document",
    "groups": [
      {
        "alias": "g1",
        "kind": "table row",
        "location": {
          "table": "table1",
          "row": "row1"
        },
        "row_role": "fact_candidate",
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
        ]
      }
    ]
  },
  "type_cards": [
    {
      "alias": "type1",
      "name": "cash_balance_snapshot_v1",
      "meaning": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "distinctions": [
        {
          "against": "type2",
          "rule": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
        },
        {
          "against": "cash_movement",
          "rule": "A movement is an event over time; this type is a state at one reporting date."
        }
      ],
      "unclassified_when": "Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context."
    },
    {
      "alias": "type2",
      "name": "printed_financial_metric_v1",
      "meaning": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "distinctions": [
        {
          "against": "type1",
          "rule": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
        },
        {
          "against": "gate2_calculated_aggregate",
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
      "type": "type2",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "printed_label_evidence_ref=g1",
        "source_label=v4",
        "statement_scope=g1"
      ]
    },
    {
      "alias": "B",
      "return_id": "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f",
      "type": "type1",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "statement_scope=g1"
      ]
    }
  ],
  "unclassified": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

This measured candidate is 2,763 minified UTF-8 bytes versus 9,638 bytes for
the current packet. With the unchanged Prompt and response format, the
repository estimator is 1,077 versus 2,937 tokens.

## Private alias receipt

The alias receipt is never part of the model message:

```json
{
  "source_packet_hash": "<exact current packet hash>",
  "slim_view_hash": "<hash of exact model-visible Slim View>",
  "value_aliases": {
    "v1": "<exact source_value_ref>"
  },
  "group_aliases": {
    "g1": "<exact association or lineage ref>"
  },
  "lineage_aliases": {
    "table1": "<exact table_ref>",
    "row1": "<exact row_ref>"
  },
  "type_aliases": {
    "type1": "<exact input_type_id>"
  },
  "choice_aliases": {
    "A": "<exact option_id>"
  },
  "evidence_only_source_refs": [
    "<omitted deterministic reference refs>"
  ],
  "integrity_sha256": "<hash of all preceding fields>"
}
```

The current synthetic example produces:

- Slim View hash
  `534478dd5679044dd241366a9d1ea44c28d5d09949594873792c691567d92ae7`;
- alias-receipt integrity
  `f13df561b0933db9751d53c65d68eb8cf6beaaca7e217fe04ac03151037cf43a`.

## Deterministic construction rules

1. Build and validate the current full packet exactly as today.
2. Assign aliases in canonical source/card/option order.
3. Group values only by existing Evidence Bundle association and lineage.
4. Never infer a missing hierarchy level or semantic label.
5. Omit a visible-context key only when the authoritative value is null.
6. Display each non-deterministic authoritative literal exactly once.
7. Keep a compact readable value type beside each literal.
8. Render deterministic-reference binding targets as the resolved group alias;
   retain exact refs in the Typed Option and receipt.
9. Preserve exact Pack meanings, distinctions and ambiguity rules.
10. Preserve each exact option ID and the current unclassified reasons.
11. Hash the candidate view and alias receipt.
12. Fail closed on any non-bijective, missing, duplicate or tampered mapping.

## Mapping invariants

```text
displayed value alias
  ↔ one exact Evidence Bundle source value

displayed group alias
  ↔ one exact association/lineage group

displayed location alias
  ↔ one exact existing page/table/row/text-segment ref

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

## Implementation gate

The next implementation PR is non-active and zero-call. It must prove:

- current packet payload/hash byte parity;
- alias bijection and stable ordering;
- exact literal and hierarchy coverage;
- binding/type/option parity;
- unchanged Choice schema hash;
- unchanged unclassified retention;
- exact replay/materialization;
- privacy-safe rendering;
- no second builder or alternative choice schema.

Semantic sufficiency cannot be proven by unit tests. A later separately
authorized provider qualification must pass two-case smoke before the full
benchmark, and runtime activation remains a separate decision.

## Research evidence

See the
[field-by-field redundancy audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_SEMANTIC_PACKET_REDUNDANCY_AUDIT.report.md)
for classifications, risk ownership and all 10 per-case size measurements.
