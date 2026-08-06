# Broker Reports DOC25 Acceptance Matrix v1

Status: `BLOCKED`

Date: 2026-08-05

| Acceptance area | Required proof | Result | Evidence boundary |
| --- | --- | --- | --- |
| 25.1 repository audit | every initial dirty path classified; consumer map; baseline tests | PASS | 183 initial dirty paths classified; migration map has no unresolved consumer class |
| 25.2 logical contract | versioned contract/schema; non-financial boundary; deterministic IDs/order/refs | PASS | schema valid; seven focused tests include three-build hash equality |
| PDF adapter | page/order/table-once behavior; DOC24 regression | PARTIAL | synthetic order/table-once PASS; current actual DOC24 product regression NOT RUN |
| HTML adapter | title/headings/text/lists/links/tables/order | PASS_FOCUSED | same FullSource parser boundary, focused synthetic test PASS; representative corpus pending |
| CSV adapter | dialect/header/empty/order/coordinates, duplicate/headerless explicit | PASS_FOCUSED | supported and duplicate-header focused tests PASS; broad corpus pending |
| XLSX adapter | workbook/sheet order, visibility, formula/cache/raw/merge/names/table refs | PASS_FOCUSED | focused synthetic test PASS; broad corpus pending |
| Storage immutability | existing ArtifactStore, file-backed private payload, original retained | PASS | existing storage/lifecycle tests plus canonical persistence test |
| Chunking/version pointer | chunk validation, cross-run versions, activation/rollback | BLOCKED | not implemented |
| Tenant isolation | trusted context, cross-scope denial | PASS | canonical cross-user test plus shared ArtifactResolver suite |
| Shadow flags | write/read/compare independently controlled, legacy authoritative | PASS_FOCUSED | flags-off and synthetic flags-on tests; read default false |
| Actual shadow run | controlled actual corpus, safe aggregate receipt | NOT_RUN | private corpus/providers not invoked |
| Consumer migration | all maintained consumers use one reader | NOT_STARTED | legacy remains authoritative |
| Cutover | canary, rollback and explicit decision | BLOCKED | prerequisites absent |
| Cleanup | delete only after migration/cutover/rollback window | NOT_STARTED | zero deletion candidates executed |
| Focused regression | architecture/storage/retention/canonical/DOC25 safe evidence | PASS | 58 passed |
| DOC23/DOC24 safe receipts | safe-evidence validators | PASS | 9 passed; historical evidence only |
| Lint | changed maintained Python/test/build files | PASS | Ruff clean |
| Full current service suite | complete terminal run | NOT_CONFIRMED | not repeated; prior DOC24 run timed out and had historical hash failures |

## Gate verdicts

- `CANONICAL_ARTIFACT_STATUS = READY_FOR_SHADOW`
- `PRODUCT_CUTOVER = NOT_READY`
- `LEGACY_CLEANUP = NOT_STARTED`
