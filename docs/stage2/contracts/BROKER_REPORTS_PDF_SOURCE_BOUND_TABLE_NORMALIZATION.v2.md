# Broker Reports PDF Source-Bound Table Normalization v2

Status: `PROPOSED / INACTIVE`

This candidate contract records the intended owner boundary for Issue #317. It
does not supersede v1, activate a product route, or authorize imports from the
current Pipe, Canonical normalizer, actions, or generated bundles.

## Scope of this slice

`LogicalRowTableFactory` is the candidate sole owner of logical table identity,
ordered rows, logical columns, source-bound title/header retention, and
cross-page continuation. In this inactive slice it consumes only the existing
normalized PDF text-layer projection and publishes only its existing recovery
result.

The owner does not decide financial meaning, create source values, mutate
Canonical, publish facts, or call a provider. `NormalizedTableProjection` and
Canonical integration remain outside this slice.

## Source authority

FullSource parser words and geometry remain authoritative. Every retained
title, header, body entry, and continuation fragment must point to those exact
source refs. A title or header cannot be discarded merely to make two fragments
geometrically compatible.

Exact word accounting is necessary but does not by itself prove table identity.
Every source word must still have exactly one table-entry or paragraph owner.

## Inactive source-bound scope input

The inactive `SourceBoundTableScopeFactory` produces a representation-only
receipt. It does not call or accept values directly from a provider transport.
The factory accepts a closed geometry-only proposal containing title boxes,
complete header-band boxes and body-anchor boxes. The host envelope is a
separate input. The binder first requires a whole FullSource payload accepted
by `validate_pdf_text_layer_payload`, then binds boxes to exact existing word
refs and to one existing table candidate through its contributing words.

The model cannot return text, word refs, candidate refs, table IDs or a
continuation decision. Runtime computes a receipt ref and the exact proposal
hash. Title, header, body-anchor and cross-table word overlap is rejected. A
missing or non-unique candidate remains inspectable `PARTIAL`; the successful
receipt state is only `BOUND`, never `COMPLETE`, and array order never resolves
ambiguity.

`source_sha256`, page identity and the full raster manifest are the trusted host
envelope. Normalized boxes are converted to PDF points only by
`PdfTableLocatorProjectionFactory`, which validates the full-page identity,
page bbox, rotation, resize flags and source-to-pixel transform. The binder
also ties the supplied source SHA to the validated payload's source checksum
ref and rejects duplicate or foreign projection refs.

The full-page raster manifest is a trusted host-issued artifact at this seam.
This binder does not recompute its `manifest_hash` or bind private PNG bytes;
those proofs remain owned by `PdfTableRasterFactory` and the host artifact
boundary. It does require the manifest's PDF SHA, document and page identity to
match the validated FullSource input. It does not claim independent raster
authenticity.

The receipt has no `authoritative_structure` field and its checksum is not a
consumer authority. A future continuation consumer must bind and consume this
evidence within one owner call; accepting a caller-created ready scope or
rehashing a dataclass is forbidden.

`EMPTY_TEMPLATE`, `UNCERTAIN` and a proposed `EXPLAINER` classification are
always non-authoritative `PARTIAL` observations. They cannot delete, release or
exclude words. `EXPLAINER` does not decide financial relevance.

## Inactive same-call recovery input

`LogicalRowTableRecoveryRuntime.recover` retains its v1 signature and output.
The separate inactive `recover_with_source_bound_scopes` entrypoint accepts
only original geometry proposals plus the whole FullSource payload, source SHA,
page identity and full raster manifests. It invokes
`SourceBoundTableScopeFactory` itself and passes receipts only to private
recovery logic within the same call. A caller cannot submit a ready receipt or
scope dataclass.

A `PARTIAL` receipt, overlapping requests or a receipt-to-region conflict is an
inspectable issue and blocks continuation. It does not release source words or
fall back to an unreviewed join. LogicalRow remains the only continuation owner.
One model-authored `ABSENT` proposal is not proof of absence: exact refs prove
what was selected, not that no header exists. This slice therefore does not
install `ABSENT` as source-proven evidence and it cannot create a continuation
match. The legacy structural owner may still prove the same continuation from
independent evidence; otherwise the fragments remain inspectably ambiguous and
separate. Promoting absence requires an independent critic/adjudication slice.
`PRESENT` header groups must be the exact leading stack with retained body rows
below it. A conflict with independently proven header evidence is typed
`source_bound_table_scope_header_presence_conflict`, remains `PARTIAL`, and
does not authorize a join.

