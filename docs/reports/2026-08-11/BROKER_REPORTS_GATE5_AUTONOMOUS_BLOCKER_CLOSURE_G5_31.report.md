# Broker Reports Gate 5 G5.31 Autonomous Blocker Closure

Date: `2026-08-11`

Status: `STRATEGIC_STOP`

Scope: inactive bounded synthetic proof only. No product activation, PROJECT,
XML, XSD, PDF, filing, push or PR is authorized or performed.

## Verdict

The Definition-driven loop advanced autonomously through six receipt-driven
iterations. It closed four exact component requirements, one elective scope
requirement and the taxable-source occurrence scope. Every change was followed
by a new G5.29 → G5.30 replay.

The loop did not reach `DECLARATION_COMPLETE`. It stopped at the first genuine
authority boundary: `professional_activity_results` requires
`typed_legal_classification`, while the current case contains no authoritative
period-wide professional-activity input and no published typed classifier.
Declarant denial is explicitly not an allowed authority for this policy.

Therefore the answer to the G5.31 question is: the loop can choose and close
ordinary proven blockers without a manual roadmap, but this current evidence
set cannot honestly reach `DECLARATION_COMPLETE` without a new strategic legal
classification boundary.

## Initial state

The exact starting replay used the unchanged trusted Definition:

| Identity | Value |
| --- | --- |
| Definition ID | `ru_3ndfl_2025_root_declaration` |
| Definition version | `2026-08-10.1` |
| Definition SHA-256 | `8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d` |
| G5.29 Scope Receipt | `f5cf22ea88e45044b9e0b27b4caf3e88cb246b55ae12e89582a00203c94670e2` |
| G5.30 Package | `cb84df3281f9804aa53bf4d21a3310dbce6c33668bdc0fa57dfcc3fc7aef8f6b` |
| Completeness Receipt | `4f2805b48a4c29a0158bf6e46799397f6d5785568da9aa571bada9819238b673` |
| Status | `DECLARATION_INCOMPLETE` |
| Resolution counts | `RESOLVED 0`, `NOT_APPLICABLE 0`, `SCOPE_UNRESOLVED 7`, `REQUIRED_MISSING 4` |
| First blocker | `filing_and_party_identity / component / REQUIRED_MISSING / required_component_missing` |

The hashes in this report are exact observed replay outputs. Assertion and
artifact identities are generated per replay, so a fresh run is expected to
produce new receipt/package hashes while preserving the states and invariants.

## Iteration ledger

| Iteration | Blocker before | Minimal fix | New Scope Receipt | New Package | New Completeness Receipt | Blocker after |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | filing component missing | exact filing/party owner with explicitly synthetic, case-bound evidence | `28604c1087b87a3332a702186e692096f76f72f987a65448f9bf4a85cd588b4f` | `35ff921c40cbfd5458e3f010612138b6c5bc9d312dff34ca610e9a52a772e3c5` | `295708a6a5579f131c4d86d2ec968d19b86e17bb2a7cac4b68673341d5d0568e` | budget component missing |
| 2 | budget requires complete settlement | exact income-group base/settlement aggregate using existing G5.22/G5.14 owners and a published methodology resource | `a83256e44cd2bb8151e74b8f0a0dfeab7b611ee73bada79874e6c85de458b1ff` | `a8938667c9913f279a4df83c2e3caa279ab632c5592565d38ed57330af6fda17` | `7b867cd10ab163399050b05398ec682be20fdb478492d879df7f1684e378bbc2` | budget component missing |
| 3 | budget component missing | exact declaration-level disposition over filing and settlement owners | `68a3a2ee1094a89fcf6c789674f355f174c42da9c02508ecc50cc5f6a73ad15d` | `530218513c446428e48aca392e4d559ff3182ea23a2eb8fe8d944f188be3b8ef` | `8ebae597e6d231e17cde79b39dd4d5f4e42d171cd849aeb24e4edd3b9ac0779e` | refundable election scope unresolved |
| 4 | refundable election scope | policy-allowed synthetic case-bound authenticated non-election | `74cffd4be891a5205a13519e22f85a7ef3813c3f4238fec7df2ce2323765f` | `132ad42330b7fd0216e7456302fb89a413b13239bda89866fae0bbef87e9af25` | `7ec1d7b93aa1cf12f2d6197c52310582eb02e4b4bbf2dcac9dab41e8ad50d7db` | taxable-source scope unresolved |
| 5 | taxable-source scope | policy-allowed synthetic positive occurrence, because the validated securities income exists | `1f17cc3e0b442869f8d12efab64ad23589df3df5f4be175563cf153265a67dec` | `6fc32786477965e4da7bca082a5f41426556f7103f3b332b1fc0733bb37f1287` | `48d4c2ec95bf214689ca124508252781fef75f594fc598d0efa1dd4b6cb99068` | taxable-source component missing |
| 6 | taxable-source component missing | exact source aggregate accounting every validated income group with explicit RU/foreign, agent and foreign-tax semantics | `0f717cc2bfe09395581dd8056a128cff05d0f4e6fcf2984e0efe9354e111392b` | `98678bf086d0d07fbd5dc65a0ab1ce668d4ef7cb1b72661120afd43d92af33f7` | `cdeea0cae8e84e666d5d778e393a48f443f4552c1e070fc504667e07a3982347` | professional-activity typed classification unavailable |

Iteration 2 was the only prerequisite detour. The machine selected the budget
domain, but an honest declaration-level disposition first required a complete
income-group settlement. No dependency graph or forward roadmap was created.

## Trusted semantics and owners added

The implementation keeps one owner per meaning:

