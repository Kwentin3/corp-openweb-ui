from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from referencing import Registry, Resource

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    Gate4FinancialCaseCacheError,
    Gate4FinancialCaseMaterializationError,
    Gate4FinancialCaseRuntimeFactory,
    Gate4FinancialCaseSqlCacheFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate4_financial_case_cache import (
    FACTORY_REQUIRED as CACHE_FACTORY_REQUIRED,
    FORBIDDEN as CACHE_FORBIDDEN,
)
from broker_reports_gate1.gate4_financial_case_materialization import (
    FACTORY_REQUIRED as MATERIALIZER_FACTORY_REQUIRED,
    FORBIDDEN as MATERIALIZER_FORBIDDEN,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CONTRACTS = REPO_ROOT / "docs" / "stage2" / "contracts"
MODEL_ID = "models/gemini-3.5-flash"

_SOURCE_ROWS = (
    "Покупка|10.01.2026|ACME|10|125,00|USD|12,50",
    "Продажа|11.02.2026|ACME|4|60,00|USD|15,00",
    "Дивиденд|12.03.2026|ACME|8,00|USD",
    "Комиссия|11.02.2026|1,25|USD",
    "Налог|12.03.2026|1,20|USD",
)
_FACT_SPECS = (
    (
        "SECURITY_PURCHASE",
        (
            ("date", "10.01.2026"),
            ("asset", "ACME"),
            ("quantity", "10"),
            ("amount", "125,00"),
            ("currency", "USD"),
            ("unit_price", "12,50"),
        ),
    ),
    (
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2026"),
            ("asset", "ACME"),
            ("quantity", "4"),
            ("amount", "60,00"),
            ("currency", "USD"),
            ("unit_price", "15,00"),
        ),
    ),
    (
        "DIVIDEND_INCOME",
        (
            ("date", "12.03.2026"),
            ("amount", "8,00"),
            ("currency", "USD"),
            ("asset", "ACME"),
        ),
    ),
    (
        "TRANSACTION_CHARGE",
        (
            ("date", "11.02.2026"),
            ("amount", "1,25"),
            ("currency", "USD"),
            ("asset", None),
        ),
    ),
    (
        "TAX_WITHHELD",
        (
            ("date", "12.03.2026"),
            ("amount", "1,20"),
            ("currency", "USD"),
            ("asset", None),
        ),
    ),
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_FACT_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.schema.json"
)
_TARGET_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json"
)
_REGISTRY = Registry().with_resource(
    _TARGET_SCHEMA["$id"], Resource.from_contents(_TARGET_SCHEMA)
)
_FACT_VALIDATOR = Draft202012Validator(
    _FACT_SCHEMA,
    registry=_REGISTRY,
    format_checker=FormatChecker(),
)


def test_materializes_five_representative_types_without_financial_inference(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-representative-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    result = runtime.materialize_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )

    assert [fact["financial_type"] for fact in result.facts] == [
        item[0] for item in _FACT_SPECS
    ]
    assert all(fact["status"] == "role_complete" for fact in result.facts)
    for fact in result.facts:
        _FACT_VALIDATOR.validate(fact)
        assert fact["gate3_binding"]["financial_annotations_artifact_id"] == (
            sidecar.artifact_id
        )
        assert fact["gate3_binding"]["canonical_binding"] == {
            "document_id": document_id,
            "canonical_version_id": canonical.canonical_version_id,
        }
    purchase = result.facts[0]
    assert _values(purchase) == {
        "date": "2026-01-10",
        "asset": "ACME",
        "quantity": "10",
        "amount": "125.00",
        "currency": "USD",
        "unit_price": "12.50",
    }
    charge = result.facts[3]
    assert _values(charge)["asset"] is None
    amount = next(item for item in charge["roles"] if item["role"] == "amount")
    assert amount["source_binding"]["source_literal"] == "1,25"
    assert amount["value"] == "1.25"


