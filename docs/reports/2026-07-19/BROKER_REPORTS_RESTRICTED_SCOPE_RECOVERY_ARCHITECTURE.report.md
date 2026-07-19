# Broker Reports restricted-scope recovery architecture

Date: 2026-07-19

Status: research recommendation; no recovery capability implemented

## Boundary decision

The current gate architecture is correct:

| Recovery class | Owner | Output boundary |
| --- | --- | --- |
| Text extraction, source order and provenance | Gate 1 | Neutral source memory |
| Layout or visual table to neutral cells | Gate 1 child capability | Canonical table plus uncertainty/evidence |
| FNS XML schema to typed financial source facts | Gate 2 typed XML consumer | Source-local typed facts |
| Dividend/fee/tax/trade meaning from cells | Gate 2 | Typed financial facts |
| Financial meaning directly from image | Specialized Gate 2 visual consumer | Reviewable proposed facts, never canonical by model authority |
| Acceptance/promotion | Deterministic validators | Explicit terminal decision |

Discovery during Gate 2 preparation does not transfer representation debt to
Gate 2. The primary gap is Gate 1 for broker PDF/visual structure and Gate 2 for
the already neutral XML family.

## Ranked opportunities

### 1. Typed FNS 2-NDFL Gate 2 adapter

This is the narrowest high-value product slice.

- Scope: `24` neutral XML packages and their `24` paired PDFs; it makes PDF
  reconstruction of `180` candidate regions unnecessary for the current tax
  evidence workflow.
- Method: identify schema version by report period; validate against the
  applicable official FNS format; map schema fields to a dedicated typed source
  contract; preserve original XML node/value refs.
- Accuracy/determinism: high and deterministic if schema/version validation is
  terminal. No probabilistic parser or inferred XML semantics is needed.
- Provider calls/cost: `0`; latency is local parsing/validation and must be
  measured in implementation.
- Privacy: private resolver input only; no provider transfer.
- Validation: official-schema fixtures, actual private replay, paired-PDF
  cross-check, unknown version/field fail closed, exact terminal outcomes.
- Failure modes: wrong period/version, optional sections, vendor extension,
  invalid code list, duplicate nodes. None may fall back to an LLM silently.

### 2. Gate 1 broker PDF neutral-table normalization

- Scope: `14` unique broker table regions. `9` have validated projection records
  (`6` high, `3` low), but all remain ineligible under the current canonical
  table scope; `5` are topology-unresolved.
- Method: revalidate high projections against complete row/header/total coverage;
  run deterministic PyMuPDF/pdfplumber layout reconstruction; emit an explicit
  text fallback when topology is not provable.
- Provider calls/cost: `0` for the deterministic path.
- Validation: original-to-memory operator reference, all contributing refs owned
  exactly once, header/row association, totals included, repeated run equality,
  holdout templates and no semantic-table-truth claim from geometry alone.
- Failure modes: merged cells, continuation pages, sparse columns, clipped
  totals, form panels misclassified as tables.
- Human review: required for the acceptance reference and unresolved ambiguous
  cases, not for every deterministic replay once a template contract is proven.

The `90` false-positive table detections should be reclassified in the same Gate
1 representation layer. The `81` material form panels must remain available as
neutral structured/text evidence; only the `9` section headings are safe
non-material deferrals.

### 3. Bounded visual-only table recovery

- Scope: `11` unique material visual scopes across the full restricted corpus:
  `5` unique scopes inside the current `67`, plus `6` pages in the
  document-level restricted broker source.
- First attempt: deterministic image preprocessing, OCR and line/cell geometry.
- Escalation: a bounded VL primary proposal only for unresolved page/region
  scopes, followed by a deterministic contract validator and explicit review.
- Default path: remain text/table/XML only. Do not pass whole documents where a
  page or region is sufficient.
- Required evidence: image hash, page/region provenance, renderer/OCR/model and
  prompt versions, raw provider response kept private, uncertainty, validator
  result and fan-out identity.

No audit evidence proves that an LLM is mandatory for these `11` scopes. It
proves only that a visual-capable recovery path is required. OCR/geometry must
be benchmarked first.

### 4. Safe consolidation and provenance fan-out

- Candidate repeated-content templates: `11` groups, `84` members beyond the
  first.
- Exact visual media: `11` groups, `13` members beyond the first.
- Exact source duplicates: `2` PDF groups, `2` redundant records.

