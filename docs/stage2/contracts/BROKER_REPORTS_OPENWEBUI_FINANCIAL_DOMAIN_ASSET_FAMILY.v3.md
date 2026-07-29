# Broker Reports OpenWebUI Financial Domain Asset Family v3

Status: implemented inactive GOAL 7 successor; not live.

Family ID:
`broker_reports_gate2_financial_domain_assets`

Family semantic version: `1.2.0`

Manifest schema:
`broker_reports_financial_domain_managed_asset_manifest_v3`

## 1. Purpose

Family v3 packages the GOAL 6 decision-reason catalog v2 and identifies one
minimal managed Pack/reason projection profile for the future Context V2.1
work. It is an additive version of the existing family, not a second family
or runtime authority.

The immutable family v1 and family v2 manifests remain the active-baseline and
historical Context V2.0 records. Family v3 has
`runtime_activation=false`, `response_profile_status=not_implemented` and
`transport_eligible=false`.

## 2. Exact predecessor and rollback

Family v3 pins family v2 as its only predecessor:

| Field | Exact value |
| --- | --- |
| predecessor semantic version | `1.1.0` |
| predecessor manifest schema | `broker_reports_financial_domain_managed_asset_manifest_v2` |
| predecessor manifest integrity | `4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d` |
| predecessor manifest Git-blob SHA-256 | `4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586` |
| draft rollback | `discard_without_runtime_mutation` |
| active rollback | `select_previous_validated_immutable_family_version` |

No live full-family publisher or rollback executor is implemented.

## 3. Composition

The manifest keeps the exact three OpenWebUI assets and four base dependencies
from family v1. Its single reason-authority trio points to:

1. `broker_reports_gate2_financial_decision_reason_catalog@2.0.0`;
2. its Python-generated v2 JSON Schema; and
3. its existing v2 validator source.

There are exactly seven dependencies. Catalog v1 is not duplicated in family
v3; its immutable packaging remains preserved by family v2. The full Semantic
Pack v1 and full decision-reason catalog v2 files are not rewritten or
minimized.

The top-level composition remains exact family-v1 composition and therefore
keeps `strict_output_contract=broker_reports_gate2_financial_evidence_decision_v1`.
Catalog v2, its schema and validator are referenced only inside
`minimal_projection_profile`; they are not declared compatible with that
active two-reason response contract. The manifest separately preserves the
active decision-code authority and labels catalog v2 only as the inactive
minimal reason-card source.

The manifest has:

```text
manifest_sha256 =
8d48e23a876844376443eeb357bb381fe0443c2bf1525657b6f81979408c630c

Git-blob SHA-256 =
34c7c0528d1d4954681e36353f9b82c89e324955ce5916cb5c6b0588e75e85f3
```

## 4. Minimal managed projection profile

The sole profile identity is:

```text
profile_id =
broker_reports_gate2_minimal_managed_projection_v1_candidate

semantic_version = 1.0.0
status = inactive_candidate
runtime_activation = false
response_profile_status = not_implemented
transport_eligible = false
```

The single closed-world loader entrypoint is
`load_gate2_financial_semantic_model_assets(profile="minimal_model_surface_v1_candidate")`.
The single Pack/reason projection entrypoint remains
`Gate2FinancialSemanticV5ProjectionFactory.create_minimal_managed_projection`.

The emitted model payload contains only `type_cards` and
`unclassified_reasons`. Profile identity, source identities, canonical type
IDs and integrity metadata remain backend-only.

The exact current model payload is 2,102 canonical minified UTF-8 bytes with
SHA-256
`fae235725094d45d82dfe0eee3fefd4268cf1cd6a2c0aa8a5a7392a4b75acca5`.

## 5. Mapping and failure boundary

The projection implements only the exact mappings in
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
over the reason set selected by
[Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md).
Managed financial and reason wording is read from the Pack/catalog snapshots;
it is not copied into Python, Prompt, Packet or provider adapters.

Construction fails closed unless:

- the visible Pack set contains exactly the current two ordered types;
- each primary positive and negative signal exists and is non-empty;
- each type has exactly one direct reciprocal distinction against the other;
- catalog v2 is exact, inactive and has three ordered unique reasons; and
- every projected reason meaning has the contracted first-sentence boundary.

No shortlist, ranking, repair, wording fallback or truncation is permitted.

## 6. Runtime boundary

GOAL 7 does not:

- change the default active asset payload or historical Context V2.0 payload;
- change Packet, Choice, Prompt, request, adapter or provider code;
- add the catalog-v2 reason to the active two-reason Choice contract;
- create Context V2.1 or its private mapping receipt;
- activate OpenWebUI records, transport, persistence or replay;
- call a provider; or
- run the full benchmark.

GOAL 8 may consume this profile only through the existing Packet factory to
build the separately reviewed inactive Context V2.1 candidate.

## 7. Deterministic checks

From `services/broker-reports-gate1-proof`:

```powershell
python scripts/build_openwebui_managed_financial_assets.py --check
python scripts/build_gate2_financial_semantic_model_assets.py --check
python -m pytest -q tests/test_broker_reports_gate2_minimal_managed_projection.py tests/test_broker_reports_managed_decision_reason_catalog.py tests/test_broker_reports_gate_architecture.py --tb=short
```

Acceptance:

```text
SAME_FAMILY: YES
HISTORICAL_FAMILY_BYTES_CHANGED: ZERO
FULL_PACK_BYTES_CHANGED: ZERO
FULL_CATALOG_V2_BYTES_CHANGED: ZERO
MINIMAL_PROFILE: VERSIONED_AND_HASH_IDENTIFIED
MODEL_PAYLOAD_FIELDS: GOAL5_ONLY
SECOND_PROJECTION_AUTHORITY: ZERO
RUNTIME_ACTIVATION: FALSE
RESPONSE_PROFILE: NOT_IMPLEMENTED
PROVIDER_CALLS: ZERO
FULL_BENCHMARK: NOT_RUN
```