def test_required_missing_is_preserved_and_unsupported_value_fails_closed(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    missing = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-required-missing",
        created_at="2026-08-08T10:00:00+00:00",
        purchase_date=None,
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    facts = runtime.materialize_artifact(
        financial_annotations_artifact_id=missing.artifact_id,
        context=context,
    ).facts

    assert facts[0]["status"] == "role_incomplete"
    assert facts[0]["roles"][0] == {
        "role": "date",
        "requirement": "required",
        "status": "missing",
    }
    _FACT_VALIDATOR.validate(facts[0])

    invalid = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-invalid-date",
        created_at="2026-08-08T10:01:00+00:00",
        purchase_date="10",
    )
    with pytest.raises(Gate4FinancialCaseMaterializationError) as failure:
        runtime.materialize_artifact(
            financial_annotations_artifact_id=invalid.artifact_id,
            context=context,
        )
    assert failure.value.code == "gate4_role_value_invalid"


def test_sql_queries_and_delete_rebuild_preserve_exact_facts(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-cache-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )
    first_bytes = _canonical_json(first)
    first_ids = [fact["fact_id"] for fact in first]

    for financial_type in (
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
        "TRANSACTION_CHARGE",
        "TAX_WITHHELD",
    ):
        selected = runtime.list_by_financial_type(
            context=context,
            financial_type=financial_type,
        )
        assert [fact["financial_type"] for fact in selected] == [financial_type]
    assert {
        fact["financial_type"]
        for fact in runtime.list_by_asset(context=context, asset="ACME")
    } == {
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
    }
    assert {
        fact["financial_type"]
        for fact in runtime.list_by_period(
            context=context,
            date_from="2026-02-11",
            date_to="2026-02-11",
        )
    } == {"SECURITY_DISPOSAL", "TRANSACTION_CHARGE"}
    assert runtime.get_fact(context=context, fact_id=first_ids[0]) == first[0]

    runtime.clear_case_cache(context=context)
    with pytest.raises(Gate4FinancialCaseCacheError) as missing:
        runtime.list_facts(context=context)
    assert missing.value.code == "gate4_cache_missing"

    rebuilt = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )
    assert [fact["fact_id"] for fact in rebuilt] == first_ids
    assert _canonical_json(rebuilt) == first_bytes


def test_new_sidecar_and_new_canonical_never_reuse_old_current_cache(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    first_sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-stale-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    old = runtime.rebuild_artifact(
        financial_annotations_artifact_id=first_sidecar.artifact_id,
        context=context,
    )

    second_sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-stale-b",
        created_at="2026-08-08T10:01:00+00:00",
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as sidecar_stale:
        runtime.list_facts(context=context)
    assert sidecar_stale.value.code == "gate4_cache_stale"
    refreshed = runtime.rebuild_artifact(
        financial_annotations_artifact_id=second_sidecar.artifact_id,
        context=context,
    )
    assert {fact["fact_id"] for fact in refreshed}.isdisjoint(
        fact["fact_id"] for fact in old
    )

    replacement_context = replace(
        context,
        normalization_run_id="g4-runtime-run-2",
    )
    _activate_canonical(
        store=store,
        context=replacement_context,
        document_id=document_id,
        artifact_version=2,
        expected_previous_version_id=canonical.canonical_version_id,
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as canonical_stale:
        runtime.get_fact(context=context, fact_id=refreshed[0]["fact_id"])
    assert canonical_stale.value.code == "gate4_cache_stale"


def test_cache_uses_existing_artifact_lifecycle_and_tenant_scope(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-lifecycle-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    cached = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )

    different_tenant = replace(context, user_id="different-user")
    with pytest.raises(Gate4FinancialCaseCacheError) as denied:
        runtime.get_fact(
            context=different_tenant,
            fact_id=cached[0]["fact_id"],
        )
    assert denied.value.code == "gate4_cache_missing"

    store.purge_case(context)
    cache = Gate4FinancialCaseSqlCacheFactory(
        store=store,
        read_enabled=True,
    ).create()
    with cache._transactions.open(context=context, write=False) as repository:
        assert repository.generations() == ()


def test_factory_closed_world_and_non_goal_guards() -> None:
    assert "Gate4FinancialCaseMaterializerFactory.create" in (
        MATERIALIZER_FACTORY_REQUIRED
    )
    assert "Gate4FinancialCaseRuntimeFactory.create" in CACHE_FACTORY_REQUIRED
    assert "ArtifactStore" in CACHE_FACTORY_REQUIRED
    assert "LLM" in MATERIALIZER_FORBIDDEN
    assert "second database" in CACHE_FORBIDDEN

    materializer_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate4_financial_case_materialization.py"
    ).read_text(encoding="utf-8")
    cache_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate4_financial_case_cache.py"
    ).read_text(encoding="utf-8")
    bundle_builder = (
        SERVICE_ROOT / "scripts" / "build_openwebui_pipe_bundle.py"
    ).read_text(encoding="utf-8")
    assert "Gate3RoleValueResolverFactory.create_from_active_canonical" in (
        materializer_source
    )
    assert "Gate3FinancialRolePackFactory.create" in materializer_source
    assert "Gate3NdflCaseReadinessFactory" in cache_source
    assert "self._store.sqlite_path" in cache_source
    assert "process.env" not in cache_source
    for forbidden_source_marker in (
        "pdf",
        "csv",
        "xlsx",
        "raw_report",
        "source_payload",
    ):
        assert forbidden_source_marker not in cache_source.casefold()
        assert forbidden_source_marker not in materializer_source.casefold()
    assert '"gate4_financial_case_materialization"' in bundle_builder
    assert '"gate4_financial_case_cache"' in bundle_builder


