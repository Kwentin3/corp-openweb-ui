# Broker Reports Gate 5 — Declaration-Driven Tax Model (G5.13)

Date: 2026-08-09

Goal status: `G5.13_CLOSED`

Proof outcome: `PROVEN_WITH_EXPLICIT_PROOF_ASSUMPTIONS`

Architecture verdict: `MINIMAL_DECLARATION_DRIVEN_TAX_MODEL_SEAM_WORKS`

Product status: `INACTIVE`

## Verdict

Да. Existing Gate 5 contour способен из source-tagged resolved inputs и
hash-pinned trusted Tax Methodology детерминированно построить первый
устойчивый securities-disposal Tax Model slice, не приписывая Financial Case
отсутствующий tax meaning, не смешивая related и allowable expenses и не
встраивая представление 3-НДФЛ в Tax Model.

Доказанный минимальный seam:

```text
G5.5 Financial Case + persistent Supplemental Facts
+ closed source-tagged operation/context/evidence inputs
+ G5.8 trusted methodology
        -> Gate5SecuritiesDisposalTaxModelRuntimeFactory.create
        -> Securities Disposal Tax Model V0
        -> private five-concept semantic adapter
        -> existing G5.12 projector
        -> same Appendix 8 fragment
```

Semantic architecture proven. Production evidence acquisition is not proven
for sale/redemption, organized-market status, IIS status, case tax context,
loss treatment, category-scope completeness, or expense-evidence flags. The
representative positive proof marks every such value as `proof_assumption`.

## Evidence-readiness audit

Current representative Financial Case asserts only the existing Gate 4
`SECURITY_DISPOSAL` fact and its roles. In particular:

```text
asset = ACME
financial_type = SECURITY_DISPOSAL
```

does not establish an external instrument identity, organized-market status,
sale versus redemption, or IIS status. G5.13 performs no hidden inference from
either value.

| Tax Model prerequisite | Required value | Proven source in this proof | Proof-only assumption? | Production gap? |
| --- | --- | --- | --- | --- |
| operation kind | `sale` | closed resolved operation input | yes | yes: sale/redemption acquisition path is not proven |
| organized-market status | `organized_market` | closed resolved operation input | yes | yes: `ACME` is insufficient external identity |
| IIS status | `outside_iis` | closed resolved operation input | yes | yes: trusted case/user evidence path is not proven here |
| residency | `resident_individual` | minimal tax-context input | yes | yes: trusted case evidence path is not proven here |
| tax period | `2025` | minimal tax-context input | yes | yes: case-period acquisition/binding is not proven here |
| exemption applicability | `not_applicable` | minimal tax-context input | yes | yes: eligibility decision inputs are not proven here |
| loss treatment | `none` | explicit minimal tax-context input | yes | yes: no inference from absent loss facts is allowed |
| scope completeness | `complete_for_category_in_proof` | explicit scope input | yes | yes: annual/multi-operation completeness is G5.14 or later |
| acquisition cost relatedness/documented/incurred | all `true` | closed expense-evidence inputs | yes | yes: documents/verification path is not proven here |
| transaction fee relatedness/documented/incurred | all `true` | closed expense-evidence inputs | yes | yes: documents/verification path is not proven here |

The three money inputs have different non-assumption provenance:

| Value | Amount | Source |
| --- | ---: | --- |
| category gross income input | `100.00 RUB` | existing Gate 4 Financial Case through G5.5 |
| acquisition cost input | `70.00 RUB` | persistent G5.3 Supplemental Fact discovered through G5.5 |
| transaction expense input | `2.00 RUB` | persistent G5.3 Supplemental Fact discovered through G5.5 |

The user-provided amount provenance is preserved. It is not treated as proof
that an expense is legally allowable; allowability requires a separate
methodology decision over separate evidence flags.

## Bounded primary-source expense research

The reviewed allowability behavior is bound to Tax Code Article 214.1
paragraph 10: securities expenses must be documented, actually incurred, and
related to acquisition, disposal, storage, or redemption. The provision also
identifies acquisition payments and professional securities-market
participant services among the expense classes.

