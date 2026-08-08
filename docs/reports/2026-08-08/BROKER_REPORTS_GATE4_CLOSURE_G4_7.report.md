# Broker Reports — Gate 4 Closure (G4.7)

Date: `2026-08-08`

Goal type: `CLOSURE / INTEGRATION / DOCUMENTATION`

## Final status

```text
G4.7_CLOSED
GATE4 = CLOSED
READY_FOR_GATE5_DESIGN
COMPLETED — MERGED
```

Gate 4 целиком доказан через существующие production boundaries. Обычный
downstream consumer получает единый current Financial Case через
`Gate4FinancialCaseRuntimeFactory.create`, не знает брокерский формат, Gate 3
target grammar или физические SQL tables и не обращается к LLM для повторного
понимания документа.

G4.7 не добавляет runtime-функциональность, DTO, storage, relation layer или
налоговую семантику. Он закрывает current authority drift и оставляет один
короткий [Gate 4 -> Gate 5 handoff](../../stage2/contracts/BROKER_REPORTS_GATE4_HANDOFF.v1.md).

## Final architecture

```text
current validated FinancialAnnotationsV2 sidecars
+ exact active CanonicalArtifactV1 bindings
+ trusted ArtifactAccessContext
        ↓
Gate4FinancialCaseMaterializerFactory.create
        ↓
Gate4FinancialCaseFactV1
        ↓
Gate4FinancialCaseRuntimeFactory.create
        ↓
whole-case assembly + rebuildable same-ArtifactStore SQL cache
        ↓
official current/stale fail-closed reads
        ↓
ordinary Gate 5 consumer
```

Sole/current meaning and runtime owners:

- gate map/status — [Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md);
- Gate 3 output — `FinancialAnnotationsV2` and current Gate 3 contracts;
- Gate 4 fact — [Financial Case Fact v1](../../stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) and its schema;
- materialization/cache/read — [SQL Materialization v1](../../stage2/contracts/BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md);
- case assembly/completeness — [Case Assembly v1](../../stage2/contracts/BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md);
- maintained factories — [Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).

The SQL cache is a deletable working projection. It is not financial meaning
authority or the Gate 5 contract.

## Representative production-boundary proof

The existing executable three-document proof uses validated V2 sidecars, the
real ArtifactStore/canonical path, the production materializer, real
tenant/case-scoped SQLite and the official runtime. Core Gate 3/Gate 4 logic is
not mocked.

It proves through the official runtime:

- `SECURITY_PURCHASE`;
- `SECURITY_DISPOSAL`;
- `DIVIDEND_INCOME`;
- `TRANSACTION_CHARGE`;
- `TAX_WITHHELD`;
- current case read;
- queries by financial type, asset and period;
- lookup by `fact_id`;
- normalized typed roles, `role_complete | role_incomplete` and explicit
  missing values;
- exact sidecar/annotation/canonical/source provenance.

The downstream helper contains no `CanonicalReader`, Gate 3, SQLite/table or
broker-parser dependency. Duplicate-looking dividends from two documents stay
distinct with separate deterministic IDs and provenance.

## Rebuild and freshness proof

```text
build case
-> delete only derived cache
-> rebuild from unchanged exact upstream
-> identical logical case, fact IDs, values and provenance
```

Publication order does not change the deterministic logical result. A new
current document, selected sidecar or active canonical version makes the old
generation stale; reads fail closed until a whole-case rebuild. ArtifactStore
lifecycle removes derived rows and does not leave ghost facts.

No new freshness mechanism was created.

## Semantics audit

Maintained Gate 4 code was checked for broker-specific interpretation,
financial reclassification, role inference, deduplication, reconciliation,
semantic relation matching, trade allocation, FIFO, cost basis, tax attribution
and tax calculation. None is implemented.

The only value transformation is the current contract-owned mechanical,
fail-closed normalization of already role-bound date/decimal/string literals.
It neither chooses a financial role nor interprets a broker column.

Comments next to the main boundaries explain only invariants: technical case
completeness, derived SQL/cache status, current-upstream freshness and trusted
transaction scope. No narrative or obvious-operation comments were added.

## Relation decision

```text
NO_RELATION_LAYER_NEEDED_YET
minimal relation set = ∅
G4.5 = NOT_APPLICABLE_WITHOUT_NEW_EVIDENCE
```

Queryable association by type, asset, date, amount or provenance is not a
persisted semantic relation. G4.4 found no current consumer/evidence that needs
such a layer. Purchase/disposal allocation and tax attribution belong to a
future concrete Gate 5 methodology, not to Gate 4 closure.

## Completeness terminology

`CASE_COMPLETE_FOR_CURRENT_INPUT_SET` is only technical materialization
completeness for the readiness-visible current input set and exact cache
generation. It does not claim that:

- every economically required document was uploaded;
- Gate 3 found every financial fact;
- the economic history is complete;
- the case is ready for tax calculation or declaration.

The runtime name is retained to avoid compatibility churn; current contracts
and handoff make its narrow meaning explicit.

## Known limitations

- Sparse Gate 3: omitted annotations remain non-claims; Gate 4 cannot prove
  corpus/source-fact completeness.
- `role_incomplete`: Gate 4 exposes required missing roles and never guesses
  their values.
- Current input set: Gate 4 knows only documents visible to the current trusted
  OpenWebUI/ArtifactStore case scope.
- Relations: no semantic relation layer exists because none is currently
  evidence-required.

## Gate 5 handoff

Gate 5 receives complete `Gate4FinancialCaseFactV1` payloads through
`Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()`. It starts from
the question: how should tax methodology be applied to this prepared Financial
Case?

Gate 5 must not read broker reports, parse `CanonicalArtifactV1`, consume Gate
3 targets directly, query physical Gate 4 SQL tables, repeat financial
classification or add broker adapters. G4.7 does not design Tax DTOs, FIFO,
cost basis, tax rules, declarations, FNS XML or PDF projection.

## Documentation audit

- Current authorities now show Gates 1-4 `CLOSED` and Gate 5 design as the next
  allowed boundary.
- The new handoff is supporting documentation, not a competing authority.
- G4.5 is explicitly not unfinished technical debt.
- The Stage 2 context index gives a seven-document maximum onboarding path.
- Historical reports and superseded architecture remain unchanged and are
  classified as evidence/history, not current design input.
- A stale README `FinancialAnnotationsV1`/“Gate 4 next” statement and current
  contract next-goal pointers were corrected to current V2/Gate 4 closure.

## Validation

- clean current-main baseline before edits: `42 passed` focused Gate 4 and
  architecture tests;
- final changed-boundary and representative focused proof: `60 passed`;
- canonical/Gate 3/Gate 4/architecture regression: `173 passed`;
- non-overlapping ArtifactStore/canonical/lifecycle regression: `34 passed`;
  total relevant regression = `207 passed`;
- generated OpenWebUI Function bundle smoke: `2 passed` (only pre-existing
  SWIG deprecation warnings);
- Ruff, local Markdown links, whitespace, Cyrillic/mojibake and changed-content
  privacy/secret-like scans: passed;
- GitHub CI and merge status are the delivery evidence attached to the final
  PR lifecycle.

## KISS closure

- New runtime functionality: zero.
- New fact/cache/relation/tax schema: zero.
- New authority document: zero; one supporting handoff was added.
- Historical reports rewritten: zero.
- Gate 5 implementation or tax design: zero.
- Current onboarding now reaches Gate 5 without commit-history archaeology.

```text
NEXT_ALLOWED_BOUNDARY = GATE5_DESIGN
```
