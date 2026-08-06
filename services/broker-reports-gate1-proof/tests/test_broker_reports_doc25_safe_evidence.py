from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE2 = REPO_ROOT / "docs" / "stage2"
REPORTS = REPO_ROOT / "docs" / "reports" / "2026-08-05"
SAFE_FILES = [
    STAGE2 / "BROKER_REPORTS_DOC25_REPOSITORY_AUDIT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_LEGACY_MIGRATION_MAP.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_FORMAT_ADAPTER_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_STORAGE_RETENTION_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_SHADOW_COMPARISON.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_CONSUMER_MIGRATION.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_REPOSITORY_HYGIENE.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_TEST_RESULTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC25_DECISION.safe.json",
    REPORTS / "BROKER_REPORTS_DOC25_GATE2_PRODUCTIZATION.receipt.safe.json",
]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_doc25_safe_json_is_parseable_and_privacy_scanned():
    forbidden = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/|private_media_base64)")
    for path in SAFE_FILES:
        payload = _read_json(path)
        assert payload["schema_version"]
        assert forbidden.search(json.dumps(payload, ensure_ascii=False)) is None


def test_doc25_schema_is_valid_and_non_financial():
    schema = _read_json(
        STAGE2
        / "contracts"
        / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    serialized = json.dumps(schema, ensure_ascii=False).lower()
    for field in (
        "financial_fact",
        "financial_role",
        "tax_treatment",
        "declaration_field",
        "ontology",
    ):
        assert f'"{field}"' not in serialized


def test_doc25_decision_and_closure_receipt_are_consistent():
    decision = _read_json(STAGE2 / "BROKER_REPORTS_DOC25_DECISION.safe.json")
    receipt = _read_json(
        REPORTS / "BROKER_REPORTS_DOC25_GATE2_PRODUCTIZATION.receipt.safe.json"
    )
    assert decision["doc25_program"] == receipt["doc25_program"]
    assert decision["product_cutover"] == receipt["product_cutover"]
    assert decision["legacy_cleanup"] == receipt["legacy_cleanup"]
    assert decision["gate3"] == receipt["gate3"] == "not_started"
    assert receipt["cutover_authorized"] is False


def test_doc25_repository_audit_accounts_for_every_initial_dirty_path():
    audit = _read_json(STAGE2 / "BROKER_REPORTS_DOC25_REPOSITORY_AUDIT.safe.json")
    inventory = audit["dirty_inventory_baseline"]
    assert inventory["files_total"] == len(inventory["files"]) == 183
    assert inventory["unclassified_dirty_files"] == 0
    assert audit["delete_candidates"] == []
