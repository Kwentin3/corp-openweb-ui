# Broker Reports Gate 5 Definition-driven Declaration Scope Resolution — G5.29

Date: 2026-08-11

Status: `G5.29_CLOSED`

Outcome: `PROVEN`

Runtime status: `INACTIVE PROOF`

Representative receipt: `SCOPE_INCOMPLETE`

Next allowed boundary: `RESOLVED_DECLARATION_PACKAGE_COMPLETENESS_PROOF`

## Verdict

Да. Trusted Full Declaration Definition реально управляет case-time scope
resolution без questionnaire/rules engine, case-time LLM authority и нового
runtime primitive.

Реализован один factory-routed RESOLVE-accountant. Он получает все 11 domains,
их порядок, policy и allowed evidence classes только через exact hash-pinned
G5.28B authority; читает Financial Case только через Gate 4 factory; принимает
существующий validated typed component как positive evidence; оставляет
неизвестное `UNRESOLVED`; выдаёт один policy-authorized human residual; хранит
структурированный ответ в текущем ArtifactStore; при противоположных ответах
возвращает `CONFLICT`.

## Bounded case

Использован только synthetic proof case:

```text
tax period                    2025
current Gate 4 sources        1
current Gate 4 facts          1 SECURITY_DISPOSAL
existing typed component      1 G5.13 operation Tax Model
trusted Definition domains   11
customer/private data         0
provider calls                0
```

Runtime сам получил следующий результат:

| State | Count | Domains |
| --- | ---: | --- |
| `APPLICABLE` | 4 | `filing_and_party_identity`, `declaration_budget_disposition`, `income_group_tax_results`, `financial_investment_results` |
| `NOT_APPLICABLE` | 0 | none |
| `UNRESOLVED` | 7 | все оставшиеся conditional domains |
| `CONFLICT` | 0 | none in the primary receipt |

`financial_investment_results` стал `APPLICABLE` через уже существующий typed
component. Его payload перепроверен G5.14 validator-ом; embedded Financial Case
source refs сверены с текущими Gate 4 fact IDs, roles и values.

Три `definition_mandatory` domains стали `APPLICABLE` только из Definition.
Ни один отсутствующий Gate 4 fact не был превращён в `NOT_APPLICABLE`.

Privacy-safe machine projection:
[receipt](./BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION_G5_29.receipt.safe.json).

## Human residual and conflict proof

Первый Definition-ordered unresolved domain, где policy разрешает
`user_case_evidence`, получился автоматически:

```text
domain  refundable_amount_disposal
policy  elective_claim
answer  exact yes | no
```

Это не hardcode domain list. Runtime выбирает row из trusted policy audit.
Product-facing wording может быть простым, например: «Хотите ли вы указать в
декларации за 2025 год распоряжение суммой налога к возврату?». Такое wording
не меняет domain, policy, sufficiency или state.

Representative tests доказали:

- exact policy-bound `no` даёт `NOT_APPLICABLE` только этому elective domain;
- `yes` и `no` от двух допустимых case-bound assertions дают `CONFLICT`;
- conflict останавливает дальнейший human residual;
- caller не может заменить request на typed-legal-classification domain;
- foreign authenticated user не может повторно использовать assertion.

## Absence and identity boundary

```text
CASE_COMPLETE_FOR_CURRENT_INPUT_SET
!=
complete taxpayer/declaration scope
```

Gate 4 technical status и его hashes присутствуют в receipt, но не дают
negative applicability. `taxpayer_scope_ref` остаётся отдельным от application
user. User/case/normalization-run binding берётся только из
`ArtifactAccessContext`, а не из caller DTO.

## First real blockers

Scope-level first permitted residual:

```text
refundable_amount_disposal / elective_claim
```

First downstream component blocker, вычисленный из первого `APPLICABLE` domain
с Definition-owned `expected_component.availability != published_exact`:

```text
filing_and_party_identity
required_component_missing
```

Это важное различие. `filing_and_party_identity` уже входит в scope как
mandatory, но trusted filing/taxpayer/signer semantics ещё отсутствуют.
G5.29 их не реализует.

## Fail-closed evidence

Проверены representative invariants:

- exact Definition tuple и tax-period binding;
- 11/11 rows, missing/extra/duplicate rejection;
- component payload hash и повторная live-сверка current Gate 4 binding;
- policy/evidence compatibility;
- current-input absence остаётся unresolved;
- case/user/run-bound assertion persistence;
- policy-bound negative only;
- conflict without last-write-wins;
- decision/scope/Gate 4/receipt hash drift;
- deterministic generated-bundle parity after ArtifactStore allowlist change.

## Architecture and KISS

Добавлены:

```text
1 owner module
1 existing-authority read method
1 private assertion artifact type
1 contract
1 privacy-safe receipt projection
```

Не добавлены:

```text
new DB/table/service/registry
rules engine or applicability DSL
questionnaire/workflow graph
generic taxpayer profile/knowledge model
case-time LLM tax authority
sixth runtime primitive
Declaration Model or PROJECT
```

`architecture-blueprint-guardrails` удержал один owner и explicit downstream
stop. `pb-factories-antidrift` сохранил trusted Definition, Gate 4 and G5.14
factory routes. `pb-db-tenant-rls-tx` убрал caller-owned application user/case
identity из scope input. `pb-tests-integrity` потребовал observable receipt,
persisted assertion, access denial and conflict outcomes, а не snapshots.

## Verification

Final repository replay:

```text
Ruff, new owner + Definition bridge + focused tests: PASS
focused scope/Definition tests:                       27 passed
all Gate 5 tests:                                    180 passed
architecture + ArtifactStore tests:                   61 passed, 1 warning
closed-world bundle smoke/parity tests:               12 passed, 5 warnings
generated bundle rebuild:                             idempotent, 3/3 hashes stable
```

Warnings are pre-existing deprecation warnings from the PDF/SWIG test path;
there were no assertion failures. The repository-wide service suite was not
run; the replay was limited to the complete Gate 5 set plus the directly
affected architecture, ArtifactStore and bundled-runtime boundaries.

A standalone lint of the package-wide `broker_reports_gate1/__init__.py` is not
green: it reports 102 existing `F401` findings outside the G5.29 export block.
The targeted G5.29/Definition files are green, and the G5.29 imports are present
in `__all__`.

## Scope stop

G5.29 закрыт на receipt + first downstream blocker.

Не реализованы filing context, taxpayer/signer authority, missing typed
components, tax settlement, complete Declaration Model, resolved package,
PROJECT, XML/PDF, GUI, product activation, push или PR.
