from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping


SCRIPT_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_ROOT.parent
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.canonical_artifact import (  # noqa: E402
    CanonicalNormalizerConfig,
)
from broker_reports_gate1.managed_pdf_to_canonical import (  # noqa: E402
    ManagedPdfToCanonicalFactory,
)


RECEIPT_SCHEMA_VERSION = "broker_reports_issue317_disposable_candidate_receipt_v1"
DEFAULT_SCHEMA = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the inactive Managed semantic candidate route locally."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-artifact-ref", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--user-scope-sha256", required=True)
    parser.add_argument("--provider-profile", required=True)
    parser.add_argument("--proposal-model", required=True)
    parser.add_argument("--critic-model", required=True)
    parser.add_argument("--artifact-version", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--created-at")
    parser.add_argument("--previous-version-ref")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path)
    return parser


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _load_openwebui(user_id: str) -> tuple[Any, Any]:
    try:
        config = importlib.import_module("open_webui.config")
        users = importlib.import_module("open_webui.models.users")
        user = users.Users.get_user_by_id(user_id)
    except Exception as exc:
        raise RuntimeError("openwebui_runtime_unavailable") from exc
    if user is None:
        raise RuntimeError("openwebui_user_unavailable")
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=config))
    )
    return request, user


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _require_candidate_complete_evidence(
    *,
    canonical: Mapping[str, Any],
    candidate: Mapping[str, Any],
    binding: Mapping[str, Any],
    visual: Mapping[str, Any],
    semantic: Mapping[str, Any],
    source_sha256: str,
) -> None:
    executions = semantic.get("executions")
    if (
        not canonical
        or candidate.get("document_candidate_status") != "CANDIDATE_COMPLETE"
        or visual.get("provider_http_calls") != 4
        or visual.get("model_generation_calls") != 2
        or visual.get("count_tokens_http_calls") != 2
        or visual.get("same_raster_binding") is not True
        or semantic.get("local_invocations") != 2
        or semantic.get("provider_submissions") != 2
        or semantic.get("provider_responses") != 2
        or not isinstance(executions, list)
        or len(executions) != 2
        or [item.get("phase") for item in executions if isinstance(item, Mapping)]
        != ["PROPOSAL", "CRITIC"]
        or any(
            not isinstance(item, Mapping)
            or item.get("fallback_used") is not False
            or item.get("repair_attempt_count") != 0
            for item in executions
        )
    ):
        raise RuntimeError("candidate_complete_evidence_invalid")
    source = _mapping(canonical.get("source"))
    required_hashes = (
        visual.get("document_binding_sha256"),
        visual.get("proposal_sha256"),
        visual.get("critic_sha256"),
        canonical.get("canonical_root_hash"),
        source.get("source_sha256"),
        candidate.get("document_candidate_sha256"),
        binding.get("binding_sha256"),
    )
    if not all(isinstance(value, str) and _sha256(value) for value in required_hashes):
        raise RuntimeError("candidate_complete_hash_binding_invalid")
    if source.get("source_sha256") != source_sha256:
        raise RuntimeError("candidate_complete_source_binding_invalid")


