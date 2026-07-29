from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest

from broker_reports_gate1.gate2_financial_evidence_decision import (
    UNCLASSIFIED_REASON_CODES,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
ASSET_ROOT = SERVICE_ROOT / "managed_assets"
SCRIPT_ROOT = SERVICE_ROOT / "scripts"
CATALOG_PATH = (
    ASSET_ROOT
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.json"
)
CATALOG_SCHEMA_PATH = CATALOG_PATH.with_name(
    "broker_reports_gate2_financial_decision_reason_catalog.v1.schema.json"
)
CATALOG_V2_PATH = CATALOG_PATH.with_name(
    "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
CATALOG_V2_SCHEMA_PATH = CATALOG_PATH.with_name(
    "broker_reports_gate2_financial_decision_reason_catalog.v2.schema.json"
)
CATALOG_CONTRACT_PATH = (
    SCRIPT_ROOT / "broker_reports_financial_decision_reason_catalog_contracts.py"
)
DECISION_CONTRACT_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "gate2_financial_evidence_decision.py"
)
MANIFEST_V1_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v1.manifest.json"
)
MANIFEST_V2_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v2.manifest.json"
)
MANIFEST_V2_SCHEMA_PATH = MANIFEST_V2_PATH.with_name(
    "broker_reports_financial_domain_assets.v2.manifest.schema.json"
)
MANIFEST_V3_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v3.manifest.json"
)
MANIFEST_V3_SCHEMA_PATH = MANIFEST_V3_PATH.with_name(
    "broker_reports_financial_domain_assets.v3.manifest.schema.json"
)
TOOL_V1_PATH = (
    ASSET_ROOT / "tools" / "broker_reports_financial_semantic_pack_tool.v1.py"
)
PACK_V1_PATH = (
    SERVICE_ROOT / "semantic_packs" / "broker_reports_financial_semantic_pack.v1.json"
)
RUNTIME_MODEL_ASSETS_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "gate2_financial_semantic_model_assets.py"
)
BUILD_SCRIPT = SCRIPT_ROOT / "build_openwebui_managed_financial_assets.py"
RUNTIME_BUILD_SCRIPT = SCRIPT_ROOT / "build_gate2_financial_semantic_model_assets.py"

EXPECTED_V1_MANIFEST_GIT_BLOB_SHA256 = (
    "2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315"
)
EXPECTED_V1_MANIFEST_SHA256 = (
    "b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59"
)
EXPECTED_V1_TOOL_GIT_BLOB_SHA256 = (
    "e7c1a49cc8988e88a16a0696c03ec7469c961a838fd22dd315257e50815ffaee"
)
EXPECTED_PACK_GIT_BLOB_SHA256 = (
    "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f"
)
EXPECTED_PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
EXPECTED_CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256 = (
    "99be5272ebab4e69e2533391f381bd27682496148f760e1e4a171f9e7162cdad"
)
EXPECTED_ACTIVE_ASSET_PAYLOAD_SHA256 = (
    "b80eed8b9a41fa039a9a8d961c972817ae840ce81d7c163de624b7d5a4ec123b"
)
EXPECTED_V2_MANIFEST_GIT_BLOB_SHA256 = (
    "4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586"
)
EXPECTED_CATALOG_V2_GIT_BLOB_SHA256 = (
    "cb784fe262c08297b9cd71c84e2bf36195d214f7aec82f3cc74f5707a24dde24"
)
EXPECTED_CATALOG_V2_SCHEMA_GIT_BLOB_SHA256 = (
    "d576e9368272f8bf6dd46250e9d798e7bf40c1dd56f98216262d770a12c2aa24"
)
EXPECTED_V3_MANIFEST_GIT_BLOB_SHA256 = (
    "34c7c0528d1d4954681e36353f9b82c89e324955ce5916cb5c6b0588e75e85f3"
)
EXPECTED_V3_MANIFEST_SHA256 = (
    "8d48e23a876844376443eeb357bb381fe0443c2bf1525657b6f81979408c630c"
)
EXPECTED_V3_MANIFEST_SCHEMA_GIT_BLOB_SHA256 = (
    "5f63f716c53440c88851de63d54c9c14ba708ff64ecc3599af6c7bed93d28020"
)


