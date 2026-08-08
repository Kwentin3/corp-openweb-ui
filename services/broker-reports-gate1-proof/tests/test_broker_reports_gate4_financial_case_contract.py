from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
import pytest
from referencing import Registry, Resource

from broker_reports_gate1.artifact_models import ARTIFACT_TYPES


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CONTRACTS = REPO_ROOT / "docs" / "stage2" / "contracts"
FACT_SCHEMA_PATH = (
    CONTRACTS / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.schema.json"
)
TARGET_SCHEMA_PATH = CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json"
CONTRACT_PATH = CONTRACTS / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md"
PIPELINE_PATH = CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
HANDOFF_PATH = CONTRACTS / "BROKER_REPORTS_GATE3_HANDOFF.v1.md"
AUTHORITY_PATH = CONTRACTS / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
ROLE_PACK_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate3_financial_role_pack.v1.json"
)
GIT_ATTRIBUTES_PATH = REPO_ROOT / ".gitattributes"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


FACT_SCHEMA = _read_json(FACT_SCHEMA_PATH)
TARGET_SCHEMA = _read_json(TARGET_SCHEMA_PATH)
ROLE_PACK = _read_json(ROLE_PACK_PATH)
REGISTRY = Registry().with_resource(
    TARGET_SCHEMA["$id"],
    Resource.from_contents(TARGET_SCHEMA),
)
VALIDATOR = Draft202012Validator(
    FACT_SCHEMA,
    registry=REGISTRY,
    format_checker=FormatChecker(),
)
PROFILES = {
    item["financial_label"]: item for item in ROLE_PACK["profiles"]
}


