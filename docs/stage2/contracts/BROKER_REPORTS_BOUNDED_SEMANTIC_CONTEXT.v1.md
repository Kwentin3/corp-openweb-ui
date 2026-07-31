# Broker Reports bounded semantic context contract v1

Status: inactive proof contract
Schema: `broker_reports_bounded_semantic_context_v1`

## Responsibility

`Gate2BoundedSemanticContextFactory` is the sole deterministic builder of the
model-visible context used by the inactive same-source Type-First proof. It is
a subordinate capability of `current_source_fact_orchestration`; it is not a
product owner or entrypoint.

The builder may copy only source-bound data already present in supplied Gate 2
packages and their existing deterministic financial source package. It must
not receive a Type Card, inspect a canonical type, build a shortlist, use
financial regex/synonyms, call a provider, or create a canonical fact.

## Model-visible payload

Each source unit contains exactly these layers:

1. `document_context`: document type/role/title, issuer role, reporting period,
   statement scope, account type, and language when present.
2. `section_context`: bounded section path, table title, group labels, and
   related notes.
3. `table_context`: raw headers and normalized column roles together, plus
   header confidence and reconstruction quality.
4. `target_unit`: raw cells, mechanically normalized values, visible labels,
   row role, and row ordinal.
5. `local_structural_context`: explicit parent rows, at most two preceding and
   two following rows from the same document/table, linked footnotes, and
   continuation.
6. `quality_and_restrictions`: input/representation modes, truncation,
   missing facets, unresolved issues, interpretation permission, source
   completeness, and restriction codes.

Source refs, canonical type IDs, typed option IDs, sealed role bindings, and
customer identity are not model-visible.

## Selection and budgets

Selection uses only document identity, table identity, row ordinal, and
explicit parent/footnote/continuation links. Unrelated documents or tables are
excluded even when their text looks similar.

Budgets are: two neighbors per side, two parents, four group labels, four
footnotes/notes, section depth six, 2,000 characters per text value, 24,000
JSON characters, and 32,000 UTF-8 bytes per context. Any loss caused by a
budget sets `context_truncated=true`; typed output then fails closed.

## Type requirements and guard

Type Card `required_context_facets` are projected generically from the sole
Financial Semantic Pack's required roles, identity roles, date/period rule,
and currency/unit rule. `context_disqualifiers` are the Pack's ambiguity
guidance. Pack bytes and canonical meaning are unchanged.

After a simulated response, `Gate2ContextSufficiencyGuard` checks context
integrity, exact source-package binding, required facets, truncation,
interpretation permission, and blocking unresolved issues. A typed result is
allowed only when there is one plausible type, one exact restored option, a
sufficient context decision, and acceptance by the existing validator.

Otherwise the code-owned proof reason is
`INSUFFICIENT_SEMANTIC_CONTEXT`; the existing validator/materializer receives
the safe `unclassified_financial_input` choice. No second validator,
materializer, replay owner, or product route is introduced.

## Ablation invariant

The deterministic A-F ablation sequence is values only, normalized roles,
raw headers, section/table, local structural context, and full bounded context.
Removing a layer must never turn insufficient into sufficient, ambiguity into
a unique typed result, or unclassified into typed. Values-only and
normalized-roles-only typed totals must remain zero.