def _portable_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(_portable_bytes(path))
    assert isinstance(value, dict)
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _canonical_integrity(
    payload: dict[str, Any],
    *,
    field: str,
) -> str:
    material = copy.deepcopy(payload)
    material.pop(field)
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(encoded)


def _refresh_catalog_integrity(payload: dict[str, Any]) -> dict[str, Any]:
    payload["integrity_sha256"] = _canonical_integrity(
        payload,
        field="integrity_sha256",
    )
    return payload


def _load_contract_module() -> ModuleType:
    name = "broker_reports_financial_decision_reason_catalog_contracts_test"
    spec = importlib.util.spec_from_file_location(name, CATALOG_CONTRACT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _factory(module: ModuleType) -> Any:
    return module.Gate2FinancialDecisionReasonCatalogContractFactory(
        decision_contract_source=DECISION_CONTRACT_PATH.read_text(encoding="utf-8")
    )


def test_catalog_schema_is_python_owned_generated_and_gui_ready() -> None:
    module = _load_contract_module()
    factory = _factory(module)
    catalog = _read_json(CATALOG_PATH)
    schema = _read_json(CATALOG_SCHEMA_PATH)

    expected_schema_bytes = (
        json.dumps(
            factory.schema(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    assert _portable_bytes(CATALOG_SCHEMA_PATH) == expected_schema_bytes
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(catalog)

    snapshot = factory.create(catalog=catalog)
    assert snapshot.schema_version == (
        "broker_reports_gate2_financial_decision_reason_catalog_v1"
    )
    assert snapshot.catalog_id == (
        "broker_reports_gate2_financial_decision_reason_catalog"
    )
    assert snapshot.semantic_version == "1.0.0"
    assert snapshot.lifecycle_status == "draft"
    assert snapshot.runtime_activation is False
    assert snapshot.reason_codes == UNCLASSIFIED_REASON_CODES
    assert snapshot.integrity_sha256 == catalog["integrity_sha256"]
    assert snapshot.integrity_sha256 == _canonical_integrity(
        catalog,
        field="integrity_sha256",
    )

    assert catalog["gui"] == {
        "collection_title": "Unclassified financial decision reasons",
        "item_key": "code",
        "item_label": "human_title",
        "order_field": "display_order",
        "editable_fields": [
            "human_title",
            "meaning",
            "use_when",
            "do_not_use_when",
            "positive_example",
            "contrast_with_neighbouring_reasons",
        ],
        "immutable_fields": [
            "code",
            "selection_boundary",
        ],
    }


def test_reason_meanings_are_complete_and_mechanically_distinct() -> None:
    catalog = _read_json(CATALOG_PATH)
    reasons = catalog["reasons"]
    codes = {reason["code"] for reason in reasons}

    assert codes == set(UNCLASSIFIED_REASON_CODES)
    assert {reason["display_order"] for reason in reasons} == {1, 2}
    assert {
        reason["code"]: (
            reason["selection_boundary"]["minimum_inclusive"],
            reason["selection_boundary"]["maximum_inclusive"],
        )
        for reason in reasons
    } == {
        "no_registry_type": (0, 0),
        "ambiguous_registry_type": (2, "unbounded"),
    }
    for reason in reasons:
        assert set(reason) == {
            "code",
            "display_order",
            "human_title",
            "meaning",
            "use_when",
            "do_not_use_when",
            "positive_example",
            "contrast_with_neighbouring_reasons",
            "selection_boundary",
        }
        for field in (
            "human_title",
            "meaning",
            "use_when",
            "do_not_use_when",
            "positive_example",
        ):
            assert len(reason[field].split()) >= 4
        contrasts = reason["contrast_with_neighbouring_reasons"]
        assert {item["reason_code"] for item in contrasts} == (codes - {reason["code"]})
        assert all(item["reason_code"] != reason["code"] for item in contrasts)


def test_python_contract_contains_no_catalog_human_wording() -> None:
    catalog = _read_json(CATALOG_PATH)
    source = CATALOG_CONTRACT_PATH.read_text(encoding="utf-8")
    human_values = [catalog["gui"]["collection_title"]]
    for reason in catalog["reasons"]:
        human_values.extend(
            reason[field]
            for field in (
                "human_title",
                "meaning",
                "use_when",
                "do_not_use_when",
                "positive_example",
            )
        )
        human_values.extend(
            item["distinction"] for item in reason["contrast_with_neighbouring_reasons"]
        )

    assert all(value not in source for value in human_values)
    assert "UNCLASSIFIED_REASON_CODES = " not in source
    assert "input_type_id" not in json.dumps(catalog, ensure_ascii=False)
    assert '"roles"' not in json.dumps(catalog, ensure_ascii=False)
    assert '"provider_metadata"' not in json.dumps(
        catalog,
        ensure_ascii=False,
    )


def test_catalog_factory_fails_closed_on_semantic_and_integrity_drift() -> None:
    module = _load_contract_module()
    factory = _factory(module)
    catalog = _read_json(CATALOG_PATH)
    schema_validator = jsonschema.Draft202012Validator(_read_json(CATALOG_SCHEMA_PATH))
    error = module.Gate2FinancialDecisionReasonCatalogContractError

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0]["code"] = "invented_reason"
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(error, match="decision_reason_catalog_codes_mismatch"):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][1]["code"] = invalid["reasons"][0]["code"]
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(error, match="decision_reason_catalog_codes_mismatch"):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0]["contrast_with_neighbouring_reasons"][0]["reason_code"] = (
        invalid["reasons"][0]["code"]
    )
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(
        error,
        match="decision_reason_catalog_self_contrast_forbidden",
    ):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0]["contrast_with_neighbouring_reasons"].clear()
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(
        error,
        match="decision_reason_catalog_contrasts_invalid",
    ):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0]["selection_boundary"] = {
        "minimum_inclusive": 1,
        "maximum_inclusive": 1,
    }
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(
        error,
        match="decision_reason_catalog_boundaries_invalid",
    ):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0].pop("meaning")
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(
        error,
        match="decision_reason_catalog_reason_projection_invalid",
    ):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["reasons"][0]["unexpected_field"] = "not permitted"
    _refresh_catalog_integrity(invalid)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator.validate(invalid)
    with pytest.raises(
        error,
        match="decision_reason_catalog_reason_projection_invalid",
    ):
        factory.create(catalog=invalid)

    invalid = copy.deepcopy(catalog)
    invalid["integrity_sha256"] = "0" * 64
    with pytest.raises(
        error,
        match="decision_reason_catalog_integrity_invalid",
    ):
        factory.create(catalog=invalid)


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        (
            "human_title",
            "Short",
            "decision_reason_catalog_human_title_invalid",
        ),
        (
            "human_title",
            "A " + ("b" * 119),
            "decision_reason_catalog_human_title_invalid",
        ),
        (
            "display_order",
            True,
            "decision_reason_catalog_display_order_invalid",
        ),
        (
            "display_order",
            1.5,
            "decision_reason_catalog_display_order_invalid",
        ),
    ],
)
def test_catalog_schema_and_factory_reject_same_scalar_contract_violations(
    field: str,
    value: Any,
    error_code: str,
) -> None:
    module = _load_contract_module()
    factory = _factory(module)
    invalid = copy.deepcopy(_read_json(CATALOG_PATH))
    invalid["reasons"][0][field] = value
    _refresh_catalog_integrity(invalid)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_read_json(CATALOG_SCHEMA_PATH)).validate(
            invalid
        )
    with pytest.raises(
        module.Gate2FinancialDecisionReasonCatalogContractError,
        match=error_code,
    ):
        factory.create(catalog=invalid)


