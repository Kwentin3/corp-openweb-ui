from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import local_pdf_dual_vlm_fact_locator_delta as DELTA  # noqa: E402
import pdf_dual_vlm_fact_review as REVIEW  # noqa: E402


def test_locator_delta_builds_hash_bound_russian_review_pack(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)

    result = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )

    attestation = _read(Path(result["attestation"]))
    delta = _read(Path(result["delta"]))
    rendered = Path(result["html"]).read_text(encoding="utf-8")
    unsigned_attestation = copy.deepcopy(attestation)
    checksum = unsigned_attestation.pop("attestation_checksum")
    assert checksum == REVIEW.sha256_json(unsigned_attestation)
    unsigned_delta = copy.deepcopy(delta)
    delta_checksum = unsigned_delta.pop("delta_checksum")
    assert delta_checksum == REVIEW.sha256_json(unsigned_delta)
    payload = copy.deepcopy(delta)
    payload.pop("delta_checksum")
    payload.pop("confirmation_text")
    payload_sha = payload.pop("payload_sha256")
    assert payload_sha == REVIEW.sha256_json(payload)
    assert result["status"] == "locator_delta_human_confirmation_required"
    assert result["changed_facts"] == 1
    assert result["groups"] == 1
    assert delta["summary"] == {
        "changed_facts": 1,
        "headerless_classifications": 1,
        "locator_updates": 1,
        "region_groups": 1,
        "text_mismatch_confirmations": 1,
    }
    assert delta["groups"][0]["fact_changes"][0]["revised_fact"]["uncertainty"] == [
        "proposed_from_unreviewed_legacy_grid",
        "header_not_present_in_source",
        "source_locator_text_mismatch_requires_human_confirmation",
    ]
    assert delta["source_policy"]["revised_preparation_binding_valid"] is True
    assert delta["source_policy"]["locator_geometry_lineage"] == {
        "declared_origin": "legacy_pdf_table_strategy_terminal",
        "legacy_provider_vlm_involvement_disclosed": True,
        "legacy_terminal_file_reverified_by_delta_builder": False,
    }
    assert delta["source_policy"]["current_dual_vlm_run1_lineage"] == {
        "absence_from_upstream_preparation_proven_here": False,
        "direct_run1_artifacts_are_builder_inputs": False,
    }
    assert attestation["reviewer"]["identity"] == "Роман"
    assert (
        attestation["reported_scope"][
            "human_reported_visible_values_and_interpretations"
        ]
        is True
    )
    assert attestation["authority"] == {
        "authoritative_for_final_reference": False,
        "final_decisions_must_use_review_decision_factory": True,
        "may_be_used_as_review_intent": False,
    }
    assert result["payload_sha256"] in result["confirmation_text"]
    assert "все 1 изменений источника верны" in result["confirmation_text"]
    assert '<html lang="ru">' in rendered
    assert "Короткая проверка привязок к PDF" in rendered
    assert "Особо проверить расхождение старого чтения и изображения" in rendered
    assert "Загружаем материалы" in rendered
    assert "Не удалось открыть материалы проверки" in rendered
    assert "Изменений для проверки нет" in rendered
    assert "Материалы готовы" in rendered
    assert "Скопировать строку подтверждения" in rendered
    assert 'label for="confirmation"' in rendered
    assert 'id="loading" class="state" role="status"' in rendered
    assert "loading.hidden=true" in rendered
    assert "empty.hidden=false" in rendered
    assert "success.hidden=false" in rendered
    assert "error.hidden=false" in rendered
    assert "content.hidden=false" in rendered
    assert "button.disabled=false" in rendered
    assert "Особая проверка" in rendered
    assert "проверьте особенно внимательно" in rendered
    assert "Копируем строку" in rendered
    assert "Строка скопирована" in rendered
    assert "button:disabled" in rendered and ":focus-visible" in rendered
    assert "data:image/png;base64," in rendered