Consolidate only when immutable content/image hash, bounded scope, surrounding
context class, consumer version and validation policy all match. Reuse the
result as a proposal and fan it back to every source provenance. Do not merge or
delete customer source identities.

### 5. Archive handoff correction

Move `24` lineage-only ZIP container identities out of the source-fact-ready
bucket and retain them in lineage/audit context. This removes spurious Gate 2
memory-blocked errors without changing member readiness. It is a small contract
hygiene slice and may precede the XML adapter, but it does not itself recover
business evidence.

## Recovery comparison

| Option | Scope | Accuracy | Determinism | Calls | Measured-cost basis | Privacy | Main risk |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| FNS XML typed adapter | 24 XML / 180 paired PDF candidates | High with exact schema | Deterministic | 0 | Local only; implementation latency unmeasured | Private local | Wrong period/schema mapping |
| Deterministic PDF layout | 14 broker tables | Medium/high on proven templates | Deterministic | 0 | Local; benchmark required | Private local | Merged/continued/sparse tables |
| OCR + geometry | 11 visual scopes | Unknown until benchmark | Mostly deterministic | 0 | Local; benchmark required | Private local | OCR loss, cell association |
| One VL extraction | Only OCR failures | Prior real-table accuracy insufficient for auto-accept | Probabilistic | 1/job | Historical per-call estimate: OpenAI `$0.006394`, `9.485 s`; Gemini `$0.032021`, `19.177 s` | Provider transfer of bounded crop | Omission and structural drift |
| Dual VL proposal | Only hard unresolved scopes | Consensus coverage `0/9` on prior real tables | Probabilistic | 2/job | `$0.038415` and `28.661 s` serial per job | Two providers | Disagreement still needs review |
| Human adjudication | Ambiguous validated evidence | Highest with adequate source pack | Human | 0 provider | Operator time | Private operator scope | Cost, consistency, queueing |
| Permanent deferral | 10 non-material visuals, 9 headings | Exact for declared scenario | Deterministic | 0 | None | None | Scope expansion may change materiality |

The VL estimates are extrapolations from the project benchmark dated
2026-07-16, not current provider price quotes. That benchmark measured detection
at `8` calls / `58.993 s` / `$0.029577`, Gemini extraction at `9` calls /
`172.589 s` / `$0.2881905`, and OpenAI extraction at `9` calls / `85.364 s` /
`$0.057546`. Prior research also found `0/9` full structural/content consensus
on real tables; dual-model agreement is therefore not acceptance authority.

## Provider-volume scenarios

| Scenario | Jobs | Calls | Estimated provider cost | Serial provider latency | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Current preparation | 0 | 0 | `$0` | `0 s` | Proven current state |
| Typed XML adapter | 24 packages | 0 | `$0` | Local only | Recommended first product slice |
| Current-67 unique visual-only, one OpenAI proposal | 5 | 5 | `$0.03197` | `47.4 s` | Only after OCR failure |
| Current-67 unique visual-only, dual proposal | 5 | 10 | `$0.19208` | `143.3 s` | Review research, not auto-accept |
| Full restricted visual-only, one OpenAI proposal | 11 | 11 | `$0.07033` | `104.3 s` | Bounded recovery ceiling |
| Full restricted visual-only, dual proposal | 11 | 22 | `$0.42257` | `315.3 s` | Expensive and still review-bound |
| Naive all-194 detection + dual extraction | 194 | 582 | `$8.16978` | `6990.9 s` | Rejected fan-out |

Parallel provider latency may reduce wall time but does not improve correctness,
cost, privacy or review burden. A timeout increase would mask neither extraction
error nor unnecessary fan-out and remains unjustified.

## Regression-proof sequence

1. Correct archive-container handoff classification in an isolated contract
   slice; prove member accounting unchanged.
2. Deliver the FNS 2-NDFL Gate 2 adapter with official-schema and actual-pair
   replay; keep Gate 1 XML semantics neutral.
3. Benchmark deterministic normalization on the `14` broker regions and accept
   only coverage-proven canonical tables.
4. Benchmark OCR/geometry on the `11` unique visual scopes. Add bounded VL
   proposals only for measured failures.
5. Keep model output proposal-only; require deterministic validation and human
   adjudication for disagreements.

No resumable processing, broad cache or timeout change is needed for this
recovery plan. Resumability becomes relevant only if provider-backed work is
introduced, at which point the job identity must include bounded source hash,
consumer/model/prompt version and validator policy.