def test_catalog_schema_and_factory_accept_integral_json_numbers() -> None:
    module = _load_contract_module()
    factory = _factory(module)
    catalog = copy.deepcopy(_read_json(CATALOG_PATH))
    catalog["reasons"][0]["display_order"] = 1.0
    catalog["reasons"][0]["selection_boundary"] = {
        "minimum_inclusive": 0.0,
        "maximum_inclusive": 0.0,
    }
    _refresh_catalog_integrity(catalog)

    jsonschema.Draft202012Validator(_read_json(CATALOG_SCHEMA_PATH)).validate(catalog)
    snapshot = factory.create(catalog=catalog)
    assert snapshot.reason_codes == UNCLASSIFIED_REASON_CODES


def test_family_v2_is_additive_inactive_and_has_exact_rollback() -> None:
    manifest_v1 = _read_json(MANIFEST_V1_PATH)
    manifest_v2 = _read_json(MANIFEST_V2_PATH)
    schema_v2 = _read_json(MANIFEST_V2_SCHEMA_PATH)
    schema_v1 = _read_json(
        MANIFEST_V1_PATH.with_name(
            "broker_reports_financial_domain_assets.v1.manifest.schema.json"
        )
    )

    jsonschema.Draft202012Validator.check_schema(schema_v2)
    jsonschema.Draft202012Validator(schema_v2).validate(manifest_v2)
    assert (
        schema_v2["properties"]["assets"]["items"]["properties"]["api_identity"]
        == schema_v1["$defs"]["apiIdentity"]
    )
    invalid_manifest = copy.deepcopy(manifest_v2)
    invalid_manifest["assets"][0]["api_identity"] = {
        "x": 1,
        "y": 2,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema_v2).validate(invalid_manifest)
    assert manifest_v2["manifest_sha256"] == _canonical_integrity(
        manifest_v2,
        field="manifest_sha256",
    )
    assert manifest_v2["family_id"] == manifest_v1["family_id"]
    assert manifest_v2["semantic_version"] == "1.1.0"
    assert manifest_v2["runtime_activation"] is False
    assert manifest_v2["lifecycle"] == {
        "status": "draft",
        "previous_family_semantic_version": "1.0.0",
        "draft_rollback": "discard_without_runtime_mutation",
        "active_rollback": ("select_previous_validated_immutable_family_version"),
        "rollback_manifest_schema_version": manifest_v1["schema_version"],
        "rollback_manifest_sha256": manifest_v1["manifest_sha256"],
        "rollback_manifest_git_blob_sha256": (EXPECTED_V1_MANIFEST_GIT_BLOB_SHA256),
        "live_publisher_implemented": False,
    }
    assert manifest_v2["assets"] == manifest_v1["assets"]
    assert manifest_v2["dependencies"][:4] == manifest_v1["dependencies"]
    assert {item["dependency_id"] for item in manifest_v2["dependencies"][4:]} == {
        "broker_reports_gate2_financial_decision_reason_catalog",
        "broker_reports_gate2_financial_decision_reason_catalog_schema",
        "broker_reports_gate2_financial_decision_reason_catalog_contract",
    }
    assert (
        manifest_v2["authority"]["decision_reason_code_authority_dependency_id"]
        == "broker_reports_financial_decision_contract"
    )
    assert (
        manifest_v2["authority"]["decision_reason_meaning_authority_dependency_id"]
        == "broker_reports_gate2_financial_decision_reason_catalog"
    )
    assert (
        manifest_v2["authority"]["decision_reason_schema_authority_dependency_id"]
        == "broker_reports_gate2_financial_decision_reason_catalog_contract"
    )


