# Broker Reports Gate 5 Methodology Selection v0

Status: `EXPERIMENTAL_G5_2_CONTRACT`

Goal status: `G5.2_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract defines one minimal proof seam. An external, machine-readable
Tax Methodology fragment states which current financial types and roles it
needs. A small Gate 5 runtime uses that fragment to select facts through the
official Gate 4 Financial Case boundary and reports what was found, partial or
missing.

```text
external methodology requirements
-> Gate5MethodologySelectionRuntimeFactory.create
-> Gate4FinancialCaseRuntimeFactory.create
-> list_by_financial_type
-> structured selection result
```

This is not the full Tax Methodology format. It has no lifecycle, publication,
storage or tax-calculation meaning.

## Ownership

| Concern | Owner |
| --- | --- |
| financial facts and their typed roles | unchanged `Gate4FinancialCaseFactV1` |
| current case reads | unchanged `Gate4FinancialCaseRuntimeFactory.create` |
| which fact types and roles this methodology fragment requires | external fragment supplied to Gate 5 |
| validation, selection and found/partial/missing projection | `Gate5MethodologySelectionRuntimeFactory.create` |

Gate 4 is unchanged. Gate 5 does not add tax requirements to Gate 4 and does
not read broker reports, `CanonicalArtifactV1`, Gate 3 targets or physical Gate
4 SQL.

## Minimal input

The input is a closed JSON-compatible object:

```json
{
  "schema_version": "broker_reports_gate5_methodology_requirements_v0",
  "requirements": [
    {
      "requirement_id": "disposal",
      "financial_type": "SECURITY_DISPOSAL",
      "roles": ["date", "asset", "quantity", "amount", "currency"]
    }
  ]
}
```

Rules:

- the top level contains exactly `schema_version` and `requirements`;
- `requirements` is a non-empty ordered list;
- every item contains exactly `requirement_id`, `financial_type` and `roles`;
- `requirement_id` is an opaque unique non-empty string;
- `financial_type` is passed to the existing Gate 4 public query;
- `roles` is a non-empty ordered list of unique non-empty role names;
- the runtime has no built-in financial-type or scenario table.

The contract intentionally supports one selector only: exact
`financial_type`. Asset, period, Boolean expressions, joins and a generic query
language are out of scope.

## Minimal output

```json
{
  "schema_version": "broker_reports_gate5_methodology_selection_result_v0",
  "requirements": [
    {
      "requirement_id": "disposal",
      "financial_type": "SECURITY_DISPOSAL",
      "roles": ["date", "asset", "quantity", "amount", "currency"],
      "status": "found",
      "matches": [
        {
          "fact_id": "g4fact_<exact-id>",
          "financial_type": "SECURITY_DISPOSAL",
          "fact_status": "role_complete",
          "values": {
            "date": "2026-02-11",
            "asset": "ACME",
            "quantity": "4",
            "amount": "60.00",
            "currency": "USD"
          },
          "missing_roles": []
        }
      ]
    }
  ],
  "summary": {
    "requirements_total": 1,
    "found": 1,
    "partial": 0,
    "missing": 0
  }
}
```

Requirement status is derived mechanically:

- `missing`: Gate 4 returned no fact of the requested `financial_type`;
- `partial`: facts exist, but at least one lacks a requested role;
- `found`: facts exist and every returned fact has every requested role.

`fact_id` retains the exact pointer to the complete Gate 4 fact. The selection
result does not copy source targets or introduce a second provenance schema.

## Demonstrated disposal scenario

The representative synthetic case contains one `SECURITY_PURCHASE` and one
`SECURITY_DISPOSAL` and no `TRANSACTION_CHARGE`.

With two external requirements, the result reports purchase and disposal as
`found`. Adding a third external requirement for `TRANSACTION_CHARGE` changes
the same runtime result to two `found` plus one `missing`. Narrowing the role
list to `amount` and `currency` narrows the projected values without changing
runtime control flow.

The proof therefore establishes:

> External machine-readable Tax Methodology requirements can control which
> data a small runtime collects from the existing Financial Case without
> moving tax methodology into Gate 4 or hardcoding a tax scenario in the
> runtime.

## Fail-closed behavior

The runtime rejects unsupported schema versions, extra or missing object keys,
an empty requirement list, empty strings, duplicate requirement IDs and
duplicate roles. Existing Gate 4 errors for invalid financial types, missing
cache or stale upstream identity pass through unchanged.

## KISS boundary

G5.2 adds only:

- one small factory-backed module;
- one closed requirement shape;
- one closed result shape;
- behavior and anti-drift tests.

It adds no Tax Engine, rules DSL, Repository, database, workflow, LLM,
relation layer, tax ontology, Tax Model, supplemental-fact storage or
methodology lifecycle.

## Stop condition

G5.2 is closed when the representative proof shows that changing only the
external requirement list changes the Gate 4 selection and role projection,
while the runtime remains independent of concrete financial types and uses
only `Gate4FinancialCaseRuntimeFactory.create` plus its public
`list_by_financial_type` method.

No later Gate 5 slice is authorized by this contract.
