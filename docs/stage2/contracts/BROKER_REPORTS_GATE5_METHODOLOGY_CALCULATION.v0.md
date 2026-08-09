# Broker Reports Gate 5 Methodology Calculation v0

Status: `EXPERIMENTAL_G5_7_CONTRACT`

Goal status: `G5.7_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract proves one minimal machine boundary between changing Tax
Methodology meaning and ordinary deterministic calculation code.

```text
external methodology projection
-> existing G5.5 satisfied values
-> one named deterministic behavior
-> closed calculation result
```

The result is an experimental securities-disposal net result. It is not a
complete Russian tax base, tax payable calculation or final Tax Model.

## Research basis

The [G5.1 Tax Methodology Boundary research](../../reports/2026-08-08/BROKER_REPORTS_GATE5_TAX_METHODOLOGY_BOUNDARY_G5_1.report.md)
established the relevant ownership split:

- methodology owns applicability, required semantic inputs and stable rule
  identity;
- ordinary code owns Decimal validation and deterministic arithmetic;
- runtime LLM, executable rules, a generic DSL and a universal Tax Engine are
  not required.

G5.7 makes no new legal assertion. The representative rule is explicitly
experimental and exists only to prove the contract seam.

## Options considered

### Executable logic inside methodology

Rejected. A formula/expression language would require parsing, safety,
versioning and execution semantics that one representative calculation does
not justify.

### One implicit calculator selected by orchestration

Rejected. Requirements would be external, but the applied behavior would be
hidden in runtime control flow and the methodology would be partly decorative.

### Methodology names a deterministic implementation

Selected. The projection supplies `rule_id`, `behavior_id`, requirements and
explicit semantic input bindings. Code accepts one known behavior and fails
closed for every other identity.

This is a one-behavior seam, not a plugin system or rules registry.

## Ownership

| Concern | Owner |
| --- | --- |
| required Gate 5 values and their source selection | methodology projection through unchanged G5.5 |
| rule and calculation behavior identity | methodology projection |
| exact money binding from requirements to behavior inputs | methodology projection |
| trusted discovery and source-tagged sufficiency | unchanged `Gate5SupplementalFactDiscoveryRuntimeFactory.create` |
| closed validation, Decimal arithmetic and result projection | `Gate5MethodologyCalculationRuntimeFactory.create` |
| Gate 4, supplemental persistence and provenance | unchanged existing owners |

## Minimal methodology projection

The input is one closed JSON-compatible object:

```json
{
  "schema_version": "broker_reports_gate5_calculation_methodology_v0",
  "methodology_id": "ru-ndfl-securities-proof",
  "methodology_version": "2026.0-experimental",
  "calculation": {
    "calculation_id": "security-disposal-1-result",
    "rule_id": "experimental-security-disposal-net-result-v0",
    "behavior_id": "security_disposal_net_result_v0",
    "input_bindings": {
      "proceeds": {
        "amount_requirement_id": "disposal-proceeds-required",
        "currency_requirement_id": "disposal-currency-required"
      },
      "acquisition_cost": {
        "amount_requirement_id": "acquisition-cost-required",
        "currency_requirement_id": "acquisition-cost-required"
      },
      "transaction_expense": {
        "amount_requirement_id": "transaction-expense-required",
        "currency_requirement_id": "transaction-expense-required"
      }
    }
  },
  "requirements": [
    {
      "requirement_id": "disposal-proceeds-required",
      "financial_type": "SECURITY_DISPOSAL",
      "value_key": "amount",
      "subject_ref": "security-disposal-1"
    }
  ]
}
```

The abbreviated example shows one requirement; the representative proof also
contains disposal currency, acquisition cost and transaction expense
requirements in the unchanged G5.4 shape.

No formula, Python, expression tree, rate, provider prompt or executable byte
is present in the methodology projection.

## Money binding

Each behavior input names an amount requirement and a currency requirement.
This is necessary because current G5.5 source shapes differ:

- a Financial Case `amount` and `currency` are separate role requirements;
- one Supplemental Fact money value already carries amount and currency, so
  both binding refs may point to that same requirement.

The runtime requires the two requirements to have the same `subject_ref`. A
Financial Case requirement must resolve to exactly one fact value. This proof
does not add aggregation or allocation semantics.

## Supported deterministic behavior

The only supported behavior is:

```text
security_disposal_net_result_v0
```

Its stable technical input interface is:

```text
proceeds
acquisition_cost
transaction_expense
```

Ordinary code performs:

```text
recognized_expense = acquisition_cost + transaction_expense
net_result = proceeds - recognized_expense
```

All values must be non-negative canonical money values in one identical
currency. The operation uses `Decimal`; no LLM, float arithmetic, retry,
repair or fallback participates.

The methodology owns the tax-domain decision to bind particular satisfied
requirements into these semantic slots. The code owns only this exact,
reviewed implementation. A future rule requiring different arithmetic needs a
new reviewed behavior implementation and a new `behavior_id`; that code
change is an accepted KISS cost at the current scale.

## Closed result

The representative result is:

```json
{
  "schema_version": "broker_reports_gate5_calculation_result_v0",
  "status": "calculated",
  "methodology_binding": {
    "methodology_id": "ru-ndfl-securities-proof",
    "methodology_version": "2026.0-experimental",
    "projection_sha256": "<sha256 of exact canonical projection>"
  },
  "calculation_binding": {
    "calculation_id": "security-disposal-1-result",
    "rule_id": "experimental-security-disposal-net-result-v0",
    "behavior_id": "security_disposal_net_result_v0"
  },
  "inputs": [
    {
      "input_name": "proceeds",
      "requirement_refs": [
        "disposal-proceeds-required",
        "disposal-currency-required"
      ],
      "value": {
        "kind": "money",
        "amount": "100.00",
        "currency": "RUB"
      },
      "sources": [
        {
          "requirement_id": "disposal-proceeds-required",
          "source": {
            "source_kind": "financial_case",
            "matches": [{"fact_id": "g4fact_<exact>", "role": "amount", "value": "100.00"}]
          }
        }
      ]
    }
  ],
  "outputs": {
    "proceeds": {"kind": "money", "amount": "100.00", "currency": "RUB"},
    "recognized_expense": {"kind": "money", "amount": "72.00", "currency": "RUB"},
    "net_result": {"kind": "money", "amount": "28.00", "currency": "RUB"}
  }
}
```

The abbreviated input list retains the exact shape. The complete proof result
contains all three inputs. Financial values preserve their Gate 4 `fact_id`;
supplemental values preserve their artifact ref, scope and provenance.

The methodology projection hash binds the exact requirements, bindings, rule
and behavior used. Replaying the same stored inputs and the same projection
through a new runtime returns the identical result.

## Fail-closed boundary

- an unsupported schema or malformed closed object is rejected;
- an unknown `behavior_id` is rejected before calculation;
- missing G5.5 requirements produce no calculation result;
- missing/extra behavior inputs are rejected;
- amount and currency requirements from different subjects are rejected;
- multiple Financial Case values are not silently aggregated;
- invalid money or mixed currencies are rejected;
- no calculation fallback exists;
- the runtime has no write boundary.

## Controlled change boundary

If a new methodology version uses the same calculation behavior, it may
change its version, requirement selection and input bindings without changing
the arithmetic runtime.

If tax meaning requires different arithmetic, the controlled change is a new
named code implementation plus a new behavior identity and tests. G5.7 does
not prove that a data-only rules language would make this safer or cheaper.

Methodology lifecycle, publication, effective-period selection and trusted
Tax Context remain later uncertainties; they are not simulated here.

## KISS and stop condition

G5.7 adds one read-only factory-backed runtime, one experimental projection,
one behavior implementation, one closed result and focused tests.

It adds no Tax Engine, DSL, expression interpreter, plugin system, Tax Case,
Repository, DB/table, workflow, relation graph, LLM call, rate calculation,
tax payable or declaration projection.

The representative proof passed, so `G5.7_CLOSED`. No later Gate 5 slice is
authorized by this contract.
