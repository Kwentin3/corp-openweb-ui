# G5.39AF - Declaration Release Authority

Verified: 2026-08-12

Mode: autonomous test-first implementation loop

Terminal: `DECLARATION_RELEASE_AUTHORITY_PROVEN`

## Result

The existing `Gate5DeclarationSemanticInputRuntime` now exposes one additive,
inactive release seam:

```text
release_declaration_value_candidate(package=..., candidate=...)
```

It validates one sealed Resolved Package through the existing validation-only
Package factory, reconstructs the exact AE candidate, rejects candidate drift,
accounts for completeness and existing evidence owners, and returns an
in-memory released-values envelope.

The release status is:

```text
DECLARATION_VALUES_RELEASED
```

This status authorizes only the already calculated declaration values to leave
the audit boundary. It does not activate a projector, product route, persisted
artifact, download or public API.

Safe machine-readable evidence is in the
[terminal receipt](./BROKER_REPORTS_GATE5_DECLARATION_RELEASE_AUTHORITY_G5_39AF.receipt.safe.json).

## Ownership and boundary

| Concern | Owner after AF |
| --- | --- |
| Package validity and sealed audit authority | unchanged `Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only` |
| supplied-case completeness | unchanged Package completeness receipt |
| declaration candidate compilation | unchanged `Gate5DeclarationSemanticInputRuntimeFactory.create` |
| release accounting | additive method on that same Semantic Input runtime |
| calculation/direct evidence | unchanged component and Tax Model owners inside the Package |
| projection/XML/product | unchanged legacy path; AF has no caller there |

No separate release service, evidence registry, graph, database, methodology
engine or calculation path was introduced.

## Release contract

```text
schema_version = broker_reports_gate5_released_declaration_values_v0
status = DECLARATION_VALUES_RELEASED
release_receipt.schema_version = broker_reports_gate5_declaration_release_receipt_v0
release_policy.id = supplied_case_existing_evidence_release
release_policy.version = 2026-08-12.0-bounded
```

The envelope retains the unchanged AE `value_contract`, `declaration_values`
and `semantic_value_sha256`. The release receipt contains only hashes,
identities, value paths and accounting metadata; it does not duplicate raw
component snapshots or declaration values.

The release algorithm is linear in Package obligations and candidate value
leaves. It validates the Package once, performs no upstream replay and makes no
Gate 4, SQL, store, source-document, provider, LLM, projection or XML read.

## Completeness proof

On the frozen supplied case the existing trusted Definition and sealed Package
produce:

| Observation | Result |
| --- | --- |
| Definition obligations | 25 |
| unique obligations | 25 |
| terminal obligations | 25 |
| `RESOLVED` | 11 |
| `NOT_APPLICABLE` | 0 |
| `NOT_ACTIVATED_FOR_SUPPLIED_CASE` | 14 |
| Package blockers | 0 |
| real-world taxpayer tax completeness asserted | false |

The obligation manifest SHA-256 is
`88883f05c12fc93a7c8a5a0a97f519f1d8eb2e59f4c0b6939274ba810275aeaa`.

An independently valid incomplete Package retains the existing
`DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE` terminal and release stops with
`gate5_declaration_semantic_source_package_incomplete`.

## Evidence accounting proof

Every concrete declared-value leaf in the AE candidate has exactly one binding:

| Origin kind | Count | Required authority |
| --- | ---: | --- |
| `DERIVED` | 15 | existing calculation owner plus calculation-authority and replay-input hashes |
| `DIRECT` | 28 | existing exact component owner plus direct-evidence hash; no calculation fields |
| `REFERENCE` | 3 | trusted Definition or allocation-reference owner plus direct-evidence hash; no calculation fields |
| total / unique paths | 46 / 46 | no missing, duplicate or unknown owner |

Derived bindings reuse the existing budget-outcome, income-group tax-base,
tax-settlement and tax-period category aggregation owners. Direct/reference
bindings reuse the filing/party, budget allocation, settlement/source component
or trusted Definition owner. No calculation object is fabricated for direct
facts.

The evidence-binding manifest SHA-256 is
`8b589631119598b1b69115938d05a706b43a9a9dec3c5fc49dc5796fea117a11`.

## Frozen supplied-case identity