def _setup(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g4-runtime-user",
        normalization_run_id="g4-runtime-run-1",
        case_id="g4-runtime-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    document_id = "g4-runtime-document"
    canonical = _activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
    )
    return store, context, document_id, canonical


def _activate_canonical(
    *,
    store,
    context: ArtifactAccessContext,
    document_id: str,
    artifact_version: int,
    expected_previous_version_id: str | None,
):
    retention = build_retention_policy(mode="api_smoke")
    source_ref = f"g4-runtime-source-{artifact_version}"
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={
                "openwebui_file_id": f"synthetic-g4-file-{artifact_version}"
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload={"synthetic": True},
        )
    )
    normalizer = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version=f"g4-runtime-test-v{artifact_version}"
        )
    ).create()
    artifact = normalizer.build(
        tenant_id=context.user_id,
        artifact_version=artifact_version,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(
                f"g4-runtime-{artifact_version}".encode("utf-8")
            ).hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "text",
                            "text": text,
                            "source_location": {"block_index": index},
                        }
                        for index, text in enumerate(_SOURCE_ROWS, start=1)
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )
    canonical = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=canonical.canonical_version_id,
        expected_previous_version_id=expected_previous_version_id,
        context=context,
        actor="g4-runtime-test",
        reason="G4.2 deterministic cache test",
    )
    return canonical


def _persist_sidecar(
    *,
    store,
    context: ArtifactAccessContext,
    document_id: str,
    canonical_version_id: str,
    artifact_id: str,
    created_at: str,
    purchase_date: str | None = "10.01.2026",
) -> ArtifactRecord:
    envelope = CanonicalReaderFactory(
        store=store,
        read_enabled=True,
    ).create().read_active_envelope(document_id, context)
    nodes = envelope.artifact["nodes"]
    assert len(nodes) >= len(_FACT_SPECS)
    annotations = []
    for index, (financial_type, role_specs) in enumerate(_FACT_SPECS):
        target = {"kind": "node", "node_id": nodes[index]["node_id"]}
        roles = []
        for role, literal in role_specs:
            if index == 0 and role == "date":
                literal = purchase_date
            if literal is None:
                roles.append({"role": role, "status": "missing"})
            else:
                roles.append(
                    {
                        "role": role,
                        "status": "bound",
                        "target": copy.deepcopy(target),
                        "exact_text": literal,
                    }
                )
        annotations.append(
            {
                "target": target,
                "financial_label": financial_type,
                "roles": roles,
            }
        )
    payload = {
        "schema_version": "broker_reports_financial_annotations_v2",
        "canonical_binding": {
            "document_id": document_id,
            "canonical_version_id": canonical_version_id,
        },
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "role_pack_identity": {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "role_instruction_identity": {
            "instruction_id": "broker-reports-source-bound-role-labeling",
            "semantic_version": "1.0.0",
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": annotations,
        "validation_status": "validated",
    }
    return store.put_record(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": True,
                "financial_annotations_sidecar_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=payload,
            safe_metadata={
                "provider_profile_id": "google_gemini",
                "document_completion_status": "complete",
                "annotations_total": len(annotations),
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _values(fact: dict) -> dict[str, str | None]:
    return {
        item["role"]: item.get("value")
        for item in fact["roles"]
    }


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