Primary evidence fixed in the trusted methodology resource:

1. consolidated Tax Code Part Two locator on the
   [Official Internet Portal of Legal Information](https://pravo.gov.ru/proxy/ips/?docbody=&nd=102067058),
   Article 214.1 paragraph 10;
2. [Federal Law No. 281-FZ dated 25.11.2009 on the FNS site](https://www.nalog.gov.ru/rn77/about_fts/docs/3897104/)
   and its [official RTF](https://www.nalog.gov.ru/html/docs/281_fz.rtf),
   Article 2 replacement text for Article 214.1 paragraph 10.

The RTF downloaded during the bounded audit was `766722` bytes, SHA-256
`7246df15386c36a3bc0ffee3699aacc1edef752a7f8e442b058de204a3f1a417`.
The consolidated portal entry is explicitly recorded as
`official_locator_verified_no_bytes`; no byte-capture claim is invented.

This evidence justifies the two proof rules only when their explicit
prerequisites are satisfied. It is not a universal fee allowlist or legal
advice.

## Implemented owners

- [G5.13 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL.v0.md)
- [`Gate5SecuritiesDisposalTaxModelRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_securities_disposal_tax_model.py)
- [trusted methodology resource](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json)
- [behavior and architecture tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_securities_disposal_tax_model.py)

The G5.8 authority was extended additively with an expected schema field and
one new id/version/resource/hash entry. Its original G5.7 identity and composed
calculation behavior remain unchanged.

## Tax Model result

The representative Tax Model contains the following stable semantics:

```json
{
  "schema_version": "broker_reports_gate5_securities_disposal_tax_model_v0",
  "status": "complete",
  "model_kind": "securities_disposal",
  "calculation_scope": {
    "subject_ref": "security-disposal-1",
    "aggregation_kind": "complete_category_scope",
    "completeness": {
      "value": "complete_for_category_in_proof",
      "provenance": {
        "source_kind": "proof_assumption"
      }
    }
  },
  "operation": {
    "kind": {
      "value": "sale",
      "provenance": {
        "source_kind": "proof_assumption"
      }
    },
    "category": {
      "value": "organized_market_securities_outside_iis",
      "decision_provenance": {
        "source_kind": "methodology_derived"
      }
    }
  },
  "category_gross_income": {
    "value": {
      "kind": "money",
      "amount": "100.00",
      "currency": "RUB"
    }
  },
  "related_expenses": {
    "components": [
      "acquisition_cost = 70.00 RUB",
      "transaction_expense = 2.00 RUB"
    ],
    "total": {
      "kind": "money",
      "amount": "72.00",
      "currency": "RUB"
    }
  },
  "allowable_expenses": {
    "decisions": [
      "acquisition_cost = allowed",
      "transaction_expense = allowed"
    ],
    "total": {
      "kind": "money",
      "amount": "72.00",
      "currency": "RUB"
    }
  },
  "loss_treatment": {
    "value": "none",
    "provenance": {
      "source_kind": "proof_assumption"
    }
  }
}
```

The actual result additionally carries exact Financial/Supplemental sources,
full tagged prerequisites, authority/resource/projection hashes, rule IDs,
legal evidence refs, prerequisite decisions, and all 14 proof assumptions.

It contains none of the five Russian declaration attribute names, declaration
code `01`, `tax_base`, or `net_result`.

## Expense semantics proof

Positive case:

```text
related components      70.00 + 2.00
related total           72.00 RUB

both components:
  related               true
  documented            true
  actually incurred     true
  methodology rule      bound

allowable total         72.00 RUB
```

Negative control changes only transaction-expense `documented` to `false`:

```text
related total                         72.00 RUB
transaction decision                  not_allowed_unproven
failed prerequisite                   documented
allowable total                       70.00 RUB
```

Thus relatedness does not imply allowability.

## G5.12 projection

The private adapter emitted the existing five-concept consumer contract:

```json
{
  "operation_category": "organized_market_securities_outside_iis",
  "operation_category_gross_income": {"amount": "100.00", "currency": "RUB"},
  "related_expenses": {"amount": "72.00", "currency": "RUB"},
  "allowable_expenses": {"amount": "72.00", "currency": "RUB"},
  "loss_treatment": "none"
}
```

Existing G5.12 returned the same representative fragment:

```json
{
  "ВидОпер": "01",
  "ДохСовОпер": "100.00",
  "РасхРеалЦБ": "72.00",
  "РасхУмДохОпер": "72.00",
  "ПризУчетУбыт": "0"
}
```

Only G5.12 knows these attribute names and codes. The Tax Model and adapter do
not.

## Provenance by transition

| Transition | Meaning owner | Evidence / result |
| --- | --- | --- |
| Financial Case / Supplemental Facts -> resolved money | G5.5 and its existing upstream owners | source-tagged `100`, `70`, `2`; no tax conclusion |
| resolved operation/context -> category | trusted methodology + reviewed G5.13 behavior | stable category with every prerequisite/provenance and no declaration code |
| expense inputs -> related total | G5.13 Tax Model behavior | relation evidence determines component membership; Decimal sum |
| related components -> allowable total | trusted methodology + reviewed G5.13 behavior | component-level legal rule and three prerequisite decisions |
| Tax Model -> five consumer concepts | private mechanical G5.13 adapter | no calculation, default, code, XML name, or repair |
| five concepts -> Appendix 8 representation | existing G5.12 spec/projector | declaration-specific names, codes, transforms, and evidence |

## Fail-closed and replay proof

Focused tests prove:

- missing organized-market status blocks classification;
- missing loss treatment does not become `none`;
- incomplete scope blocks complete category gross income;
- related but undocumented expense remains related and is excluded from
  allowable total;
- multiple matching Supplemental Facts raise the existing explicit G5.4
  ambiguity error;
- mixed RUB/USD inputs fail before totals;
- unknown behavior fails before model/projection;
- exact input, context, methodology version, persisted artifacts, and reopened
  store produce a structure-equivalent result.

## Anti-drift proof

The positive test snapshots and compares before/after:

- official Gate 4 Financial Case output: unchanged;
- Supplemental Fact artifact refs and facts: unchanged;
- trusted methodology package bytes: unchanged;
- G5.12 Declaration Projection Spec bytes: unchanged.

G5.13 imports no G5.11 runtime and mutates no external evidence. Its legal
evidence references are immutable content inside the new hash-pinned
methodology resource.

## Verification

Completed terminal checks:

```text
all Gate 5 test modules:
46 passed in 9.53s

architecture + successor-hash + fail-closed contract checks:
72 passed, 2 skipped in 34.91s

focused G5.13 replay after the KISS reduction:
8 passed in 2.46s

ruff check/format for the focused authority/runtime/test files:
passed

package export surface check with pre-existing F401 debt excluded:
passed
```

A separate full service invocation was attempted twice. The first command
hit its 124-second command limit. The second remained alive for 603 seconds
but was terminated by the external command timeout before pytest produced a
summary; pytest then raised an stdout flush `OSError` during process teardown.
This is recorded as `FULL_SUITE_TERMINAL_VERDICT = NOT_OBTAINED_TIMEOUT`, not
as green and not as an assertion failure. The complete Gate 5 and relevant
architecture/hash-pin suites above are terminal and green.

## KISS and stop condition

Added:

- one Tax Model module/factory;
- one trusted methodology resource and additive G5.8 map entry;
- one closed resolved-input/model/result contract;
- one private five-concept semantic adapter;
- one focused test module;
- this contract/report and authority-map routing.

Not added:

```text
Tax Case
TaxModelRepository
DB/table
annual aggregation
Tax Context framework
Reference Data platform
rules DSL
workflow
relation graph
LLM calculation
tax rate/base/tax
XML/PDF serializer
```

## Final answer

Да. Existing Gate 5 contour can deterministically produce the first stable
declaration-driven Tax Model slice from explicitly source-tagged and
sufficiently resolved inputs. The proof neither enriches Financial Case with
missing tax meaning, nor equates related expenses with allowable expenses,
nor embeds 3-NDFL representation in the Tax Model.

`G5.13_CLOSED`. The next Gate 5 slice was not started.