def _safe_receipt(result: Any, *, source_bytes: bytes) -> dict[str, Any]:
    execution = _mapping(getattr(result, "execution_receipt", None))
    evidence_result = getattr(result, "evidence_result", None)
    canonical_result = getattr(evidence_result, "canonical_result", None)
    managed_result = getattr(canonical_result, "managed_result", None)
    canonical = _mapping(getattr(canonical_result, "canonical_artifact", None))
    candidate = _mapping(getattr(result, "document_candidate", None))
    binding = _mapping(
        getattr(result, "semantic_review_candidate_binding", None)
    )
    managed_private = _mapping(
        getattr(managed_result, "private_diagnostics", None)
    )
    projection_safe = _mapping(
        getattr(managed_result, "whole_table_projection_diagnostics", None)
    )
    visual_accounting = _mapping(
        managed_private.get("adjudication_provider_accounting")
    )
    source = _mapping(canonical.get("source"))
    expected_visual = {
        "provider_http_calls": 4,
        "model_generation_calls": 2,
        "count_tokens_http_calls": 2,
        "same_raster_binding": True,
    }
    if canonical and any(
        visual_accounting.get(key) != value
        for key, value in expected_visual.items()
    ):
        raise RuntimeError("visual_provider_accounting_invalid")
    candidate_runtime = candidate.get("runtime_activation")
    candidate_publication = candidate.get("publication_authorized")
    binding_consumer = binding.get("consumer_eligible")
    if candidate and (
        candidate_runtime is not False
        or candidate_publication is not False
        or binding_consumer is not False
    ):
        raise RuntimeError("candidate_safety_contract_invalid")
    if getattr(result, "status", None) == "CANDIDATE_COMPLETE":
        _require_candidate_complete_evidence(
            canonical=canonical,
            candidate=candidate,
            binding=binding,
            visual=visual_accounting,
            semantic=execution,
            source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        )
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": str(getattr(result, "status", "BLOCKED")),
        "reason_code": getattr(result, "reason_code", None),
        "source": {
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "size_bytes": len(source_bytes),
        },
        "execution": {
            "visual": {
                key: visual_accounting.get(key)
                for key in (
                    "provider_http_calls",
                    "model_generation_calls",
                    "count_tokens_http_calls",
                    "same_raster_binding",
                    "document_binding_sha256",
                    "proposal_sha256",
                    "critic_sha256",
                )
            },
            "semantic": {
                "local_invocations": execution.get("local_invocations", 0),
                "provider_submissions": execution.get("provider_submissions", 0),
                "provider_responses": execution.get("provider_responses", 0),
                "executions": [
                    {
                        "phase": item.get("phase"),
                        "fallback_used": item.get("fallback_used"),
                        "repair_attempt_count": item.get("repair_attempt_count"),
                    }
                    for item in execution.get("executions", [])
                    if isinstance(item, Mapping)
                ],
            },
        },
        "artifacts": {
            "managed_status": getattr(managed_result, "status", None),
            "whole_table_projection_status": projection_safe.get("status"),
            "canonical_root_sha256": canonical.get("canonical_root_hash"),
            "canonical_source_sha256": source.get("source_sha256"),
            "document_candidate_status": candidate.get("document_candidate_status"),
            "document_record_candidates": len(
                candidate.get("document_record_candidates", [])
            ),
            "candidate_sha256": candidate.get("document_candidate_sha256"),
            "binding_sha256": binding.get("binding_sha256"),
        },
        "safety": {
            "mutation_apis_imported": False,
            "direct_transport_used": False,
            "consumer_eligible": binding_consumer,
            "runtime_activation": candidate_runtime,
            "publication_authorized": candidate_publication,
        },
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if not _sha256(args.user_scope_sha256):
        raise RuntimeError("user_scope_sha256_invalid")
    if args.artifact_version < 1 or args.dpi < 72:
        raise RuntimeError("runner_arguments_invalid")
    source_bytes = args.source.read_bytes()
    if not source_bytes:
        raise RuntimeError("source_pdf_empty")
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    request, user = _load_openwebui(args.user_id)
    builder = ManagedPdfToCanonicalFactory().create_semantic_review_for_openwebui(
        schema,
        request,
        user,
        normalizer_config=CanonicalNormalizerConfig(
            normalizer_version="issue317_disposable_candidate_v1"
        ),
        provider_profile_id=args.provider_profile,
    )
    result = await builder.build_with_semantic_compiled_document_candidate(
        source_bytes,
        tenant_id=args.tenant_id,
        artifact_version=args.artifact_version,
        source_artifact_ref=args.source_artifact_ref,
        task_id=args.task_id,
        user_scope_sha256=args.user_scope_sha256,
        proposal_model_id=args.proposal_model,
        critic_model_id=args.critic_model,
        dpi=args.dpi,
        created_at=args.created_at,
        previous_version_ref=args.previous_version_ref,
    )
    return _safe_receipt(result, source_bytes=source_bytes)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = asyncio.run(run(args))
    except Exception:
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": "BLOCKED",
            "reason_code": "RUNNER_BLOCKED",
            "safety": {
                "mutation_apis_imported": False,
                "direct_transport_used": False,
                "consumer_eligible": None,
                "runtime_activation": None,
                "publication_authorized": None,
            },
        }
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0 if receipt["status"] == "CANDIDATE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
