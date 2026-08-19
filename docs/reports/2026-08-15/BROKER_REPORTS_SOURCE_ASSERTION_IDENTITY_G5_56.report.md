# Broker Reports G5.56 — Source Assertion Identity Across Canonical Anchors

Date: `2026-08-15`

Status: `PROVEN_WITH_REAL_ROLE_CONFLICT_FAIL_CLOSED`

## Outcome

Proven terminals:

- `SOURCE_ASSERTION_REFINEMENT_LINEAGE_PROVEN`;
- `CROSS_CANONICAL_ANCHOR_SUPERSESSION_PROVEN`;
- `DUPLICATE_SOURCE_ASSERTION_PUBLICATION_ELIMINATED`;
- `GATE4_GATE5_SOURCE_ASSERTION_COUNT_CORRECT`;
- `REAL_G554_ROLE_BINDING_CONFLICT_FAIL_CLOSED`.

The frozen five old and five recovered `SECURITY_PURCHASE` annotations represent
five visible source assertions with two Canonical anchors each, not ten source
rows. Financial values were diagnostic clues only and are not part of the
production identity rule.

## Visual qualification

The original PDF page was rendered and inspected outside Git. It contains one
visible transaction table and exactly five relevant data rows. The five
Canonical rows preserve source order, full row width and column alignment;
there is no visible extra purchase row, invented row or row shift.

| Pair | Visible row | Old anchor | Recovered anchor | Classification |
| --- | --- | --- | --- | --- |
| `old_purchase_1` / `recovered_purchase_1` | `source_row_1` | `table_cell` | `table_row` | `SAME_SOURCE_ASSERTION_PROVEN` |
| `old_purchase_2` / `recovered_purchase_2` | `source_row_2` | `table_cell` | `table_row` | `SAME_SOURCE_ASSERTION_PROVEN` |
| `old_purchase_3` / `recovered_purchase_3` | `source_row_3` | `table_cell` | `table_row` | `SAME_SOURCE_ASSERTION_PROVEN` |
| `old_purchase_4` / `recovered_purchase_4` | `source_row_4` | `table_cell` | `table_row` | `SAME_SOURCE_ASSERTION_PROVEN` |
| `old_purchase_5` / `recovered_purchase_5` | `source_row_5` | `table_cell` | `table_row` | `SAME_SOURCE_ASSERTION_PROVEN` |

Visual inspection was a qualification oracle only. No image, customer literal
or visual inference enters production persistence.

## Deterministic provenance proof

All five pairs have the same exact Canonical document/version. Each pair has:

- one old `table_cell` target and one recovered `table_row` target;
- the same table `node_id` and exact row index;
- a unique row-owner identity;
- every bound role target contained in that same table node and row.

The existing Canonical owner relation is stronger than ordinary bbox overlap:
the row is explicit and its cells carry the same `node_id + row`. No new ID
registry, source graph or geometry matcher is required.

The safe pair hashes and classification matrix are recorded in
[`BROKER_REPORTS_SOURCE_ASSERTION_IDENTITY_G5_56.receipt.safe.json`](./BROKER_REPORTS_SOURCE_ASSERTION_IDENTITY_G5_56.receipt.safe.json).

## Minimal contract refinement

The existing `Gate3FinancialAnnotationsPersistenceFactory.create` remains the
only owner. Recovery now recognizes one narrow cross-anchor lineage case:

```text
same Canonical document/version
+ same financial label
+ table_cell <-> table_row
+ same table node_id and row
+ all bound role targets remain within that row
```

For compatible roles, a recovered `table_row` supersedes the old `table_cell`
anchor. Same values on different rows remain distinct. Cell-to-cell overlap,
different labels, different source versions and unproven geometry do not
collapse. The rule never reads date, asset, quantity, amount, currency,
unit-price or literal values.

G5.55 remains intact: unrelated facts are preserved, new assertions are added,
compatible completeness may supersede, omission never deletes and conflicts
fail before ArtifactStore write.

## Real replay: lineage same, roles conflicting

The five real pairs prove source-row identity, but their complete role bindings
are not compatible. Four role targets agree structurally; `amount` and
`currency` point to different source columns in every pair. The coincident
literals cannot select the correct binding because values are forbidden as
identity authority.

Therefore the frozen real delta is not repaired and does not supersede the old
view. Recovery terminates with `gate3_annotations_recovery_conflict` before
write. This is the required fail-closed result, not a missing implementation.

Controlled replay on an isolated copy produced:

- provider calls: `0`;
- source store changed: `false`;
- Gate 3 recovery artifacts written: `0`;
- current document view: `21` annotations;
- purchases: `5`, not `10`;
- unrelated commission/charge: `16`;
- Gate 4 document facts: `21`;
- Gate 5 case security facts: `48`;
- stored financial-event relations: `0`;
- deleted facts: `0`.

The earlier G5.55 report remains historical evidence of behavior under the old
exact-target-only law. G5.56 does not rewrite that evidence.

## Mandatory scenarios

| Scenario | Black-box result |
| --- | --- |
| A — same source row, refined anchor | compatible `cell -> row` supersedes one current assertion |
| B — same values, different rows | two assertions retained |
| C — unproven partial/cell overlap | no collapse |
| D — different source version | existing canonical-binding guard rejects |
| E — different financial labels | no merge |
| F — unrelated facts | 16 commission/charge facts preserved |
| G — visual versus lineage | five visual rows agree with five deterministic row owners |
| H — no economic keys | equal-value different-row test remains distinct |
| I — downstream | Gate 4 sees five purchases; Gate 5 receives no duplicate source facts |

Tests use the real SQLite ArtifactStore and public factories; the persistence
unit and downstream runtimes are not mocked. The irreversible boundary is
`ArtifactStore.put_record`; conflict tests assert no record crosses it.

## Architecture, verification and KISS

The implementation adds three small private helpers inside the existing
persistence module. Gate 2 remains source structure/provenance, Gate 3 remains
source semantic assertion, Gate 4 remains normalized facts and Gate 5 remains
tax consumption. No `TransactionIdentity`, economic event matcher, graph,
registry, similarity logic, new store or second owner was introduced.

Verification in PowerShell:

- focused persistence suite: `26 passed`;
- Gate 3/Gate 4/Gate 5, cross-gate architecture and bundled path: `128 passed`;
- live persistence-script tests: `2 passed`;
- Ruff: passed;
- three generated OpenWebUI bundles: deterministic rebuild passed;
- frozen private replay: passed with zero provider calls and unchanged source
  store.

G5.56 stops here. It does not authorize semantic repair of the frozen provider
output, product activation, commit, push, PR, declaration release or another
GOAL. `NEXT_ALLOWED_GOAL = EXPLICIT_USER_AUTHORIZATION_REQUIRED`.
