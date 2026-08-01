# Broker Reports Managed Document Coverage v1

Effective date: 2026-08-01
Status: inactive DOC2 proof contract

This contract reconciles every pre-loss PDF source observation with exactly one
coverage entry. It does not activate a product route and does not alter Managed
Document v1.

Allowed observation kinds are `PAGE_BOUNDARY`, `TEXT_BLOCK`, `TEXT_LINE`,
`TABLE_REGION`, `VALIDATED_LOGICAL_TABLE`, `VISUAL_REGION`,
`FULL_PAGE_VISUAL`, `UNSUPPORTED_REGION`, `PARSER_FAILURE`, and
`UNKNOWN_OBSERVATION`.

Allowed dispositions are `REPRESENTED_BY_BLOCK`, `REPRESENTED_BY_ANCHOR`,
`REPRESENTED_BY_TABLE`, `DUPLICATE_SUPPRESSED`, `KNOWN_LOSS`,
`BLOCKED_AT_SOURCE`, and `UNRESOLVED`.

An accepted readable build requires all of the following:

- the inventory and coverage entries are bijective by `observation_id`;
- `unresolved_total = 0`;
- `unaccounted_context_loss_total = 0`;
- `invented_source_content_total = 0`;
- `blocked_at_source_total = 0`;
- the receipt and observation inventory pass their canonical SHA-256 seals.

`KNOWN_LOSS` is accepted only when the Managed Document contains a source-bound
block or anchor and the DOC1 loss ledger describes the missing interpretation or
structure. `BLOCKED_AT_SOURCE` is terminal and cannot produce an accepted
Managed Document.

`REPRESENTED_BY_TABLE` additionally requires a source-bound `table_ids` entry
and a deterministic `mapping_method`; every other disposition must leave those
fields empty and null respectively.

The normative JSON shape is
`BROKER_REPORTS_MANAGED_DOCUMENT_COVERAGE.v1.schema.json`. Private inventories
and receipts remain outside Git. Only aggregate, privacy-scanned summaries may
be committed.
