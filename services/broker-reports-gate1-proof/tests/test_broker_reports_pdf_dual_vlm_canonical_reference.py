from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_canonical_reference as REFERENCE  # noqa: E402


def _sources() -> tuple[dict, str, dict, str]:
    path = (
        ROOT
        / "benchmarks"
        / "pdf_dual_vlm_canonical_table_v1"
        / "controlled_reference.json"
    )
    raw = path.read_bytes()
    controlled = json.loads(raw.decode("utf-8"))
    crops = []
    for index, case in enumerate(controlled["cases"]):
        crops.append(
            {
                "case_id": case["case_id"],
                "crop_path": f"crops/{case['case_id']}.png",
                "crop_sha256": hashlib.sha256(f"crop-{index}".encode()).hexdigest(),
                "crop_width": 1200,
                "crop_height": 900,
            }
        )
    crop_pack = {"crops": crops}
    crop_bytes = json.dumps(crop_pack, sort_keys=True).encode()
    return (
        controlled,
        hashlib.sha256(raw).hexdigest(),
        crop_pack,
        hashlib.sha256(crop_bytes).hexdigest(),
    )


def _template() -> dict:
    controlled, controlled_hash, crop_pack, crop_hash = _sources()
    return REFERENCE.build_review_template(
        controlled_reference=controlled,
        controlled_reference_sha256=controlled_hash,
        crop_pack=crop_pack,
        crop_pack_sha256=crop_hash,
    )


def _decisions(template: dict) -> dict:
    decisions = REFERENCE.build_decisions_template(template)
    decisions["reviewer"] = {
        "kind": "human",
        "identity": "Roman",
        "reviewed_at": "2026-07-21T12:00:00+03:00",
    }
    for entry in decisions["entries"]:
        entry["decision"] = "approve"
        entry["attestations"] = {key: True for key in REFERENCE.REVIEW_ATTESTATIONS}
    return decisions


def test_review_template_is_contract_bound_and_contains_no_provider_output() -> None:
    template = _template()

    assert REFERENCE.validate_review_template(template) == []
    assert template["provider_outputs_included"] is False
    assert template["consensus_included"] is False
    assert len(template["entries"]) == 5
    assert all(
        entry["proposed_table"]["table_id"] == entry["case_id"]
        for entry in template["entries"]
    )


def test_explicit_human_review_can_finalize_compatible_immutable_reference() -> None:
    template = _template()
    reference, seal = REFERENCE.finalize_human_reference(
        review_template=template,
        decisions=_decisions(template),
    )

    assert REFERENCE.validate_human_reference(reference) == []
    assert REFERENCE.validate_reference_seal(reference=reference, seal=seal) == []
    assert reference["human_reviewed"] is True
    assert reference["lineage"]["provider_outputs_used"] is False
    assert reference["lineage"]["provider_consensus_used"] is False
    assert all(
        case["table"]["schema_version"] == "broker_reports_canonical_table_v1"
        for case in reference["cases"]
    )


@pytest.mark.parametrize(
    "identity",
    ["Codex reviewer", "OpenAI", "GPT bot", "Gemini model"],
)
def test_ai_reviewer_identity_is_rejected(identity: str) -> None:
    template = _template()
    decisions = _decisions(template)
    decisions["reviewer"]["identity"] = identity

    with pytest.raises(
        REFERENCE.CanonicalReferenceError,
        match="canonical_reference_decisions_invalid",
    ):
        REFERENCE.finalize_human_reference(
            review_template=template,
            decisions=decisions,
        )


def test_incomplete_review_attestation_cannot_create_reference() -> None:
    template = _template()
    decisions = _decisions(template)
    decisions["entries"][0]["attestations"]["every_visible_cell_checked"] = False

    with pytest.raises(
        REFERENCE.CanonicalReferenceError,
        match="canonical_reference_review_attestation_incomplete",
    ):
        REFERENCE.finalize_human_reference(
            review_template=template,
            decisions=decisions,
        )


def test_reference_or_seal_mutation_is_detected() -> None:
    template = _template()
    reference, seal = REFERENCE.finalize_human_reference(
        review_template=template,
        decisions=_decisions(template),
    )
    tampered_reference = copy.deepcopy(reference)
    tampered_reference["cases"][0]["table"]["cells"][0]["source_text"] = "mutated"
    tampered_seal = copy.deepcopy(seal)
    tampered_seal["reference_sha256"] = "f" * 64

    assert "canonical_human_reference_seal_invalid" in (
        REFERENCE.validate_reference_seal(
            reference=tampered_reference,
            seal=seal,
        )
    )
    errors = REFERENCE.validate_reference_seal(
        reference=reference,
        seal=tampered_seal,
    )
    assert "canonical_human_reference_seal_invalid" in errors
    assert "canonical_human_reference_seal_hash_invalid" in errors
