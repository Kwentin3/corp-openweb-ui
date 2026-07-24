"""Pure contracts for the Broker Reports atomic stage release tooling."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from broker_reports_gate1.architecture_policy import (
    ARCHITECTURE_POLICY_VERSION,
    KNOWLEDGE_RAG_VECTORIZATION_ALLOWED,
    LOCAL_OCR_PRODUCTION_ALLOWED,
    LOCAL_OCR_WORKER_POOL_ALLOWED,
    NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED,
    WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED,
)
from broker_reports_gate1.pdf_hybrid_provider import project_gemini_schema
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
    semantic_table_transcription_schema,
)
from broker_reports_gate1.semantic_visual_table_migration import (
    GOAL5_QUALIFICATION_GATE_HASH,
    GOAL5_QUALIFICATION_RECEIPT_HASH,
    SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID,
    SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"

SCHEMA_VERSION = "broker_reports_atomic_stage_release_v3"
RELEASE_ID_RE = re.compile(r"^broker-reports-[0-9a-f]{12}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PINNED_IMAGE = (
    "corp-openwebui/openwebui:"
    "v0.9.6-native-web-stt-broker-intake-v2-8e6a71f"
)
PINNED_IMAGE_ID = (
    "sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83"
)
PINNED_IMAGE_REVISION = "8e6a71f13cf4f9cec0e5be191fac924548050e48"
PRIVATE_INTAKE_CONTRACT = "server-authoritative-v2"
REQUIRED_FITZ_VERSION = "1.26.5"

ACTION_ID = "broker_reports_private_intake_action"
ACTION_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_private_intake_action.py"
)
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"

TERMINAL_WORKLOAD_STATES = frozenset({"completed", "failed", "cancelled"})

WORKLOAD_PROVIDER_BUDGETS = {
    "alibaba_qwen": 1,
    "anthropic_claude": 1,
    "deepseek": 1,
    "google_gemini": 1,
    "openai_gpt": 2,
    "openwebui_completion": 2,
    "zai_glm": 1,
}
WORKLOAD_PROVIDER_BUDGETS_JSON = json.dumps(
    WORKLOAD_PROVIDER_BUDGETS,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)

COMMON_WORKLOAD_VALVES: dict[str, Any] = {
    "workload_store_path": "",
    "workload_temp_root": "",
    "workload_lease_seconds": 90.0,
    "workload_poll_interval_seconds": 0.2,
    "workload_provider_budgets_json": WORKLOAD_PROVIDER_BUDGETS_JSON,
}

GATE1_RELEASE_VALVES: dict[str, Any] = {
    **COMMON_WORKLOAD_VALVES,
    "pdf_table_intake_enabled": True,
    "pdf_table_intake_provider_profile": "google_gemini",
    "pdf_table_intake_model_id": "models/gemini-3.5-flash",
    "pdf_table_intake_dpi": 150,
    "pdf_table_intake_maximum_pages": 64,
    "pdf_table_intake_maximum_candidates_per_page": 32,
    "pdf_table_intake_horizontal_padding_fraction": 0.08,
    "pdf_table_intake_vertical_padding_fraction": 0.08,
    "pdf_dual_vlm_enabled": True,
    "pdf_dual_vlm_provider_selection_policy_version": (
        "pdf_semantic_vlm_provider_selection_v1"
    ),
    "pdf_dual_vlm_openai_invocation_policy": "disabled",
    "pdf_dual_vlm_gemini_model_id": "models/gemini-3.5-flash",
    "pdf_dual_vlm_openai_model_id": "gpt-5.4-mini-2026-03-17",
    "pdf_dual_vlm_timeout_seconds": 240,
    "pdf_dual_vlm_maximum_output_tokens": 16_384,
    "pdf_dual_vlm_maximum_counted_input_tokens": 24_000,
    "pdf_dual_vlm_maximum_candidates": 8,
    "pdf_semantic_visual_table_downstream_enabled": True,
    "pdf_semantic_visual_table_migration_policy_version": (
        SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION
    ),
    "pdf_semantic_visual_table_accepted_profile_id": (
        SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID
    ),
    "pdf_hybrid_shadow_enabled": False,
    "pdf_hybrid_shadow_table_allowlist": "",
    "pdf_structural_repair_shadow_enabled": False,
    "pdf_structural_repair_shadow_table_allowlist": "",
    "pdf_vlm_guided_intake_shadow_enabled": False,
    "pdf_vlm_guided_intake_shadow_page_allowlist": "",
    "pdf_semantic_header_shadow_enabled": False,
}

SOURCE_RELEASE_VALVES: dict[str, Any] = {
    **COMMON_WORKLOAD_VALVES,
    "default_wave": "primary",
    "semantic_selection_enabled": False,
    "table_max_rows": 40,
    "text_max_chars": 6000,
    "max_estimated_input_tokens": 12000,
}

DOMAIN_RELEASE_VALVES: dict[str, Any] = {
    **COMMON_WORKLOAD_VALVES,
    "default_wave": "primary",
    "default_document_batch_limit": 1,
    "default_source_unit_limit": 1,
    "segmentation_enabled": True,
    "prefer_table_projections": False,
    "allow_standalone_semantic_visual_projections": True,
    "candidate_binding_enabled": False,
    "gate3_context_manifest_enabled": False,
    "answer_context_selection_enabled": True,
    "default_source_segment_limit": 1,
    "table_segment_max_refs": 8,
    "text_segment_max_refs": 12,
    "max_repair_attempts": 1,
    "table_max_rows": 40,
    "text_max_chars": 6000,
    "financial_evidence_enabled": True,
    "financial_evidence_registry_version": (
        "broker_reports_gate2_financial_evidence_registry_v1"
    ),
    "financial_evidence_maximum_scopes": 64,
}


@dataclass(frozen=True)
class FunctionReleaseContract:
    function_id: str
    bundle_path: Path
    valves: Mapping[str, Any]
    required_markers: tuple[str, ...]


FUNCTION_CONTRACTS = (
    FunctionReleaseContract(
        function_id="broker_reports_gate1_pipe",
        bundle_path=(
            SERVICE_ROOT
            / "openwebui_actions"
            / "broker_reports_gate1_pipe_bundled.py"
        ),
        valves=GATE1_RELEASE_VALVES,
        required_markers=(
            "WorkloadAuthorityFactory",
            "PdfVisualTableReviewFactory",
            "Gate2TablePackageFactory",
            "SemanticVisualTableMigrationFactory",
            "broker_reports_semantic_visual_table_envelope_v1",
            "broker_reports_visual_table_review_receipt_v1",
            "broker_reports_fns_2ndfl_source_facts_v1",
        ),
    ),
    FunctionReleaseContract(
        function_id="broker_reports_gate2_source_fact_pipe",
        bundle_path=(
            SERVICE_ROOT
            / "openwebui_actions"
            / "broker_reports_gate2_source_fact_pipe_bundled.py"
        ),
        valves=SOURCE_RELEASE_VALVES,
        required_markers=(
            "WorkloadAuthorityFactory",
            "Gate2SourceFactRuntimeFactory",
            "broker_reports_fns_2ndfl_source_facts_v1",
        ),
    ),
    FunctionReleaseContract(
        function_id="broker_reports_gate2_domain_source_fact_pipe",
        bundle_path=(
            SERVICE_ROOT
            / "openwebui_actions"
            / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
        ),
        valves=DOMAIN_RELEASE_VALVES,
        required_markers=(
            "WorkloadAuthorityFactory",
            "Gate2DomainSourceFactRuntimeFactory",
            "Gate2CandidateBindingRuntimeFactory",
            "allow_standalone_semantic_visual_projections",
            "AnswerContextSelectionFactory",
            "broker_reports_answer_context_selection_receipt_v1",
            "Gate2FinancialEvidenceProductionRuntimeFactory",
            "broker_reports_gate2_financial_evidence_registry_v1",
            "broker_reports_gate2_financial_context_v1",
            "financial_evidence_enabled",
        ),
    ),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized_text_sha256(path: Path) -> str:
    return sha256_text(normalized_text(path))


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def release_id(source_revision: str) -> str:
    assert_revision(source_revision)
    return f"broker-reports-{source_revision[:12]}"


def assert_revision(value: str) -> None:
    if not REVISION_RE.fullmatch(str(value or "")):
        raise ValueError("stage_release_source_revision_invalid")


def assert_release_id(value: str) -> None:
    if not RELEASE_ID_RE.fullmatch(str(value or "")):
        raise ValueError("stage_release_id_invalid")


def merged_valves(function_id: str, current: Mapping[str, Any]) -> dict[str, Any]:
    contract = function_contract(function_id)
    return {**dict(current), **dict(contract.valves)}


def valve_projection(function_id: str, valves: Mapping[str, Any]) -> dict[str, Any]:
    contract = function_contract(function_id)
    return {key: valves.get(key) for key in sorted(contract.valves)}


def valves_match(function_id: str, valves: Mapping[str, Any]) -> bool:
    contract = function_contract(function_id)
    return all(valves.get(key) == expected for key, expected in contract.valves.items())


def function_contract(function_id: str) -> FunctionReleaseContract:
    for contract in FUNCTION_CONTRACTS:
        if contract.function_id == function_id:
            return contract
    raise ValueError("stage_release_function_id_unknown")


def nonterminal_workload_count(state_counts: Mapping[str, int]) -> int:
    return sum(
        int(count)
        for state, count in state_counts.items()
        if state not in TERMINAL_WORKLOAD_STATES
    )


def build_manifest(
    *,
    source_revision: str,
    prompt_contracts: Mapping[str, Mapping[str, Any]],
    provider_policy: Mapping[str, Any],
    loader_bytes: bytes,
) -> dict[str, Any]:
    assert_revision(source_revision)
    if not isinstance(loader_bytes, bytes) or not loader_bytes:
        raise ValueError("stage_release_loader_bytes_invalid")
    functions = []
    for contract in FUNCTION_CONTRACTS:
        content = normalized_text(contract.bundle_path)
        missing = [marker for marker in contract.required_markers if marker not in content]
        if missing:
            raise ValueError(
                "stage_release_bundle_required_markers_missing:"
                + contract.function_id
                + ":"
                + ",".join(missing)
            )
        functions.append(
            {
                "function_id": contract.function_id,
                "bundle_name": contract.bundle_path.name,
                "content_sha256": sha256_text(content),
                "required_markers": list(contract.required_markers),
                "valves": dict(contract.valves),
            }
        )
    prompts = []
    for prompt_id in sorted(prompt_contracts):
        item = prompt_contracts[prompt_id]
        prompts.append(
            {
                "prompt_id": prompt_id,
                "command": item["command"],
                "version": item["version"],
                "content": item["content"],
                "content_sha256": item["content_sha256"],
                "meta": dict(item.get("meta") or {}),
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id(source_revision),
        "source_revision": source_revision,
        "image": {
            "configured_image": PINNED_IMAGE,
            "image_id": PINNED_IMAGE_ID,
            "source_revision": PINNED_IMAGE_REVISION,
            "private_intake_contract": PRIVATE_INTAKE_CONTRACT,
        },
        "action": {
            "action_id": ACTION_ID,
            "content_sha256": normalized_text_sha256(ACTION_PATH),
            "active": True,
            "global": False,
        },
        "loader": {
            "file_name": LOADER_PATH.name,
            "content_sha256": sha256_bytes(loader_bytes),
        },
        "functions": functions,
        "managed_prompts": prompts,
        "provider_policy": dict(provider_policy),
        "runtime": {
            "fitz_version": REQUIRED_FITZ_VERSION,
            "vlm_default_enabled": True,
            "semantic_visual_profile_default_enabled": True,
            "visual_auto_publication_enabled": False,
            "gate1_heavy_concurrency": 1,
            "gate2_local_maximum_concurrency": 2,
        },
    }
    manifest["manifest_sha256"] = sha256_text(canonical_json(manifest))
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("stage_release_manifest_schema_invalid")
    assert_revision(str(manifest.get("source_revision") or ""))
    assert_release_id(str(manifest.get("release_id") or ""))
    supplied_digest = str(manifest.get("manifest_sha256") or "")
    if not SHA256_RE.fullmatch(supplied_digest):
        raise ValueError("stage_release_manifest_digest_invalid")
    material = dict(manifest)
    material.pop("manifest_sha256", None)
    if sha256_text(canonical_json(material)) != supplied_digest:
        raise ValueError("stage_release_manifest_digest_mismatch")
    function_ids = [item.get("function_id") for item in manifest.get("functions", [])]
    if function_ids != [contract.function_id for contract in FUNCTION_CONTRACTS]:
        raise ValueError("stage_release_manifest_function_set_invalid")
    prompts = manifest.get("managed_prompts") or []
    if not prompts or any(not isinstance(item, dict) for item in prompts):
        raise ValueError("stage_release_manifest_prompt_set_invalid")
    prompt_ids = [str(item.get("prompt_id") or "") for item in prompts]
    if len(prompt_ids) != len(set(prompt_ids)) or any(not item for item in prompt_ids):
        raise ValueError("stage_release_manifest_prompt_set_invalid")
    for item in prompts:
        content = item.get("content")
        if (
            not isinstance(content, str)
            or not content.strip()
            or sha256_text(content) != item.get("content_sha256")
            or not str(item.get("command") or "")
            or not str(item.get("version") or "")
            or not isinstance(item.get("meta"), dict)
        ):
            raise ValueError("stage_release_manifest_prompt_contract_invalid")
    if manifest.get("image") != {
        "configured_image": PINNED_IMAGE,
        "image_id": PINNED_IMAGE_ID,
        "source_revision": PINNED_IMAGE_REVISION,
        "private_intake_contract": PRIVATE_INTAKE_CONTRACT,
    }:
        raise ValueError("stage_release_manifest_image_invalid")
    loader = manifest.get("loader") or {}
    if (
        loader.get("file_name") != LOADER_PATH.name
        or not SHA256_RE.fullmatch(str(loader.get("content_sha256") or ""))
    ):
        raise ValueError("stage_release_manifest_loader_invalid")
    runtime = manifest.get("runtime") or {}
    if (
        runtime.get("vlm_default_enabled") is not True
        or runtime.get("semantic_visual_profile_default_enabled") is not True
        or runtime.get("visual_auto_publication_enabled") is not False
    ):
        raise ValueError("stage_release_manifest_semantic_activation_invalid")
    semantic = (manifest.get("provider_policy") or {}).get(
        "semantic_visual_table_contract"
    ) or {}
    if semantic != semantic_visual_table_contract_manifest():
        raise ValueError("stage_release_manifest_semantic_contract_invalid")
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    financial_registry = (
        (manifest.get("provider_policy") or {}).get(
            "financial_evidence_registry"
        )
        or {}
    )
    if financial_registry != {
        "registry_id": registry.registry_id,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
        "runtime_schema_version": (
            "broker_reports_gate2_financial_evidence_production_run_v1"
        ),
        "context_schema_version": (
            "broker_reports_gate2_financial_context_v1"
        ),
        "legacy_read_policy": "dual_read",
        "write_policy": "new_schema_only",
    }:
        raise ValueError(
            "stage_release_manifest_financial_registry_invalid"
        )


def provider_policy_manifest(provider_profiles: tuple[Any, ...]) -> dict[str, Any]:
    profiles = []
    for profile in provider_profiles:
        profiles.append(
            {
                "profile_id": profile.profile_id,
                "gate2_status": profile.gate2_status,
                "approved_model_ids": list(profile.approved_model_ids),
                "model_id_prefixes": list(profile.model_id_prefixes),
            }
        )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    return {
        "gate2_profile_contract": "gate2_provider_profile_registry_v1",
        "gate1_visual_selection_policy": "pdf_semantic_vlm_provider_selection_v1",
        "gate1_visual_model_ids": {
            "google_gemini": "models/gemini-3.5-flash",
            "openai_gpt": "gpt-5.4-mini-2026-03-17",
        },
        "semantic_visual_table_contract": semantic_visual_table_contract_manifest(),
        "financial_evidence_registry": {
            "registry_id": registry.registry_id,
            "registry_version": registry.registry_version,
            "registry_hash": registry.registry_hash,
            "runtime_schema_version": (
                "broker_reports_gate2_financial_evidence_production_run_v1"
            ),
            "context_schema_version": (
                "broker_reports_gate2_financial_context_v1"
            ),
            "legacy_read_policy": "dual_read",
            "write_policy": "new_schema_only",
        },
        "profiles": profiles,
    }


def semantic_visual_table_contract_manifest() -> dict[str, Any]:
    schema = semantic_table_transcription_schema()
    gemini_schema, gemini_transforms = project_gemini_schema(schema)
    return {
        "prompt_version": SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
        "prompt_sha256": sha256_text(SEMANTIC_TABLE_TRANSCRIPTION_PROMPT),
        "schema_version": SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
        "canonical_schema_sha256": sha256_text(canonical_json(schema)),
        "gemini_adapted_schema_sha256": sha256_text(
            canonical_json(gemini_schema)
        ),
        "gemini_schema_transform_count": gemini_transforms,
        "openai_adapted_schema_sha256": sha256_text(canonical_json(schema)),
        "openai_schema_transform_count": 0,
        "migration_policy_version": (
            SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION
        ),
        "accepted_profile_id": SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID,
        "qualification_receipt_sha256": GOAL5_QUALIFICATION_RECEIPT_HASH,
        "qualification_gate_sha256": GOAL5_QUALIFICATION_GATE_HASH,
        "runtime_boundary": {
            "architecture_policy_version": ARCHITECTURE_POLICY_VERSION,
            "knowledge_rag_vectorization_allowed": (
                KNOWLEDGE_RAG_VECTORIZATION_ALLOWED
            ),
            "local_ocr_production_allowed": LOCAL_OCR_PRODUCTION_ALLOWED,
            "local_ocr_worker_pool_allowed": LOCAL_OCR_WORKER_POOL_ALLOWED,
            "native_openwebui_document_processing_allowed": (
                NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED
            ),
            "whole_document_provider_upload_allowed": (
                WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED
            ),
        },
    }
