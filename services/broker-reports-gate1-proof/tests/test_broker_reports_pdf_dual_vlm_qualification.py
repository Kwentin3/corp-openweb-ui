from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_pdf_dual_vlm_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "broker_reports_pdf_dual_vlm_qualification_under_test",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
QUALIFICATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = QUALIFICATION
SPEC.loader.exec_module(QUALIFICATION)


def _candidate() -> dict:
    return {
        "manifest": {
            "schema_version": "broker_reports_pdf_table_candidate_v1",
            "page_number": 1,
            "dpi": 150,
            "lossless": True,
            "silent_resize_performed": False,
        },
        "private_png_base64": "synthetic-private-crop",
    }


def _qualification(provider: str, model_id: str) -> dict:
    return {
        "status": "qualified",
        "provider_profile": provider,
        "provider_profile_revision": provider + "_revision",
        "requested_model_id": model_id,
        "resolved_model_id": model_id,
        "exact_model_match": True,
        "image_input_supported": True,
        "structured_output_supported": True,
        "native_provider_transport": True,
        "credentials_from_openwebui_connection": True,
        "hidden_retry": False,
        "provider_failover": False,
    }


def _execution(provider: str, model_id: str) -> dict:
    return {
        "provider": provider,
        "requested_model_id": model_id,
        "resolved_model_id": model_id,
        "canonical_schema_hash": "a" * 64,
        "provider_adapted_schema_hash": "b" * 64,
        "preflight": {"within_hard_guard": True},
        "validator_result": {"status": "passed"},
        "terminal_provider_status": "completed",
        "input_hash": "c" * 64,
        "hidden_retry": False,
        "provider_failover": False,
        "provider_switch": False,
        "whole_document_uploaded": False,
        "raw_private_response": {"must_not_escape": True},
        "text": "must not escape",
    }


def test_safe_live_qualification_receipt_is_hashed_and_drops_provider_values() -> None:
    gemini_model = "models/gemini-3.5-flash"
    openai_model = "gpt-5.4-mini-2026-03-17"
    decision = {
        "executions": [
            _execution("gemini", gemini_model),
            _execution("openai", openai_model),
        ],
        "canonical_table": None,
        "provider_proposal_canonical_authority": False,
        "status": "proposal_requires_review",
        "reason_codes": ["source_to_table_accounting_unavailable"],
        "decision_hash": "d" * 64,
        "proposals": {"gemini": {"private": 1}, "openai": {"private": 1}},
    }
    outcome = SimpleNamespace(
        safe_summary={
            "provider_qualifications": {
                "gemini": _qualification("google_gemini", gemini_model),
                "openai": _qualification("openai_gpt", openai_model),
            }
        },
        private_decisions=[decision],
    )
    runtime = SimpleNamespace(run=lambda candidates: outcome)
    factory = SimpleNamespace(create_for_openwebui=lambda request: runtime)
    implementation_hashes = {"qualification_tool": "e" * 64}

    with (
        patch.object(QUALIFICATION.importlib, "import_module", return_value=object()),
        patch.object(QUALIFICATION, "_synthetic_candidate", return_value=_candidate()),
        patch.object(
            QUALIFICATION,
            "PdfDualVlmRuntimeFactory",
            return_value=factory,
        ),
        patch.object(
            QUALIFICATION,
            "_implementation_hashes",
            return_value=implementation_hashes,
        ),
    ):
        receipt = QUALIFICATION.qualify(
            config_module="open_webui.config",
            gemini_model=gemini_model,
            openai_model=openai_model,
        )

    assert receipt["status"] == "requalified"
    assert all(receipt["checks"].values())
    assert receipt["implementation_source_hashes"] == implementation_hashes
    assert receipt["raw_provider_responses_retained"] is False
    assert receipt["provider_output_values_retained"] is False
    assert "proposals" not in receipt
    assert "raw_private_response" not in str(receipt)
    assert "must not escape" not in str(receipt)
    unhashed = copy.deepcopy(receipt)
    qualification_hash = unhashed.pop("qualification_hash")
    assert QUALIFICATION.sha256_json(unhashed) == qualification_hash