def test_family_v2_pins_exact_catalog_schema_and_validator_blobs() -> None:
    manifest = _read_json(MANIFEST_V2_PATH)
    dependencies = {item["dependency_id"]: item for item in manifest["dependencies"]}
    paths = {
        "broker_reports_gate2_financial_decision_reason_catalog": (CATALOG_PATH),
        "broker_reports_gate2_financial_decision_reason_catalog_schema": (
            CATALOG_SCHEMA_PATH
        ),
        "broker_reports_gate2_financial_decision_reason_catalog_contract": (
            CATALOG_CONTRACT_PATH
        ),
    }
    for dependency_id, path in paths.items():
        assert dependencies[dependency_id]["git_blob_sha256"] == _sha256(
            _portable_bytes(path)
        )
    catalog = _read_json(CATALOG_PATH)
    catalog_dependency = dependencies[
        "broker_reports_gate2_financial_decision_reason_catalog"
    ]
    assert (
        catalog_dependency["semantic_integrity_sha256"] == (catalog["integrity_sha256"])
    )
    assert catalog_dependency["lifecycle_status"] == "draft"
    assert catalog_dependency["runtime_activation"] is False


def test_family_v3_packages_only_catalog_v2_and_minimal_profile() -> None:
    manifest_v1 = _read_json(MANIFEST_V1_PATH)
    manifest_v2 = _read_json(MANIFEST_V2_PATH)
    manifest_v3 = _read_json(MANIFEST_V3_PATH)
    schema_v3 = _read_json(MANIFEST_V3_SCHEMA_PATH)
    catalog_v2 = _read_json(CATALOG_V2_PATH)

    jsonschema.Draft202012Validator.check_schema(schema_v3)
    jsonschema.Draft202012Validator(schema_v3).validate(manifest_v3)
    assert _sha256(_portable_bytes(MANIFEST_V2_PATH)) == (
        EXPECTED_V2_MANIFEST_GIT_BLOB_SHA256
    )
    assert _sha256(_portable_bytes(CATALOG_V2_PATH)) == (
        EXPECTED_CATALOG_V2_GIT_BLOB_SHA256
    )
    assert _sha256(_portable_bytes(CATALOG_V2_SCHEMA_PATH)) == (
        EXPECTED_CATALOG_V2_SCHEMA_GIT_BLOB_SHA256
    )
    assert _sha256(_portable_bytes(MANIFEST_V3_PATH)) == (
        EXPECTED_V3_MANIFEST_GIT_BLOB_SHA256
    )
    assert _sha256(_portable_bytes(MANIFEST_V3_SCHEMA_PATH)) == (
        EXPECTED_V3_MANIFEST_SCHEMA_GIT_BLOB_SHA256
    )
    assert manifest_v3["manifest_sha256"] == (
        EXPECTED_V3_MANIFEST_SHA256
    )
    assert manifest_v3["manifest_sha256"] == _canonical_integrity(
        manifest_v3,
        field="manifest_sha256",
    )
    assert manifest_v3["family_id"] == manifest_v2["family_id"]
    assert manifest_v3["semantic_version"] == "1.2.0"
    assert manifest_v3["runtime_activation"] is False
    assert manifest_v3["assets"] == manifest_v1["assets"]
    assert manifest_v3["dependencies"][:4] == manifest_v1["dependencies"]
    assert [
        item["dependency_id"] for item in manifest_v3["dependencies"]
    ] == [
        *[
            item["dependency_id"]
            for item in manifest_v1["dependencies"]
        ],
        "broker_reports_gate2_financial_decision_reason_catalog",
        "broker_reports_gate2_financial_decision_reason_catalog_schema",
        "broker_reports_gate2_financial_decision_reason_catalog_contract",
    ]
    catalog_dependency = manifest_v3["dependencies"][4]
    assert catalog_dependency["contract_identity"] == (
        "broker_reports_gate2_financial_decision_reason_catalog@2.0.0"
    )
    assert catalog_dependency["git_blob_sha256"] == (
        EXPECTED_CATALOG_V2_GIT_BLOB_SHA256
    )
    assert catalog_dependency["semantic_integrity_sha256"] == (
        catalog_v2["integrity_sha256"]
    )
    assert catalog_dependency["canonical_semantic_bytes"] == 6393
    assert catalog_dependency["family_packaging_status"] == (
        "packaged_in_inactive_family_v3"
    )
    assert manifest_v3["lifecycle"] == {
        "status": "draft",
        "previous_family_semantic_version": "1.1.0",
        "draft_rollback": "discard_without_runtime_mutation",
        "active_rollback": (
            "select_previous_validated_immutable_family_version"
        ),
        "rollback_manifest_schema_version": manifest_v2[
            "schema_version"
        ],
        "rollback_manifest_sha256": manifest_v2["manifest_sha256"],
        "rollback_manifest_git_blob_sha256": (
            EXPECTED_V2_MANIFEST_GIT_BLOB_SHA256
        ),
        "live_publisher_implemented": False,
    }
    profile = manifest_v3["composition"]["minimal_projection_profile"]
    assert {
        key: value
        for key, value in manifest_v3["composition"].items()
        if key != "minimal_projection_profile"
    } == manifest_v1["composition"]
    assert profile == {
        "profile_id": (
            "broker_reports_gate2_minimal_managed_projection_v1_candidate"
        ),
        "semantic_version": "1.0.0",
        "status": "inactive_candidate",
        "runtime_activation": False,
        "response_profile_status": "not_implemented",
        "transport_eligible": False,
        "semantic_pack_dependency_id": (
            "broker_reports_financial_semantic_pack"
        ),
        "decision_reason_catalog_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog"
        ),
        "decision_reason_catalog_schema_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_schema"
        ),
        "decision_reason_catalog_contract_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_contract"
        ),
        "model_surface_contract_identity": (
            "broker_reports_gate2_minimal_model_surface_v1"
        ),
        "projection_owner_entrypoint": (
            "Gate2FinancialSemanticV5ProjectionFactory."
            "create_minimal_managed_projection"
        ),
    }
    assert manifest_v3["authority"][
        "minimal_pack_projection_owner_entrypoint"
    ] == manifest_v3["authority"][
        "minimal_reason_projection_owner_entrypoint"
    ]
    assert manifest_v3["authority"][
        "active_decision_reason_code_authority_dependency_id"
    ] == "broker_reports_financial_decision_contract"
    assert (
        "minimal_projection_reason_code_authority_dependency_id"
        not in manifest_v3["authority"]
    )


