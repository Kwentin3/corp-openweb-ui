# Broker Reports restricted-scope actual-corpus audit

Date: 2026-07-19

Status: completed

Workload fingerprint: `8bc80a70c4f228670dcf71acdd824389b63215308f377a9cfe8436c0fccdc9b7`

## Executive verdict

The current process is safe, but the blocked counts are not one homogeneous
engineering backlog.

- The canonical preparation path re-ran in `50.824279 s` and produced the exact
  accounting `928 = 667 + 194 + 67`: `602` text, `41` canonical-table and `24`
  neutral-structure packages; `194` noncanonical PDF candidates and `67` visual
  units remained explicit. Provider calls, retries and tokens were `0 / 0 / 0`.
- The `194` candidates are `194` non-overlapping physical regions, not `194`
  physical tables. There are `80` real table regions and `114` form or heading
  regions. Candidate duplicates, overlap pairs and shared word owners are all
  zero.
- Primary candidate classes are: `33` existing validated projections, `71`
  text/layout-complete regions with unresolved topology, and `90` false-positive
  table detections. The latter comprise structured form panels and `9`
  non-material section headings; they must be reclassified, not silently
  discarded.
- All `194` candidates retain complete private text/layout memory, but none of
  their candidate refs is in the accepted text packages. Across representations,
  `180` withholding-report candidates have a paired neutral XML equivalent. The
  only candidate-family-unique broker-report table debt is `14` regions.
- Of `67` blocked visual units, `51` have a same-page text/layout sibling, `10`
  are non-material images, and only `6` are material without a text sibling.
  Exact visual dedup reduces the latter to `5` unique scopes.
- One separately restricted broker document contains another `6` material
  visual-only table pages. They are intentionally outside the `928` Gate 2
  accounting because the document itself is not source-fact ready. Therefore the
  full restricted corpus has `11` unique material visual scopes needing
  visual-capable recovery: `5` from the current `67`, plus `6` document-level
  scopes.
- The `24` XML packages form one identifiable FNS 2-NDFL grammar family with
  `17` optional structural variants. They pair one-to-one with `24` PDFs. Across
  private comparison, every unmatched XML value was certificate metadata
  (`26` values); unmatched financial values were `0`. A deterministic typed
  Gate 2 adapter is feasible and an LLM is not required.

The main gap is split by source family: Gate 1 neutral representation for the
`14` broker PDF tables and `11` unique visual-only scopes; Gate 2 typed
consumption for the `24` neutral XML packages. A generic LLM call over all
formats is not justified.

## What the 194 candidates physically represent

| Finding | Count | Meaning |
| --- | ---: | --- |
| Candidate objects | 194 | Complete inventory |
| Distinct, non-overlapping regions | 194 | No detector fan-out collapse |
| Real table regions | 80 | Likely material tables |
| Form/heading regions | 114 | Not physical tables |
| Existing validated projections | 33 | 9 broker tables; 24 withholding form blocks |
| Text/layout-complete, topology unresolved | 71 | 5 broker tables; 66 withholding tables |
| False-positive table candidates | 90 | 81 structured form panels; 9 headings |
| Duplicate candidate members | 0 | No geometric duplicates |
| Overlap pairs | 0 | No containment/IoU group |
| Repeated-content groups | 11 | Template/content repetition, not physical duplication |
| Repeated-content redundant members | 84 | Potential processing dedup with provenance fan-out |

This answers the apparent contradiction directly: all `194` are distinct
regions, but only `80` are physical tables. The `114` other regions are still
preserved because some form panels contain material context.

### Materiality and fallback

- All `14` broker-report candidate regions contain likely material positions,
  transactions, totals or balance evidence. Their values are absent from
  permitted text packages. `9` have a validated projection record (`6` high,
  `3` low), but none is eligible under the current document canonical-table
  scope; `5` remain topology-unresolved. This restriction is correct because
  geometry validation does not establish semantic table truth.
- The `180` withholding candidates include `66` physical income/deduction
  tables, `24` recipient form blocks with existing projections, `81` other form
  panels and `9` headings. Their PDF refs are not packageable, but the paired XML
  carries the material values structurally. PDF table reconstruction for these
  `180` objects can be deferred if the XML adapter is delivered.
- Accepted text refs do not contain any of the `194` candidate refs. Saying that
  “all values are in page text” would therefore be false. The correct statement
  is that all values survive in private layout memory, and the withholding
  family additionally has cross-format XML equivalence.

## Visual-unit audit

| Primary class | Units | Unique material groups | Disposition |
| --- | ---: | ---: | --- |
| Visual fallback with text/layout sibling | 51 | n/a | Default Gate 2 may remain text/table-only; visual path deferred |
| Visual-only material table | 6 | 5 | Bounded visual reconstruction required |
| Non-material visual content | 10 | 0 | Safe permanent deferral |
| **Total in Gate 2 accounting** | **67** | **5** | Complete |

There are `11` exact visual checksum groups with `13` members beyond the first,
including repeated documents and repeated logos/signatures. Deduplication may
avoid repeat processing, but every source identity must retain fan-out
provenance.

The default source-fact path should remain text/canonical-table/neutral-XML
only. A separate typed visual path is preferable, scoped to a declared page or
region. Whole-document images are unnecessary for all identified recovery
jobs.

### Document-level restricted visual source