def test_exact_confirmation_creates_factory_validated_review_intent(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )

    confirmed = DELTA.confirm_locator_delta(
        **inputs,
        attestation_path=Path(built["attestation"]),
        delta_path=Path(built["delta"]),
        confirmation=built["confirmation_text"],
        confirmed_at="2026-07-16T21:30:00+03:00",
        output_dir=tmp_path / "confirmed",
    )

    intent = _read(Path(confirmed["review_intent"]))
    record = _read(Path(confirmed["confirmation_record"]))
    revised = _read(inputs["revised_proposed_path"])
    revised_index = _read(inputs["revised_review_index_path"])
    decisions = REVIEW.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
        review_index=revised_index,
        intent=intent,
    )
    table_entry = next(
        item for item in intent["entries"] if item["card_id"] == "region:example_p01:r1"
    )
    negative_entry = next(
        item
        for item in intent["entries"]
        if item["card_id"] == "negative:betterment_p02"
    )
    assert confirmed["status"] == "locator_confirmation_review_intent_ready"
    assert intent["reviewer"] == {
        "identity": "Роман",
        "kind": "human",
        "reviewed_at": "2026-07-16T21:30:00+03:00",
    }
    assert table_entry["region_decision"] == "approve"
    assert set(table_entry["checklist"].values()) == {"pass"}
    assert table_entry["fact_decisions"][0]["decision"] == "confirm"
    assert built["payload_sha256"] in table_entry["region_note"]
    assert negative_entry["region_decision"] == "approve"
    assert negative_entry["fact_decisions"] == []
    assert "оглавлением, а не таблицей" in negative_entry["region_note"]
    assert record["review_intent_sha256"] == REVIEW.sha256_json(intent)
    assert record["expected_review_decisions_sha256"] == REVIEW.sha256_json(decisions)
    unsigned_record = copy.deepcopy(record)
    checksum = unsigned_record.pop("confirmation_checksum")
    assert checksum == REVIEW.sha256_json(unsigned_record)
    assert record["authority"] == {
        "final_decisions_must_use_review_decision_factory": True,
        "final_reference_created_here": False,
    }
    assert not (
        tmp_path / "confirmed" / "reference.human-reviewed.private.json"
    ).exists()

    rejected_output = tmp_path / "missing-confirmation-record"
    with pytest.raises(
        REVIEW.ReviewContractError,
        match="review_locator_confirmation_required",
    ):
        REVIEW.finalize_human_reference(
            proposed_reference=revised,
            review_index=revised_index,
            review_decisions=decisions,
            output_dir=rejected_output,
        )
    assert not (rejected_output / "reference.human-reviewed.private.json").exists()

    finalized = REVIEW.finalize_human_reference(
        proposed_reference=revised,
        review_index=revised_index,
        review_decisions=decisions,
        output_dir=tmp_path / "finalized",
        confirmation_record=record,
    )
    reference = finalized["reference"]
    table_case = next(
        item for item in reference["cases"] if item["case_id"] == "example_p01"
    )
    negative_case = next(
        item for item in reference["cases"] if item["case_id"] == "betterment_p02"
    )
    assert reference["human_reviewed"] is True
    assert table_case["regions"][0]["facts"][0]["accepted_for_scoring"] is True
    assert negative_case["expected_kind"] == "negative"
    assert negative_case["negative_review"]["decision"] == "approve"


def test_locator_confirmation_rejects_nonmatching_text_before_writes(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )
    output = tmp_path / "rejected-confirmation"

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_confirmation_text_mismatch",
    ):
        DELTA.confirm_locator_delta(
            **inputs,
            attestation_path=Path(built["attestation"]),
            delta_path=Path(built["delta"]),
            confirmation=built["confirmation_text"] + " altered",
            confirmed_at="2026-07-16T21:30:00+03:00",
            output_dir=output,
        )
    assert not output.exists()


def test_locator_confirmation_rejects_delta_tamper_before_writes(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )
    delta = _read(Path(built["delta"]))
    delta["summary"]["changed_facts"] = 999
    tampered_path = tmp_path / "tampered-delta.json"
    tampered_path.write_bytes(REVIEW.canonical_json_bytes(delta))
    output = tmp_path / "rejected-tamper"

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_confirmation_delta_lineage_mismatch",
    ):
        DELTA.confirm_locator_delta(
            **inputs,
            attestation_path=Path(built["attestation"]),
            delta_path=tampered_path,
            confirmation=built["confirmation_text"],
            confirmed_at="2026-07-16T21:30:00+03:00",
            output_dir=output,
        )
    assert not output.exists()


def test_locator_confirmation_rejects_weak_bulk_statement_before_writes(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=["Всё верно."],
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )
    output = tmp_path / "rejected-weak-attestation"

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_confirmation_attestation_scope_unproven",
    ):
        DELTA.confirm_locator_delta(
            **inputs,
            attestation_path=Path(built["attestation"]),
            delta_path=Path(built["delta"]),
            confirmation=built["confirmation_text"],
            confirmed_at="2026-07-16T21:30:00+03:00",
            output_dir=output,
        )
    assert not output.exists()


