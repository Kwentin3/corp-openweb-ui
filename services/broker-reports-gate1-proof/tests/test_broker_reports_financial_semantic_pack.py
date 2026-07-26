from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACK_ROOT = SERVICE_ROOT / "semantic_packs"
PACK_PATH = PACK_ROOT / "broker_reports_financial_semantic_pack.v1.json"
SCHEMA_PATH = PACK_ROOT / "broker_reports_financial_semantic_pack.v1.schema.json"
GOAL2_RECEIPT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-26"
    / "BROKER_REPORTS_GATE2_DOMAIN_GOAL2_FINANCIAL_SEMANTIC_PACK.receipt.safe.json"
)
EXPECTED_TYPES = (
    "cash_balance_snapshot_v1",
    "printed_financial_metric_v1",
)
EXPECTED_DEFERRED_TYPES = (
    "credit_loss_allowance_movement_v1",
    "credit_loss_allowance_snapshot_v1",
    "equity_balance_snapshot_v1",
    "lease_liability_snapshot_v1",
    "lease_payment_schedule_item_v1",
    "lease_right_of_use_asset_snapshot_v1",
    "payable_balance_snapshot_v1",
    "receivable_balance_snapshot_v1",
    "regulated_asset_balance_snapshot_v1",
    "security_inventory_balance_snapshot_v1",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_integrity(payload: dict[str, Any]) -> tuple[str, int]:
    material = copy.deepcopy(payload)
    material.pop("integrity_sha256")
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), len(canonical)


def test_financial_semantic_pack_identity_and_integrity_are_exact() -> None:
    pack = _read(PACK_PATH)
    digest, canonical_bytes = _canonical_integrity(pack)

    assert pack["schema_version"] == "broker_reports_financial_semantic_pack_v1"
    assert pack["pack_id"] == "broker_reports_managed_financial_semantic_pack"
    assert pack["semantic_version"] == "1.0.0"
    assert pack["consumer_contract_version"] == (
        "broker_reports_managed_financial_domain_contract_v1"
    )
    assert pack["authority_status"] == "target_normative_not_live"
    assert pack["runtime_activation"] is False
    assert digest == pack["integrity_sha256"] == (
        "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
    )
    assert canonical_bytes == 9404


def test_full_compact_snapshot_contains_only_accepted_sorted_types() -> None:
    pack = _read(PACK_PATH)
    types = pack["full_compact_snapshot"]
    type_ids = tuple(item["input_type_id"] for item in types)
    baseline = pack["source_baseline"]

    assert type_ids == EXPECTED_TYPES
    assert tuple(baseline["accepted_type_ids"]) == EXPECTED_TYPES
    assert tuple(baseline["deferred_candidate_ids"]) == EXPECTED_DEFERRED_TYPES
    assert set(type_ids).isdisjoint(baseline["deferred_candidate_ids"])
    assert baseline["registry_sha256"] == (
        "0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8"
    )
    assert baseline["legacy_python_status"] == (
        "current_runtime_migration_source_not_target_authority"
    )


def test_base_definitions_are_exact_accepted_registry_migration_text() -> None:
    definitions = {
        item["input_type_id"]: item["definition"]
        for item in _read(PACK_PATH)["full_compact_snapshot"]
    }

    assert definitions == {
        "cash_balance_snapshot_v1": (
            "A source-stated cash-class balance for an explicit statement scope "
            "and reporting date. Restricted or segregated balances are excluded "
            "unless the source explicitly classifies them as ordinary cash."
        ),
        "printed_financial_metric_v1": (
            "A financial total or metric printed by the source for an explicit "
            "reporting scope and date or period. It remains distinct from every "
            "aggregate calculated by Gate 2."
        ),
    }