Operator review also inspected all `6` visual pages belonging to the one
document with `source_fact_scope_blocked_unreadable`. All six contain material
broker tables. This is not missing accounting: these units are preserved in
Gate 1 memory but excluded before the `928` source-ready contour. The document
is effectively unusable for current Gate 2 and requires explicit visual
recovery and review.

## XML-family audit

The `24` XML members and `24` paired PDFs occur in `24` archive groups. The XML
documents expose ordered neutral rows while correctly retaining
`financial_interpretation_allowed=false`.

Private schema inspection found the stable `Документ` / `НДФЛ-2` grammar and
one schema family, with optional sections producing `17` structural variants.
The FNS publishes official electronic 2-NDFL formats and archived period
variants; see the [FNS NDFL format index](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/)
and the [official 2015 format order, Appendix 3](https://www.nalog.gov.ru/html/sites/www.rn31.nalog.ru/pril_prkz/prik_30102015_485%40.pdf).
The implementation must select the applicable archived schema by report period
instead of assuming the newest schema.

| XML check | Result |
| --- | ---: |
| Neutral packages | 24 |
| PDF/XML pairs | 24 |
| Grammar families | 1 |
| Optional structural variants | 17 |
| Distinct XML values inspected | 785 |
| Values found in paired PDF layout | 759 (`96.6879%`) |
| Unmatched certificate metadata | 26 |
| Unmatched financial values | 0 |

This does not make XML semantics a Gate 1 concern. Gate 1 owns lossless ordered
structure and provenance; a versioned Gate 2 adapter owns the mapping from FNS
schema fields to typed financial source facts.

## Duplicate sources and representation fan-out

- `104` source records collapse to `102` byte-hash groups.
- There are `2` exact duplicate PDF groups and `2` redundant source records.
- The `24` PDF/XML pairs are semantic sibling representations, not byte
  duplicates.
- Candidate geometry contributes no duplicate fan-out; repeated template
  content contributes `84` potentially avoidable processing jobs if results are
  fanned back to every provenance identity after context validation.
- Visual checksum grouping contributes `13` potentially avoidable repeated
  media jobs.

Caching by customer value is not recommended. Safe consolidation keys are
immutable source/media checksum, declared region identity, consumer version and
validation policy, followed by provenance fan-out.

## Document coverage

The safe inventory contains all `104` source records and all `80` logical
documents after excluding `24` archive-container identities.

| Coverage status | Source records |
| --- | ---: |
| Fully usable for declared current scopes | 10 |
| Usable for text-bounded scopes with visual omissions | 13 |
| PDF recovery deferable via paired neutral XML | 24 |
| Neutral XML requires typed Gate 2 adapter | 24 |
| Materially incomplete: Gate 1 table reconstruction | 1 |
| Materially incomplete: visual recovery | 5 |
| Requires visual consumer and explicit review | 1 |
| Duplicate/non-primary source | 2 |
| Archive lineage only | 24 |

`55` source records are listed by opaque id as having material evidence not
usable by current Gate 2. This is a source-record count, not `55` independent
business gaps: it includes both sides of `24` paired PDF/XML representations.

Four documents in the `67`-visual contour have no eligible package and are
effectively unusable today. The separately restricted broker document is a
fifth document-level visual blocker outside that contour. The broker PDF with
`14` candidate regions is packageable only for residual line clusters and is
materially incomplete.

## Can Gate 2 start useful bounded interpretation?

Yes, but not as a complete-corpus financial workflow.

- The `2` CSV operation sources and `4` HTML sources provide complete declared
  text/canonical-table scopes.
- `602` text packages allow source-local, text-bounded work for packageable PDF
  sections.
- The withholding workflow should wait for the typed XML adapter, not for PDF
  table reconstruction.
- Full broker/declaration coverage must exclude documents marked materially
  incomplete until their Gate 1 representation or typed consumer is delivered.

The current `667` packages are therefore sufficient for named bounded CSV,
HTML and text-local scenarios, but not for a claim of complete interpretation
of every accepted logical document.

## Correct restrictions that should remain

1. Geometry-only PDF candidates cannot be promoted as canonical tables.
2. Low-quality or semantically unproven projections cannot become financial
   facts.
3. Visual units require a declared typed consumer and bounded image scope.
4. Neutral XML must not receive financial meaning in Gate 1.
5. The unreadable visual document must remain review-restricted until neutral
   representation is validated.
6. Duplicate source identities must not be deleted even when provider work is
   consolidated.

## Confirmed contract defect

The `24` ZIP container identities are `lineage_only` in document memory but are
also declared source-fact-ready in the DCP. Gate 2 correctly rejects them and
emits `24` memory-blocked errors, even though the `48` member documents carry the
actual PDF/XML content. This is a Gate 1 handoff-classification mismatch, not a
candidate or visual extraction failure. The fix is to route container identities
to lineage/audit context while keeping members in source-ready buckets. It must
not suppress member accounting or change the `194/67` restrictions.

No candidate-scope or visual-scope implementation defect was confirmed.

## Evidence

- Complete safe inventory:
  `BROKER_REPORTS_RESTRICTED_SCOPE_SAFE_INVENTORY.v1.safe.json`.
- Reproducible audit:
  `services/broker-reports-gate1-proof/scripts/audit_restricted_source_scopes.py`.
- Private resolver identities, review verdicts and geometry checks remain under
  ignored `local/stage2/restricted_scope_audit_private/`; no source value, image,
  filename or path is tracked.
- Prior hot-path closure:
  `BROKER_REPORTS_GATE2_PACKAGE_HOT_PATH_PERFORMANCE_CLOSURE.report.md`.