REPRESENTATIVE_VALUES = {
    "SECURITY_PURCHASE": {
        "date": ("10.01.2026", "2026-01-10"),
        "asset": ("ACME", "ACME"),
        "quantity": ("10", "10"),
        "amount": ("125,00", "125.00"),
        "currency": ("USD", "USD"),
        "unit_price": ("12,50", "12.50"),
    },
    "SECURITY_DISPOSAL": {
        "date": ("11.02.2026", "2026-02-11"),
        "asset": ("ACME", "ACME"),
        "quantity": ("4", "4"),
        "amount": ("60,00", "60.00"),
        "currency": ("USD", "USD"),
        "unit_price": ("15,00", "15.00"),
    },
    "DIVIDEND_INCOME": {
        "date": ("12.03.2026", "2026-03-12"),
        "amount": ("8,00", "8.00"),
        "currency": ("USD", "USD"),
        "asset": ("ACME", "ACME"),
    },
    "TRANSACTION_CHARGE": {
        "date": ("11.02.2026", "2026-02-11"),
        "amount": ("1,25", "1.25"),
        "currency": ("USD", "USD"),
        "asset": None,
    },
    "TAX_WITHHELD": {
        "date": ("12.03.2026", "2026-03-12"),
        "amount": ("1,20", "1.20"),
        "currency": ("USD", "USD"),
        "asset": None,
    },
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fact_id(fact: dict) -> str:
    material = {
        "schema_version": fact["schema_version"],
        "case_binding": fact["case_binding"],
        "financial_annotations_artifact_id": fact["gate3_binding"][
            "financial_annotations_artifact_id"
        ],
        "annotation_index": fact["gate3_binding"]["annotation_index"],
        "canonical_binding": fact["gate3_binding"]["canonical_binding"],
        "financial_type": fact["financial_type"],
    }
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return "g4fact_" + digest[:32]


def _target(label: str, role: str = "fact") -> dict:
    return {
        "kind": "node",
        "node_id": f"node-{label.lower()}-{role}",
    }


def _fact(label: str, annotation_index: int) -> dict:
    profile = PROFILES[label]
    requirements = {
        **{role: "required" for role in profile["required_roles"]},
        **{role: "optional" for role in profile["optional_roles"]},
    }
    roles = []
    for role in [*profile["required_roles"], *profile["optional_roles"]]:
        source_and_value = REPRESENTATIVE_VALUES[label][role]
        if source_and_value is None:
            roles.append(
                {
                    "role": role,
                    "requirement": requirements[role],
                    "status": "missing",
                }
            )
            continue
        source_literal, value = source_and_value
        source_binding = {
            "target": _target(label, role),
            "source_literal": source_literal,
        }
        if label == "DIVIDEND_INCOME" and role == "asset":
            source_binding["target"] = _target(label, "description")
            source_binding["exact_text"] = source_literal
        roles.append(
            {
                "role": role,
                "requirement": requirements[role],
                "status": "value",
                "value": value,
                "source_binding": source_binding,
            }
        )
    fact = {
        "schema_version": "broker_reports_gate4_financial_case_fact_v1",
        "fact_id": "g4fact_" + "0" * 32,
        "case_binding": {"scope_kind": "case", "scope_id": "case-g4-proof"},
        "gate3_binding": {
            "financial_annotations_artifact_id": "art-gate3-v2-proof",
            "financial_annotations_schema_version": (
                "broker_reports_financial_annotations_v2"
            ),
            "annotation_index": annotation_index,
            "canonical_binding": {
                "document_id": "document-g4-proof",
                "canonical_version_id": "canonical-g4-proof-v1",
            },
        },
        "financial_type": label,
        "annotation_target": _target(label),
        "roles": roles,
        "status": "role_complete",
    }
    fact["fact_id"] = _fact_id(fact)
    return fact


def _representative_facts() -> list[dict]:
    return [
        _fact(label, index)
        for index, label in enumerate(REPRESENTATIVE_VALUES)
    ]


def test_gate4_fact_schema_is_closed_and_reuses_gate3_target_grammar() -> None:
    Draft202012Validator.check_schema(TARGET_SCHEMA)
    Draft202012Validator.check_schema(FACT_SCHEMA)

    target_id = TARGET_SCHEMA["$id"]
    assert FACT_SCHEMA["properties"]["annotation_target"]["$ref"] == target_id
    assert FACT_SCHEMA["$defs"]["sourceBinding"]["properties"]["target"][
        "$ref"
    ] == target_id
    assert FACT_SCHEMA["additionalProperties"] is False


def test_hash_pinned_role_pack_has_cross_platform_lf_checkout_policy() -> None:
    attributes = GIT_ATTRIBUTES_PATH.read_text(encoding="utf-8")
    for path in (
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_financial_role_pack.v1.json",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate3_role_labeling_response.v1.schema.json",
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE3_ROLE_LABELING_RESPONSE.v1.schema.json",
    ):
        assert f"{path} text eol=lf" in attributes


def test_five_current_gate3_fact_profiles_fit_one_minimal_gate4_contract() -> None:
    facts = _representative_facts()
    for fact in facts:
        VALIDATOR.validate(fact)
        profile = PROFILES[fact["financial_type"]]
        expected_order = [
            *profile["required_roles"],
            *profile["optional_roles"],
        ]
        assert [item["role"] for item in fact["roles"]] == expected_order
        assert [item["requirement"] for item in fact["roles"]] == [
            "required" if role in profile["required_roles"] else "optional"
            for role in expected_order
        ]
        assert fact["fact_id"] == _fact_id(fact)
        assert fact["status"] == "role_complete"

    by_type = {fact["financial_type"]: fact for fact in facts}
    purchase = by_type["SECURITY_PURCHASE"]
    assert {item["role"]: item.get("value") for item in purchase["roles"]} == {
        "date": "2026-01-10",
        "asset": "ACME",
        "quantity": "10",
        "amount": "125.00",
        "currency": "USD",
        "unit_price": "12.50",
    }
    dividend_asset = next(
        item
        for item in by_type["DIVIDEND_INCOME"]["roles"]
        if item["role"] == "asset"
    )
    assert dividend_asset["source_binding"]["exact_text"] == "ACME"
    for label in ("TRANSACTION_CHARGE", "TAX_WITHHELD"):
        asset = next(
            item for item in by_type[label]["roles"] if item["role"] == "asset"
        )
        assert asset == {
            "role": "asset",
            "requirement": "optional",
            "status": "missing",
        }


def test_required_missing_role_is_explicit_and_controls_fact_status() -> None:
    incomplete = _fact("SECURITY_PURCHASE", 0)
    date_role = next(item for item in incomplete["roles"] if item["role"] == "date")
    date_role.clear()
    date_role.update(
        {"role": "date", "requirement": "required", "status": "missing"}
    )
    incomplete["status"] = "role_incomplete"
    incomplete["fact_id"] = _fact_id(incomplete)
    VALIDATOR.validate(incomplete)

    falsely_complete = copy.deepcopy(incomplete)
    falsely_complete["status"] = "role_complete"
    with pytest.raises(ValidationError):
        VALIDATOR.validate(falsely_complete)

    optional_missing_only = _fact("TRANSACTION_CHARGE", 3)
    optional_missing_only["status"] = "role_incomplete"
    with pytest.raises(ValidationError):
        VALIDATOR.validate(optional_missing_only)


def test_fact_identity_is_rebuild_stable_and_upstream_sensitive() -> None:
    fact = _fact("SECURITY_DISPOSAL", 1)
    assert _fact_id(copy.deepcopy(fact)) == fact["fact_id"]

    changed_sidecar = copy.deepcopy(fact)
    changed_sidecar["gate3_binding"][
        "financial_annotations_artifact_id"
    ] = "art-gate3-v2-successor"
    assert _fact_id(changed_sidecar) != fact["fact_id"]

    changed_version = copy.deepcopy(fact)
    changed_version["gate3_binding"]["canonical_binding"][
        "canonical_version_id"
    ] = "canonical-g4-proof-v2"
    assert _fact_id(changed_version) != fact["fact_id"]


@pytest.mark.parametrize(
    "mutation",
    (
        lambda fact: fact.update({"tax_base": "100.00"}),
        lambda fact: fact["roles"][0].update({"confidence": 0.9}),
        lambda fact: fact["roles"][3].update({"value": 125.0}),
        lambda fact: fact["roles"][3].update({"value": "125,00"}),
        lambda fact: fact["roles"].append(copy.deepcopy(fact["roles"][0])),
    ),
)
def test_contract_rejects_enrichment_untyped_values_and_duplicate_roles(
    mutation,
) -> None:
    fact = _fact("SECURITY_PURCHASE", 0)
    mutation(fact)
    with pytest.raises(ValidationError):
        VALIDATOR.validate(fact)


def test_missing_role_cannot_carry_invented_value_or_source() -> None:
    fact = _fact("TRANSACTION_CHARGE", 3)
    missing = next(item for item in fact["roles"] if item["status"] == "missing")
    missing["value"] = "ACME"
    missing["source_binding"] = {
        "target": _target("TRANSACTION_CHARGE", "asset"),
        "source_literal": "ACME",
    }
    with pytest.raises(ValidationError):
        VALIDATOR.validate(fact)

    blank_asset = _fact("DIVIDEND_INCOME", 2)
    asset = next(item for item in blank_asset["roles"] if item["role"] == "asset")
    asset["value"] = "   "
    with pytest.raises(ValidationError):
        VALIDATOR.validate(blank_asset)


def test_g41_is_contract_only_and_reuses_existing_openwebui_scope_lifecycle() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    pipeline = PIPELINE_PATH.read_text(encoding="utf-8")
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")
    authority = AUTHORITY_PATH.read_text(encoding="utf-8")

    for marker in (
        "Goal status: `G4.1_CLOSED`",
        "Runtime status: `IMPLEMENTED_BY_G4.2`",
        "Gate 4 status: `CLOSED_BY_G4.7`",
        "ArtifactAccessContext",
        "ArtifactStore/ArtifactResolver",
        "OpenWebUI-injected context",
        "Next allowed boundary: `GATE5_DESIGN`",
    ):
        assert marker in contract
    assert "G4.1_CLOSED" in pipeline
    assert "Gate 4 Financial Case Fact Contract" in authority
    assert "Gate 4 Multi-Document Case Assembly" in authority
    assert "Historical Financial Domain Consumer" in authority
    assert "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md" in handoff
    assert "broker_reports_gate4_financial_case_fact_v1" not in ARTIFACT_TYPES