def test_historical_assets_and_active_loader_output_remain_exact() -> None:
    assert _sha256(_portable_bytes(MANIFEST_V1_PATH)) == (
        EXPECTED_V1_MANIFEST_GIT_BLOB_SHA256
    )
    assert _read_json(MANIFEST_V1_PATH)["manifest_sha256"] == (
        EXPECTED_V1_MANIFEST_SHA256
    )
    assert _sha256(_portable_bytes(TOOL_V1_PATH)) == (EXPECTED_V1_TOOL_GIT_BLOB_SHA256)
    assert _sha256(_portable_bytes(PACK_V1_PATH)) == (EXPECTED_PACK_GIT_BLOB_SHA256)
    assert _read_json(PACK_V1_PATH)["integrity_sha256"] == (
        EXPECTED_PACK_INTEGRITY_SHA256
    )
    assert _sha256_json(
        load_gate2_financial_semantic_model_assets()
    ) == (
        EXPECTED_ACTIVE_ASSET_PAYLOAD_SHA256
    )


def test_catalog_contract_is_build_time_closed_world_only() -> None:
    source = CATALOG_CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots == {
        "__future__",
        "ast",
        "copy",
        "dataclasses",
        "hashlib",
        "json",
        "re",
        "typing",
    }
    for forbidden in (
        "Path(",
        "open(",
        "os.environ",
        "requests",
        "urllib",
        "socket",
        "provider_adapter",
    ):
        assert forbidden not in source

    active_sources = [
        SERVICE_ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_packet.py",
        SERVICE_ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_choice.py",
        SERVICE_ROOT / "broker_reports_gate1" / "gate2_model_requests.py",
    ]
    for path in active_sources:
        assert (
            "broker_reports_financial_decision_reason_catalog_contracts"
            not in path.read_text(encoding="utf-8")
        )


