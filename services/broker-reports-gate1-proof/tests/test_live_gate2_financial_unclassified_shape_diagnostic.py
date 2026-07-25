from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from live_gate2_economy_contract_qualification import (  # noqa: E402
    build_financial_qualification_cases,
)
from live_gate2_financial_unclassified_shape_diagnostic import (  # noqa: E402
    EXPECTED_DECISION_KEYS,
    FACTORY_REQUIRED,
    FORBIDDEN,
    decision_branch_shapes,
    safe_decision_shape,
    schema_projection_summary,
    write_safe_receipt_atomically,
)


MODULE_PATH = SCRIPT_DIR / "live_gate2_financial_unclassified_shape_diagnostic.py"


def test_safe_shape_localizes_extra_branch_key_without_values() -> None:
    payload = {
        "decision": {
            "disposition": "unclassified_financial_input",
            "input_type_id": "printed_financial_metric_v1",
            "reason_code": "no_registry_type",
            "value_bindings": [
                {
                    "role_id": "unknown_value",
                    "source_value_ref": "private-value-ref",
                }
            ],
        }
    }

    shape = safe_decision_shape(json.dumps(payload))

    assert shape["missing_decision_keys"] == []
    assert shape["extra_decision_keys"] == ["input_type_id"]
    assert shape["value_bindings_type"] == "array"
    assert shape["value_binding_item_keys"] == ["role_id", "source_value_ref"]
    assert "private-value-ref" not in json.dumps(shape)
    assert "printed_financial_metric_v1" not in json.dumps(shape)
    assert shape["raw_values_included"] is False


def test_financial_schema_has_exact_conditional_branch_shapes() -> None:
    case = next(
        item
        for item in build_financial_qualification_cases()
        if item.case_id == "unclassified"
    )
    schema = case.contract.openai_response_format()["json_schema"]["schema"]
    branches = decision_branch_shapes(schema)

    assert len(branches) == 3
    assert any(
        set(item["required_keys"]) == EXPECTED_DECISION_KEYS
        and item["disposition_enum_present"] is True
        for item in branches
    )
    assert all("input_type_id" not in item["required_keys"] for item in branches)


def test_gemini_projection_removes_only_the_branch_discriminator_signal() -> None:
    case = next(
        item
        for item in build_financial_qualification_cases()
        if item.case_id == "unclassified"
    )
    projection = schema_projection_summary(case.contract.openai_response_format())

    assert projection["canonical_disposition_enum_present"] is True
    assert projection["adapted_disposition_enum_present"] is False
    assert projection["canonical_schema_hash"] != projection["adapted_schema_hash"]
    assert projection["schema_transform_count"] > 0
    assert [item["required_keys"] for item in projection["canonical_branches"]] == [
        item["required_keys"] for item in projection["adapted_branches"]
    ]


def test_atomic_safe_receipt_has_no_bom_or_temp_residue(tmp_path) -> None:
    path = tmp_path / "diagnostic.safe.json"
    payload = {"status": "passed", "raw_provider_output_included": False}

    write_safe_receipt_atomically(path=path, payload=payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert path.read_bytes()[:3] != b"\xef\xbb\xbf"
    assert not list(tmp_path.glob("*.tmp"))


def test_diagnostic_is_factory_backed_and_has_no_vendor_bypass() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "only provider request" in FACTORY_REQUIRED
    assert "must not retain raw provider output" in FORBIDDEN
    assert "Gate2FinancialEvidenceShadowDecisionRunnerFactory" in source
    assert "_model_client" in source
    assert not any(
        name.startswith(("openai", "anthropic", "google.generativeai"))
        for name in imported
    )
    assert "api.openai.com" not in source
    assert "generativelanguage.googleapis.com" not in source