- [`gate5_declaration_filing_context.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_filing_context.py) owns filing, taxpayer, signer and representation semantics.
- [`gate5_declaration_tax_settlement.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_tax_settlement.py) owns exact income-group tax base/settlement pairing and delegates base validation to the existing owner.
- [`gate5_declaration_budget_outcome.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_budget_outcome.py) owns the declaration-level payable/refundable disposition.
- [`gate5_declaration_income_sources.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_income_sources.py) owns exact taxable-source accounting over validated income-group results.
- [`gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v0.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v0.json) is the SHA-pinned, versioned settlement methodology resource. Its SHA-256 is `aa72892a061428ca622066e6b4ef222ba4f9e325cd6fbe2bc92da40a50c49a79`.

The existing trusted methodology authority publishes the resource; no new
registry, DB, service, DSL or sixth primitive was added. The unchanged G5.30
factory is the only package composition owner. Exact components self-bind only
when owner, family and the complete ordered obligation set match one domain in
the same immutable Definition. The original Definition availability remains
sealed and is not relabelled.

All proof inputs introduced here are marked `synthetic_proof_evidence` and
`real_user_fact = false`. They are bound to the synthetic case, taxpayer scope,
tax period and normalization run. No proof value is represented as a real user
fact.

## Official methodology evidence

The settlement behavior was checked on `2026-08-11` against the existing
official FNS procedure source:

- [FNS 3-NDFL filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx), verified content SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

The published resource retains the procedure's ruble-rounding rule, the 2025
five-band group-01/group-08 schedule and the relevant settlement inputs from
procedure paragraphs 6 and 48–55. The proof uses `Decimal`; it does not infer
tax values with an LLM.

## Final state

The final exact replay remains bound to Definition SHA-256
`8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d`:

```text
Scope Receipt          0f717cc2bfe09395581dd8056a128cff05d0f4e6fcf2984e0efe9354e111392b
Package                98678bf086d0d07fbd5dc65a0ab1ce668d4ef7cb1b72661120afd43d92af33f7
Completeness Receipt   cdeea0cae8e84e666d5d778e393a48f443f4552c1e070fc504667e07a3982347

RESOLVED          4
NOT_APPLICABLE    1
SCOPE_UNRESOLVED  5
SCOPE_CONFLICT    0
REQUIRED_MISSING  1

status            DECLARATION_INCOMPLETE
```

The first blocker is:

```text
domain   professional_activity_results
class    scope
state    SCOPE_UNRESOLVED
reason   applicability_unresolved
policy   typed_legal_classification
```

The remaining human residual is `deduction_claims / elective_claim`. It is not
the first blocker and was not pre-answered to manufacture progress.

## Strategic stop

### Problem

The trusted Definition permits only `published_typed_classification` or
`validated_typed_component` authority for `professional_activity_results`.
The G5.29 human route intentionally supports only `elective_claim` and
`factual_occurrence`; a declarant denial cannot decide typed legal scope.

The current Gate 4 evidence is complete for the supplied broker input, not for
all taxpayer activity in the tax period. Treating the absence of professional
activity in that input as a taxpayer-wide negative would repeat the exact
completeness error prohibited by the Gate 4/Gate 5 boundary. Wrapping such an
absence in a typed component would change only the acquisition route, not the
nature of the missing fact.

### Competing options

1. Recommended future route: authorize a separate reviewed, versioned
   professional-activity classifier over a genuinely authoritative period-wide
   case input/coverage contract, then replay G5.29/G5.30.
2. Change the trusted Definition to allow declarant denial. Rejected here:
   there is no new official evidence authoring cycle proving that policy change.
3. Introduce a generic classifier, questionnaire/rules engine or case-time LLM
   legal authority. Rejected by the G5.31 architecture contract.
4. Assert synthetic/private absence as a real authoritative fact. Rejected as
   proof cheating.

This matches `STRATEGIC_STOP` criteria 3, 5, 6, 9 and 10. No implementation
difficulty or test failure caused the stop.

## Verification

Focused progression:

- filing/settlement/package focused set: `20 passed` after two mechanical test-boundary fixes;
- filing/settlement/budget/package focused set: `29 passed` after replacing one source-text false positive with an AST import check;
- final filing/settlement/budget/source/package set: `33 passed`;
- full relevant Gate 5, architecture and bundle suite: `273 passed`, `6` unrelated deprecation warnings;
- exact final G5.29 → G5.30 replay: `DECLARATION_INCOMPLETE`, first blocker exactly `professional_activity_results`;
- validation-only replay of the final sealed package: passed without Gate 4, SQL, ArtifactStore business-value lookup, LLM or user interaction.

The transient focused-test failures were attributed before correction: one
error-precedence expectation, one architecture filename literal check and one
test that matched a forbidden word inside its own constant. No validator or
business invariant was weakened.

## Architecture audit

- Five primitive families are unchanged; exact owners are domain-specific typed components, not a new base primitive.
- No hidden SQL dependency or direct Gate 4/Gate 3/canonical read was added to the new owners.
- No case-time LLM tax calculation or legal/applicability decision exists.
- No generic rules, classifier, questionnaire, workflow, dependency graph, DB or registry was added.
- No research scar workaround was introduced; the only prerequisite detour reused current G5.14/G5.22 owners.
- No bounded component was renamed or promoted to exact. Exact owners carry new semantic proof and full obligation coverage; the bounded financial component remains bounded and unresolved at root.
- The trusted Definition identity, version, hash and semantics are unchanged.
- G5.31 stops before Complete Declaration Model, PROJECT, XML/XSD/PDF and product activation.

## Scope stop

Final result: `STRATEGIC_STOP`.

The next allowed work is not another ordinary blocker iteration. It requires a
separately authorized decision on the authoritative period-wide input and
reviewed typed classification boundary for `professional_activity_results`.
