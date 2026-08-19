# Broker Reports G5.54 — Adaptive Packaging KISS Audit & Real Purchase Recovery

Date: `2026-08-14`

Status: `PROVEN`

## Outcome

Both ordered phases completed without an architecture or runtime change.

Proven terminals:

- `ADAPTIVE_PACKAGING_ACCOUNTING_PROVEN`;
- `SMART_CHUNK_CONTRACT_HEALTHY`;
- `REAL_PURCHASE_SOURCE_CONTEXT_LOCALIZED`;
- `ONE_REAL_PURCHASE_FACT_PROVEN`;
- `ORDINARY_GATE4_GATE5_REPLAY_PROVEN`.

The observed `140 chunks` are 140 final Gate 3 model contexts, not 140
internal Canonical units and not 140 fragments of the repaired table. A full
document batch would submit one type request per context and at most one role
request per context. G5.54 did not execute that batch; it executed one selected
context with exactly two submissions.

## Phase A — exact packaging accounting

The same document and the same `60,000` character budget were reconstructed
through `Gate3StructuralChunkFactory.create` before and after G5.52.

| Metric | Before G5.52 | After G5.52 |
| --- | ---: | ---: |
| complete projection chars | 231,703 | 444,117 |
| structural units | 205 | 205 |
| target-bearing units | 140 | 140 |
| Canonical targets | 140 nodes | 66 nodes + 2,456 rows + 16,538 cells |
| table units | 0 | 74 |
| final contexts | 4 `structural_blocks` | 66 `structural_blocks` + 74 `whole_table` |
| maximum context chars | 59,174 | 10,340 |
| coverage | exact | exact |

G5.52 therefore changed addressability, not the count of source structural
units. The previous fallback exposed 140 coarse node targets and allowed them
to be packed into four large contexts. The repaired Canonical exposes 74 real
table boundaries; the active contract keeps every fitting table whole and does
not cross a table boundary.

All 74 tables fit below the budget and all 74 remain one `whole_table` each.
The exact G5.52 repaired table appears in exactly one chunk: 7,678 characters,
289 target mappings, no row split, no repeated header and no target loss or
duplication. Row/cell identities remain mappings and provenance inside that one
context; they do not create requests.

The cost distinction is explicit:

| Metric | Before repair full pass | Current bounded purchase proof |
| --- | ---: | ---: |
| Canonical targets | 140 | 19,060 in the repaired document; 294 in the selected purchase document |
| available semantic contexts | 4 | 140 in the repaired document; 1 selected |
| actual provider calls | 8 | 2 |
| maximum input tokens per call | not retained by the earlier safe receipt | 9,310 |
| total input tokens | not retained by the earlier safe receipt | 13,441 |
| tables kept whole | 0 | 74/74 in the repaired document |

A new full-document pass over the repaired document was not executed. Under
the current batch contract it would require 140 type calls and up to 140 role
calls. The `140` count therefore is not a harmless internal counter, but it
also does not automatically become 140 calls in a bounded indexed replay. This
cost boundary is now explicit: a future full semantic republication of this
document is a strategic review point, not an authorization to merge tables or
add a second router. G5.54 needed one source-bound indexed context and used two
calls.

The complete repaired document is 444,117 characters, so `whole_document`
would violate the fixed budget. No fragmentation defect exists and no KISS fix
to the chunker is justified.

## Phase B — real purchase recovery

The existing authenticated case catalog, current Canonical bindings, persisted
FinancialAnnotationsV2 and exact target mappings were used as the index. No
keyword scanner, new reader or semantic router was added.

The catalog contains 28 existing `SECURITY_PURCHASE` annotations. Two current
Canonical documents provide 13 Role-Pack-complete purchases on exact
`table_cell` targets; every target maps exactly once into one
`whole_document` context. The smaller source-bound context was selected:

- 14,088 model-view characters;
- 294 exact target mappings;
- current Canonical version;
- identical selected document, canonical version, model-view SHA-256 and
  target count in the source store and the G5.52 working copy.

One clean demand-bounded Gate 3 execution through
`Gate3ChunkBatchLabelingFactory.create` produced:

- 5 demanded `SECURITY_PURCHASE` annotations;
- 5 Role-Pack-complete annotations;
- 2 provider submissions: one type pass and one role pass;
- 13,441 input tokens and 1,822 output tokens;
- zero retry, repair, fallback or persistence;
- unchanged ArtifactStore.

The clean result is not a partial chunk result: the selected document has one
and only one `whole_document` chunk, selection mode is `full_document` and
document status is `complete`. It was therefore persisted through the ordinary
FinancialAnnotationsV2 owner in an isolated local proof store after the
provider-step unchanged-store assertion.

An initial downstream attempt in the G5.52 working store correctly failed
closed with `gate4_cache_stale`: the separately repaired dividend document has
no current complete Gate 3 sidecar. The exact purchase document has identical
Canonical version, model-view SHA-256 and target count in the source proof
store, whose four-document case is current. The strict replay there produced:

- Gate 4 materialized the new sidecar into 5 `SECURITY_PURCHASE` facts;
- all 5 purchases are `role_complete` and target exact `table_cell` identities;
- ordinary Gate 4 `rebuild_case` returned
  `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`, 170 facts and all 5 new fact IDs;
- Gate 5 assessed those same 5 new fact IDs as `ready`;
- terminal `SOURCE_FACT_ASSERTIONS_PRESERVED` was returned;
- stored financial-event relations remain zero.

The five required-role value sets equal the previous five purchase facts.
Consequently the Gate 5 security assessment remains exactly 48 facts: 33
`ready` and 15 `source_evidence_insufficient`, with identical insufficiency
reason counts. Acquisition-basis coverage delta and security client-review
finding delta are both zero.

One limitation is explicit. Demand-scoped full-document publication contains
only the requested label, so the selected document changed from 21 prior facts
to 5 purchase facts; 16 unrelated commission/charge facts are absent from the
latest local proof-sidecar projection. This does not affect the purchase proof
or security assessment, but it prevents treating G5.54 as a product-sidecar
replacement or activation proof. Any product publication must preserve or
re-run the complete intended financial-label scope; G5.54 does neither.

The G5.52 repaired dividend/withholding table was not relabeled as a purchase.
Phase B correctly localized a different exact table document whose current
source evidence already proves purchases.

## Owner and guardrail evidence

Factory routing remains unchanged:

- `gate3_structural_chunking.py:54` owns final packaging;
- `gate3_structural_chunking.py:88` owns the `whole_document` budget decision;
- `gate3_structural_chunking.py:198` and `:328` preserve table boundaries and
  whole-table behavior;
- `gate4_financial_case_cache.py:153`, `:158` and `:183` own ordinary Gate 4
  materialization;
- `gate5_deterministic_source_fact_consumption.py:95`, `:105` and `:144` own
  deterministic Gate 5 assessment from Gate 4.

The pre-call owner-path seam completed with `31 passed`. Final relevant
regression and privacy checks are recorded in the safe receipt.

## KISS and stop

No chunker, threshold, prompt, parser, reader, router, dictionary, schema,
provider client or persistence behavior changed. No retry, best-of-N, manual
semantic repair, proximity relation, row/cell deletion, partial-chunk
persistence or Gate 4 bypass was used. The new sidecar and cache rebuild exist
only in local private proof stores; no product route was activated.

Observed guardrails: Gate 5 Canonical reads = 0, Gate 5 source-provider calls =
0, Gate 4 provider calls = 0 and projection changes = 0.

G5.54 stops here. It does not authorize activation, declaration release,
commit, push, PR or another Gate goal.
