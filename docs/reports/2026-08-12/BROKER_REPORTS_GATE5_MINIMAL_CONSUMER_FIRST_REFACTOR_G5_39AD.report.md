# G5.39AD - Minimal Test-First Refactor Design for the Consumer-First Declaration Boundary

Verified: 2026-08-12
Mode: refactor-design research only
Terminal result: `MINIMAL_REFRACTOR_DESIGN_READY`

## Decision

A small reversible refactor exists. The first implementation slice must add an
inactive strict declaration-value candidate to the existing Semantic Input
factory owner. It must not change, replace, route around, serialize, persist or
publish that candidate.

The current rich `broker_reports_gate5_declaration_semantic_input_v0` remains
the only projection authority until a later dual-path stage proves parity. The
first slice therefore changes no tax result, completeness result, XML byte,
artifact, product response, public hash or rollback route.

The design is deliberately asymmetric:

```text
add value boundary first
prove release and projection parity second
move the consumer only after all profiles pass
remove old coupling last
```

The exact eight-root shape remains bounded to the frozen 2025 supplied-case
contract. It is not declared universal for all 3-NDFL cases or inactive domains.

Safe detail is also recorded in the
[design matrix](./BROKER_REPORTS_GATE5_MINIMAL_CONSUMER_FIRST_REFACTOR_G5_39AD.matrix.safe.json)
and the
[research receipt](./BROKER_REPORTS_GATE5_MINIMAL_CONSUMER_FIRST_REFACTOR_G5_39AD.receipt.safe.json).

## Frozen baseline and scope stop

Repository baseline used for this design:

| Item | Frozen value |
| --- | --- |
| branch | `feature/gate5-tax-period-category-aggregation` |
| HEAD | `02659a9b0bdfb2f19171d2a070a660af85119d59` |
| HEAD tree | `0a696522eb37eca13bb9224a41f7227823c8ce8c` |
| current Semantic Input | `broker_reports_gate5_declaration_semantic_input_v0` |
| current Projection Definition | `ru_3ndfl_2025_full_target_supplied_case`, `2026-08-11.0-proof`, hash `48109cc6...c7b26` |
| current official XSD | hash `08312832...1e4484` |
| AC result | 49/49 rendered values, 49/49 paths, byte-identical 1,112-byte XML, XSD pass |

The checkout was already dirty and contains the prior Gate 5 chain. G5.39AD
adds reports only. It does not edit production code, production tests, DTOs,
schemas, Projection Definitions, persistence, bundles, product routing or Git
delivery state.

## 1. Current Semantic Input consumer inventory

The inventory searched the service, tests, scripts, OpenWebUI action source,
generated bundle, current contracts and safe reports for the class and factory
names, v0 schema string, `semantic_input`, and `semantic_input_sha256`.

