from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import goal391_native_table_annotation_lab as lab  # noqa: E402


def test_selected_pages_require_a_sorted_unique_bounded_zero_based_slice() -> None:
    assert lab._parse_zero_based_pages("0,2,7", source_page_count=8) == (0, 2, 7)
    for value in ("", "2,0", "0,0", "8", "-1", "0,1,2,3,4,5,6,7,8"):
        with pytest.raises(lab.NativeTableAnnotationLabError):
            lab._parse_zero_based_pages(value, source_page_count=8)


def test_external_output_must_be_new_and_outside_repository(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(lab.NativeTableAnnotationLabError):
        lab._require_new_external_path(repo_root / "receipt.json", repo_root=repo_root)

    existing = tmp_path / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(lab.NativeTableAnnotationLabError):
        lab._require_new_external_path(existing, repo_root=repo_root)

    assert lab._require_new_external_path(tmp_path / "new.json", repo_root=repo_root) == (
        tmp_path / "new.json"
    )


def test_safe_receipt_does_not_contain_private_prompt_or_page_values() -> None:
    prompt = "private table instruction"
    receipt = lab._safe_receipt(
        status="PREFLIGHT_PASSED",
        terminal="READY",
        source_sha256="a" * 64,
        source_bytes_total=123,
        source_page_count=9,
        selected_pages=(4, 5),
        prompt=prompt,
        annotation_attempts_started_total=0,
        annotation_responses_validated_total=0,
    )
    serialized = str(receipt)
    assert prompt not in serialized
    assert "[4, 5]" not in serialized
    assert receipt["selected_pages_total"] == 2
    assert receipt["annotation_attempts_started_total"] == 0
    assert receipt["annotation_responses_validated_total"] == 0


def test_raw_response_receipt_exposes_only_hash_and_size(tmp_path: Path) -> None:
    raw_response = b'{"document_annotation":"private provider response"}'
    private_path = tmp_path / "provider-response.private.json"

    lab._write_private_bytes_new(private_path, raw_response)
    receipt = lab._safe_receipt(
        status="RAW_RESPONSE_CAPTURED_AWAITING_PRIVATE_AUDIT",
        terminal="ONE_CLEAN_CALL_RAW_RESPONSE_READY",
        source_sha256="a" * 64,
        source_bytes_total=123,
        source_page_count=9,
        selected_pages=(4, 5),
        prompt="private table instruction",
        annotation_attempts_started_total=1,
        annotation_responses_validated_total=0,
        raw_response=raw_response,
    )

    assert private_path.read_bytes() == raw_response
    assert receipt["raw_response_sha256"] == hashlib.sha256(raw_response).hexdigest()
    assert receipt["raw_response_bytes_total"] == len(raw_response)
    assert raw_response.decode("utf-8") not in str(receipt)
    with pytest.raises(lab.NativeTableAnnotationLabError):
        lab._write_private_bytes_new(private_path, raw_response)