def test_locator_confirmation_rejects_timestamp_before_attestation(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )
    output = tmp_path / "rejected-early-time"

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_confirmation_timestamp_precedes_review",
    ):
        DELTA.confirm_locator_delta(
            **inputs,
            attestation_path=Path(built["attestation"]),
            delta_path=Path(built["delta"]),
            confirmation=built["confirmation_text"],
            confirmed_at="2026-07-16T20:00:00+03:00",
            output_dir=output,
        )
    assert not output.exists()


def test_locator_confirmation_record_blocks_intent_and_note_bypasses(
    tmp_path: Path,
) -> None:
    inputs = _review_inputs(tmp_path)
    built = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=list(DELTA.FROZEN_ROMAN_ATTESTATION_STATEMENTS),
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )
    confirmed = DELTA.confirm_locator_delta(
        **inputs,
        attestation_path=Path(built["attestation"]),
        delta_path=Path(built["delta"]),
        confirmation=built["confirmation_text"],
        confirmed_at="2026-07-16T21:30:00+03:00",
        output_dir=tmp_path / "confirmed",
    )
    intent = _read(Path(confirmed["review_intent"]))
    record = _read(Path(confirmed["confirmation_record"]))
    revised = _read(inputs["revised_proposed_path"])
    revised_index = _read(inputs["revised_review_index_path"])

    tampered_intent = copy.deepcopy(intent)
    tampered_intent["entries"][0]["region_note"] += " altered"
    tampered_decisions = (
        REVIEW.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
            review_index=revised_index,
            intent=tampered_intent,
        )
    )
    with pytest.raises(
        REVIEW.ReviewContractError,
        match="review_locator_confirmation_invalid",
    ):
        REVIEW._require_locator_confirmation_record(
            record,
            review_decisions=tampered_decisions,
            review_intent=tampered_intent,
            required=True,
        )

    marker_removed_intent = copy.deepcopy(intent)
    for entry in marker_removed_intent["entries"]:
        entry["region_note"] = "Human confirmation marker removed."
        for fact in entry["fact_decisions"]:
            fact["note"] = "Human confirmation marker removed."
    marker_removed_decisions = (
        REVIEW.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
            review_index=revised_index,
            intent=marker_removed_intent,
        )
    )
    with pytest.raises(
        REVIEW.ReviewContractError,
        match="review_locator_confirmation_required",
    ):
        REVIEW._require_locator_confirmation_record(
            None,
            review_decisions=marker_removed_decisions,
            review_intent=marker_removed_intent,
            required=True,
        )

    malformed_intent = copy.deepcopy(intent)
    malformed_intent["entries"][0]["region_note"] = (
        "Роман подтвердил; locator-delta SHA-256: malformed."
    )
    malformed_decisions = (
        REVIEW.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
            review_index=revised_index,
            intent=malformed_intent,
        )
    )
    with pytest.raises(
        REVIEW.ReviewContractError,
        match="review_locator_confirmation_notes_invalid",
    ):
        REVIEW._require_locator_confirmation_record(
            record,
            review_decisions=malformed_decisions,
            review_intent=malformed_intent,
            required=True,
        )

    forged_record = copy.deepcopy(record)
    forged_record["expected_review_decisions_sha256"] = "f" * 64
    forged_record.pop("confirmation_checksum")
    forged_record["confirmation_checksum"] = REVIEW.sha256_json(forged_record)
    decisions = REVIEW.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
        review_index=revised_index,
        intent=intent,
    )
    output = tmp_path / "forged-record-final"
    with pytest.raises(
        REVIEW.ReviewContractError,
        match="review_locator_confirmation_invalid",
    ):
        REVIEW.finalize_human_reference(
            proposed_reference=revised,
            review_index=revised_index,
            review_decisions=decisions,
            output_dir=output,
            confirmation_record=forged_record,
        )
    assert not (output / "reference.human-reviewed.private.json").exists()


def test_locator_delta_rejects_semantic_fact_change(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path, semantic_change=True)

    with pytest.raises(
        DELTA.LocatorDeltaError, match="locator_delta_semantic_change_forbidden"
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "semantic-rejected",
            reviewer_identity="Роман",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["Всё верно."],
            attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
        )


