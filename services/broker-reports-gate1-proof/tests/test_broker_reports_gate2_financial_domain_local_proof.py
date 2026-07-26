from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_domain_contracts import (  # noqa: E402
    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_financial_domain_local_proof import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    LOCAL_DOMAIN_PROOF_POLICY_VERSION,
    LOCAL_DOMAIN_PROOF_RECEIPT_SCHEMA_VERSION,
    Gate2FinancialDomainLocalProofFactory,
)
from broker_reports_gate1.gate2_financial_domain_persistence import (  # noqa: E402,E501
    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402,E501
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402,E501
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4,
    SUCCESSOR_PROMPT_CONTRACT_ID_V4,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402,E501
    MANAGED_ASSET_IDENTITIES_SHA256,
    PACK_INTEGRITY_SHA256,
)
from broker_reports_gate1.gate2_successor_local_proof_v2 import (  # noqa: E402,E501
    Gate2SuccessorLocalProofV2Error,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODULE_PATHS = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_domain_local_proof.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_domain_persistence.py",
)
SAFE_RECEIPT_PATH = (
    ROOT.parents[1]
    / "docs"
    / "reports"
    / "2026-07-26"
    / "BROKER_REPORTS_GATE2_DOMAIN_GOAL9_LOCAL_DOMAIN_PROOF.receipt.safe.json"
)
SNAPSHOT_AUTHORITY_KEY = (
    b"synthetic-local-domain-authority-key-32"
)
CONTINUATION_KEY = b"synthetic-local-domain-continuation-key-32"


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _proof(manifest=None):
    return Gate2FinancialDomainLocalProofFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(manifest=manifest or _manifest())


def test_local_domain_proof_passes_exact_acceptance_contract():
    receipt = _proof()

    assert receipt["schema_version"] == (
        LOCAL_DOMAIN_PROOF_RECEIPT_SCHEMA_VERSION
    )
    assert receipt["policy_version"] == LOCAL_DOMAIN_PROOF_POLICY_VERSION
    assert receipt["status"] == "passed"
    assert receipt["acceptance"] == {
        "local_domain_proof": "PASSED",
        "literal_loss": "ZERO",
        "query_gaps": "ZERO",
        "provider_calls": "ZERO",
    }
    assert all(receipt["checks"].values())
    assert receipt["product_invariants"]["literal_loss_total"] == 0
    assert receipt["domain"]["query_gaps_total"] == 0


def test_local_domain_proof_binds_current_v4_assets_and_domain_contracts():
    receipt = _proof()

    assert receipt["exact_contracts"] == {
        "model_input_schema_version": (
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
        ),
        "prompt_contract_id": SUCCESSOR_PROMPT_CONTRACT_ID_V4,
        "prompt_sha256": (
            "3f169c79a9bf6f0eb1b476853ed1ace50cca9b2f7fd2d2fe3394f2ab3f6d5a2e"
        ),
        "source_context_schema_version": (
            "broker_reports_gate2_financial_evidence_source_context_v2"
        ),
        "domain_snapshot_schema_version": (
            FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
        ),
        "persistence_schema_version": (
            FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
        ),
        "query_schema_version": FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
        "query_policy_version": FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
        "semantic_pack_sha256": PACK_INTEGRITY_SHA256,
        "managed_asset_identities_git_blob_sha256": (
            MANAGED_ASSET_IDENTITIES_SHA256
        ),
        "managed_asset_manifest_sha256": (
            "b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59"
        ),
    }
    assert len(receipt["exact_hashes"]["model_input_sha256"]) == 12
    assert len(receipt["exact_hashes"]["source_context_sha256"]) == 12


def test_local_domain_proof_covers_all_branches_catalog_and_queries():
    receipt = _proof()

    assert receipt["terminal_disposition_counts"] == {
        "typed_input": 4,
        "unclassified_financial_input": 6,
        "no_financial_input": 1,
        "unsupported": 1,
    }
    assert receipt["domain"]["records_total"] == 10
    assert receipt["domain"]["typed_records_total"] == 4
    assert receipt["domain"]["unclassified_records_total"] == 6
    assert receipt["domain"]["coverage_records_total"] == 12
    assert receipt["domain"]["provenance_records_total"] == 12
    assert receipt["domain"]["coverage_gaps_total"] == 0
    assert receipt["domain"]["provenance_gaps_total"] == 0
    assert receipt["domain"]["query_pages_total"] == 36


