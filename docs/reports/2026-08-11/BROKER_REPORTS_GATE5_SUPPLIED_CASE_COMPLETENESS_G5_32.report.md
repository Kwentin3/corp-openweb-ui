# Broker Reports Gate 5 G5.32 Supplied-case Completeness Correction

Date: `2026-08-11`

Status: `PROVEN`

Terminal result: `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE`

Scope: inactive bounded synthetic proof only. No product activation, PROJECT,
XML/XSD/PDF, filing, deployment, push or PR is authorized or performed.

## Verdict

G5.32 corrected the G5.31 research scar without changing the trusted Full
Declaration Definition. Conditional domains with no positive evidence and no
observed missing-source clue are now
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`; they are not universal taxpayer-period
questions and do not block the supplied evidence set.

The corrected receipt-driven loop then exposed one ordinary component blocker,
`financial_investment_results`, and closed it with one exact supplied-case
owner over the existing validated category model. The final package has no
blockers and explicitly states that it does not assert real-world taxpayer
completeness.

## Research scar

The G5.31 loop interpreted empty evidence for every conditional Definition
domain as `UNRESOLVED`. It consequently created a universal residual sequence
and stopped at `professional_activity_results`, because that domain correctly
rejects declarant denial under `typed_legal_classification`.

That policy protection was sound; the trigger was not. The current broker case
contained no positive professional-activity evidence and no source fact showing
an incomplete professional-activity event. Therefore the case supplied no
basis to activate or block that conditional domain.

The historical G5.31 terminal receipt remains preserved as research evidence:

```text
Scope Receipt          0f717cc2bfe09395581dd8056a128cff05d0f4e6fcf2984e0efe9354e111392b
Package                98678bf086d0d07fbd5dc65a0ab1ce668d4ef7cb1b72661120afd43d92af33f7
Completeness Receipt   cdeea0cae8e84e666d5d778e393a48f443f4552c1e070fc504667e07a3982347
status                 DECLARATION_INCOMPLETE
first blocker          professional_activity_results / SCOPE_UNRESOLVED
```

It is no longer the current completeness interpretation.

## Corrected contract

The trusted Definition remains unchanged:

```text
definition_id      ru_3ndfl_2025_root_declaration
definition_version 2026-08-10.1
definition_sha256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
```

Conditional domain resolution now follows exactly three default evidence
cases:

1. validated positive occurrence/component/election -> `APPLICABLE`;
2. current relevant `role_incomplete` fact with exact missing required roles ->
   source-bound `UNRESOLVED` blocker and concrete acquisition request;
3. neither -> `NOT_ACTIVATED_FOR_SUPPLIED_CASE`, with no real-world absence
   claim.

Definition-mandatory domains remain `APPLICABLE`. Evidence-bound negative
answers and conflicts retain their previous policy checks. Elective claims are
not universally prompted; the authenticated user may initiate only an exact
Definition domain whose policy permits user evidence. An LLM cannot select or
decide the final state.

The package terminal states are now:

```text
RESOLVED
NOT_APPLICABLE
NOT_ACTIVATED_FOR_SUPPLIED_CASE
```

The terminal success status is deliberately narrow:

```text
DECLARATION_COMPLETE_FOR_SUPPLIED_CASE
completeness_kind = supplied_case_evidence_set
real_world_taxpayer_completeness_asserted = false
```

The governing contract is
[Supplied-case Completeness v1](../../stage2/contracts/BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md).

## Regression proof

Executable behavioral tests cover the mandatory cases:

| Case | Observed result |
| --- | --- |
| no positive conditional evidence | every conditional row is `NOT_ACTIVATED_FOR_SUPPLIED_CASE`; no residual question |
| validated securities operation/source evidence | the corresponding Definition domains are `APPLICABLE` |
| current `SECURITY_DISPOSAL` fact with required `amount` missing | `financial_investment_results` is `UNRESOLVED`; request binds fact ID/hash, `amount`, scope hash and action `provide_missing_source_or_values` |
| mandatory Definition domains | remain `APPLICABLE` with no caller evidence |
| rehashed promotion of the source blocker | rejected by sealed package validation |
| exact financial component or completeness tamper | rejected fail-closed |

The missing-source proof starts from a real Gate 4 `role_incomplete` fact and
derives its exact missing required-role set. There is no caller-owned Boolean
or free-form LLM blocker.

## Receipt-driven iteration ledger

The first corrected replay reused the G5.31 exact filing, budget, settlement
and taxable-source components and removed the spurious universal assertions.

| Iteration | Machine result | Counts | First blocker | Action |
| --- | --- | --- | --- | --- |
| correction replay | `DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE` | `RESOLVED 4`, `NOT_ACTIVATED_FOR_SUPPLIED_CASE 6`, `REQUIRED_MISSING 1` | `financial_investment_results / component / required_component_bounded_only` | implement one exact supplied-case financial owner |
| exact financial replay | `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` | `RESOLVED 5`, `NOT_ACTIVATED_FOR_SUPPLIED_CASE 6` | none | terminal; stop |

Observed hash chain for one exact bound fixture:

```text
Corrected Scope Receipt       b248ad787f35a9e8bf7d963ec271a71d9c6883f91d512250fcbd66c27ecd30fc
Iteration 1 Package           667dbee774a2330ef8c960b8a65eab78bc96a9839c978f58a9c1197d31fceb79
Iteration 1 Completeness      ce354a41adaf6de06f974434eb84bbc4550d01f39654a730a711896b68644e7b
Final Package                 f1e827c7c77c95c1afa5b669e838d7daf4dc8252d916e3f08894db57a5e0bfde
Final Completeness            28dce4d3329bdafa8aa43dc3740dde902f71ca8b5b56888a136135dfb470512a
```

Scope and final package replays were byte-equal for the same bound inputs. A
fresh synthetic fixture can have different upstream artifact identities and
therefore different hashes; its states and invariants remain identical.

## Ordinary blocker closure

The exact owner
`Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create` validates
the existing G5.14 category model rather than copying its calculations. It
accounts for the trusted financial domain as follows:

```text
obl_securities_and_derivatives_results              RESOLVED
obl_digital_financial_asset_and_right_results       NOT_ACTIVATED_FOR_SUPPLIED_CASE
obl_investment_partnership_results                  NOT_ACTIVATED_FOR_SUPPLIED_CASE
```

Its completeness manifest covers only financial-investment evidence supplied
to the bound case and requires
`real_world_taxpayer_absence_asserted = false`. The package owner validates the
exact family and all three ordered obligation refs against the unchanged
Definition. The bounded operation/category snapshots remain bounded; only the
new aggregate component claims exact supplied-case root accounting.

## Verification

```text
Focused corrected scope/package/component suite      49 passed
All tests selected by -k gate5                       219 passed
Gate 5 + architecture + bundle suite                 294 passed, 1 skipped
Same-bound-input scope replay                        byte-equal
Same-bound-input final package replay                byte-equal
Validation-only final sealed package                 equal
Definition SHA                                      unchanged
Final blockers                                      0
```

The skip is the pre-existing optional Windows symlink capability check. Six
unrelated dependency/deprecation warnings remain non-assertion output.

## Anti-cheating and KISS review

- One unchanged Definition remains the only domain/policy/obligation authority.
- Factory entrypoints remain the only execution path; package validation uses
  native component owners.
- The new exact owner composes the existing category validator and contains no
  Gate 4, SQL, ArtifactStore, provider, LLM or direct document read.
- Tests assert terminal behavior and fail-closed tamper outcomes, not snapshots
  alone.
- No sixth base primitive, DB/table, registry, graph, workflow, generic rules
  engine or universal questionnaire was added.
- The output is filed under the repository's dated report route; the current
  supporting contract is under `docs/stage2/contracts`.

## Final result and scope stop

Final result: `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE`.

This means only that the supplied synthetic case evidence is fully accounted
against the unchanged trusted Definition under the corrected contract. It does
not mean the taxpayer supplied every real-world tax event, the declaration is
legally or filing-complete, or the product path may activate.

G5.32 stops here. Any consumer, Declaration Model, PROJECT, XML/XSD/PDF,
filing, GUI or activation work requires separate authorization.
