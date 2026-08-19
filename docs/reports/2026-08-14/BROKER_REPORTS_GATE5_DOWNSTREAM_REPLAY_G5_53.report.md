# Broker Reports G5.53 — Downstream Replay from Restored Gate 2 Structure

Date: `2026-08-14`

Status: `SOURCE_EVIDENCE_INSUFFICIENT_FOR_COMPLETE_PURCHASE_FACT`

## Outcome

The restored G5.52 table structure is naturally consumable by the ordinary
Adaptive Context and Gate 3 owners. One clean approved-model execution over
the exact table produced 40 validated, Role-Pack-complete source annotations:

- 20 `DIVIDEND_INCOME`;
- 19 `TAX_WITHHELD`;
- 1 `COMMISSION`.

All 40 annotation targets and all 160 bound role targets resolve to cells in
the repaired Canonical table. Every role target remains in the same exact
Canonical row as its annotation target. No Gate 3 special case, manual value,
retry, response repair or fallback model was used.

The requested `SECURITY_PURCHASE` proof cannot proceed. New source-bound
evidence contradicts the semantic premise carried forward from G5.52: the
exact repaired table is a dividend/withholding table, not a purchase table. It
contains 40 explicit dividend data rows and zero purchase or disposal rows.
The earlier G5.52 structural proof remains valid; only its informal
characterization as the corroborating purchase table is corrected here.

Proven terminals:

- `RESTORED_GATE2_STRUCTURE_CONSUMPTION_PROVEN`;
- `RESTORED_STRUCTURE_PIPELINE_PROVEN`;
- `SOURCE_EVIDENCE_INSUFFICIENT_FOR_COMPLETE_PURCHASE_FACT`.

Not proven and intentionally not claimed:

- `ONE_REAL_PURCHASE_ROLE_PACK_COMPLETE`;
- `ORDINARY_GATE4_MATERIALIZATION_PROVEN`;
- `DETERMINISTIC_GATE5_REPLAY_FROM_REPAIRED_SOURCE_PROVEN`;
- `CROSS_GATE_STRUCTURAL_REPAIR_E2E_PROVEN`.

Exact terminal:

`NEXT_DOWNSTREAM_BLOCKER_LOCALIZED=SOURCE_EVIDENCE/no_SECURITY_PURCHASE_row_in_exact_repaired_table`.

## Provider boundary

The existing NDFL production binding remains:

```text
provider profile = google_gemini
approved model = models/gemini-3.5-flash
```

Authenticated inventory and health checks passed immediately before the
execution. The exact approved model was published. No wrapper, similar model,
provider adapter or fallback was selected.

Execution discipline:

- provider submissions: 2 (one type pass and one role pass);
- retry: 0;
- repair: 0;
- fallback: 0;
- best-of-N: 1;
- manual completion: 0;
- source/Gate 4/Gate 5 provider calls: 0.

The raw provider result and customer literals remain outside Git. The private
result is bound by SHA-256 in the safe receipt.

## Ordinary structural path receipt

| Boundary | Result |
| --- | --- |
| active Canonical | exact G5.52 proof version remained active |
| repaired table | 42 structural rows, 247 exact cells |
| Adaptive Context mode | `structural_chunks` |
| document chunks | 140 |
| exact target chunk | ordinary `whole_table`, ordinal 22 |
| target chunk size | 7,678 model-view characters |
| target chunk mappings | 289 |
| selected structural row closure | 1 row alias plus 6 cell aliases |
| ancestors/header | 2 ancestor headings; table header retained |
| coverage | 19,060/19,060 targets, zero loss, duplication or row overlap |
| Gate 3 type pass | validated |
| Gate 3 role pass | validated |
| store after replay | byte-identical |

The selected G5.52 “fully literal row” is a structural/header row, not a
financial transaction. It remains useful structural evidence but cannot be
promoted to `SECURITY_PURCHASE`.

## Source-evidence correction

A bounded read-only inspection of the exact repaired table found:

- 40 data rows with explicit dividend source context;
- 40/40 contain an exact date literal;
- 40/40 contain numeric source literals;
- 40/40 contain an explicit row-level currency literal;
- 40/40 contain five non-empty source cells and one source-backed empty cell;
- 0 rows contain purchase evidence;
- 0 rows contain disposal evidence.

The clean provider result independently agrees with that structure: it emits
only dividend, withholding and commission types. Therefore zero
`SECURITY_PURCHASE` annotations is not a Gate 3 type-extraction defect and must
not be “fixed” with demand wording, broker vocabulary or prompt pressure.

One exact safe-alias row, `restored_table_dividend_row_1`, demonstrates the
positive structural path:

- exact Canonical cell target: present;
- row cells: 6, of which 5 have non-empty literals;
- all cells have source provenance;
- explicit dividend/date/amount/currency source evidence: present;
- required `DIVIDEND_INCOME` roles `date`, `amount`, `currency`: all `bound`;
- optional `asset`: `bound`;
- validator rejection: none.

This answers the architectural question positively: ordinary Gate 3 can use
the restored Gate 2 table structure without a special mechanism. It does not
answer the different question of where a purchase exists.

## Gate 4 and Gate 5 stop

The representative chunk run is intentionally non-persisted. The official
Gate 3 persistence owner accepts only a complete full-document result, and the
exact document now has 140 structural chunks. Persisting a hand-built partial
sidecar or injecting the one row into Gate 4 would violate the ordinary path.

More importantly, the requested purchase fact does not exist in this exact
source table. Consequently:

- Gate 4 received no new persisted purchase annotation;
- Gate 4 materialized no new fact;
- Gate 5 was not run from Gate 3 output;
- acquisition-basis coverage and declaration blockers remain unchanged.

Running all 140 chunks to publish unrelated dividend facts would expand the
goal after its requested purchase premise had failed. KISS and the strategic
source-insufficiency stop require no such expansion.

## Exact local correction

The reused G5.48 live evidence script had one stale safe-report predicate: it
looked for role status `value`, while the current Role Pack contract and
`FinancialAnnotationsV2` use `bound`. The production Gate 3 validator and
artifacts were already correct.

The script now delegates completion counting to one small helper that accepts
only all-required-role `bound` outcomes. A behavioral test proves that a
missing required role remains incomplete. No runtime, provider, Gate 2,
Gate 3, Gate 4 or Gate 5 owner changed.

## Verification and guardrails

- Pre-call local seam: `102 passed` across Adaptive Context, Gate 3 type/role,
  Evidence Demand, Gate 4 and cross-gate architecture.
- Post-correction focused tests: `21 passed`.
- Final combined relevant regression: `109 passed`.
- Explicit G5.50 architecture/anti-drift check: `48 passed`.
- Approved provider/model publication: verified.
- One clean execution: terminal and validator-complete.
- Private store mutation: zero.
- Private/customer literals committed: zero.

Architecture invariants remain:

```text
Gate 2 financial semantics = 0
Gate 3 tax semantics = 0
Gate 4 provider calls = 0
Gate 5 source reads = 0
Gate 5 source-semantic provider calls = 0
Projection changes = 0
```

KISS is preserved: no replay engine, chunker, semantic runtime, purchase
parser, source relation graph, prompt change or second reader was added.

## Stop and next allowed boundary

G5.53 stops at the contract's source-insufficiency terminal. The next work, if
explicitly authorized, must first identify a different exact Canonical table
that genuinely contains `SECURITY_PURCHASE` source rows. It must not reuse this
dividend table, infer purchase identity from the earlier coarse fallback, or
repeat the current provider call.

No commit, push, PR, product activation or full-document provider run is
authorized by this report.