def test_local_domain_proof_fail_closed_negatives_are_executed():
    receipt = _proof()

    assert receipt["negative_checks"] == {
        "managed_asset_drift_rejected": True,
        "materialized_artifact_tamper_rejected": True,
        "persistence_envelope_tamper_rejected": True,
        "wrong_snapshot_authority_rejected": True,
        "wrong_access_scope_rejected": True,
        "continuation_tamper_rejected": True,
        "query_gap_rejected": True,
    }


def test_local_domain_proof_is_deterministic_and_safe():
    manifest = _manifest()
    first = _proof(manifest)
    second = _proof(copy.deepcopy(manifest))
    rendered = json.dumps(first, ensure_ascii=False, sort_keys=True)
    literals = [
        cell["literal"]
        for case in manifest["cases"]
        for key in ("cells", "neighbour_cells")
        for cell in case.get(key) or []
    ]

    assert first == second
    assert all(literal not in rendered for literal in literals)
    assert '"source_value_ref":' not in rendered
    assert "document:" not in rendered
    assert "user:synthetic" not in rendered
    assert SNAPSHOT_AUTHORITY_KEY.decode("ascii") not in rendered
    assert CONTINUATION_KEY.decode("ascii") not in rendered
    assert first["execution_accounting"] == {
        "provider_calls_total": 0,
        "source_model_calls_total": 0,
        "domain_model_calls_total": 0,
        "financial_model_calls_total": 0,
        "fallback_total": 0,
        "repair_attempts_total": 0,
        "hidden_retry_total": 0,
        "persistence_writes_total": 0,
        "production_route_activations_total": 0,
    }


def test_local_domain_proof_rejects_manifest_drift():
    manifest = _manifest()
    manifest["schema_version"] = "drifted"

    with pytest.raises(
        Gate2SuccessorLocalProofV2Error,
        match="successor_local_proof_v2_manifest_identity_invalid",
    ):
        _proof(manifest)


def test_local_domain_proof_has_closed_world_factory_boundaries():
    assert "frozen synthetic" in FACTORY_REQUIRED
    assert "must not call providers" in FORBIDDEN
    imported_modules = set()
    combined_source = ""
    for path in MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        combined_source += source
        tree = ast.parse(source)
        imported_modules.update(
            str(node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )

    assert "ArtifactStore" not in combined_source
    assert ".write_" not in combined_source
    assert "open(" not in combined_source
    assert not {
        module
        for module in imported_modules
        if "provider_adapters" in module
        or "model_clients" in module
        or "production_runtime" in module
        or "artifact_store" in module
    }


def test_goal9_safe_receipt_hashes_current_git_blobs():
    receipt = json.loads(SAFE_RECEIPT_PATH.read_text(encoding="utf-8"))

    assert receipt["hash_boundary"] == "git_blob_bytes"
    assert receipt["local_proof"]["acceptance"] == {
        "local_domain_proof": "PASSED",
        "literal_loss": "ZERO",
        "query_gaps": "ZERO",
        "provider_calls": "ZERO",
    }
    for deliverable in receipt["deliverables"]:
        blob = subprocess.check_output(
            ["git", "show", f":{deliverable['path']}"],
            cwd=ROOT.parents[1],
        )
        assert hashlib.sha256(blob).hexdigest() == (
            deliverable["git_blob_sha256"]
        )

    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert all(
        cell["literal"] not in rendered
        for case in _manifest()["cases"]
        for key in ("cells", "neighbour_cells")
        for cell in case.get(key) or []
    )
    assert '"source_value_ref":' not in rendered
    assert SNAPSHOT_AUTHORITY_KEY.decode("ascii") not in rendered
    assert CONTINUATION_KEY.decode("ascii") not in rendered
