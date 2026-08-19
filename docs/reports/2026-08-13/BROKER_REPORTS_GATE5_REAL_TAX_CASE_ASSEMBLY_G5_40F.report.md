# Broker Reports G5.40F — Real Tax Case Assembly from Available Evidence

Date: 2026-08-13

## Terminal

```text
REAL_CASE_ASSEMBLY_PROVEN
EXACT_EVIDENCE_GAPS_LOCALIZED
```

The bounded real corpus does not contain a complete supplied declaration case.
This is an evidence terminal, not a strategic stop and not an extraction
failure. The case assembler classified every reviewed declaration demand,
retained every available fact, calculated everything supported by the supplied
facts, and stopped without synthetic supplementation.

## Frozen input boundary

G5.40F reused the exact completed G5.40E ArtifactStore and safe receipt:

```text
G5.40E receipt SHA-256
a2b055c5954af99600936a0f0261e1bcd3acdc08ef55e19aa6363dcfec2f1f9e

provider calls in G5.40F       0
provider reruns in G5.40F      0
synthetic supplemental facts   0
store tree before/after        equal
```

No source extraction or model inference was rerun. Private exact facts and
blocker values remain outside Git.

## Minimal ownership

| Meaning | Existing/new owner | Role |
| --- | --- | --- |
| normalized source facts and exact FIFO groups | `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` | existing owner, additively exposes independent available-evidence assembly |
| reviewed declaration demands and policies | existing trusted full Declaration Definition and obligation-package factories | no copied obligation authority |
| demand-first case accounting | `Gate5RealTaxCaseAssemblyRuntimeFactory.create` | small read-only composition; no persistence |
| proof replay | `live_gate5_real_tax_case_assembly.py` | reads frozen store and writes private/safe evidence only |

No TaxCase database, workflow, evidence graph, relation store, new provider
adapter or product route was introduced.

## Declaration-demand matrix

The exact 25-row matrix is stored in
`BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY_G5_40F.matrix.safe.json`.

| Terminal | Demands | Meaning in this supplied case |
| --- | ---: | --- |
| `RESOLVED` | 0 | no complete declaration obligation is supported by the supplied evidence |
| `AVAILABLE` | 0 | no securities calculation reached all Tax Model inputs |
| `MISSING_EVIDENCE` | 4 | filing/party identity and budget-disposition evidence were not supplied |
| `SOURCE_EVIDENCE_INSUFFICIENT` | 5 | income-group, source-jurisdiction and securities demands are activated but not supportable |
| `METHODOLOGY_UNRESOLVED` | 0 | no case demand reaches a facts-complete but rule-missing state |
| `NOT_ACTIVATED_FOR_SUPPLIED_CASE` | 16 | no supplied evidence activates the corresponding optional/typed domain |
| **Total** | **25** | exact reviewed obligation count |

`RESOLVED = 0` is intentional. Synthetic identity, filing, acquisition,
currency or expense values were not injected to improve the metric.

## Knowledge-origin accounting

| Origin | Status | Count | Evidence |
| --- | --- | ---: | --- |
| A — source / financial fact | `AVAILABLE` | 186 | current Gate 4 facts from four independently normalized documents |
| B — external reference fact | `AVAILABLE` | 4 | hash-pinned official-source bindings in the reviewed obligation package |
| C — user / case fact | `MISSING_EVIDENCE` | 0 | no authenticated taxpayer/case answer was supplied |
| D — methodology-derived tax fact | `MISSING_EVIDENCE` | 0 | no real FIFO group satisfied the complete inputs |
| E — declaration / filing context | `MISSING_EVIDENCE` | 0 | no authenticated filing instance/status/signer context was supplied |

The categories remain separate in the runtime output. Methodology and official
Definition knowledge cannot silently become a user fact or a financial fact.

## Multi-source assembly proof

The real case contains all 186 current facts from four document sources under
one authenticated case binding. `multi_source_status = PROVEN`.

Case membership asserts only:

```text
these evidence items were supplied for this case/task boundary
```

It does not assert:

```text
rows from different sources describe the same event
```

The deterministic consumer selects only exact asset, currency, date/order,
financial type and methodology-defined structural conditions.

## Real deterministic calculation evidence

The security slice contains:

```text
security facts total                 48
source-input-ready facts             33
source-evidence-insufficient facts   15
exact instrument/currency groups      9
purchase-only groups                  5
disposal groups lacking acquisition   4
FIFO calculations                     0
Tax Model-ready calculations          0
```

