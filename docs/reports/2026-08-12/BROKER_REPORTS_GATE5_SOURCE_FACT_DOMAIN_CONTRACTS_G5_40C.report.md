# Broker Reports G5.40C — Source-Fact Contract & Domain Boundary Audit / Refactor

Date: 2026-08-12

Terminal:

```text
SOURCE_FACT_DOMAIN_CONTRACTS_PROVEN
OVERINTERPRETATION_REMOVED
DOMAIN_BOUNDARIES_EXPLICIT
```

Mode: autonomous audit, minimal refactor and proof loop. No production
activation, commit, push or PR was performed.

## Outcome

The current Gate 2-5 path now exposes a versioned source-fact boundary instead
of implying that normalized structure proves an economic relation.

- Gate 3 Dictionary and Role Pack `2.0.0` distinguish commission detail,
  source-authored transaction charge, commission total, withholding detail and
  withholding total.
- Gate 4 Fact v2 identifies every result as `normalized_source_fact` and retains
  exact dictionary/Role Pack versions.
- The inferred purchase-to-disposal relation runtime and its Tax Model/E2E
  consumer route were removed.
- The supported declaration vertical still succeeds through explicit
  supplemental acquisition/expense values.
- Without those methodology inputs the Tax Model stops at
  `gate5_tax_model_inputs_not_satisfied`; no relation, Tax Model or XML is
  synthesized.

## Domain map

| Boundary | Kept meaning | Forbidden meaning | Producer | Consumer |
| --- | --- | --- | --- | --- |
| source -> Canonical | exact bytes, regions, rows, cells, literals, provenance | financial type, event identity, tax relation | existing normalizer/canonical factories | Gate 3 |
| Canonical -> Gate 3 | sparse source fact and exact literal roles; same-target source context | calculation, reconciliation, FIFO, allocation, hidden relation | dictionary/Role Pack and labeling factories | persistence/Gate 4 |
| Gate 3 -> Gate 4 | typed normalized source value with exact semantic identity and source literal | label repair, detail-total reconciliation, relation or methodology | materializer factory | SQL cache/Gate 5 |
| Gate 4 -> Gate 5 | current facts plus explicit missing values | treating structural proximity as relation evidence | Gate 4 runtime factory | published typed methodologies |
| Gate 5 -> declaration/XML | authorized methodology-derived values with provenance and completeness | defaulted or inferred missing source/methodology inputs | existing Gate 5 factories | deterministic declaration consumer |

The normative map is
[Source-Fact Domain Boundaries v1](../../stage2/contracts/BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md).

## Construct audit

| Construct | Verdict | Reason / change |
| --- | --- | --- |
| rich Canonical target/row/table structure | `KEEP` | required for source preservation and literal binding; does not assert financial-event identity |
| Gate 3 sparse financial label | `NARROW` | source observation only; current wording forbids inferred relation and reconciliation |
| `TRANSACTION_CHARGE` | `NARROW` | valid only when the accepted source target explicitly contains the transaction context |
| generic commission | `KEEP_AS_SOURCE_FACT` | new `COMMISSION`; no operation relation |
| source commission total | `KEEP_AS_INDEPENDENT_SOURCE_FACT` | new `COMMISSION_TOTAL`; never recomputed or allocated upstream |
| withholding detail/total | `SPLIT` | `TAX_WITHHELD` and `TAX_WITHHELD_TOTAL` preserve source granularity |
| Gate 4 normalized value | `KEEP_AND_VERSION` | fact v2 retains literal plus exact semantic authorities |
| Gate 4 SQL | `KEEP_AS_CACHE` | mechanical JSON projection only; no semantic columns or relation query |
| purchase/charge/disposal relation from date, asset and quantity | `REMOVE` | structure/proximity does not prove economic identity |
| expense eligibility and relation evidence | `MOVE/RETAIN_DOWNSTREAM` | remains a Gate 5 methodology input; must be explicit and fail closed |
| partial acquisition-cost and commission allocation | `UNRESOLVED_GAP` | no authorized method or complete evidence; deliberately not solved here |

## Contract diff

Added immutable authorities:

- `gate3_financial_label_dictionary.v2.json`, SHA-256
  `a43e20351a83d19e6f12efdcde48a90e5c70fb995c37459d446d10c399109a87`;
- `gate3_financial_role_pack.v2.json`, SHA-256
  `22b033a2f6ff041b29ad62d4c966e042b72e258dd67f7e2a0b6606627998723e`;
