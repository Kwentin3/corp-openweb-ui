# Broker Reports Gate 2 Financial Semantic Slim View

Status: `GOAL3_LINTED_NOT_ACTIVE`

Date: 2026-07-28

This document originated as the model-context research design and now records
the GOAL 1-3 non-active implementation. It changes no active runtime contract,
Prompt, Semantic Pack, Candidate Compiler, Typed Option, canonical Choice,
validator, materializer, Evidence Bundle or provider adapter.

## Contract relationship

The
[LLM Semantic Context v1](../contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the closed final boundary for the complete model-visible request.

Slim View v2 is implemented inside the existing V6 packet owner and remains
non-active. Canonical option IDs are absent from it. The separate versioned
[Local Choice v1](../contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
uses request-local response aliases and normalizes them back to the unchanged
current Choice.

## Purpose

Present the existing V6 semantic decision surface in a shorter human-readable
form while keeping all technical identity, provenance, binding and replay
complexity code-owned.

The model still performs one operation:

```text
select one visible local choice, or select unclassified
```

## Authority

The only permitted construction owner remains
`Gate2FinancialSemanticV6PacketFactory.create` in the current V6 packet
module. The GOAL 1/2 implementation computes the non-active candidate and
alias receipt inside that owner.

Forbidden:

- a second packet builder;
- a second Candidate Compiler;
- a second active/canonical model-choice schema or hidden schema rewrite;
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

The non-active strict response schema accepts `alias` as local `choice`.
Backend normalization resolves it through the private receipt before the
unchanged canonical Choice and expansion authorities run.

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

This implemented candidate is 2,513 minified UTF-8 bytes versus 9,638 bytes for
the current packet. With the unchanged Prompt and Local Choice response
format, the repository estimator is 921 versus 2,937 tokens.

## Private alias receipt

The alias receipt is never part of the model message:

```json
{
  "schema_version": "broker_reports_gate2_financial_semantic_slim_alias_receipt_v2",
  "policy_version": "broker_reports_gate2_llm_semantic_context_local_choice_v1",
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
  `ac9c598bcb5ed94b7af566c7b16e2f07ae22edf6025137fe6c2b7bf1e7541ce8`;
- alias-receipt integrity
  `997b90920c63c5d79272269f6d24cc5232f2d611855a951d6592b78fd03a9989`.

## Deterministic construction rules

1. Build and validate the current full packet exactly as today.
2. Assign source/card aliases in canonical order. Assign choice aliases in
   canonical option order unless code supplies one exact complete permutation;
   then the visible records and private mapping move together.
3. Group values only by existing Evidence Bundle association and lineage.
4. Never infer a missing hierarchy level or semantic label.
5. Omit a visible-context key only when the authoritative value is null.
6. Display each non-deterministic authoritative literal exactly once.
7. Keep a compact readable value type beside each literal.
8. Render deterministic-reference binding targets as the resolved structural
   alias; retain each exact ref in the Typed Option and role-specific receipt.
9. Preserve exact Pack meanings, distinctions and ambiguity rules.
10. Keep each exact option ID only in the private alias receipt; preserve the
    current unclassified reasons model-visible.
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

displayed choice alias
  ↔ one exact compiled typed_option_id in the private receipt
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

## GOAL 1-3 implementation evidence

The non-active implementation proves:

- all 10 frozen current packet hashes and byte counts remain exact;
- aliases are deterministic and value/type/choice/structural mappings are
  bijective;
- every semantic literal and available non-null metadata is preserved once;
- every displayed binding resolves to the exact compiled option binding;
- all 10 active Choice schema hashes remain exact;
- exact messages plus Local Choice response schema contain zero opaque IDs;
- local typed/unclassified answers have exact canonical
  expansion/materialization parity and unchanged unclassified retention;
- candidate and receipt tampering fail closed;
- repository-safe rendering contains counts and hashes only;
- active request construction still consumes only `packet.payload`; the
  separate candidate profile requires a passed lint receipt;
- provider calls and stage mutations are zero;
- one separate versioned Local Choice candidate exists inside the current
  Choice factory; it is non-active and introduces no second factory.

| Case | Current bytes | Implemented Slim bytes | Current estimator | Local estimator |
| --- | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 9,638 | 2,513 | 2,937 | 921 |
| `syn_successor_v2_unique_printed_total` | 9,905 | 2,511 | 3,004 | 921 |
| `syn_successor_v2_multiple_compatible` | 4,246 | 816 | 1,393 | 448 |
| `syn_successor_v2_no_registry_type` | 9,770 | 2,508 | 2,970 | 920 |
| `syn_successor_v2_missing_discriminator` | 9,145 | 2,409 | 2,797 | 891 |
| `syn_successor_v2_detail_vs_subtotal` | 3,822 | 751 | 1,278 | 428 |
| `syn_successor_v2_adjacent_equal` | 3,724 | 747 | 1,253 | 427 |
| `syn_successor_v2_adjacent_fx` | 4,066 | 820 | 1,348 | 449 |
| `syn_successor_v2_optional_missing` | 9,779 | 2,511 | 2,973 | 921 |
| `syn_successor_v2_forbidden_neighbour` | 9,875 | 2,512 | 2,997 | 921 |
| **Total** | **73,970** | **18,098** | **22,950** | **7,247** |

The complete messages-plus-response-schema projection is 89,220 current bytes
versus 26,404 candidate bytes, a 70.4% reduction. The deterministic local
repository-estimator reduction is 68.4%; Prompt text is unchanged, while the
non-active user view and response schema change together.

GOAL 3 adds
`Gate2FinancialSemanticV6ContextLinterFactory.create` after packet, Prompt and
Choice construction. It checks the complete candidate request and seals a
receipt before the existing request builder may construct the version-pinned
candidate request:

```text
OPAQUE_IDS: ZERO
DUPLICATE_LITERALS: ZERO
NULL_FIELDS: ZERO
UNMAPPED_ALIASES: ZERO
ORPHAN_ALIASES: ZERO
ALIAS_COLLISIONS: ZERO
SEMANTIC_LITERAL_COVERAGE: 100_PERCENT
STRUCTURAL_HIERARCHY: VALID
EXACT_OPTION_COVERAGE: COMPLETE
ALIAS_RECEIPT_INTEGRITY: VALID
EXACT_REPLAY: 10_OF_10
LOCAL_TOTAL_MATERIALIZATION: 32_OF_32
PROVIDER_CALLS: ZERO
```

The linter does not repair input, create a second packet, compile options or
assemble provider form data. `Gate2OpenWebUIRequestBuilder.build` remains the
sole request constructor and its candidate profile rejects a missing or
tampered receipt before transport. The profile is present in the rebuilt
closed-world bundles without importing the qualification-only linter module.

Validation receipt:

- focused linter, architecture and budget tests:
  `47 passed in 27.22s`;
- extended V6 regression contour:
  `147 passed in 290.63s`;
- full service suite:
  `1866 passed, 20 skipped, 5 warnings in 449.17s`;
- focused Ruff validation: passed;
- 11 JSON examples parsed, 71 relative documentation links resolved and
  repository-safe privacy scan returned zero findings;
- all three generated bundles were rebuilt from maintained source; the Gate 2
  domain bundle loaded in an isolated process and rejected a missing lint
  receipt before transport;
- `git diff --check`: passed.

Semantic sufficiency cannot be proven by unit tests. GOAL 4 is the separately
authorized bounded Nano/Haiku Slim diagnostic; it must preserve exact
input/output evidence and pass the required two-case Haiku smoke before any
full benchmark. Runtime activation remains a separate later decision.

## Research evidence

See the
[field-by-field redundancy audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_SEMANTIC_PACKET_REDUNDANCY_AUDIT.report.md)
for classifications, risk ownership and all 10 per-case size measurements.
