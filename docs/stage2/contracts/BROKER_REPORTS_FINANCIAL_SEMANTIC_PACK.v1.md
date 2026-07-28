# Broker Reports Financial Semantic Pack v1

Status: normative target asset; validated; not live-activated

Pack schema version: `broker_reports_financial_semantic_pack_v1`

Semantic version: `1.0.0`

Pack ID: `broker_reports_managed_financial_semantic_pack`

Consumer contract:
`broker_reports_managed_financial_domain_contract_v1`

Machine-readable assets:

- `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.json`;
- `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.schema.json`.

## 1. Authority boundary

The Pack is the semantic authority for the target Managed Financial Domain.
Type definitions, roles, examples, counterexamples, synonyms, semantic
distinctions, ambiguity guidance, and lifecycle metadata are data in the Pack,
not type-specific Python behavior.

This authority is deliberately type-scoped. The closed Choice/decision
contracts own decision-reason codes and response shape. Human-readable
cross-decision reason meanings belong in one separately versioned catalog
dependency of the existing OpenWebUI Financial Domain asset family. That
catalog may contrast reasons such as "no available type applies" versus
"multiple available types remain plausible"; it must not copy or redefine a
financial type.

Per-type `experimental` / `active` / `deprecated` / `retired` state in this
Pack is not the publication state of the Pack or managed asset family. Complete
asset-version `draft` / validation / active selection / retirement / rollback
is an explicit release-layer gap while this Pack remains not live-activated.

The current live/runtime Registry remains a migration source until later
GOALs. It is not silently replaced or reported as live by GOAL 2:

- Registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- accepted Registry SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- Pack authority status: `target_normative_not_live`;
- runtime activation: `false`.

No provider call, customer call, stage mutation, runtime route change, or
production admission is part of this contract.

## 2. Full compact snapshot

`full_compact_snapshot` is the complete, ordered type inventory delivered to a
consumer. There is no second reduced copy whose meaning can drift.

Version `1.0.0` contains exactly the two accepted active types from the pinned
baseline:

1. `cash_balance_snapshot_v1`;
2. `printed_financial_metric_v1`.

Every type contains:

- stable `input_type_id`, title, definition, and semantic class;
- required, optional, and forbidden roles;
- value type, cardinality, and mandatory source-ref policy for each admitted
  role;
- date/period, currency/unit, sign, and identity policy;
- examples, counterexamples, and synonyms;
- explicit distinctions from adjacent concepts;
- fail-safe ambiguity guidance;
- lifecycle and deprecation/replacement fields;
- operational contract IDs, safe evidence refs, test refs, and legacy
  migration fingerprint.

Array order is normative. Type definitions are sorted by `input_type_id`; role
specs and guidance preserve their committed review order.

## 3. Deliberately deferred candidates

The following research candidates remain outside the type snapshot:

- `credit_loss_allowance_movement_v1`;
- `credit_loss_allowance_snapshot_v1`;
- `equity_balance_snapshot_v1`;
- `lease_liability_snapshot_v1`;
- `lease_payment_schedule_item_v1`;
- `lease_right_of_use_asset_snapshot_v1`;
- `payable_balance_snapshot_v1`;
- `receivable_balance_snapshot_v1`;
- `regulated_asset_balance_snapshot_v1`;
- `security_inventory_balance_snapshot_v1`.

Listing a candidate in `source_baseline.deferred_candidate_ids` is not
admission. A deferred ID cannot be returned as a typed record.

Broad legacy fact IDs, router domains, source labels, evidence kinds, and
technical dispositions are not Pack type IDs.

## 4. Canonical serialization and integrity

The canonical Pack material is:

1. the complete Pack object with top-level `integrity_sha256` omitted;
2. UTF-8 without BOM;
3. object keys sorted lexicographically;
4. arrays kept in normative committed order;
5. no insignificant whitespace;
6. SHA-256 over the resulting bytes.

For Pack `1.0.0`:

- canonical bytes: `9404`;
- integrity SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`.

Any change to type meaning, role policy, guidance, lifecycle, ordering, source
baseline, overlay policy, or serialization material changes the integrity
hash. A breaking semantic change also requires a new semantic version and,
when DTO interpretation changes, a new schema version.

## 5. Tenant overlay contract

Tenant extension is optional, explicit, versioned, and disabled by default.
The same JSON Schema defines
`broker_reports_financial_semantic_pack_tenant_overlay_v1`.

Every overlay pins:

- overlay ID and semantic version;
- opaque tenant scope ref;
- lifecycle: `draft`, `qualified`, or `retired`;
- exact base Pack ID, semantic version, and integrity hash;
- its own integrity hash.

Allowed changes are limited to:

- augmenting synonyms, examples, counterexamples, or ambiguity guidance for a
  named base type;
- adding a complete experimental tenant type.

An experimental tenant type remains non-production until independently
qualified. The overlay cannot:

- modify a base definition, roles, or identity;
- remove a base type;
- activate an unqualified type;
- add tax methodology.

An overlay is rejected when its base Pack identity is stale, its tenant scope
does not match the authorized request, its integrity hash fails, it tries a
forbidden change, or an added type is not experimental and explicitly
qualified.

## 6. Semantic rules

The Pack provides meaning and ambiguity guidance; it does not perform
classification itself. The later managed Skill/Prompt and universal validator
must:

- consume the exact pinned Pack;
- choose only a Pack type;
- preserve source refs and source literals;
- choose first-class unclassified data when the Pack does not support a safe
  type;
- never infer missing values or create a new type.

The Pack does not contain Gate 3 tax, declaration, ledger, cost-basis, P/L,
netting, or currency-conversion methodology.

## 7. Migration and non-goals

GOAL 2 does not remove the legacy current-runtime Python Registry. Later GOALs
must route the target path through the Pack, prove parity, and retire
type-specific Python meaning from the default route.

`TYPE_MEANINGS_IN_PYTHON: ZERO_IN_TARGET` means the new
`semantic_packs/` target asset contains JSON only. It does not make a false
claim that the current live legacy path has already been retired.

## 8. Normative status

```text
SEMANTIC_PACK: VALIDATED_AND_VERSIONED
TYPE_MEANINGS_IN_PYTHON: ZERO_IN_TARGET
FULL_PACK_DELIVERY: SUPPORTED
TENANT_EXTENSION: EXPLICIT_AND_VERSIONED
RUNTIME_ACTIVATION: FALSE
GATE3_TAX_METHODOLOGY: ZERO
```