`ManagedPdfDocumentV2Factory` may coordinate that same entrypoint only through
its inactive additive `build_with_source_bound_scopes` method. The raw requests are
still bound inside `LogicalRowTableFactory`; the ManagedDocument builder never
accepts ready receipts. Both legacy `build` and the additive scoped method
invoke the existing FullSource owner exactly once from original bytes; no
public FullSource result input exists. The sealed v2 document carries recovered
rows, issues and word ownership. Only an actually accepted `PRESENT` leading
title/header/body partition adds a narrow reviewed evidence record containing
the same-call scope receipt ref, proposal/raster hashes and bound source-word
refs. Raw private receipt transport is not copied.

Rows classified through that evidence use `REVIEWED_SOURCE_BOUND`, never
`DETERMINISTIC_DERIVED` or `MODEL_PROPOSED`. Their direct text remains in the
FullSource word anchors.

A `BOUND` receipt alone is not role authority. `ABSENT`, `EMPTY`, `EXPLAINER`
and partial outcomes remain audit-only, contribute no private reviewed plan and
cannot relabel any title, header or data row. A model-only `ABSENT` remains an
inspectable `PARTIAL` ambiguity until independent evidence resolves it.

Public Managed v2 validation/sealing rejects invented reviewed evidence. The
same Managed builder call alone passes its exact recovered evidence plan to a
private sealing seam, which compares it before sealing.

## Fragment-local continuation rule

A right fragment may join one previous logical table only when all of the
following are true:

1. its page immediately follows the predecessor page;
2. the predecessor reaches the page bottom and the right fragment starts at
   the next page top under the configured source-geometry thresholds;
3. the fragments have compatible width and multi-column alignment;
4. the first fragment supplies a complete stable leading header stack with
   body support;
5. a right-side stable header stack, when present, repeats that full stack;
6. the predecessor is unique;
7. the right fragment has no new source-bound title.

A headerless fragment is a continuation candidate, not proof on its own. A
repeated header is retained as provenance but does not override a new title.
A new source-bound title is a hard table boundary even when grid and header are
otherwise identical.

Header evidence is structural and covers every leading header row, not the
first text row. Existing row roles, proven header coalescence, column evidence,
and body support may prove the stack. If a text-only fragment can be either a
header stack or body data and no source-bound header-presence evidence exists,
this inactive slice must not guess. It remains separate and `PARTIAL` with
`logical_table_continuation_header_ambiguous`. Exact `PRESENT` refs may prove a
leading stack. Exact refs selected under a single `ABSENT` proposal cannot prove
absence or authorize an autonomous join.

For a chain of three or more pages, the first fragment remains the stable header
authority. Each adjacent pair must independently satisfy the page-edge and grid
conditions.

## Fail-closed terminals

- One compatible predecessor: join the fragment.
- No compatible predecessor: keep a separate logical table.
- More than one compatible predecessor: keep a separate table, emit
  `logical_table_continuation_ambiguous`, and publish `PARTIAL` completeness.
- Header presence cannot be distinguished from text-only body rows: keep the
  fragment, emit `logical_table_continuation_header_ambiguous`, and publish
  `PARTIAL` completeness.

Ambiguity must not be silently resolved by iteration order, text deletion, or a
fallback continuation writer.

## Invariants

- This owner remains inactive until a separate controlled-cutover PR changes
  the current architecture authority and product graph.
- The active neutral grouping and mechanical continuation linker are unchanged
  by this slice.
- No broker, year, filename, language, or header dictionary participates.
- No model-authored text, cells, values, table identity, or facts are accepted.
- `LogicalRowTableFactory` makes the continuation decision; a later projection
  adapter may only carry that decision.
- Canonical must not repair or reinterpret this result.
- Any unresolved continuation is `PARTIAL` and therefore cannot support atomic
  fact publication.

## Focused controls

The inactive owner must prove at least:

- an adjacent, structurally proven headerless next-page fragment joins its
  unique predecessor;
- same-grid tables with a distinct source-bound title remain separate even
  when the column header repeats;
- the complete stable multi-row header stack participates in the decision;
- a text-only fragment without header-presence evidence is retained with an
  inspectable `PARTIAL` terminal rather than silently joined or discarded;
- a three-page edge-continuous chain becomes one logical table;
- multiple compatible predecessors produce an inspectable `PARTIAL` result;
- exact title/header source refs and total word ownership are preserved.

These controls are owner evidence only. They are not product activation,
full-document Canonical proof, financial-role proof, or release acceptance.
