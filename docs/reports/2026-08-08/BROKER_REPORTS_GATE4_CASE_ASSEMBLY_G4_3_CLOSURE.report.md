# Broker Reports Gate 4 Case Assembly — G4.3 Closure

Date: 2026-08-08

Status: `G4.3_CLOSED`

## Result

Ordinary deterministic code can now read all current validated Gate 3 V2
outputs in one trusted OpenWebUI case as a single current
`Gate4FinancialCaseFactV1` set. The path does not read broker formats, invoke an
LLM or reinterpret financial meaning.

## Reused boundary

- `ArtifactAccessContext` remains the trusted tenant/case scope.
- `Gate3NdflCaseReadinessFactory.create` remains the current document and exact
  sidecar/canonical selection owner.
- `Gate4FinancialCaseMaterializerFactory.create` remains the only V2-to-fact
  implementation.
- The existing ArtifactStore SQLite adapter, two G4.2 cache tables, access
  checks and upstream lifecycle remain in use.

G4.3 adds no registry, database, table, index, ACL, lifecycle owner, OpenWebUI
API or upstream OpenWebUI model.

## Added boundary

`Gate4FinancialCaseRuntimeFactory.create` now exposes whole-case rebuild and
read operations. Rebuild derives the complete current readiness source set,
materializes every exact eligible binding in deterministic document order, and
replaces the derived case generation in one tenant-scoped transaction. A read
is current only when its stored generation equals the whole current eligible
binding tuple.

The returned state distinguishes:

- `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`: every document currently selected by
  readiness is eligible and the cache exactly represents that input set;
- `CASE_INCOMPLETE`: at least one current case document is not ready, or no
  exact complete current generation can be read.

This is technical assembly completeness only. It makes no claim that all
documents were uploaded, Gate 3 found every financial fact, the economic
history is complete or the case is ready for tax calculation.

## Representative proof

Synthetic tests over the real ArtifactStore/canonical/V2 path prove:

- three documents assemble purchase, disposal, dividend, withheld-tax and
  transaction-charge facts into one case-scoped read;
- each fact retains its sidecar, annotation, canonical and source-document
  provenance;
- two identical-looking dividends from different documents remain two facts
  with distinct deterministic IDs and provenance;
- reversing publication order and rebuilding after cache deletion yields the
  same ordered logical facts, IDs, values and provenance;
- adding a current document invalidates the old generation until whole-case
  rebuild, after which its facts are present;
- replacing a document's current canonical/V2 binding invalidates the old
  derived facts and rebuild selects only the new exact binding;
- lifecycle expiry fails closed, reports the document as not ready and exposes
  no ghost fact from its removed projection.

## KISS review

- one existing G4.2 materializer: retained;
- one existing readiness source-set owner: retained;
- new registry/table/index/database: none;
- deduplication or reconciliation: none;
- relation schema or linking: none;
- LLM, broker-specific parsing or tax logic: none.

## Validation

- focused G4.1-G4.3, pipeline and generated-bundle contracts:
  `32 passed`;
- full service regression suite: `2972 passed, 5 skipped`, `0 failures`,
  `0 errors` (`2977` collected; JUnit terminal run, `exit 0`);
- generated OpenWebUI Function bundle: rebuilt from the closed source package;
- modified Python files: `ruff` and `py_compile` pass (the package initializer
  retains pre-existing unrelated `F401` debt, so it was checked with `F401`
  excluded);
- JSON, repository diff, local links and targeted secret-like scan: pass.

## Non-goals and next boundary

G4.3 does not decide whether facts are identical, related, conflicting or
economically complete. It does not implement commission-to-trade,
tax-to-dividend or purchase-to-sale links, FIFO, cost basis, tax logic, Gate 5,
RAG, embeddings or graph storage.

Next allowed Goal: `G4.4 — минимальный домен связей`. It has not started.
