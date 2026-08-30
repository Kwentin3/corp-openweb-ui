from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.test_broker_reports_managed_semantic_product_path_counterexamples_v1 import (
    _pdf_bytes,
    _run,
    _trade_page,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "run_managed_semantic_candidate_local.py"


def _module():
    spec = importlib.util.spec_from_file_location("issue317_candidate_runner", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Builder:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def build_with_semantic_compiled_document_candidate(self, content, **kwargs):
        self.calls.append((content, copy.deepcopy(kwargs)))
        return self.result


def _result():
    managed = SimpleNamespace(
        status="COMPLETE",
        safe_diagnostics={},
        private_diagnostics={
            "adjudication_provider_accounting": {
                    "provider_http_calls": 4,
                    "model_generation_calls": 2,
                    "count_tokens_http_calls": 2,
                    "same_raster_binding": True,
                    "document_binding_sha256": "1" * 64,
                    "proposal_sha256": "2" * 64,
                    "critic_sha256": "3" * 64,
                "secret": "must-not-escape",
            }
        },
        whole_table_projection_diagnostics={"status": "COMPLETE"},
    )
    canonical = {
        "artifact_id": "canonical-safe-id",
        "canonical_root_hash": "4" * 64,
        "source": {
            "source_sha256": hashlib.sha256(b"%PDF-1.7 safe-test").hexdigest(),
            "literal": "private",
        },
    }
    return SimpleNamespace(
        status="CANDIDATE_COMPLETE",
        reason_code=None,
        execution_receipt={
            "local_invocations": 2,
            "provider_submissions": 2,
            "provider_responses": 2,
            "executions": [
                {
                    "phase": "PROPOSAL",
                    "fallback_used": False,
                    "repair_attempt_count": 0,
                    "provider_execution": {"raw": "private"},
                },
                {
                    "phase": "CRITIC",
                    "fallback_used": False,
                    "repair_attempt_count": 0,
                    "provider_execution": {"raw": "private"},
                },
            ],
        },
        evidence_result=SimpleNamespace(
            canonical_result=SimpleNamespace(
                managed_result=managed,
                canonical_artifact=canonical,
            )
        ),
        document_candidate={
            "document_candidate_status": "CANDIDATE_COMPLETE",
            "document_record_candidates": [{"private_literal": "GAZP"}],
            "document_candidate_sha256": "6" * 64,
            "runtime_activation": False,
            "publication_authorized": False,
        },
        semantic_review_candidate_binding={
            "binding_sha256": "7" * 64,
            "consumer_eligible": False,
        },
    )


def _args(tmp_path: Path) -> argparse.Namespace:
    source = tmp_path / "control.pdf"
    source.write_bytes(b"%PDF-1.7 safe-test")
    schema = tmp_path / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    return argparse.Namespace(
        source=source,
        source_artifact_ref="source-ref",
        task_id="task-id",
        tenant_id="tenant-id",
        user_id="private-user",
        user_scope_sha256="a" * 64,
        provider_profile="google_gemini",
        proposal_model="proposal-model",
        critic_model="critic-model",
        artifact_version=3,
        dpi=175,
        created_at="2026-08-30T00:00:00Z",
        previous_version_ref="previous-ref",
        schema=schema,
        output=None,
    )


def _mutate(result, case: str) -> None:
    visual = result.evidence_result.canonical_result.managed_result.private_diagnostics[
        "adjudication_provider_accounting"
    ]
    canonical = result.evidence_result.canonical_result.canonical_artifact
    if case.startswith("visual."):
        visual[case.split(".", 1)[1]] = None
    elif case == "semantic.phase":
        result.execution_receipt["executions"][0]["phase"] = "CRITIC"
    elif case == "semantic.fallback":
        result.execution_receipt["executions"][0]["fallback_used"] = True
    elif case == "semantic.repair":
        result.execution_receipt["executions"][0]["repair_attempt_count"] = 1
    elif case.startswith("semantic."):
        result.execution_receipt[case.split(".", 1)[1]] = None
    elif case == "canonical":
        result.evidence_result.canonical_result.canonical_artifact = None
    elif case == "canonical.root":
        canonical["canonical_root_hash"] = "bad"
    elif case == "canonical.source":
        canonical["source"]["source_sha256"] = "bad"
    elif case == "canonical.source_rebound":
        canonical["source"]["source_sha256"] = "8" * 64
    elif case == "candidate.hash":
        result.document_candidate["document_candidate_sha256"] = "bad"
    elif case == "candidate.terminal":
        result.document_candidate["document_candidate_status"] = "BLOCKED"
    elif case == "binding.hash":
        result.semantic_review_candidate_binding["binding_sha256"] = "bad"
    elif case == "safety.consumer":
        result.semantic_review_candidate_binding["consumer_eligible"] = True
    elif case == "safety.runtime":
        result.document_candidate["runtime_activation"] = True
    elif case == "safety.publication":
        result.document_candidate["publication_authorized"] = True
    else:  # pragma: no cover - test table owns this vocabulary
        raise AssertionError(case)


@pytest.mark.asyncio
async def test_runner_forwards_exact_raw_pdf_scope_and_emits_safe_receipt(
    monkeypatch, tmp_path
) -> None:
    module = _module()
    result = _result()
    builder = _Builder(result)
    captured = {}

    class Factory:
        def create_semantic_review_for_openwebui(self, schema, request, user, **kwargs):
            captured.update(schema=schema, request=request, user=user, kwargs=kwargs)
            return builder

    monkeypatch.setattr(module, "ManagedPdfToCanonicalFactory", Factory)
    monkeypatch.setattr(
        module,
        "_load_openwebui",
        lambda user_id: ("owner-request", "owner-user"),
    )
    args = _args(tmp_path)
    receipt = await module.run(args)

    assert captured["request"] == "owner-request"
    assert captured["user"] == "owner-user"
    assert captured["kwargs"]["provider_profile_id"] == "google_gemini"
    assert len(builder.calls) == 1
    content, call = builder.calls[0]
    assert content == args.source.read_bytes()
    assert call == {
        "tenant_id": "tenant-id",
        "artifact_version": 3,
        "source_artifact_ref": "source-ref",
        "task_id": "task-id",
        "user_scope_sha256": "a" * 64,
        "proposal_model_id": "proposal-model",
        "critic_model_id": "critic-model",
        "dpi": 175,
        "created_at": "2026-08-30T00:00:00Z",
        "previous_version_ref": "previous-ref",
    }
    assert receipt["execution"]["semantic"]["provider_submissions"] == 2
    assert receipt["execution"]["visual"]["provider_http_calls"] == 4
    assert receipt["safety"] == {
        "mutation_apis_imported": False,
        "direct_transport_used": False,
        "consumer_eligible": False,
        "runtime_activation": False,
        "publication_authorized": False,
    }
    encoded = json.dumps(receipt, sort_keys=True)
    for forbidden in (
        str(args.source),
        "private-user",
        "must-not-escape",
        "private_literal",
        "GAZP",
        "provider_execution",
        "source-ref",
    ):
        assert forbidden not in encoded


def test_runner_fails_closed_when_openwebui_runtime_is_absent(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ModuleNotFoundError()),
    )
    with pytest.raises(RuntimeError, match="openwebui_runtime_unavailable"):
        module._load_openwebui("user")


def test_runner_has_no_forbidden_mutation_or_transport_imports() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported.intersection(
        {
            "requests",
            "httpx",
            "urllib",
            "open_webui.models.files",
            "open_webui.models.chats",
        }
    )
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called.isdisjoint({"upload", "create_chat", "put_candidate", "publish"})
    assert "create_semantic_review_for_openwebui" in source
    assert "build_with_semantic_compiled_document_candidate" in source


@pytest.mark.asyncio
async def test_safe_receipt_reads_real_composite_owner_accounting(
    monkeypatch,
) -> None:
    module = _module()
    page = _trade_page()
    source_bytes = _pdf_bytes([page])
    result, _semantic = await _run(monkeypatch, [page], (8,))
    receipt = module._safe_receipt(result, source_bytes=source_bytes)

    assert receipt["status"] == "CANDIDATE_COMPLETE"
    assert receipt["execution"]["visual"] == {
        "provider_http_calls": 4,
        "model_generation_calls": 2,
        "count_tokens_http_calls": 2,
        "same_raster_binding": True,
        "document_binding_sha256": receipt["execution"]["visual"][
            "document_binding_sha256"
        ],
        "proposal_sha256": receipt["execution"]["visual"]["proposal_sha256"],
        "critic_sha256": receipt["execution"]["visual"]["critic_sha256"],
    }
    for key in (
        "document_binding_sha256",
        "proposal_sha256",
        "critic_sha256",
    ):
        assert module._sha256(receipt["execution"]["visual"][key])
    for key in (
        "canonical_root_sha256",
        "canonical_source_sha256",
        "candidate_sha256",
        "binding_sha256",
    ):
        assert module._sha256(receipt["artifacts"][key])
    assert receipt["execution"]["semantic"]["provider_submissions"] == 2
    assert set(receipt) == {
        "schema_version",
        "status",
        "reason_code",
        "source",
        "execution",
        "artifacts",
        "safety",
    }
    assert set(receipt["artifacts"]) == {
        "managed_status",
        "whole_table_projection_status",
        "canonical_root_sha256",
        "canonical_source_sha256",
        "document_candidate_status",
        "document_record_candidates",
        "candidate_sha256",
        "binding_sha256",
    }


def test_main_sanitizes_unexpected_exception(monkeypatch, capsys, tmp_path) -> None:
    module = _module()
    args = _args(tmp_path)
    monkeypatch.setattr(module, "_parser", lambda: SimpleNamespace(parse_args=lambda _: args))

    async def fail(_args):
        raise RuntimeError("private path and provider body")

    monkeypatch.setattr(module, "run", fail)
    assert module.main([]) == 1
    output = capsys.readouterr().out
    assert "private path" not in output
    assert json.loads(output)["reason_code"] == "RUNNER_BLOCKED"


@pytest.mark.parametrize(
    "case",
    (
        "visual.provider_http_calls",
        "visual.model_generation_calls",
        "visual.count_tokens_http_calls",
        "visual.same_raster_binding",
        "visual.document_binding_sha256",
        "visual.proposal_sha256",
        "visual.critic_sha256",
        "semantic.local_invocations",
        "semantic.provider_submissions",
        "semantic.provider_responses",
        "semantic.phase",
        "semantic.fallback",
        "semantic.repair",
        "canonical",
        "canonical.root",
        "canonical.source",
        "canonical.source_rebound",
        "candidate.hash",
        "candidate.terminal",
        "binding.hash",
        "safety.consumer",
        "safety.runtime",
        "safety.publication",
    ),
)
def test_candidate_complete_rejects_each_missing_or_mutated_proof(case) -> None:
    module = _module()
    result = _result()
    _mutate(result, case)
    with pytest.raises(RuntimeError):
        module._safe_receipt(result, source_bytes=b"%PDF-1.7 safe-test")