def test_locator_delta_renders_reachable_empty_state(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)
    inputs["baseline_proposed_path"] = inputs["revised_proposed_path"]
    inputs["baseline_review_index_path"] = inputs["revised_review_index_path"]

    result = DELTA.build_locator_delta(
        **inputs,
        output_dir=tmp_path / "empty-delta",
        reviewer_identity="Роман",
        reviewed_at="2026-07-16T20:50:10+03:00",
        statements=["Изменений нет."],
        attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
    )

    delta = _read(Path(result["delta"]))
    rendered = Path(result["html"]).read_text(encoding="utf-8")
    assert result["status"] == "locator_delta_empty"
    assert delta["summary"]["changed_facts"] == 0
    assert delta["summary"]["region_groups"] == 0
    assert 'id="copy" type="button" aria-describedby="feedback" disabled' in rendered
    assert "if(state.groups===0){empty.hidden=false;return;}" in rendered


def test_locator_delta_rejects_crop_tamper(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)
    crop_path = inputs["revised_artifact_root"] / "example_p01" / "crop.png"
    crop_path.write_bytes(crop_path.read_bytes() + b"tampered")

    with pytest.raises(
        DELTA.LocatorDeltaError, match="locator_delta_crop_identity_mismatch"
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "crop-rejected",
            reviewer_identity="Роман",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["Всё верно."],
            attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
        )


def test_locator_delta_rejects_forged_review_index_projection(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)
    index = _read(inputs["revised_review_index_path"])
    index["cards"][0]["region"]["facts"][0]["visible_value"] = "$ 999"
    index.pop("index_sha256")
    index["index_sha256"] = REVIEW.sha256_json(index)
    forged_path = tmp_path / "forged-review.index.json"
    forged_path.write_bytes(REVIEW.canonical_json_bytes(index))
    inputs["revised_review_index_path"] = forged_path

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_delta_review_index_projection_mismatch",
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "index-rejected",
            reviewer_identity="Роман",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["Всё верно."],
            attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
        )


def test_locator_delta_rejects_forged_source_preparation(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)
    preparation = _read(inputs["revised_preparation_path"])
    preparation["proposed_reference_sha256"] = "f" * 64
    preparation.pop("preparation_sha256")
    preparation["preparation_sha256"] = REVIEW.sha256_json(preparation)
    forged_path = tmp_path / "forged-preparation.safe.json"
    forged_path.write_bytes(REVIEW.canonical_json_bytes(preparation))
    inputs["revised_preparation_path"] = forged_path

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_delta_revised_preparation_invalid",
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "preparation-rejected",
            reviewer_identity="Roman",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["All visible source material was reviewed."],
            attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
        )


def test_locator_delta_requires_source_preparation_file(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)
    inputs["revised_preparation_path"] = tmp_path / "missing-preparation.json"

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_delta_revised_preparation_invalid",
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "missing-preparation-rejected",
            reviewer_identity="Roman",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["All visible source material was reviewed."],
            attestation_scope=DELTA.ATTESTATION_SCOPE_ALL_VISIBLE,
        )


def test_locator_delta_requires_explicit_attestation_scope(tmp_path: Path) -> None:
    inputs = _review_inputs(tmp_path)

    with pytest.raises(
        DELTA.LocatorDeltaError,
        match="locator_delta_attestation_scope_invalid",
    ):
        DELTA.build_locator_delta(
            **inputs,
            output_dir=tmp_path / "scope-rejected",
            reviewer_identity="Roman",
            reviewed_at="2026-07-16T20:50:10+03:00",
            statements=["All visible source material was reviewed."],
            attestation_scope="unspecified",
        )


