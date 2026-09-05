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
    PDF_DOCUMENT_EXTRACTION_PRODUCTION_CONFIGURED,
    PDF_DOCUMENT_EXTRACTION_SELECTED_ADAPTER,
    PDF_DOCUMENT_EXTRACTION_SELECTED_ENGINE,
    PDF_DOCUMENT_EXTRACTION_STATIC_READY,
)
from broker_reports_gate1.pdf_document_ai import (
    PDF_DOCUMENT_AI_NOT_CONFIGURED,
    PDF_DOCUMENT_AI_POLICY_VERSION,
    PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"

SCHEMA_VERSION = "broker_reports_atomic_stage_release_v11"
RELEASE_ID_RE = re.compile(r"^broker-reports-[0-9a-f]{12}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PINNED_IMAGE = "corp-openwebui/openwebui:v0.9.6-native-web-stt-native-pdf-21545c1"
PINNED_IMAGE_ID = (
    "sha256:dd1fbeafeeb35a0750b472ab040d9d4b26c6408b9e50d3fe3ba2dcb2eadd9176"
)
PINNED_IMAGE_REVISION = "21545c12a679df1733d11ebc2cc46ab5219bb938"
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"

TERMINAL_WORKLOAD_STATES = frozenset({"completed", "failed", "cancelled"})
RELEASE_QUIESCENT_WORKLOAD_STATES = frozenset(
    {*TERMINAL_WORKLOAD_STATES, "awaiting_review"}
)

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
    "canonical_gate2_write_enabled": True,
    "canonical_gate2_read_enabled": True,
    "ndfl_gate3_enabled": False,
    "ordinary_trade_candidate_enabled": True,
    "ndfl_gate3_provider_profile_id": "google_gemini",
    "ndfl_gate3_model_id": "models/gemini-3.5-flash",
    "ndfl_presentation_llm_enabled": True,
    "ndfl_presentation_model_id": "models/gemini-3.5-flash",
    "ndfl_presentation_openwebui_origin": "https://gpt.alpha-soft.ru",
}

GATE1_RETIRED_VALVE_KEYS = (
    "pdf_table_intake_enabled",
    "pdf_table_intake_provider_profile",
    "pdf_table_intake_model_id",
    "pdf_table_intake_dpi",
    "pdf_table_intake_maximum_pages",
    "pdf_table_intake_maximum_candidates_per_page",
    "pdf_table_intake_horizontal_padding_fraction",
    "pdf_table_intake_vertical_padding_fraction",
    "canonical_gate2_compare_enabled",
    "broker_pdf_neutral_table_profile_v1_enabled",
    "pdf_dual_vlm_enabled",
    "pdf_dual_vlm_provider_selection_policy_version",
    "pdf_dual_vlm_openai_invocation_policy",
    "pdf_dual_vlm_gemini_model_id",
    "pdf_dual_vlm_openai_model_id",
    "pdf_dual_vlm_timeout_seconds",
    "pdf_dual_vlm_maximum_output_tokens",
    "pdf_dual_vlm_maximum_counted_input_tokens",
    "pdf_dual_vlm_maximum_candidates",
    "pdf_semantic_visual_table_downstream_enabled",
    "pdf_semantic_visual_table_migration_policy_version",
    "pdf_semantic_visual_table_accepted_profile_id",
    "pdf_hybrid_shadow_enabled",
    "pdf_hybrid_shadow_table_allowlist",
    "pdf_structural_repair_shadow_enabled",
    "pdf_structural_repair_shadow_table_allowlist",
    "pdf_vlm_guided_intake_shadow_enabled",
    "pdf_vlm_guided_intake_shadow_page_allowlist",
    "pdf_semantic_header_shadow_enabled",
    "ndfl_full_product_enabled",
    "ndfl_full_product_synthetic_only",
)

RETIRED_FUNCTION_IDS = (
    "broker_reports_private_intake_action",
    "broker_reports_gate2_source_fact_pipe",
    "broker_reports_gate2_domain_source_fact_pipe",
)


@dataclass(frozen=True)
class FunctionReleaseContract:
    function_id: str
    bundle_path: Path
    valves: Mapping[str, Any]
    required_markers: tuple[str, ...]
    retired_valve_keys: tuple[str, ...] = ()


FUNCTION_CONTRACTS = (
    FunctionReleaseContract(
        function_id="broker_reports_gate1_pipe",
        bundle_path=(
            SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
        ),
        valves=GATE1_RELEASE_VALVES,
        required_markers=(
            "WorkloadAuthorityFactory",
            "PdfDocumentExtractorFactory",
            "PDF_DOCUMENT_AI_NOT_CONFIGURED",
            "Gate2TablePackageFactory",
            "broker_reports_fns_2ndfl_source_facts_v1",
            "Gate5DeclarationPreparationRuntimeFactory",
            "broker_reports_current_pipeline_result_v1",
            "OrdinaryTradeProductionRuntimeFactory",
            "ordinary_trade_automatic_semantic_mapping_v1",
            "legacy_fallback_used",
        ),
        retired_valve_keys=GATE1_RETIRED_VALVE_KEYS,
    ),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    retained = {
        key: value
        for key, value in dict(current).items()
        if key not in contract.retired_valve_keys
    }
    return {**retained, **dict(contract.valves)}


def valve_projection(function_id: str, valves: Mapping[str, Any]) -> dict[str, Any]:
    contract = function_contract(function_id)
    return {key: valves.get(key) for key in sorted(contract.valves)}


def valves_match(function_id: str, valves: Mapping[str, Any]) -> bool:
    contract = function_contract(function_id)
    return all(
        valves.get(key) == expected for key, expected in contract.valves.items()
    ) and all(key not in valves for key in contract.retired_valve_keys)


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


def release_blocking_workload_count(state_counts: Mapping[str, int]) -> int:
    return sum(
        int(count)
        for state, count in state_counts.items()
        if state not in RELEASE_QUIESCENT_WORKLOAD_STATES
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
        missing = [
            marker for marker in contract.required_markers if marker not in content
        ]
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
                "activation_policy": "preserve_existing",
                "content_sha256": sha256_text(content),
                "required_markers": list(contract.required_markers),
                "valves": dict(contract.valves),
                "retired_valve_keys": list(contract.retired_valve_keys),
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
        },
        "loader": {
            "file_name": LOADER_PATH.name,
            "content_sha256": sha256_bytes(loader_bytes),
        },
        "functions": functions,
        "retired_function_ids": list(RETIRED_FUNCTION_IDS),
        "managed_prompts": prompts,
        "provider_policy": dict(provider_policy),
        "runtime": {
            "pdf_document_ai_static_ready": PDF_DOCUMENT_EXTRACTION_STATIC_READY,
            "pdf_document_ai_production_configured": (
                PDF_DOCUMENT_EXTRACTION_PRODUCTION_CONFIGURED
            ),
            "legacy_table_route_available": False,
            "release_quiescent_workload_states": sorted(
                RELEASE_QUIESCENT_WORKLOAD_STATES
            ),
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
    if manifest.get("retired_function_ids") != list(RETIRED_FUNCTION_IDS):
        raise ValueError("stage_release_manifest_retired_function_set_invalid")
    if set(function_ids) & set(RETIRED_FUNCTION_IDS):
        raise ValueError("stage_release_manifest_function_sets_overlap")
    if any(
        item.get("activation_policy") != "preserve_existing"
        for item in manifest.get("functions", [])
    ):
        raise ValueError("stage_release_manifest_activation_policy_invalid")
    for item, contract in zip(manifest.get("functions", []), FUNCTION_CONTRACTS):
        retired = item.get("retired_valve_keys")
        if retired != list(contract.retired_valve_keys) or set(retired or []) & set(
            (item.get("valves") or {}).keys()
        ):
            raise ValueError("stage_release_manifest_retired_valves_invalid")
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
    }:
        raise ValueError("stage_release_manifest_image_invalid")
    loader = manifest.get("loader") or {}
    if loader.get("file_name") != LOADER_PATH.name or not SHA256_RE.fullmatch(
        str(loader.get("content_sha256") or "")
    ):
        raise ValueError("stage_release_manifest_loader_invalid")
    runtime = manifest.get("runtime") or {}
    if (
        runtime.get("pdf_document_ai_static_ready") is not True
        or runtime.get("pdf_document_ai_production_configured") is not True
        or runtime.get("legacy_table_route_available") is not False
        or runtime.get("release_quiescent_workload_states")
        != sorted(RELEASE_QUIESCENT_WORKLOAD_STATES)
    ):
        raise ValueError("stage_release_manifest_current_route_invalid")
    document_ai = (manifest.get("provider_policy") or {}).get(
        "pdf_document_ai_contract"
    ) or {}
    if document_ai != pdf_document_ai_contract_manifest():
        raise ValueError("stage_release_manifest_pdf_document_ai_contract_invalid")
    if "financial_evidence_registry" in (manifest.get("provider_policy") or {}):
        raise ValueError("stage_release_manifest_legacy_registry_present")


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
    return {
        "gate2_profile_contract": "gate2_provider_profile_registry_v1",
        "pdf_document_ai_contract": pdf_document_ai_contract_manifest(),
        "profiles": profiles,
    }


def pdf_document_ai_contract_manifest() -> dict[str, Any]:
    return {
        "configured": PDF_DOCUMENT_EXTRACTION_PRODUCTION_CONFIGURED,
        "adapter_status": "static_ready",
        "selected_engine": PDF_DOCUMENT_EXTRACTION_SELECTED_ENGINE,
        "selected_adapter": PDF_DOCUMENT_EXTRACTION_SELECTED_ADAPTER,
        "static_ready": PDF_DOCUMENT_EXTRACTION_STATIC_READY,
        "policy_version": PDF_DOCUMENT_AI_POLICY_VERSION,
        "extraction_schema_version": PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION,
        "composition_owner": "PdfDocumentExtractorFactory",
        "terminal_blockers": {"unconfigured": PDF_DOCUMENT_AI_NOT_CONFIGURED},
        "automatic_fallback": False,
        "runtime_boundary": {
            "architecture_policy_version": ARCHITECTURE_POLICY_VERSION,
            "knowledge_rag_vectorization_allowed": (
                KNOWLEDGE_RAG_VECTORIZATION_ALLOWED
            ),
            "local_ocr_production_allowed": LOCAL_OCR_PRODUCTION_ALLOWED,
            "local_ocr_worker_pool_allowed": LOCAL_OCR_WORKER_POOL_ALLOWED,
        },
    }