| Consumer/surface | Class | Exact use | Compatibility consequence |
| --- | --- | --- | --- |
| `Gate5FullTargetXmlProjectionRuntime.project` in [`gate5_full_target_xml_projection.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_target_xml_projection.py#L190) | `PROJECTOR_VALUE`, `AUDIT_CONSUMER`, `COMPLETENESS_CONSUMER` | validates the entire v0 object, reads values through `_source_root`, reads domain/obligation states through `_coverage_proof`, and writes source hashes to its receipt | keep `project(semantic_input=...)` and all v0 behavior untouched through shadow parity |
| current Projection Definition resource | `PROJECTOR_VALUE`, `PERSISTED_FORMAT_CONSUMER` | pins v0 input contract and all current source paths | retain immutable v0; any changed source path requires a distinct v1 resource/version/hash |
| `Gate5EndToEndFullTargetXmlRuntime` in [`gate5_end_to_end_full_target_xml.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_end_to_end_full_target_xml.py#L534) | `AUDIT_CONSUMER`, runtime-return/debug surface | compiles v0, invokes the projector, returns the full object, hashes it into the chain, derives stable semantic comparison and builds critical provenance audit rows | old result shape and receipt v0 stay exact until an explicitly versioned consumer move |
| `Gate5OpenWebUIProductRuntime.process` in [`gate5_openwebui_product.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_openwebui_product.py#L219) | `PERSISTED_FORMAT_CONSUMER`, product/public surface | exposes `semantic_input_sha256` and passes the XML and current receipt to persistence | additive candidate must not change this hash or response v0 |
| XML artifact persistence in [`gate5_openwebui_product.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_openwebui_product.py#L449) | `PERSISTED_FORMAT_CONSUMER`, `AUDIT_CONSUMER` | persists exact XML, current Semantic Input hash, Projection Definition binding, XSD proof and nested E2E receipt in `broker_reports_gate5_openwebui_xml_artifact_v0` | no mutation or backfill; a future changed payload requires v1 |
| OpenWebUI pipe result in [`broker_reports_gate1_pipe.py`](../../../services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py#L1254) | `UNKNOWN_EXTERNAL` | returns the product v0 object to clients; repository cannot enumerate every client of `semantic_input_sha256` | preserve field and meaning; external uncertainty blocks removal, not an additive internal view |
| root package exports in [`__init__.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/__init__.py#L522) | `UNKNOWN_EXTERNAL` | exports v0 constants, error, runtime and factory | do not rename/remove/change the existing method contract |
| generated OpenWebUI bundle and bundle builder | `PERSISTED_FORMAT_CONSUMER`, deployment executable | embeds this module in the closed-world product artifact | every future source edit must regenerate the Gate 1 bundle and pass exact bundle checks |
| `test_broker_reports_gate5_declaration_semantic_input.py` | `TEST_ONLY` | exact schema, hashes, rich domain rows, leakage, factory and import assertions | retain as legacy-contract coverage; add candidate tests beside it |
| `test_broker_reports_gate5_full_target_xml_projection.py` | `TEST_ONLY` | current 49 mappings, 25 coverage rows, XSD, missing value, resource pins, closed-world path | becomes the main old/new parity owner; never weaken legacy assertions |
| `test_broker_reports_gate5_end_to_end_full_target_xml.py` | `TEST_ONLY` | E2E return, hash chain, tamper failure, persistence, replay, ACL and bundle hashes | must prove default legacy product result remains exact |
| `test_broker_reports_gate5_coverage_expansion.py` and architecture allowlists | `TEST_ONLY` | reads returned v0 values and protects module/factory routing | preserve; a new module is unnecessary for the first slice |
| current contracts and historical safe receipts/reports | `RESEARCH_ONLY` | document v0 and store hashes/counts, not raw live Semantic Input bytes | preserve as historical evidence; they do not authorize runtime compatibility changes |

Negative inventory findings are material:

- no fixture serializes a raw v0 Semantic Input object;
- no standalone Semantic Input artifact type or database row was found;
- no CLI directly consumes the rich object;
- no separate PDF production consumer was found;
- live control scripts reach the product boundary, not the rich object directly;
- the generated bundle is a distribution mirror, not a second semantic owner.

The absence of a raw standalone artifact does not make v0 disposable. Its hash
and nested receipts are persisted, its object is an E2E return contract, and its
symbols are exported. External clients outside the checkout cannot be disproved.
That uncertainty is fully contained by leaving every old surface unchanged.
`STRATEGIC_STOP_CONSUMER_INVENTORY_INCOMPLETE` would apply before any schema
replacement, field removal or public output change, but does not block the
selected additive inactive slice.

## 2. Minimal seam decision

Four seams were compared.

| Candidate | Owners touched | Persisted/public change | Dual run | Rollback | Decision |
| --- | ---: | --- | --- | --- | --- |
| extend the existing `Gate5DeclarationSemanticInputRuntime` with one inactive candidate method | one semantic owner plus tests/generated bundle | none | yes | delete unused method | **selected** |
| add a parallel value-model module/factory | at least two semantic owners plus architecture/bundle allowlists | none initially | yes | possible, but leaves duplicate owner | rejected as needless parallel infrastructure |
| adapt rich v0 inside the projector | projector only | none initially | yes | easy | rejected because the projector still owns audit/completeness parsing and the consumer-first boundary is fake |
| replace or shrink v0 in place | semantic, projector, E2E, product, persistence, bundle and external clients | destructive | difficult | migration required | rejected; triggers the strategic stop |

### Selected first seam

The future first implementation adds this method to the already factory-created
runtime; names are part of this design contract:

```text
Gate5DeclarationSemanticInputRuntime.compile_declaration_value_candidate(
    package=validated_or_untrusted_package_bytes
) -> candidate envelope
```

The method must call the existing `compile(package=...)` path exactly once. It
must not create another Package reader, validator, schema owner or source lookup.

The inactive envelope is:

```text
schema_version = broker_reports_gate5_declaration_value_candidate_v0
status = DECLARATION_VALUE_CANDIDATE_READY_NOT_RELEASED
value_contract = {
  id = ru_3ndfl_2025_supplied_case_declaration_values
  version = 2026-08-12.0-bounded
}
declaration_values = {
  tax_period,
  filing,
  taxpayer,
  signer,
  budget_dispositions[],
  income_group_results[],
  russian_source_income[],
  financial_investment_results[]
}
semantic_value_sha256
```

`semantic_value_sha256` is SHA-256 over canonical JSON containing only
`value_contract` and `declaration_values`. It excludes Package, component,
scope, case, run, completeness, methodology, Projection Definition and target
identities. The candidate status is explicitly not a release authorization.

The method copies already-computed values from the validated current v0 object.
It does no tax calculation and no evidence replay. If abandoned, no caller,
artifact or product output has changed.

## 3. Old/new dual-path diagram

```text
                              same Resolved Package
                                       |
                                       v
              Gate5DeclarationSemanticInputRuntimeFactory.create
                                       |
                       +---------------+---------------+
                       |                               |
                       v                               v
              current rich v0                 strict value candidate
                       |                               |
                       |                        release checks (slice 2)
                       |                               |
                       v                               v
        v0 Projection Definition            released declaration values
                       |                         + target mechanics
                       v                               |
          current project(...)                         v
                       |                   v1 Projection Definition
                       |                               |
                       |                   same TreeProjector
                       |                   same Serializer
                       |                   same XSD validator
                       |                               |
                       +---------------+---------------+
                                       v
                              parity comparator
                                       |
                 pass: legacy remains authority during shadow
                 fail: legacy remains authority; candidate is discarded
```

Exact owners remain:

- Package audit/completeness: `Gate5ResolvedDeclarationPackageRuntimeFactory`;
- value extraction and later release orchestration:
  `Gate5DeclarationSemanticInputRuntimeFactory`;
- target mechanics, mapping, serialization and XSD:
  `Gate5FullTargetXmlProjectionRuntimeFactory`;
- same-Package ordering and temporary shadow invocation:
  `Gate5EndToEndFullTargetXmlRuntimeFactory`.

No generic adapter framework, registry, feature-flag service or second model is
introduced.

## 4. Exact parity contract

Parity is evaluated for the same sealed Package, same target context, same XSD
bytes and corresponding immutable Projection Definitions.

A case is parity-equal only if all checks pass:

1. both paths terminate successfully, or both fail before XML with the same
   primary terminal/error for a characterized unsupported profile;
2. all rendered target mapping occurrences have equal mapping IDs, occurrence
   order, target paths and target-value hashes;
3. the target-path multisets are equal;
4. both outputs pass the same official XSD when success is expected;
5. XML byte equality is mandatory whenever target mechanics, constants,
   transforms, ordering, serializer and target context are identical;
6. Projection Definition ID/version/hash and input contract are reported
   separately; their hashes are not expected to be equal;
7. a missing required declaration value emits no candidate XML and cannot fall
   back to Package or rich v0;
8. audit/completeness/evidence metadata is absent from projector values and its
   omission after release cannot change mappings or XML.

Target mechanics are explicit:

- electronic file ID is target context, not declaration semantics;
- program version, format version, KND and period code remain target constants;
- budget row payable/refundable shaping is target mechanics and may only be
  enabled for a profile with old/new characterization evidence;
- collection iteration and node ordering remain the current tree-projector
  mechanics;
- no tax result is recalculated while building target mechanics.

Changing only electronic file ID must leave `semantic_value_sha256` unchanged,
change only the `file-id` target occurrence, and change XML/target hashes.

## 5. Production prerequisite test plan

The test plan is frozen before any production implementation. In each future
slice, tests are authored first locally, observed red for the intended missing
behavior, and shipped green with that one slice. No snapshot-only assertion and
no mock of the runtime under test is allowed.

| Test ID | Behavior protected | Current owner | Proposed location | Fixture/case | Expected terminal | Must exist before |
| --- | --- | --- | --- | --- | --- | --- |
| `AD-VIEW-001` | exact bounded eight-root value surface and canonical hash | Semantic Input factory | existing Semantic Input test file | complete supplied Package | `DECLARATION_VALUE_CANDIDATE_READY_NOT_RELEASED` | slice 1 |
| `AD-VIEW-002` | no Package/source/component/methodology/completeness/target keys leak into values | Semantic Input factory | existing Semantic Input test file | candidate plus each forbidden key | `gate5_declaration_value_candidate_audit_leakage` | slice 1 |
| `AD-VIEW-003` | every required nested value fails closed | Semantic Input factory | existing Semantic Input test file | parameterized deletion of every required field | `gate5_declaration_value_candidate_required_value_missing`; no candidate | slice 1 |
| `AD-VIEW-004` | exact list ordering and multiplicity are preserved | Semantic Input factory | existing Semantic Input test file | one and repeated collection rows | candidate equals source order | slice 1 |
| `AD-ID-001` | run-local audit refs do not affect value identity | Semantic Input factory | existing Semantic Input test file | two real fresh stores/runs with equal values | value hashes equal; v0 audit hashes may differ | slice 1 |
| `AD-FACTORY-001` | existing factory/package validation route and closed-world imports | Semantic Input factory | existing Semantic Input and bundle tests | outside-CWD execution | candidate ready; no Gate 4/SQL/store/LLM/source read | slice 1 |
| `AD-REL-001` | current Package validation, zero blockers and all 25 obligations authorize release | Semantic Input factory + Package factory | new focused release test file or same semantic file | complete Package | `DECLARATION_VALUES_RELEASED` | slice 2 |
| `AD-REL-002` | missing, duplicate or unknown evidence binding blocks release | release method | release test file | one mutation per binding failure | exact evidence error; no released values | slice 2 |
| `AD-REL-003` | incomplete Package reuses current blocker and never releases | Package/Semantic Input factories | release test file | existing incomplete Package fixture | existing Package/Semantic Input incomplete terminal | slice 2 |
| `AD-EVIDENCE-001` | every projected derived path has exactly one calculation owner, methodology binding and replayable input snapshot | existing component owners | release test file, parameterized manifest | all derived paths listed below | `DECLARATION_VALUES_RELEASED`; 0 gaps/duplicates | slice 2 |
| `AD-DIRECT-001` | direct/reference facts use direct evidence and do not get fake calculation receipts | existing component owners | release test file | filing/source/credit/reference fields | direct binding accepted; calculation object absent | slice 2 |
| `AD-PARITY-001` | old/new 49 values, paths, hashes, both XSD and bytes | Projection runtime | existing projection test file | frozen payable supplied case | both `FULL_TARGET_XML_VALID`; exact parity | slice 3 |
| `AD-NEG-001` | missing released `allowable_expenses` cannot read Package/rich fallback | Projection runtime | existing projection test file | delete one required value after release | source-value-missing; no XML | slice 3 |
| `AD-AUDIT-001` | removing audit/evidence/completeness after release is inert | Projection runtime | existing projection test file | values-only copy | exact same target proof/XML | slice 3 |
| `AD-ID-002` | file ID is target identity, not semantic identity | Projection runtime | existing projection test file | same values, two file IDs | same semantic hash; only file-id occurrence and XML hash differ | slice 3 |
| `AD-TM-001` | one payable allocation | Projection runtime | existing projection test file | current valid payable Package | 49 mappings, both XSD, byte parity | slice 3 |
| `AD-TM-002` | refund mechanics are characterized before eligibility | Projection runtime | existing projection test file | fully valid refund Package, not rehashed rich mutation | exact legacy/new parity or `gate5_full_target_projection_mechanics_unproven`; legacy authoritative | slice 3 |
| `AD-TM-003` | balanced mechanics are characterized before eligibility | Projection runtime | existing projection test file | fully valid balanced Package | same rule as `AD-TM-002` | slice 3 |
| `AD-TM-004` | multiple allocation ordering and values | Projection runtime | existing projection test file | fully valid two-allocation Package | occurrence order/path/hash parity or unproven blocker | slice 3 |
| `AD-TM-005` | empty allocation cannot silently lose a disposition | release + Projection runtimes | release/projection test files | valid empty-allocation Package | explicit proven legacy-equivalent terminal; never XSD-only success | slice 3 |
| `AD-SHADOW-001` | parity failure never replaces legacy authority | E2E runtime | existing E2E test file | injected candidate mismatch at explicit shadow boundary | legacy result unchanged; shadow `PARITY_FAILED` | slice 4 |
| `AD-PERSIST-001` | v0 XML artifact/result/receipt remain readable and exact | product/artifact resolver | existing E2E product test | pre-change v0 artifact fixture plus new run | v0 resolves/downloads; no rewrite | before slice 5 |
| `AD-ROLLBACK-001` | disabling the new route needs no data/tax replay | E2E factory | existing E2E test file | shadow/new route followed by legacy route | original legacy bytes/hash/result | before slice 5 |

The irreversible boundary in these tests is XML publication/persistence. Every
negative test asserts that no candidate XML is published or persisted after a
failed release/parity check. Core factories and tax logic are exercised, not
mocked; only existing provider/storage test boundaries may be substituted.

## 6. Release gate design

The release gate is orchestration, not another tax/completeness engine. A later
method on the existing runtime may be added:

```text
Gate5DeclarationSemanticInputRuntime.release_projection_values(package=...)
```

Its required order is:

1. call the current Package validator through the current semantic `compile`;
2. reuse the current complete-status, blocker and terminal-resolution checks;
3. build the inactive strict value candidate from the validated rich object;
4. bind each declared leaf to exactly one existing direct or calculation
   evidence owner in the same validated Package;
5. reject missing/duplicate/unknown bindings;
6. emit an in-memory release receipt;
7. hand only `declaration_values` and its contract/hash to the new projector
   entrypoint.

The release receipt binds, without duplicating raw snapshots:

```text
package_sha256
current_semantic_input_sha256
completeness_receipt_sha256
definition_sha256
25 obligation dispositions and counts
semantic_value_sha256
evidence_binding_manifest_sha256
release_policy_version
status = DECLARATION_VALUES_RELEASED
```

It does not understand XML, KND, target paths, rate logic, Gate 4, source
acquisition, missing-data recovery, product state or filing readiness. Package
status remains `complete_for_supplied_case`, not real-world taxpayer tax
completeness.

## 7. Calculation Evidence boundary

Calculation Evidence is a thin view over evidence already present in sealed
component snapshots. It is not a new calculation engine, store, graph or
registry service.

For each binding:

```text
declared_value_path
origin_kind = DERIVED | DIRECT | REFERENCE
declared_value_sha256
owner_factory
source_component_contract_id
source_component_sha256
methodology_binding_sha256 or null
replayable_input_snapshot_sha256 or direct_evidence_sha256
dependent_calculation_receipt_refs[]
```

The manifest must account for every declared leaf used by the Projection
Definition. These projected derived patterns require exactly one immediate
calculation owner:

| Declared value pattern | Immediate calculation owner | Existing replay basis |
| --- | --- | --- |
| `budget_dispositions[].kind` | `Gate5DeclarationBudgetOutcomeRuntimeFactory` | settlement component plus filing/allocation input snapshot |
| `budget_dispositions[].amount` | `Gate5DeclarationBudgetOutcomeRuntimeFactory` | payable/refundable group results and allocation evidence |
| `income_group_results[].income_group` | `Gate5IncomeGroupTaxBaseRuntimeFactory` | complete group scope and methodology binding |
| `income_group_results[].total_income` | `Gate5IncomeGroupTaxBaseRuntimeFactory` | group-value input snapshot |
| `income_group_results[].taxable_income` | `Gate5IncomeGroupTaxBaseRuntimeFactory` | group formula and input snapshot |
| `income_group_results[].accepted_expenses` | `Gate5IncomeGroupTaxBaseRuntimeFactory` | category models and accepted-expense formula |
| `income_group_results[].tax_base` | `Gate5IncomeGroupTaxBaseRuntimeFactory` | complete base formula and inputs |
| `income_group_results[].calculated_tax` | `Gate5DeclarationTaxSettlementRuntimeFactory` | rate-band methodology, unrounded result and rounding |
| `income_group_results[].tax_payable` | `Gate5DeclarationTaxSettlementRuntimeFactory` | calculated tax and complete credit facts |
| `income_group_results[].tax_refundable` | `Gate5DeclarationTaxSettlementRuntimeFactory` | complete credit facts and calculated tax |
| `russian_source_income[].gross_income` | `Gate5IncomeGroupTaxBaseRuntimeFactory` via the income-source component | referenced `total_income` result and source-entry binding |
| `financial_investment_results[].operation_category` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory` | member classification consensus and methodology |
| `financial_investment_results[].category_gross_income` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory` | complete member aggregate and source evidence |
| `financial_investment_results[].related_expenses` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory` | member expense aggregates |
| `financial_investment_results[].allowable_expenses` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory` | eligibility/allocation and member/category totals |
| `financial_investment_results[].loss_treatment` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory` | member consensus and methodology binding |

Filing/taxpayer/signer values, KBK/OKTMO, non-taxable income, deductions,
settlement credit facts, source-party facts and withheld tax retain direct or
reference evidence bindings. They must not acquire fabricated formulas merely
to satisfy a uniform shape.

Runtime release checks hashes and accounting only. The prerequisite parameter
test replays every derived pattern through its current factory and compares the
observable declared value. Projection does not rerun any calculation.

### Persist versus replay

The first four slices keep the evidence view in memory and retain current
Package/E2E audit authority. This avoids a new private artifact and any
persistence migration.

A later persistence decision is allowed only after all of these are measured:

- deterministic replay across retained methodology versions;
- retention/readability of exact source and input snapshots;
- performance of replay versus a private evidence sidecar;
- audit need for post-run inspection without re-executing tax models;
- user/case isolation and privacy of raw financial values.

If a sidecar is later required, it must be a new private, case-bound, versioned
artifact referenced by a v1 receipt. Existing v0 artifacts are not rewritten.

## 8. Persistence and historical compatibility

Current persistence facts:

- raw rich Semantic Input is not stored as its own artifact;
- `semantic_input_sha256` is stored in XML artifact v0 and safe metadata;
- the nested E2E receipt v0 contains the rich-input stage hash and the
  projection receipt v0 contains Package/Definition bindings;
- the product result v0 exposes `semantic_input_sha256`;
- XML bytes are independently content-addressed and downloadable under current
  user/case access controls.

Compatibility plan:

1. slices 1-4 create no persistent value-view or release artifact;
2. v0 factories, receipts, product result and XML artifact remain readable and
   writable by the legacy route;
3. no bulk migration, rehash or tax replay is permitted;
4. a future newly persisted payload uses new schema/artifact/receipt versions;
5. readers resolve v0 and v1 explicitly; v0 is never interpreted as v1;
6. new runs may add a v1 release/value binding only after product and external
   compatibility authorization;
7. retention of old artifacts, not a migration deadline, controls eventual
   removal eligibility.

## 9. Rollback plan

Rollback is cheap because the old path is never edited out during migration.

| Stage | Rollback action | Data action |
| --- | --- | --- |
| inactive candidate/release | stop calling or remove additive method | none |
| inactive new projector | stop calling `project_released` | none |
| shadow comparison | stop invoking explicit shadow method | none; legacy result was authority |
| new route selected for a proven profile | select legacy factory route | none; no DB or Tax Model replay |
| v1 persistence later enabled | stop writing v1, continue v0 reader and legacy path | keep existing v1 immutable; no downgrade rewrite |

A parity failure is not thrown through the current product success path during
shadow. It records `PARITY_FAILED` in private test/control evidence, discards the
candidate output and returns the unmodified legacy result. No new result is
allowed to overwrite an existing XML artifact.

## 10. Ordered reversible production slices

| Slice | Change | Files/owners | Acceptance and rollback |
| --- | --- | --- | --- |
| 1. inactive value candidate | add `compile_declaration_value_candidate` to existing runtime; exact validator/hash; no caller | semantic-input module, its tests, regenerated Gate 1 bundle and the two exact bundle-hash guards | `AD-VIEW-*`, `AD-ID-001`, `AD-FACTORY-001`; delete unused method to roll back |
| 2. inactive release/evidence | add release method and thin binding manifest in the same owner; no projector call | same semantic owner/tests/bundle | all 25 obligations and evidence rows exact; remove unused method to roll back |
| 3. inactive consumer-first projector | add `project_released`; add immutable v1 Projection Definition; keep tree projector/serializer/XSD and legacy `project` exact | projection runtime/resource/tests/bundle | parity for proven payable profile plus all negative/mechanics gates; stop calling new method to roll back |
| 4. explicit shadow path | add E2E `run_with_projection_parity` or equivalently narrow opt-in entrypoint; legacy remains returned authority | E2E runtime/tests/bundle | same Package, no upstream rerun, parity receipt; remove opt-in call to roll back |
| 5. move one proven internal consumer | select released projector only for profiles whose mechanics suite is fully green; keep legacy call compiled and callable | E2E factory and tests | exact product/E2E observable parity and rollback test; select legacy route to roll back |
| 6. optional versioned persistence/public move | only if separately authorized, add v1 receipt/artifact/result fields and readers | product/persistence contracts and tests | v0 readability plus v1 isolation; stop v1 writes, never rewrite v0 |
| 7. deprecate/remove rich coupling | only after all consumers, retention, profiles and rollback evidence close | legacy source paths/definitions and exported surface | independent deprecation GOAL; not part of the initial refactor |

Every slice is independently useful or inert and leaves a terminal test surface.
No slice combines structural refactor with a tax/declaration behavior change.

## 11. Risk matrix

Risks are deliberately not collapsed into one score.

| Dimension | Concrete failure | Early-slice exposure | Control/activation gate |
| --- | --- | --- | --- |
| semantic | omitted or renamed declared value | medium | exact schema, deletion matrix, 44 value-mapping accounting |
| tax | extraction recalculates or changes a Tax Model result | low if invariant held | copy only current outputs; no tax factory changes or reruns in projection |
| audit | value hash is mistaken for Package/audit authority | high | keep three distinct hashes and Package as sealed authority |
| completeness | projector receives values before all 25 obligations/evidence bindings close | high | existing Package validation plus release receipt; no direct candidate projection |
| XML | changed paths/transforms/order or unproved mechanics alter target | high in slice 3 | immutable v1 Definition, old/new mapping/path/hash/XSD/byte parity |
| persistence | v0 artifact/receipt becomes unreadable or reinterpreted | low in slices 1-4, high later | no early writes; explicit v1, v0 reader retained, no migration |
| external consumer | exported class/result/hash client breaks | medium/unknown | preserve all v0 APIs/fields; external uncertainty blocks deletion |
| product | shadow output leaks into download/persistence | low if opt-in remains separate | legacy result authority; no shadow result in product receipt/artifact |
| rollback | new route cannot be disabled without data or tax replay | low | old code/resource/reader retained; one explicit route selection |

### Legacy target-mechanics destruction-point probe

An isolated, non-production probe started from the valid supplied-case rich v0,
changed only semantic payloads and recomputed their current content hashes. It
did not create valid alternative Tax Model/Package cases and therefore is not
tax evidence. It exposed why XSD-only tests are insufficient:

| Probe | Legacy projector terminal | XML bytes | mapping occurrences |
| --- | --- | ---: | ---: |
| current payable/single allocation | XSD-valid | 1,112 | 49 |
| balanced/empty allocation mutation | XSD-valid | 1,015 | 45 |
| refund/empty allocation mutation | XSD-valid | 1,015 | 45 |
| payable/two-allocation mutation | XSD-valid | 1,199 | 53 |

These results do not authorize any of those alternative profiles. They require
fully valid Package fixtures and explicit semantic/path parity before a profile
can leave shadow. In particular, XSD success must not hide a lost budget row.

## 12. Versioning and identity plan

Three identities remain separate and useful:

| Identity | Meaning | Must exclude/include |
| --- | --- | --- |
| `semantic_input_sha256` | exact current rich audit/source envelope for one run | includes Package/source/component/completeness bindings; may vary with run-local refs |
| `semantic_value_sha256` | version-bound declaration business values | includes value-contract ID/version and strict values; excludes audit, completeness and target context |
| target hashes | rendered mapping values and final XML for one target context | include target mechanics, Definition version/hash, transforms, order, serializer and file ID |

The value hash never authorizes release. The release receipt binds the value
hash to the audit/completeness/evidence hashes. The target receipt binds the
released value hash and target context to rendered values/XML.

Any source-path change in the Projection Definition requires:

- a new immutable input-contract ID/version;
- a new Projection Definition version and full content hash;
- retention of the current v0 resource/hash;
- an explicit legacy/new relation in parity evidence;
- no silent rewrite under `2026-08-11.0-proof`.

The v1 target tree, mapping IDs, target paths, transforms, constants, ordering,
serializer and XSD pins remain mechanically identical wherever byte parity is
claimed. Only input-contract/source paths and explicitly separated mechanics
sources may differ.

## 13. Deprecation prerequisites

Rich v0 fields or exports may be deprecated only after all conditions hold:

1. repository inventory and external-owner confirmation contain no unhandled
   rich-object consumer;
2. v0 artifacts/receipts remain readable for their full retention period;
3. all production value consumers use released values, not a compatibility
   adapter over rich v0;
4. every active target/profile has semantic, path, XSD and required byte parity;
5. refund, balanced, multi-allocation and empty-allocation mechanics have valid
   Package fixtures and explicit terminals;
6. every projected derived value has one replayable evidence binding;
7. shadow has no unresolved mismatch for the agreed observation window;
8. product/public versioning and rollback are proven;
9. a separate destructive/deprecation GOAL is authorized.

Until then v0 is not marked deprecated, fields are not removed, and old source
paths remain supported.

## 14. Explicit DO-NOT-TOUCH list

The first implementation slice must not edit:

- Gate 4 materialization/cache/readers or Gate 3 boundaries;
- any securities operation Tax Model, category aggregation, income-group base,
  settlement, filing/party, budget, income-source or financial-investment
  behavior;
- `gate5_resolved_declaration_package.py`;
- trusted Full Declaration Definition code or obligation/publication resources;
- current Semantic Input `compile`, `validate_semantic_input`, schema/status or
  exported names;
- current Projection Definition resource/hash;
- `Gate5FullTargetXmlTreeProjector`, serializer, XSD validator or official XSD;
- E2E runtime/result/receipt and hash-chain behavior;
- ArtifactStore, resolver, models, database/schema/migrations and retention;
- OpenWebUI product adapter, pipe response/download, ACL/user isolation;
- current XML artifact/product result/receipt schema versions;
- unrelated dirty-tree files.

The generated Gate 1 bundle is touched only as a closed-world mirror when the
future implementation changes a bundled source module; that mechanical update
does not authorize product routing.

## 15. Recommended first implementation GOAL

```text
G5.39AE - Additive Inactive Declaration Value Candidate
```

Only this smallest slice is recommended:

- add `compile_declaration_value_candidate(package=...)` to the existing
  `Gate5DeclarationSemanticInputRuntime`;
- call existing `compile(package=...)` exactly once;
- emit/validate the bounded candidate envelope and stable value hash;
- add `AD-VIEW-001..004`, `AD-ID-001` and `AD-FACTORY-001` tests;
- regenerate the already-required Gate 1 closed-world bundle and exact hash
  guards;
- do not export a second factory/class;
- do not add release, projector, E2E, persistence or product callers;
- do not commit/push/PR unless that future GOAL separately authorizes delivery.

Success for G5.39AE means only that an inert, strict and stable value view can
be produced by the existing owner. It does not mean `RELEASED`, parity proven,
projector migration, persistence compatibility or activation.

## Performance and bounded extensibility

Candidate extraction is one pass over already resolved declaration values:
`O(number of declaration value leaves)`. Release accounting is `O(25 + number
of evidence bindings)`. Projection remains one tree pass. Shadow temporarily
doubles projection/serialization only; it never reruns Gate 4, Tax Models,
Package assembly, source reads, LLM/provider calls or SQL.

Future domains extend the declaration-value contract only when a real
declaration consumer and evidence owner exist. They add a versioned value
surface and Projection Definition binding. They do not inherit the current rich
wrapper, create a universal ontology, or force inactive domain graphs into every
projector request.

## Validation evidence and limitation

The unchanged current E2E route passed its focused test in Windows PowerShell:

```text
test_source_to_official_xml_replays_every_gate_and_emits_hash_chain
1 passed in 1.72s
```

The separate focused projection test executed but failed during fixture setup,
before the projector or any assertion, with
`Gate4FinancialCaseCacheError: gate4_cache_missing`. This is attributed to that
fixture's Gate 4 cache setup in the current dirty checkout, not to an XML,
parity or AD report change. No production test, fixture or cache behavior was
edited to obtain a green result.

## KISS and final stop

- one existing semantic factory owner is extended;
- one current Package validator remains authoritative;
- one old projector path remains authoritative through shadow;
- one immutable v1 definition is added only when source paths actually change;
- no duplicate reader, model, database, engine, registry or migration framework;
- removal is last and separately authorized.

`MINIMAL_REFRACTOR_DESIGN_READY` is a design terminal only. No implementation,
migration, activation, commit, push or pull request is authorized by G5.39AD.