| Evidence | SHA-256 / value |
| --- | --- |
| AE semantic value | `83484fd29f261888d4c1fd466672ba52ace4653a46d89ed445ac574a47258090` |
| AF release receipt | `c825f777fb9d410ec24fec8b3405cf92f71bfdebcc9e49a601e22eba6bc0a296` |
| released envelope | `dde1d303c8b2cd2c9f8e0ff84bd12360d91b7607015045b0d17ff22230e7a26c` |
| legacy E2E terminal | `END_TO_END_FULL_TARGET_XML_VALID` |

These hashes are run-specific safe evidence. The released envelope and receipt
were not persisted.

## Negative pressure

The focused tests prove these fail-closed outcomes:

| Mutation | Terminal |
| --- | --- |
| validly rehashed candidate value tamper | `gate5_declaration_release_candidate_mismatch` |
| one declared-value evidence binding removed | `gate5_declaration_release_evidence_binding_missing` |
| duplicate binding for one declared-value path | `gate5_declaration_release_evidence_binding_duplicate` |
| unknown owner substituted with all hashes recomputed | `gate5_declaration_release_evidence_owner_unknown` |
| valid incomplete Package | existing Semantic Input incomplete terminal; no release |

No test mocks the release owner, Package validator or Tax Model logic. The
irreversible boundary remains XML publication/persistence; AF never reaches it.

## Local blocker closure

The first wide replay exposed the previously attributed shared fixture drift:
the Gate 4 test helper hard-coded role-instruction version `1.0.0`, while the
current production owner is `1.1.0`. The fixture now imports
`GATE3_ROLE_LABELING_INSTRUCTION_VERSION` from that owner. This is a test-only
anti-drift repair; it changes no production contract or result.

After that repair the upstream Package/Tax owner selection changed from
`48 failed, 17 passed` with primary `gate4_cache_missing` to `65 passed`.

The full Gate 5 replay then found one deterministic stale Gate 1 bundle hash
pin. Updating the exact guard after the official rebuild changed `398 passed,
1 failed` to `399 passed`.

## Verification

| Selection | Result |
| --- | --- |
| AF focused suite | 7 passed |
| legacy Semantic Input + AE + AF + real E2E | 162 passed |
| Package/component/Tax Model owners | 65 passed |
| architecture/product/bundle selection | 25 passed; 6 unrelated deprecation warnings |
| all `test_broker_reports_gate5_*.py` | 399 passed |
| Black on AF source and focused test | passed |
| target `py_compile` | passed |
| official Gate 1 bundle rebuild twice | byte-stable |
| `git diff --check` | passed; line-ending warnings only |

The final Gate 1 bundle SHA-256 is
`8b834107636c009ff1e66ae0a95e87d7793b021dacf5d1bf204c4edee725a331`.

## Changed owners and files

- `gate5_declaration_semantic_input.py`: additive release and strict validation
  on the existing owner; the legacy compile route retains its direct Package
  validation anchor.
- `test_broker_reports_gate5_declaration_release_authority.py`: focused AF
  observable and negative tests.
- `test_broker_reports_gate4_sql_materialization.py`: one shared fixture now
  follows the current role-instruction owner constant.
- Gate 1 bundled pipe: regenerated with the official builder.
- two existing Gate 5 exact bundle guards: updated to the final bundle hash.
- this dated report and safe receipt.

No current architecture authority document was changed because no active
consumer contract changed.

## KISS and activation audit

- existing Package and Semantic Input owners reused;
- one ordinary in-memory boundary, not a framework;
- no new module, class hierarchy, store, DB, registry, graph or public schema;
- no tax calculation, value repair, inference or Package fallback;
- no new persistence or migration;
- no projector, E2E or product caller;
- legacy XML/download/persistence authority unchanged.

An AST scan finds one production definition and one internal validator call in
the owning module, with zero callers outside that owner and its generated
bundle mirror.

## Remaining unknowns and stop

AF does not prove:

- a consumer-first projector contract or non-payable target mechanics;
- old/new target parity across supported profiles;
- shadow orchestration, product cutover or rollback;
- need for a new persisted/public contract;
- any additional tax methodology coverage.

The next strategic boundary is:

```text
G5.39AG - Consumer-First Projection Contract
```

AF stops here. No AG implementation, activation, commit, push or pull request
was performed.