def _review_inputs(tmp_path: Path, *, semantic_change: bool = False) -> dict[str, Any]:
    artifact_root = tmp_path / "artifacts"
    case_root = artifact_root / "example_p01"
    case_root.mkdir(parents=True)
    png = b"\x89PNG\r\n\x1a\nlocator-delta-fixture"
    page_path = case_root / "page.png"
    crop_path = case_root / "crop.png"
    page_path.write_bytes(png)
    crop_path.write_bytes(png)
    baseline = _proposal(png)
    revised = copy.deepcopy(baseline)
    fact = revised["cases"][0]["regions"][0]["facts"][0]
    fact["uncertainty"].append("header_not_present_in_source")
    fact["uncertainty"].append(
        "source_locator_text_mismatch_requires_human_confirmation"
    )
    fact["source_regions"]["value"]["bbox_normalized"] = [0.7, 0.2, 0.95, 0.3]
    if semantic_change:
        fact["visible_value"] = "$ 101"
        fact["numeric_value"] = "101"
        fact["source_regions"]["value"]["visible_text"] = "$ 101"
    baseline_path = tmp_path / "baseline.private.json"
    revised_path = tmp_path / "revised.private.json"
    baseline_path.write_bytes(REVIEW.canonical_json_bytes(baseline))
    revised_path.write_bytes(REVIEW.canonical_json_bytes(revised))
    baseline_pack = REVIEW.generate_review_pack(
        proposed_reference=baseline,
        page_artifact_paths={
            "betterment_p02": page_path,
            "example_p01": page_path,
        },
        crop_artifact_paths={"example_p01:r1": crop_path},
        output_dir=tmp_path / "baseline-review",
    )
    revised_pack = REVIEW.generate_review_pack(
        proposed_reference=revised,
        page_artifact_paths={
            "betterment_p02": page_path,
            "example_p01": page_path,
        },
        crop_artifact_paths={"example_p01:r1": crop_path},
        output_dir=tmp_path / "revised-review",
    )
    preparation = {
        "schema_version": DELTA.REFERENCE_PREPARATION_SCHEMA,
        "human_reviewed": False,
        "may_be_used_for_scoring": False,
        "manifest_sha256": revised["manifest_sha256"],
        "proposed_reference_sha256": REVIEW.sha256_json(revised),
        "legacy_reference_sha256": "d" * 64,
        "legacy_terminal_sha256": "e" * 64,
        "review_index_sha256": revised_pack["review_index"]["index_sha256"],
        "review_html_sha256": revised_pack["review_html_sha256"],
        "proposal_role": "unreviewed_source_only_candidate",
        "human_action_required": True,
    }
    preparation["preparation_sha256"] = REVIEW.sha256_json(preparation)
    preparation_path = tmp_path / "preparation.safe.json"
    preparation_path.write_bytes(REVIEW.canonical_json_bytes(preparation))
    return {
        "baseline_proposed_path": baseline_path,
        "baseline_review_index_path": Path(baseline_pack["review_index_path"]),
        "revised_proposed_path": revised_path,
        "revised_review_index_path": Path(revised_pack["review_index_path"]),
        "revised_preparation_path": preparation_path,
        "revised_artifact_root": artifact_root,
    }


def _proposal(png: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(png).hexdigest()

    def locator(text: str, bbox: list[float]) -> dict[str, Any]:
        return {
            "artifact_sha256": digest,
            "bbox_normalized": bbox,
            "visible_text": text,
        }

    fact = {
        "fact_id": "fact_cash",
        "fact_type": "financial_numeric_fact",
        "row_label": "Cash",
        "normalized_row_identity": None,
        "header_path": [],
        "visible_value": "$ 100",
        "numeric_value": "100",
        "sign": "positive",
        "period": None,
        "currency": None,
        "unit": None,
        "scale": None,
        "entity": None,
        "qualifiers": [],
        "source_regions": {
            "row_label": locator("Cash", [0.05, 0.2, 0.35, 0.3]),
            "header": [],
            "value": locator("$ 100", [0.65, 0.2, 0.95, 0.3]),
            "context": [],
        },
        "uncertainty": ["proposed_from_unreviewed_legacy_grid"],
        "alternative_interpretation": None,
    }
    return {
        "schema_version": REVIEW.PROPOSED_REFERENCE_SCHEMA,
        "benchmark_id": "pdf_dual_vlm_fact_v1",
        "manifest_sha256": "b" * 64,
        "cases": [
            {
                "case_id": "example_p01",
                "document_id": "example_p01",
                "pdf_sha256": "c" * 64,
                "page_number": 1,
                "page_sha256": digest,
                "expected_kind": "table",
                "regions": [
                    {
                        "region_id": "r1",
                        "bbox_normalized": [0.1, 0.1, 0.9, 0.9],
                        "crop_sha256": digest,
                        "evidence_medium": "raster",
                        "one_complete_table": True,
                        "cuts": {
                            "header": False,
                            "total": False,
                            "row": False,
                            "column": False,
                        },
                        "includes_neighboring_prose": False,
                        "includes_other_table": False,
                        "facts": [fact],
                    }
                ],
            },
            {
                "case_id": "betterment_p02",
                "document_id": "betterment_p02",
                "pdf_sha256": "d" * 64,
                "page_number": 2,
                "page_sha256": digest,
                "expected_kind": "negative",
                "regions": [],
            },
        ],
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