def test_existing_builder_checks_v1_and_new_draft_outputs() -> None:
    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["mode"] == "check"
    assert result["manifest_git_blob_sha256"] == (EXPECTED_V1_MANIFEST_GIT_BLOB_SHA256)
    assert result["tool_git_blob_sha256"] == (EXPECTED_V1_TOOL_GIT_BLOB_SHA256)
    assert result["decision_reason_catalog_schema_git_blob_sha256"] == (
        _sha256(_portable_bytes(CATALOG_SCHEMA_PATH))
    )
    assert result["manifest_v2_git_blob_sha256"] == _sha256(
        _portable_bytes(MANIFEST_V2_PATH)
    )
    assert result["manifest_v2_schema_git_blob_sha256"] == _sha256(
        _portable_bytes(MANIFEST_V2_SCHEMA_PATH)
    )
    assert result[
        "decision_reason_catalog_v2_schema_git_blob_sha256"
    ] == EXPECTED_CATALOG_V2_SCHEMA_GIT_BLOB_SHA256
    assert result["manifest_v3_git_blob_sha256"] == (
        EXPECTED_V3_MANIFEST_GIT_BLOB_SHA256
    )
    assert result["manifest_v3_schema_git_blob_sha256"] == (
        EXPECTED_V3_MANIFEST_SCHEMA_GIT_BLOB_SHA256
    )

    runtime = subprocess.run(
        [sys.executable, str(RUNTIME_BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert runtime.returncode == 0, runtime.stderr
    runtime_result = json.loads(runtime.stdout)
    assert runtime_result["context_v2_candidate_payload_sha256"] == (
        EXPECTED_CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256
    )
    assert runtime_result["minimal_managed_candidate_payload_sha256"] == (
        "6211a7668deb14191cb2a215d726d4e7782e43e4834477cb0fe49e86510c62ca"
    )
    assert runtime_result["runtime_projection_git_blob_sha256"] == _sha256(
        _portable_bytes(RUNTIME_MODEL_ASSETS_PATH)
    )
    assert runtime_result["mode"] == "check"
    assert runtime_result["status"] == "passed"
