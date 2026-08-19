# G5.39AE - Additive Inactive Declaration Value Candidate

Verified: 2026-08-12

Mode: test-first local implementation

Terminal: `G5_39AE_ADDITIVE_INACTIVE_VALUE_CANDIDATE_PROVEN`

## Result

The existing `Gate5DeclarationSemanticInputRuntime` now has one additive,
inactive method:

```text
compile_declaration_value_candidate(package=...)
```

It calls the unchanged current `compile(package=...)` path exactly once and
then selects declaration business values from the validated rich v0 result.
It creates no second factory, Package reader, store, calculation owner or
source path.

The result is not released, projected, persisted or routed into a product. The
existing Semantic Input, projector, E2E orchestration, XML artifact and public
product output remain the active legacy path.

Safe machine-readable evidence is in the
[implementation receipt](./BROKER_REPORTS_GATE5_ADDITIVE_INACTIVE_VALUE_CANDIDATE_G5_39AE.receipt.safe.json).

## Authority bootstrap

| Boundary | AE disposition |
| --- | --- |
| Pipeline authority | unchanged; Gate 1-4 remain closed and Gate 5 remains bounded |
| Package audit/completeness authority | unchanged |
| Semantic owner | existing `Gate5DeclarationSemanticInputRuntimeFactory.create` only |
| Current rich v0 contract | unchanged and still consumed by legacy projection/E2E |
| New candidate | additive in-memory value view on the same runtime |
| Documentation authority | unchanged; this dated file is evidence only |

No architecture or current contract document was edited because ownership,
the current rich v0 meaning and every active consumer contract remain
unchanged.

## Candidate contract receipt

```text
schema_version = broker_reports_gate5_declaration_value_candidate_v0
status = DECLARATION_VALUE_CANDIDATE_READY_NOT_RELEASED
value_contract.id = ru_3ndfl_2025_supplied_case_declaration_values
value_contract.version = 2026-08-12.0-bounded
```

The declaration value roots are exactly:

```text
tax_period
filing
taxpayer
signer
budget_dispositions[]
income_group_results[]
russian_source_income[]
financial_investment_results[]
```

`semantic_value_sha256` hashes canonical UTF-8 JSON containing only
`value_contract` and `declaration_values`, with sorted keys, compact separators
and `ensure_ascii=false`.

For the frozen supplied-case values:

| Evidence | Value |
| --- | --- |
| canonical declaration-value bytes | 2,507 |
| declaration-value SHA-256 | `105e8883bc138b3a72ef0f1563b0ca32fadd72ccdc419729a535c1847db962b6` |
| semantic value SHA-256 | `83484fd29f261888d4c1fd466672ba52ace4653a46d89ed445ac574a47258090` |
| optional representation authority | absent for self-signing supplied case |
| collection counts | 1 / 1 / 1 / 1 |

The implementation copies the seventh settlement amount,
`simplified_procedure_returned_or_credited`, from the already validated budget
component. This reproduces the frozen G5.39AC value fingerprint without a new
calculation.

## Fail-closed behavior

The candidate validator checks the exact envelope, eight roots, nested bounded
objects, tagged money values, non-empty collections, optional signer condition
and the outer semantic-value hash.

The parameterized deletion matrix removes every required container or leaf in
the frozen candidate: 133 cases all terminate with
`gate5_declaration_value_candidate_required_value_missing`.

Audit/completeness/target keys terminate with
`gate5_declaration_value_candidate_audit_leakage`. This includes Package,
Semantic Input, component, source, scope, case, run, obligation, methodology,
evidence, Projection Definition, KND and XML/PDF locator identities.

One, multiple and repeated-looking collection rows retain original order,
multiplicity and exact values. No sorting, deduplication, aggregation,
normalization or fallback is performed.

## Stable identity evidence

AD-ID-001 ran the current source-to-XML E2E twice against two fresh SQLite
stores and captured the two independently assembled sealed Packages before
the existing Semantic Input compile.

| Observation | Result |
| --- | --- |
| Package hashes equal | false |
| rich `semantic_input_sha256` values equal | false |
| declaration values equal | true |
| `semantic_value_sha256` values equal | true |

This proves that run-local audit identities do not enter the business-value
identity. The value hash is still not a release or completeness authority.

## Test-first and regression evidence

| Selection | Result |
| --- | --- |
| first functional RED | 139 failures on absent candidate method/validator |
| AE focused suite | 143 passed |
| required-path matrix | 133 passed |
| current legacy E2E suite | 8 passed |
| architecture/factory/bundle selection | 52 passed |
| Black check | passed |
| target `py_compile` | passed |
| `git diff --check` | passed; line-ending warnings only |

The Gate 1 bundle was regenerated twice with the official builder and remained
byte-identical at SHA-256
`d0acb85c67f8c42ef6947357fa46931f863ad22ace3da023f0113237d16229a3`.
Only its exact Gate 1 hash guard changed; both Gate 2 bundle hashes stayed
unchanged.

### Attributed dirty-tree fixture failure

The existing Semantic Input test file produced the same result before and
after AE: `3 failed, 1 passed`, before reaching the Semantic Input unit under
test. The shared synthetic Gate 4 fixture writes a role instruction identity at
`1.0.0`, while pre-existing user-owned Gate 3 role-context work in this dirty
tree has already moved the validation contract to `1.1.0`. Persistence rejects
that stale fixture as `gate3_annotations_payload_contract_invalid`; downstream
setup then reports `gate4_cache_missing`.

This is unrelated dirty-tree infrastructure explicitly covered by the AE
attribution rule. AE did not change Gate 3, Gate 4 or that fixture. The real
current E2E path is green and proves the legacy product route remains intact.

## Production usage and legacy invariance

An AST caller scan found:

```text
production definitions = 1
production callers = 0
test callers = focused AE tests only
```

The new method occurs in the maintained source and its generated Gate 1 bundle
mirror. No active runtime calls it. The legacy E2E returned the same terminal,
semantic mapping, official-XSD result, persistence/ACL behavior and bundle
contract; all eight legacy tests passed.

## Scope audit

AE intentionally did not implement or change:

- value release or 25-obligation release accounting;
- Calculation Evidence bindings;
- projector input or Projection Definition;
- old/new parity or shadow routing;
- E2E candidate routing;
- persistence, XML artifact shape or product output;
- public exports or current Semantic Input schema/status/hash meaning;
- Tax Models, Gate 4, source acquisition, SQL or provider calls;
- migration, activation, commit, push or pull request;
- speculative foreign-source, property, deduction, gift or professional roots.

The extraction and validation work is linear in the bounded declaration-value
leaves after the one existing `compile()` call.

## Dirty-tree preservation and delivery stop

The implementation stayed in the canonical working tree on branch
`feature/gate5-tax-period-category-aggregation` at HEAD
`02659a9b0bdfb2f19171d2a070a660af85119d59` and tree
`0a696522eb37eca13bb9224a41f7227823c8ce8c`.

The checkout was already materially dirty. AE used exact local patches,
regenerated only the required Gate 1 bundle and preserved all unrelated
user-owned changes. No branch, worktree, commit, push or PR was created.

The research journal was updated in
[GitHub issue #278](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5269182866).

## Terminal meaning

`G5_39AE_ADDITIVE_INACTIVE_VALUE_CANDIDATE_PROVEN` means only that the
existing Semantic Input owner can safely compile the strict bounded candidate.
It does not mean released, projection-ready, migration-ready or product-active.