def test_every_type_has_closed_roles_and_complete_semantic_guidance() -> None:
    for definition in _read(PACK_PATH)["full_compact_snapshot"]:
        roles = definition["roles"]
        required = {item["role_id"] for item in roles["required"]}
        optional = {item["role_id"] for item in roles["optional"]}
        forbidden = set(roles["forbidden"])
        available = required | optional

        assert required
        assert not required & optional
        assert not required & forbidden
        assert not optional & forbidden
        assert set(definition["identity_roles"]) <= available
        assert all(
            item["source_ref_required"] is True
            for item in roles["required"] + roles["optional"]
        )
        assert definition["synonyms"]
        assert definition["examples"]
        assert definition["counterexamples"]
        assert definition["semantic_distinctions"]
        assert definition["ambiguity_guidance"]
        assert definition["model_guidance"]
        assert definition["lifecycle"] == {
            "status": "active",
            "introduced_in": "1.0.0",
            "deprecated_in": None,
            "retired_in": None,
            "replacement_input_type_id": None,
        }


def test_pack_keeps_type_meanings_out_of_target_python() -> None:
    assert sorted(PACK_ROOT.rglob("*.py")) == []
    assert sorted(path.suffix for path in PACK_ROOT.iterdir()) == [".json", ".json"]


def test_tenant_overlay_is_explicit_versioned_and_fail_closed() -> None:
    pack = _read(PACK_PATH)
    schema = _read(SCHEMA_PATH)
    policy = pack["tenant_overlay_policy"]
    overlay = schema["$defs"]["tenantOverlay"]

    assert policy["schema_version"] == (
        "broker_reports_financial_semantic_pack_tenant_overlay_v1"
    )
    assert policy["status"] == "explicit_versioned_optional"
    assert policy["default_enabled"] is False
    assert policy["base_pack_hash_required"] is True
    assert policy["overlay_semantic_version_required"] is True
    assert set(policy["allowed_changes"]) == {
        "augment_guidance",
        "add_experimental_type",
    }
    assert {
        "modify_base_definition",
        "modify_base_roles",
        "modify_base_identity",
        "remove_base_type",
        "activate_unqualified_type",
        "add_tax_methodology",
    } == set(policy["forbidden_changes"])
    assert overlay["additionalProperties"] is False
    assert {
        "semantic_version",
        "tenant_scope_ref",
        "base_pack_identity",
        "guidance_additions",
        "experimental_type_additions",
        "integrity_sha256",
    } <= set(overlay["required"])
    assert overlay["properties"]["experimental_type_additions"]["items"] == {
        "$ref": "#/$defs/tenantExperimentalTypeDefinition"
    }
    assert len(overlay["anyOf"]) == 2


def test_pack_schema_is_strict_and_exposes_full_type_contract() -> None:
    schema = _read(SCHEMA_PATH)
    pack_schema = schema["$defs"]["semanticPack"]
    type_schema = schema["$defs"]["typeDefinition"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:broker-reports:semantic-packs:financial:v1"
    assert pack_schema["additionalProperties"] is False
    assert type_schema["additionalProperties"] is False
    assert {
        "input_type_id",
        "definition",
        "roles",
        "examples",
        "counterexamples",
        "synonyms",
        "semantic_distinctions",
        "ambiguity_guidance",
        "lifecycle",
    } <= set(type_schema["required"])


def test_pack_contains_no_gate3_methodology_fields() -> None:
    pack = _read(PACK_PATH)
    forbidden_fields = {
        "tax_methodology",
        "declaration_methodology",
        "ledger_mapping",
        "cost_basis_formula",
        "profit_loss_formula",
        "currency_conversion_formula",
    }

    for definition in pack["full_compact_snapshot"]:
        assert forbidden_fields.isdisjoint(definition)
        assert forbidden_fields.isdisjoint(definition["operational_contracts"])


def _git_index_blob(path: Path) -> bytes:
    relative = path.relative_to(REPO_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f":{relative}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode(
        "utf-8",
        errors="replace",
    )
    return completed.stdout


def test_goal2_safe_receipt_hashes_current_git_blobs() -> None:
    receipt = _read(GOAL2_RECEIPT_PATH)
    mismatches = {}

    assert receipt["evidence_reconciliation"]["hash_boundary"] == (
        "git_blob_bytes"
    )
    for item in receipt["deliverables"]:
        path = REPO_ROOT / item["path"]
        actual = hashlib.sha256(_git_index_blob(path)).hexdigest()
        if actual != item["sha256"]:
            mismatches[item["path"]] = {
                "claimed": item["sha256"],
                "actual": actual,
            }

    assert mismatches == {}