The five purchase-only groups remain
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`; a purchase is not fabricated into a sale.
Each of the four disposal groups stops at an exact minimum prior-acquisition
quantity blocker. Therefore the supplied real facts permit no FIFO result and
no legitimate declaration projection. Returning zero calculations is the
correct maximal deterministic result.

## Exact blocker examples

Private evidence retains the exact fact IDs, instrument/currency literals,
disposal dates, required quantities, available prior quantities and minimum
missing quantities. The safe evidence retains only classifications and counts.

1. Four disposal-group blockers state: acquire a normalized
   `SECURITY_PURCHASE` for the same exact instrument and currency, no later than
   the first unresolved disposal date, covering at least the computed minimum
   missing quantity.
2. Thirteen security facts identify the exact required role(s) absent from the
   source-bound proposal and the evidence type that could supply them.
3. One security fact requires a complete authoritative calendar date.
4. One security fact requires an authoritative unambiguous numeric literal.
5. Filing demands separately request authenticated filing instance, taxpayer
   and period status, signer and representation evidence; they do not return a
   generic "additional data required" message.
6. Taxable-income-by-source demands request authoritative domestic/foreign
   jurisdiction and applicable tax-agent or foreign-tax evidence. Currency or
   broker identity is not used as a jurisdiction guess.

Source blocker accounting:

| Reason | Count |
| --- | ---: |
| `gate5_source_fact_required_role_missing` | 13 |
| `gate5_source_fact_date_invalid` | 1 |
| `gate5_source_fact_decimal_invalid` | 1 |
| `gate5_source_fact_acquisition_quantity_insufficient` | 4 |

## Real versus synthetic separation

The runtime requires an explicit `REAL_EVIDENCE` or `SYNTHETIC_CONTROL` mode.
The same deterministic code was tested with a synthetic two-source control:
one complete group produced one FIFO calculation while an independent missing
acquisition group remained blocked. The control emits
`SYNTHETIC_CASE_ASSEMBLY_CONTROL`; it cannot emit
`REAL_CASE_ASSEMBLY_PROVEN` and contributes zero facts to the real receipt.

## Declaration and XML vertical

The real case has no complete Tax Model input, so it makes no real declaration
value, release, projection or XML claim. This is the required fail-closed
boundary:

```text
REAL NORMALIZED FACTS
-> CASE ASSEMBLY
-> EXACT BLOCKERS
-> NO XML CLAIM
```

The existing supported synthetic/control Tax Model, declaration package,
projection and full-target XSD/XML tests remain green in the Gate 5 regression
run. That control evidence is not counted as real-case completion.

## No-inference and no-reconciliation audit

```text
invented facts                         0
invented relations                     0
stored financial-event relations       0
reconciliation                         not_performed
detail/aggregate upstream deduplication not_performed
currency/jurisdiction defaults          0
new persistence                         false
```

Commission and withheld-tax detail/aggregate observations remain independent.
No balance, ledger or broker-account completeness claim is made.

## Validation

PowerShell was the explicit test shell. The first broad command passed an
unexpanded wildcard to pytest and aborted before collection (`no tests ran`);
no code or tests were changed in response. The corrected command enumerated the
files in PowerShell and then executed pytest:

```text
449 passed in 94.69s
```

That run includes every `test_broker_reports_gate5_*.py`, both Gate 4 fact/cache
contract suites, the new real-case assembly tests and the existing full-target
XML vertical. Additional checks passed:

- Python compile for the consumer, case assembler and live proof harness;
- isolated copied-package import under `python -I`;
- JSON parsing for the matrix, receipt and pinned methodology resource;
- `git diff --check`;
- factory/forbidden anchor audit;
- private evidence outside Git;
- no new graph, reconciliation or TaxCase-store owner.

## KISS audit

The implementation adds one read-only composition module and one proof harness.
The existing source consumer received one independent-group method because it
already owns FIFO, validation and source blockers. The declaration Definition,
obligation package, ArtifactStore, Gate 4 case, Tax Model, projection and XML
owners were reused unchanged. There is no generic rules engine, conversation
system, schema platform or persistent case object.

## Evidence

```text
safe matrix SHA-256
666a5cfb5c7127d5690c20087e8c5ec9a9362b8d498499055942930ac52a13be

safe receipt SHA-256
79d639039634329f7abbd3f93702a4088383f4da366960688dbadd3047e3e21a
```

Private exact case/blocker evidence is stored outside the repository and is
bound into the safe receipt by SHA-256.

GitHub research journal:
[`#278` safe G5.40F comment](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5278640491).

## Scope stop

G5.40F stops here. No commit, push, PR, product activation, declaration filing
mode, dependent GOAL or real-world taxpayer-completeness claim is authorized.

```text
NEXT_ALLOWED_GOAL = NONE_WITHOUT_USER_AUTHORIZATION
```
