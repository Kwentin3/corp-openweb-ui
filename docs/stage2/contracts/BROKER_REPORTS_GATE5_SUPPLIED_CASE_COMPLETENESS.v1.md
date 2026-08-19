# Broker Reports Gate 5 Supplied-case Completeness v1

Status: `CURRENT SUPPORTING CONTRACT`

Implementation status: `INACTIVE G5.32 SYNTHETIC PROOF`

G5.32 verdict: `PROVEN`

Representative terminal status: `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE`

This contract corrects the G5.29/G5.30 interpretation used by the G5.31
research loop. Completeness is defined only over evidence actually supplied to
the bound case. It never proves that a taxpayer supplied every real-world tax
event, election, source or document.

The trusted G5.28B Definition remains byte-for-byte unchanged:

```text
definition_id      ru_3ndfl_2025_root_declaration
definition_version 2026-08-10.1
definition_sha256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
```

## Corrected scope contract

`Gate5DeclarationScopeResolutionRuntimeFactory.create` remains the sole scope
owner. It derives every domain and policy from the trusted Definition and
binds the current financial facts through
`Gate4FinancialCaseRuntimeFactory.create`.

For every conditional domain, exactly one of these cases applies:

| Supplied-case evidence | Scope state | Effect |
| --- | --- | --- |
| validated positive component, occurrence evidence or authenticated election | `APPLICABLE` | exact component is required |
| current source fact proves a relevant event but a required role/value is missing | `UNRESOLVED` | source-bound acquisition request blocks completeness |
| no positive activation and no missing-source indication | `NOT_ACTIVATED_FOR_SUPPLIED_CASE` | terminal for this evidence set; no real-world absence claim |
| policy-authorized authenticated negative evidence | `NOT_APPLICABLE` | terminal, evidence-bound non-applicability |
| opposed allowed evidence | `CONFLICT` | nonterminal |

Every `definition_mandatory` domain remains `APPLICABLE`, regardless of the
conditional-domain evidence set.

The receipt embeds this machine-readable boundary:

```json
{
  "kind": "supplied_case_evidence_set",
  "activation_rule": "positive_or_missing_source_evidence_only",
  "real_world_taxpayer_absence_asserted": false
}
```

The corrected receipt states are:

```text
SCOPE_RESOLVED_FOR_SUPPLIED_CASE
SCOPE_INCOMPLETE_FOR_SUPPLIED_CASE
```

There is no universal residual questionnaire. `human_residual` is absent when
conditional domains are merely not activated. An authenticated declarant may
initiate an exact Definition domain only where its policy permits
`user_case_evidence`; typed legal classification still cannot be decided by a
declarant denial or an LLM.

## Missing-source authority

A missing-source indication is accepted only when all of the following match:

```text
Definition-listed component contract -> exact Definition domain
current Gate 4 fact ID
canonical full fact SHA-256
fact status role_incomplete
exact sorted set of required roles whose status is missing
current supplied-case scope binding
```

The resolver emits a structured request with reason
`observed_financial_fact_missing_required_values` and action
`provide_missing_source_or_values`. The request and its originating indication
are hash-bound. A caller flag, stale fact, optional role, invented role or an
LLM statement cannot create this blocker.

## Corrected package contract

`Gate5ResolvedDeclarationPackageRuntimeFactory.create` remains the sole
package owner. It adds the terminal package state
`NOT_ACTIVATED_FOR_SUPPLIED_CASE` and derives only these statuses:

```text
DECLARATION_COMPLETE_FOR_SUPPLIED_CASE
DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE
```

The completeness receipt contains:

```json
{
  "completeness_kind": "supplied_case_evidence_set",
  "real_world_taxpayer_completeness_asserted": false
}
```

`DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` requires every Definition domain to
be exactly one of `RESOLVED`, `NOT_APPLICABLE` or
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`, with all applicable exact components
validated and sealed and with no scope conflict, missing-source request,
component blocker, orphan or hash drift.

It does not authorize `DECLARATION_COMPLETE`, taxpayer-period completeness,
filing readiness, tax advice or product activation.

Completeness is Release authority, not calculation authority. An unresolved
filing/signing component can refuse release without suppressing independent
financial calculations that do not consume it. Scope/action ordering is not a
calculation dependency order.

## Exact financial supplied-case owner

The corrected replay exposed one ordinary component blocker after the four
G5.31 exact owners: the published financial models covered only a bounded
securities slice. The minimal exact owner is:

```text
Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create
```

It validates every category model through the existing
`Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` owner. Its exact-root
component accounts for all three trusted financial-investment obligations:

- securities/derivatives is `RESOLVED` from the supplied validated category;
- digital financial assets/rights is `NOT_ACTIVATED_FOR_SUPPLIED_CASE`;
- investment partnership is `NOT_ACTIVATED_FOR_SUPPLIED_CASE`.

The component requires a manifest-bound
`all_financial_investment_evidence_supplied_to_case` completeness assertion
whose `real_world_taxpayer_absence_asserted` value is exactly `false`. It does
not reimplement operation math, query Gate 4, classify law with an LLM or
promote a bounded category model by itself.

## Regression and anti-drift boundary

Executable tests prove:

- no positive evidence -> no conditional activation;
- validated positive evidence -> `APPLICABLE`;
- current incomplete fact -> source-bound `UNRESOLVED` blocker;
- mandatory Definition domains remain `APPLICABLE`;
- a rehashed scope blocker cannot be promoted by the package;
- exact financial accounting closes the representative supplied case;
- sealed validation needs no store, Gate 4 or provider;
- completeness and component tamper fail closed.

No Definition rewrite, base primitive, DB/table, component registry, generic
rules engine, global questionnaire or LLM decision authority is introduced.

## Scope stop

G5.32 stops at the inactive sealed package and its supplied-case completeness
receipt. It does not implement a Declaration Model, PROJECT, XML/XSD/PDF,
filing, GUI, deployment or product activation. The next allowed boundary is a
separately authorized consumer of `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE`.