- `Gate4FinancialCaseFactV2` schema and human contract;
- one cross-domain source-fact authority.

V1 dictionary, Role Pack and Fact contracts remain readable historical
identities. Default labeling/materialization use v2. The standalone Gate 1
OpenWebUI bundle includes v1 and v2 resources; its new SHA-256 is
`2c4d41fdbbe297ff1b4ab113d686a79744ed812a05ce010d67faa70e307ea77f`.

Removed from current runtime:

- `gate5_related_securities_events.py`;
- its exports, build inventory and Tax Model dependency;
- `run_operation_from_related_events` and `related_financial_case` source
  interpretation;
- E2E fallback that attempted to manufacture acquisition/expense inputs from
  that relation.

## Pressure proofs

### Commission detail + aggregate + hybrid

One real canonical/sidecar/materializer/SQL test preserves independent source
facts with values `10`, `15` and aggregate `30`. The deliberate arithmetic
disagreement claimed in the original text was not actually instantiated by
those equal values. Queries return exact distinct facts and no
`relation`, `aggregate_members` or reconciliation payload.

### Withheld tax detail + aggregate

The same proof preserves detail `4` and aggregate `7` without summing,
comparison, replacement or allocation.

### Negative relation proof

Static and behavioral tests prove that the relation module, symbols and runtime
path are absent. A disposal with no explicit acquisition/expense inputs returns
`gate5_tax_model_inputs_not_satisfied` through the real factory path.

## Deterministic consumer replay

The existing supported source-to-declaration vertical was replayed with no
manual repair:

```text
source -> Gate 1 custody -> Gate 2 Canonical -> Gate 3 sidecar
-> Gate 4 Fact v2 -> operation Tax Model -> category Tax Model
-> income-group base -> declaration components -> Package
-> semantic input -> projection -> official-XSD XML
```

Result:

```text
status: END_TO_END_FULL_TARGET_XML_VALID
target_status: FULL_TARGET_XML_VALID
semantic_mapping_status: passed
xsd_valid: true
hash_chain_stages: 16
xml_sha256: 07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a
```

The XML hash is byte-identical to the prior G5.35/G5.39AG proof. The Gate 4
stage hash changes because Fact v2 now intentionally seals semantic authority.

## Verification ledger

| Check | Result |
| --- | --- |
| pre-refactor focused baseline | `71 passed` |
| expanded Gate 3/4/5/architecture regression | `138 passed` |
| source-boundary consumer replay selection | `33 passed` |
| standalone bundle test | `2 passed` |
| final broad Gate 3/4/5/bundle/architecture suite (51 files) | `574 passed` |
| deterministic direct E2E replay | valid 16-stage chain, exact XML hash above |
| negative missing-methodology input | typed fail-closed blocker, no inferred relation |

The test runner completed assertions; no pass count is inferred from a timeout.
Warnings were existing Python/SWIG deprecations and did not change outcomes.

## Research scars

- G5.38's whole-quantity relation was a useful bounded experiment, but its
  event identity exceeded source proof.
- G5.39/G5.39R established that locator equality, page membership, proximity,
  date, asset and quantity are insufficient relation authority.
- The old contract is retained as `HISTORICAL RESEARCH SCAR`; the executable
  overinterpretation is removed rather than hidden behind an inactive flag.
- Rich canonical structure remains because it is valuable for source fidelity
  and exact binding. Only the unsupported semantic assertion was deleted.

## KISS and remaining gaps

There is one current label dictionary, one Role Pack, one Fact boundary, one
materializer, one SQL cache and the existing Gate 5 methodology/declaration
route. No second reader, relation ontology, reconciliation engine, generic
domain framework or new storage layer was introduced.

The remaining gap is explicit: partial-lot acquisition attribution and
commission allocation require an authorized methodology contract with its
exact required inputs. G5.40C did not prove that relation evidence is necessary
for such a method. Until then the system fails closed. This does not block the
already supported explicit-supplemental declaration vertical.

G5.40D supplies the correction proof: commission details `10` and `15` coexist
with source total `40` unchanged, and date-ordered FIFO is exercised without a
stored purchase-to-sale relation. The G5.40C evidence remains historical; the
current wording is owned by Source-Fact Domain Boundaries v1 and the G5.40D
consumer contract.

## Research journal

The existing single GitHub journal remains issue
`Kwentin3/corp-openweb-ui#278`. The G5.40C update is
[`issuecomment-5272001585`](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5272001585).
No
code branch, commit, push or PR is created by this update.
