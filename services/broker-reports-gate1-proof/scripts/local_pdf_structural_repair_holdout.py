#!/usr/bin/env python3
"""Run a pre-registered PDF holdout or non-certifying regression."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import mimetypes
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests
from pypdf import PdfReader


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
LOCAL_STAGE2 = REPO_ROOT / "local" / "stage2"
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import FileInput, Gate1Normalizer  # noqa: E402
from broker_reports_gate1.pdf_dual_oracle_consensus import (  # noqa: E402
    PdfDualOracleConsensusFactory,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (  # noqa: E402
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
    PdfGridProviderError,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_materialization import (  # noqa: E402
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_parser_geometry import (  # noqa: E402
    PdfParserGeometryError,
    PdfParserGeometryFactory,
)
from broker_reports_gate1.pdf_structural_repair_holdout_contracts import (  # noqa: E402
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES,
    PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES,
    PDF_STRUCTURAL_HOLDOUT_FRESHNESS_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA_V2,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3,
    PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA,
    PdfStructuralRepairHoldoutContractFactory,
)
from broker_reports_gate1.pdf_structural_repair_runtime import (  # noqa: E402
    PdfStructuralRepairRuntimeFactory,
)
from broker_reports_gate1.pdf_structural_row_windows import (  # noqa: E402
    PdfStructuralRowWindowError,
    PdfStructuralRowWindowFactory,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_topology_assembly import (  # noqa: E402
    PdfTopologyAssemblyError,
    PdfTopologyAssemblyFactory,
)
from broker_reports_gate1.pdf_visual_topology import (  # noqa: E402
    PdfVisualTopologyConfig,
    PdfVisualTopologyError,
    PdfVisualTopologyFactory,
)


PREREGISTRATION_SAFE_SCHEMA = (
    "broker_reports_pdf_structural_holdout_preregistration_safe_v1"
)
PREFLIGHT_SAFE_SCHEMA = (
    "broker_reports_pdf_structural_holdout_preflight_terminal_safe_v1"
)
TERMINAL_SAFE_SCHEMA = "broker_reports_pdf_structural_holdout_terminal_safe_v1"
RUN_CLAIM_SCHEMA = "broker_reports_pdf_structural_holdout_run_claim_private_v1"
RUN_CLAIM_SCHEMA_V2 = "broker_reports_pdf_structural_holdout_run_claim_private_v2"
ATTEMPTS = (1, 2)
FRESH_CORPUS_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout"]["sha256"]
)
FRESH_CORPUS_V2_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v2"]["sha256"]
)
FRESH_CORPUS_V3_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v3"]["sha256"]
)
FRESH_CORPUS_V4_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v4"]["sha256"]
)
FRESH_CORPUS_V5_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v5"]["sha256"]
)
EXPOSED_DEVELOPMENT_CORPUS_SHA256 = frozenset(
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["development_regression"][
        "sha256"
    ]
)
PARSER_ONLY_HOLDOUT_CLASSES = frozenset(
    {
        "fresh_holdout_v2",
        "fresh_holdout_v3",
        "fresh_holdout_v4",
        "fresh_holdout_v5",
    }
)
FRESH_HOLDOUT_CLASSES = frozenset(
    {"fresh_holdout", *PARSER_ONLY_HOLDOUT_CLASSES}
)
PRIOR_EXPERIMENT_PREFIXES = (
    "broker_reports_pdf",
    "broker_reports_direct_pdf",
)
QUALIFICATION_KEYS = frozenset(
    {
        "status",
        "provider_profile",
        "provider_profile_revision",
        "requested_model_id",
        "resolved_model_id",
        "exact_model_match",
        "image_input_supported",
        "structured_output_supported",
        "maximum_output_tokens",
        "maximum_input_tokens",
        "http_status",
        "response_hash",
        "native_provider_transport",
        "credentials_from_openwebui_connection",
        "hidden_retry",
        "provider_failover",
    }
)
COUNT_TOKENS_KEYS = frozenset(
    {
        "total_tokens",
        "prompt_tokens_details",
        "http_status",
        "request_hash",
        "response_hash",
        "canonical_schema_hash",
        "adapted_schema_hash",
        "schema_transform_count",
        "model_requested",
        "transport_identity",
        "within_hard_guard",
    }
)
PROVIDER_ATTEMPT_KEYS = frozenset(
    {
        "task_id",
        "attempt_id",
        "attempt_number",
        "attempt_lineage",
        "provider",
        "provider_profile",
        "provider_profile_revision",
        "model_requested",
        "model_resolved",
        "adapter_identity",
        "transport_identity",
        "request_hash",
        "crop_sha256",
        "model_view_hash",
        "canonical_schema_hash",
        "adapted_schema_hash",
        "schema_transform_count",
        "started_at",
        "ended_at",
        "duration_ms",
        "http_status",
        "provider_response_id",
        "usage",
        "finish_reason",
        "thinking_level",
        "parse_result",
        "terminal_failure_class",
        "hidden_retry",
        "provider_failover",
    }
)
PROVIDER_RESULT_KEYS = frozenset(
    {
        "attempt",
        "json_output",
        "text",
        "raw_private_response",
        "response_bytes",
        "response_hash",
        "visible_output_bytes",
        "visible_output_hash",
    }
)
SAFE_CODE_PREFIXES = (
    "pdf_structural_holdout_",
    "pdf_structural_repair_",
    "pdf_structural_window_",
    "pdf_visual_topology_",
    "pdf_parser_geometry_",
    "pdf_topology_assembly_",
    "pdf_dual_oracle_",
    "pdf_grid_",
    "pdf_hybrid_",
)
SAFE_LITERAL_CODES = frozenset(
    {
        "unknown_failure",
        "provider_non_terminal",
        "contract_or_terminal_failure",
        "timeout_or_transport",
        "provider_invalid_json",
        "provider_http",
        "provider_server",
        "provider_authentication",
        "rate_limit",
        "timeout",
        "response_budget",
        "context_budget",
        "parse_failure",
        "resolved_model_mismatch",
        "request_validation",
        "attempt_policy",
    }
)
PROVIDER_FAILURE_CLASSES = frozenset(
    {
        "provider_non_terminal",
        "timeout_or_transport",
        "provider_invalid_json",
        "provider_http",
        "provider_server",
        "provider_authentication",
        "rate_limit",
        "timeout",
        "response_budget",
        "context_budget",
        "parse_failure",
        "resolved_model_mismatch",
        "request_validation",
        "attempt_policy",
    }
)
FORBIDDEN_SAFE_KEYS = frozenset(
    {
        "accepted_binding",
        "assembly",
        "assemblies",
        "candidate_id",
        "candidate_ids",
        "crop_identity",
        "document_id",
        "document_ref",
        "exact_source_span",
        "hypothesis_set",
        "materialization",
        "model_facing",
        "neutral_atom_to_candidate_id",
        "observation_id",
        "package_id",
        "parser_geometry_observation",
        "parser_observation",
        "private_candidate_dictionary",
        "private_png_base64",
        "raw_private_response",
        "repo_relative_path",
        "source_value_refs",
        "table_ref",
        "topology_response",
        "word_refs",
    }
)


class HoldoutError(RuntimeError):
    pass


class HoldoutBoundaryError(HoldoutError):
    pass


class HoldoutTargetPreflightError(HoldoutError):
    def __init__(self, *, target_id: str, code: str) -> None:
        self.target_id = target_id
        self.code = code
        super().__init__(f"{code}:{target_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare", description="Freeze corpus selection and solver sources."
    )
    prepare_parser.add_argument("--pdf", action="append", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument(
        "--execution-class",
        required=True,
        choices=sorted(PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES),
    )

    run_parser = subparsers.add_parser(
        "run", description="Run the frozen two-attempt dual-oracle evaluation."
    )
    run_parser.add_argument("--preregistration-private", required=True)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))

    args = parser.parse_args()
    if args.command == "prepare":
        return prepare_holdout(
            pdf_paths=[Path(item) for item in args.pdf],
            output_dir=Path(args.output_dir),
            execution_class=str(args.execution_class),
        )
    if args.command == "run":
        return run_holdout(
            preregistration_path=Path(args.preregistration_private),
            output_dir=Path(args.output_dir),
            env_path=Path(args.env_file),
        )
    raise HoldoutError("pdf_structural_holdout_command_invalid")


def prepare_holdout(
    *,
    pdf_paths: list[Path],
    output_dir: Path,
    execution_class: str,
) -> int:
    output_dir = output_dir.resolve()
    _require_absent(output_dir, "pdf_structural_holdout_preregistration_output_exists")
    if execution_class not in PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_execution_class_invalid"
        )
    contracts = PdfStructuralRepairHoldoutContractFactory().create()
    source_freeze = _source_freeze()
    corpus = _collect_corpus(pdf_paths, execution_class=execution_class)
    excluded_repo_relative_root = _stage2_output_relative(output_dir)
    freshness_scan, prior_hits = _scan_prior_experiments(
        hashes=[item["pdf_sha256"] for item in corpus],
        excluded_repo_relative_root=excluded_repo_relative_root,
        excluded_input_inventory=[
            {
                "repo_relative_path": item["repo_relative_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["pdf_sha256"],
            }
            for item in corpus
        ],
    )
    if execution_class in FRESH_HOLDOUT_CLASSES and any(
        prior_hits.values()
    ):
        raise HoldoutBoundaryError("pdf_structural_holdout_prior_experiment_match")

    documents = []
    for index, item in enumerate(corpus, start=1):
        document = {
            "document_id": f"holdout_doc_{index:03d}",
            "repo_relative_path": item["repo_relative_path"],
            "pdf_sha256": item["pdf_sha256"],
            "size_bytes": item["size_bytes"],
            "page_count": 0,
            "table_candidate_count": 0,
            "selection_status": "not_evaluated",
            "prior_experiment_matches": prior_hits[item["pdf_sha256"]],
        }
        if execution_class in PARSER_ONLY_HOLDOUT_CLASSES:
            document["eligible_table_candidate_count"] = 0
        documents.append(document)
    selected_targets: list[dict[str, Any]] = []
    for index, (corpus_item, document) in enumerate(
        zip(corpus, documents, strict=True)
    ):
        projection, document_ref = _normalize_pdf(
            pdf_bytes=corpus_item["pdf_bytes"],
            pdf_sha256=corpus_item["pdf_sha256"],
        )
        candidates = _ordered_table_candidates(projection)
        eligibility_by_ref: dict[str, dict[str, Any]] = {}
        candidates_for_selection = candidates
        if execution_class in PARSER_ONLY_HOLDOUT_CLASSES:
            eligibility_by_ref = _candidate_eligibility_observations(
                projection=projection,
                candidates=candidates,
                contracts=contracts,
                execution_class=execution_class,
            )
            candidates_for_selection = [
                candidate
                for candidate in candidates
                if _object(
                    eligibility_by_ref.get(
                        str(candidate.get("table_candidate_ref") or "")
                    )
                ).get("eligible")
                is True
            ]
        document["page_count"] = _pdf_page_count(corpus_item["pdf_bytes"])
        document["table_candidate_count"] = len(candidates)
        if execution_class in PARSER_ONLY_HOLDOUT_CLASSES:
            document["eligible_table_candidate_count"] = len(
                candidates_for_selection
            )
        selected_candidates = _select_candidates_for_execution_class(
            candidates=candidates_for_selection,
            eligibility_by_ref=eligibility_by_ref,
            execution_class=execution_class,
            table_limit=contracts.config.table_limit,
        )
        if len(selected_candidates) != contracts.config.table_limit:
            document["selection_status"] = (
                "not_selected_insufficient_candidates"
            )
            continue
        document["selection_status"] = "selected"
        target_scopes = _target_scopes(
            document=document,
            projection=projection,
            selected_candidates=selected_candidates,
            eligibility_by_ref=eligibility_by_ref,
        )
        try:
            selected_targets = _build_targets(
                document=document,
                projection=projection,
                selected_candidates=selected_candidates,
                pdf_bytes=corpus_item["pdf_bytes"],
                pdf_sha256=corpus_item["pdf_sha256"],
                document_ref=document_ref,
                dpi=contracts.config.dpi,
                eligibility_by_ref=eligibility_by_ref,
            )
        except HoldoutTargetPreflightError as exc:
            _verify_source_freeze(source_freeze)
            preflight = contracts.build_preflight_terminal(
                documents=documents,
                target_scopes=target_scopes,
                frozen_source=source_freeze,
                freshness_scan=freshness_scan,
                execution_class=execution_class,
                failed_target_id=exc.target_id,
                failure_code=_safe_code(exc.code)
                or "pdf_structural_holdout_preflight_failed",
            )
            output_dir.mkdir(parents=True, exist_ok=False)
            private_dir = output_dir / "private"
            private_dir.mkdir(parents=True, exist_ok=False)
            preflight_path = private_dir / "holdout.preflight.private.json"
            _write_json(preflight_path, preflight)
            readback, _ = _load_json(preflight_path, dict, "preflight")
            preflight_errors = contracts.validate_preflight_terminal(readback)
            if preflight_errors or readback != preflight:
                raise HoldoutBoundaryError(
                    preflight_errors[0]
                    if preflight_errors
                    else "pdf_structural_holdout_preflight_readback"
                )
            _verify_freshness_scan(
                freshness_scan, runtime_output_dir=output_dir
            )
            safe = _safe_preflight(preflight)
            _assert_safe_payload(safe)
            _write_json(output_dir / "holdout.preflight.safe.json", safe)
            print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
            return 2
        if len(selected_targets) != contracts.config.table_limit:
            raise HoldoutError("pdf_structural_holdout_target_build_incomplete")
        for later in documents[index + 1 :]:
            later["page_count"] = 0
            later["table_candidate_count"] = 0
            if execution_class in PARSER_ONLY_HOLDOUT_CLASSES:
                later["eligible_table_candidate_count"] = 0
            later["selection_status"] = "not_evaluated"
        break
    if not selected_targets:
        raise HoldoutError("pdf_structural_holdout_no_eligible_document")

    _verify_source_freeze(source_freeze)
    _verify_freshness_scan(freshness_scan, runtime_output_dir=output_dir)
    preregistration = contracts.build_preregistration(
        documents=documents,
        targets=selected_targets,
        frozen_source=source_freeze,
        freshness_scan=freshness_scan,
        execution_class=execution_class,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    private_dir = output_dir / "private"
    crop_dir = private_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=False)
    prereg_path = private_dir / "holdout.preregistration.private.json"
    _write_json(prereg_path, preregistration)
    for target in selected_targets:
        png_bytes = _decode_target_png(target)
        (crop_dir / f"{target['target_id']}.png").write_bytes(png_bytes)

    readback, _ = _load_json(prereg_path, dict, "preregistration")
    errors = contracts.validate_preregistration(readback)
    if errors or readback != preregistration:
        raise HoldoutBoundaryError(
            errors[0] if errors else "pdf_structural_holdout_preregistration_readback"
        )
    _verify_source_freeze(source_freeze)
    _verify_freshness_scan(freshness_scan, runtime_output_dir=output_dir)
    safe = _safe_preregistration(preregistration)
    _assert_safe_payload(safe)
    _write_json(output_dir / "holdout.preregistration.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _collect_corpus(
    pdf_paths: list[Path], *, execution_class: str
) -> list[dict[str, Any]]:
    policy = PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES.get(execution_class, {})
    expected_hashes = set(policy.get("sha256") or set())
    expected_count = int(policy.get("document_count") or 0)
    if len(pdf_paths) != expected_count:
        raise HoldoutBoundaryError("pdf_structural_holdout_exact_corpus_size_required")
    result: list[dict[str, Any]] = []
    resolved_paths: set[Path] = set()
    for supplied in pdf_paths:
        path = supplied.resolve()
        try:
            relative = path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_pdf_outside_repository"
            ) from exc
        if path in resolved_paths or not path.is_file():
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_pdf_missing_or_duplicate"
            )
        resolved_paths.add(path)
        pdf_bytes = path.read_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        result.append(
            {
                "repo_relative_path": relative.as_posix(),
                "pdf_sha256": pdf_sha256,
                "size_bytes": len(pdf_bytes),
                "pdf_bytes": pdf_bytes,
            }
        )
    hashes = {item["pdf_sha256"] for item in result}
    if hashes != expected_hashes:
        raise HoldoutBoundaryError("pdf_structural_holdout_corpus_hash_set_invalid")
    return sorted(result, key=lambda item: item["pdf_sha256"])


def _pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        page_count = len(PdfReader(io.BytesIO(pdf_bytes), strict=False).pages)
    except Exception as exc:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_page_count_unavailable"
        ) from exc
    if page_count < 1:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_page_count_unavailable"
        )
    return page_count


def _scan_prior_experiments(
    *,
    hashes: list[str],
    excluded_repo_relative_root: str,
    excluded_input_inventory: list[dict[str, Any]] | None = None,
    runtime_excluded_roots: set[Path] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    root = LOCAL_STAGE2.resolve()
    if not root.is_dir():
        raise HoldoutBoundaryError("pdf_structural_holdout_prior_root_missing")
    excluded_paths = {
        (REPO_ROOT / excluded_repo_relative_root).resolve(),
        *(path.resolve() for path in (runtime_excluded_roots or set())),
    }
    raw_frozen_inputs: Any = (
        excluded_input_inventory
        if excluded_input_inventory is not None
        else []
    )
    if (
        not isinstance(raw_frozen_inputs, list)
        or len(_dicts(raw_frozen_inputs)) != len(raw_frozen_inputs)
    ):
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_input_exclusion_inventory_invalid"
        )
    frozen_inputs = sorted(
        _dicts(raw_frozen_inputs),
        key=lambda item: str(item.get("repo_relative_path") or ""),
    )
    excluded_input_paths: set[Path] = set()
    for item in frozen_inputs:
        path = (REPO_ROOT / str(item.get("repo_relative_path") or "")).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_input_exclusion_path_invalid"
            ) from exc
        try:
            valid = bool(
                path not in excluded_input_paths
                and path.is_file()
                and path.stat().st_size == item.get("size_bytes")
                and _sha256_file(path) == item.get("sha256")
            )
        except OSError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_input_exclusion_scan_failed"
            ) from exc
        if not valid:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_input_exclusion_inventory_invalid"
            )
        excluded_input_paths.add(path)
    roots: list[Path] = []
    for candidate in root.iterdir():
        if (
            not candidate.is_dir()
            or not candidate.name.startswith(PRIOR_EXPERIMENT_PREFIXES)
        ):
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
            resolved.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_prior_root_escape"
            ) from exc
        if resolved not in excluded_paths:
            roots.append(resolved)
    roots.sort()
    matches: dict[str, set[str]] = {item: set() for item in hashes}
    needles = {
        item: (item.encode("ascii"), item[:12].encode("ascii")) for item in hashes
    }
    inventory: list[dict[str, Any]] = []
    for experiment_root in roots:
        root_matched: set[str] = set()
        for path in sorted(item for item in experiment_root.rglob("*") if item.is_file()):
            try:
                resolved_path = path.resolve()
                if (
                    resolved_path in excluded_input_paths
                    or any(
                        _path_is_within(resolved_path, excluded_path)
                        for excluded_path in excluded_paths
                    )
                ):
                    continue
                file_sha256, size, content_matches = _scan_prior_file(
                    path, needles=needles
                )
                relative = path.resolve().relative_to(REPO_ROOT).as_posix()
                inventory.append(
                    {
                        "repo_relative_path": relative,
                        "size_bytes": size,
                        "sha256": file_sha256,
                    }
                )
                if path.suffix.lower() == ".pdf" and file_sha256 in matches:
                    root_matched.add(file_sha256)
                root_matched.update(content_matches)
            except (OSError, ValueError) as exc:
                raise HoldoutBoundaryError(
                    "pdf_structural_holdout_prior_scan_failed"
                ) from exc
        for digest in root_matched:
            matches[digest].add(experiment_root.name)
    experiment_roots = [
        path.relative_to(REPO_ROOT).as_posix() for path in roots
    ]
    inventory.sort(key=lambda item: item["repo_relative_path"])
    freshness_scan = {
        "schema_version": PDF_STRUCTURAL_HOLDOUT_FRESHNESS_SCHEMA,
        "root_repo_relative_path": LOCAL_STAGE2.relative_to(REPO_ROOT).as_posix(),
        "excluded_repo_relative_root": excluded_repo_relative_root,
        "excluded_input_inventory": copy.deepcopy(frozen_inputs),
        "experiment_roots": experiment_roots,
        "inventory": inventory,
        "inventory_checksum": sha256_json(
            {
                "excluded_input_inventory": frozen_inputs,
                "experiment_roots": experiment_roots,
                "inventory": inventory,
            }
        ),
    }
    return freshness_scan, {
        digest: len(values) for digest, values in matches.items()
    }


def _scan_prior_file(
    path: Path, *, needles: dict[str, tuple[bytes, bytes]]
) -> tuple[str, int, set[str]]:
    hasher = hashlib.sha256()
    size = 0
    tail = b""
    matched: set[str] = set()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
            size += len(chunk)
            probe = (tail + chunk).lower()
            for digest, (full, prefix) in needles.items():
                if digest not in matched and (full in probe or prefix in probe):
                    matched.add(digest)
            tail = probe[-63:]
    return hasher.hexdigest(), size, matched


def _stage2_output_relative(output_dir: Path) -> str:
    try:
        relative = output_dir.resolve().relative_to(REPO_ROOT).as_posix()
        output_dir.resolve().relative_to(LOCAL_STAGE2.resolve())
    except ValueError as exc:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_output_must_be_under_local_stage2"
        ) from exc
    if output_dir.resolve() == LOCAL_STAGE2.resolve():
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_output_must_be_stage2_child"
        )
    return relative


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _verify_freshness_scan(
    frozen: dict[str, Any], *, runtime_output_dir: Path | None = None
) -> None:
    excluded = str(frozen.get("excluded_repo_relative_root") or "")
    current, _ = _scan_prior_experiments(
        hashes=[],
        excluded_repo_relative_root=excluded,
        excluded_input_inventory=_dicts(
            frozen.get("excluded_input_inventory")
        ),
        runtime_excluded_roots=(
            {runtime_output_dir.resolve()} if runtime_output_dir is not None else set()
        ),
    )
    if current != frozen:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_freshness_inventory_mismatch"
        )


def _normalize_pdf(
    *, pdf_bytes: bytes, pdf_sha256: str
) -> tuple[dict[str, Any], str]:
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref=f"controlled-private-holdout:{pdf_sha256}",
                filename="controlled-holdout.pdf",
                content=pdf_bytes,
                mime_type=mimetypes.guess_type("controlled-holdout.pdf")[0]
                or "application/pdf",
                source_kind="local_private_holdout",
            )
        ],
        entrypoint="local_pdf_structural_repair_holdout",
        trigger_type="controlled_private_fresh_holdout",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": False,
            "pdf_hybrid_shadow_enabled": False,
            "pdf_hybrid_reliability_shadow_enabled": False,
        },
    )
    payloads = _dicts(
        normalized.package.get("private_normalized_source_payloads")
    )
    if len(payloads) != 1:
        raise HoldoutError("pdf_structural_holdout_normalized_source_scope_invalid")
    projection = payloads[0].get("pdf_text_layer_projection")
    if not isinstance(projection, dict):
        raise HoldoutError("pdf_structural_holdout_projection_missing")
    document_ref = _required_string(
        payloads[0].get("document_ref"), "document_ref"
    )
    return projection, document_ref


def _ordered_table_candidates(
    projection: dict[str, Any]
) -> list[dict[str, Any]]:
    page_numbers = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in _dicts(projection.get("page_inventory"))
    }
    candidates: list[dict[str, Any]] = []
    identities: set[tuple[int, int]] = set()
    for candidate in _dicts(projection.get("table_candidate_inventory")):
        page_number = page_numbers.get(str(candidate.get("page_ref") or ""), 0)
        parser_ordinal = int(candidate.get("parser_ordinal") or 0)
        identity = (page_number, parser_ordinal)
        if page_number < 1 or parser_ordinal < 1 or identity in identities:
            raise HoldoutError("pdf_structural_holdout_candidate_identity_invalid")
        identities.add(identity)
        candidates.append(candidate)
    return sorted(
        candidates,
        key=lambda item: (
            page_numbers[str(item.get("page_ref") or "")],
            int(item.get("parser_ordinal") or 0),
        ),
    )


def _candidate_eligibility_observations(
    *,
    projection: dict[str, Any],
    candidates: list[dict[str, Any]],
    contracts: Any,
    execution_class: str,
) -> dict[str, dict[str, Any]]:
    pages = {
        str(item.get("page_ref") or ""): item
        for item in _dicts(projection.get("page_inventory"))
    }
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in _dicts(projection.get("bbox_inventory"))
    }
    result: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        table_ref = _required_string(
            candidate.get("table_candidate_ref"), "eligibility:table_ref"
        )
        page = _object(pages.get(str(candidate.get("page_ref") or "")))
        bbox = bboxes.get(str(candidate.get("bbox_ref") or ""))
        if not page or not _valid_bbox(bbox) or table_ref in result:
            raise HoldoutError(
                "pdf_structural_holdout_candidate_eligibility_input_invalid"
            )
        result[table_ref] = contracts.build_candidate_eligibility_observation(
            candidate=candidate,
            page=page,
            candidate_bbox=list(bbox),
            execution_class=execution_class,
        )
    return result


def _select_candidates_for_execution_class(
    *,
    candidates: list[dict[str, Any]],
    eligibility_by_ref: dict[str, dict[str, Any]],
    execution_class: str,
    table_limit: int,
) -> list[dict[str, Any]]:
    if execution_class != "fresh_holdout_v5":
        return candidates[:table_limit]
    if table_limit != 3:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_v5_table_limit_invalid"
        )

    def observation(candidate: dict[str, Any]) -> dict[str, Any]:
        return _object(
            eligibility_by_ref.get(
                str(candidate.get("table_candidate_ref") or "")
            )
        )

    aligned = next(
        (
            item
            for item in candidates
            if observation(item).get("table_strategy_ref")
            == "aligned_text_v0"
        ),
        None,
    )
    if aligned is None:
        return []
    remaining = [item for item in candidates if item is not aligned]
    wide = next(
        (
            item
            for item in remaining
            if int(observation(item).get("columns_total") or 0) >= 12
        ),
        None,
    )
    if wide is None and remaining:
        highest_columns = max(
            int(observation(item).get("columns_total") or 0)
            for item in remaining
        )
        wide = next(
            item
            for item in remaining
            if int(observation(item).get("columns_total") or 0)
            == highest_columns
        )
    if wide is None:
        return []
    remaining = [item for item in remaining if item is not wide]
    ordinary = next(
        (
            item
            for item in remaining
            if observation(item).get("table_strategy_ref")
            == "ruled_lines_v0"
        ),
        remaining[0] if remaining else None,
    )
    if ordinary is None:
        return []
    selected = [aligned, wide, ordinary]
    selected_strategies = {
        str(observation(item).get("table_strategy_ref") or "")
        for item in selected
    }
    if not {"aligned_text_v0", "ruled_lines_v0"}.issubset(
        selected_strategies
    ):
        return []
    selected_refs = {
        str(item.get("table_candidate_ref") or "") for item in selected
    }
    return [
        item
        for item in candidates
        if str(item.get("table_candidate_ref") or "") in selected_refs
    ]


def _target_scopes(
    *,
    document: dict[str, Any],
    projection: dict[str, Any],
    selected_candidates: list[dict[str, Any]],
    eligibility_by_ref: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    pages = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in _dicts(projection.get("page_inventory"))
    }
    scopes: list[dict[str, Any]] = []
    for index, candidate in enumerate(selected_candidates, start=1):
        scope = {
            "target_id": f"holdout_{index:03d}",
            "document_id": document["document_id"],
            "page_number": pages.get(str(candidate.get("page_ref") or ""), 0),
            "parser_ordinal": int(candidate.get("parser_ordinal") or 0),
        }
        if eligibility_by_ref:
            table_ref = str(candidate.get("table_candidate_ref") or "")
            eligibility = eligibility_by_ref.get(table_ref)
            if not isinstance(eligibility, dict):
                raise HoldoutError(
                    "pdf_structural_holdout_target_eligibility_missing"
                )
            scope["eligibility_observation"] = copy.deepcopy(eligibility)
        scopes.append(scope)
    return scopes


def _build_targets(
    *,
    document: dict[str, Any],
    projection: dict[str, Any],
    selected_candidates: list[dict[str, Any]],
    pdf_bytes: bytes,
    pdf_sha256: str,
    document_ref: str,
    dpi: int,
    eligibility_by_ref: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    pages = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in _dicts(projection.get("page_inventory"))
    }
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in _dicts(projection.get("bbox_inventory"))
    }
    contracts = PdfDualOracleContractFactory().create()
    holdout_contracts = PdfStructuralRepairHoldoutContractFactory().create()
    parser_geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    ledger_visual = PdfVisualTopologyFactory(
        PdfVisualTopologyConfig(
            maximum_model_json_bytes=512 * 1024,
            maximum_static_input_tokens=150_000,
        )
    ).create()
    windowing = PdfStructuralRowWindowFactory().create()
    raster = PdfTableRasterFactory(
        PdfTableRasterConfig(padding_points=0.0)
    ).create()
    targets: list[dict[str, Any]] = []
    for index, candidate in enumerate(selected_candidates, start=1):
        target_id = f"holdout_{index:03d}"
        page_ref = _required_string(
            candidate.get("page_ref"), f"{target_id}:page_ref"
        )
        page_number = pages.get(page_ref, 0)
        parser_ordinal = int(candidate.get("parser_ordinal") or 0)
        table_ref = _required_string(
            candidate.get("table_candidate_ref"), f"{target_id}:table_ref"
        )
        table_bbox = bboxes.get(str(candidate.get("bbox_ref") or ""))
        if page_number < 1 or parser_ordinal < 1 or not _valid_bbox(table_bbox):
            raise HoldoutError(
                f"pdf_structural_holdout_target_geometry_invalid:{target_id}"
            )
        parser_observation = contracts.build_parser_observation_from_word_atoms(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=list(table_bbox),
            pdf_text_layer_projection=projection,
        )
        geometry_observation = parser_geometry.build_observation(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=list(table_bbox),
            pdf_text_layer_projection=projection,
        )
        try:
            execution_mode = windowing.execution_mode(parser_observation)
            window_plan = (
                windowing.plan(parser_observation)
                if execution_mode == "vertical_atom_windows"
                else None
            )
        except PdfStructuralRowWindowError as exc:
            raise HoldoutTargetPreflightError(
                target_id=target_id,
                code=str(getattr(exc, "code", str(exc))),
            ) from exc
        rendered = raster.render(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=list(table_bbox),
            dpi=dpi,
        )
        manifest = rendered.get("manifest")
        if not isinstance(manifest, dict):
            raise HoldoutError(
                f"pdf_structural_holdout_crop_manifest_missing:{target_id}"
            )
        private_png_base64 = str(rendered.get("private_png_base64") or "")
        try:
            png_bytes = base64.b64decode(private_png_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise HoldoutError(
                f"pdf_structural_holdout_crop_base64_invalid:{target_id}"
            ) from exc
        if (
            hashlib.sha256(png_bytes).hexdigest() != manifest.get("png_sha256")
            or len(png_bytes) > 8 * 1024 * 1024
        ):
            raise HoldoutError(
                f"pdf_structural_holdout_crop_hash_or_budget_invalid:{target_id}"
            )
        try:
            visual_package = (
                ledger_visual.build_ledger_package(
                    parser_observation=parser_observation,
                    crop_manifest=manifest,
                )
                if execution_mode == "vertical_atom_windows"
                else visual.build_package(
                    parser_observation=parser_observation,
                    crop_manifest=manifest,
                )
            )
        except PdfVisualTopologyError as exc:
            raise HoldoutTargetPreflightError(
                target_id=target_id,
                code=str(getattr(exc, "code", str(exc))),
            ) from exc
        window_inputs: list[dict[str, Any]] = []
        if window_plan is not None:
            for window in _dicts(window_plan.get("windows")):
                window_rendered = raster.render(
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=pdf_sha256,
                    document_ref=document_ref,
                    page_number=page_number,
                    table_ref=table_ref,
                    table_bbox=copy.deepcopy(window["crop_bbox"]),
                    dpi=dpi,
                )
                try:
                    window_png_bytes = base64.b64decode(
                        str(window_rendered.get("private_png_base64") or ""),
                        validate=True,
                    )
                except (TypeError, ValueError) as exc:
                    raise HoldoutTargetPreflightError(
                        target_id=target_id,
                        code="pdf_structural_holdout_window_crop_invalid",
                    ) from exc
                window_package = visual.build_window_package(
                    parser_observation=parser_observation,
                    full_package=visual_package,
                    window_plan=window_plan,
                    window=window,
                    crop_manifest=_object(window_rendered.get("manifest")),
                )
                window_inputs.append(
                    {
                        "window_id": window["window_id"],
                        "window_package": window_package,
                        "png_bytes": window_png_bytes,
                    }
                )
        execution_contract = holdout_contracts.build_target_execution_contract(
            parser_observation=parser_observation,
            visual_package=visual_package,
            window_plan=window_plan,
            window_inputs=window_inputs,
        )
        target = {
            "target_id": target_id,
            "document_id": document["document_id"],
            "page_number": page_number,
            "parser_ordinal": parser_ordinal,
            "parser_observation": parser_observation,
            "parser_geometry_observation": geometry_observation,
            "visual_package": visual_package,
            "private_png_base64": private_png_base64,
            "execution_contract": execution_contract,
        }
        if eligibility_by_ref:
            eligibility = eligibility_by_ref.get(table_ref)
            if not isinstance(eligibility, dict):
                raise HoldoutError(
                    f"pdf_structural_holdout_target_eligibility_missing:{target_id}"
                )
            target["eligibility_observation"] = copy.deepcopy(eligibility)
        _validate_target_state(target)
        targets.append(target)
    return targets


def run_holdout(
    *, preregistration_path: Path, output_dir: Path, env_path: Path
) -> int:
    preregistration_path = preregistration_path.resolve()
    output_dir = output_dir.resolve()
    _require_absent(output_dir, "pdf_structural_holdout_run_output_exists")
    preregistration, preregistration_file_sha256 = _load_json(
        preregistration_path, dict, "preregistration"
    )
    holdout_contract = PdfStructuralRepairHoldoutContractFactory().create()
    errors = holdout_contract.validate_preregistration(preregistration)
    if errors:
        raise HoldoutBoundaryError(errors[0])
    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )

    targets = {
        str(item.get("target_id") or ""): copy.deepcopy(item)
        for item in _dicts(preregistration.get("targets"))
    }
    for target in targets.values():
        _validate_target_state(target)
    execution_freeze = _target_execution_freeze(targets)

    output_dir.mkdir(parents=True, exist_ok=False)
    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=False)
    claim = {
        "schema_version": (
            RUN_CLAIM_SCHEMA_V2 if execution_freeze else RUN_CLAIM_SCHEMA
        ),
        "holdout_id": preregistration["holdout_id"],
        "execution_class": preregistration["execution_class"],
        "certification_eligible": preregistration["certification_eligible"],
        "corpus_policy": preregistration["corpus_policy"],
        "preregistration_file_sha256": preregistration_file_sha256,
        "source_inventory_checksum": preregistration["frozen_source"][
            "inventory_checksum"
        ],
        "provider_calls_started": False,
        **(
            {
                "target_execution_freeze": execution_freeze,
                "execution_freeze_checksum": sha256_json(execution_freeze),
            }
            if execution_freeze
            else {}
        ),
    }
    claim["claim_checksum"] = sha256_json(claim)
    claim_path = private_dir / "run.claim.private.json"
    _write_json(claim_path, claim)
    readback_claim, _ = _load_json(claim_path, dict, "run_claim")
    if readback_claim != claim:
        raise HoldoutBoundaryError("pdf_structural_holdout_run_claim_readback")

    parser_contracts = PdfDualOracleContractFactory().create()
    parser_geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    assembler = PdfTopologyAssemblyFactory(
        visual_topology=visual,
        parser_geometry=parser_geometry,
    ).create()
    solver = PdfDualOracleConsensusFactory().create()
    materializer = PdfHybridMaterializationFactory().create()
    for target in targets.values():
        _validate_target_state(
            target,
            parser_contracts=parser_contracts,
            parser_geometry=parser_geometry,
            visual=visual,
        )

    provider_config = PdfGridProviderConfig(
        provider_profile="google_gemini",
        model_id="models/gemini-3.5-flash",
        maximum_output_tokens=8192,
        maximum_counted_input_tokens=20_000,
        thinking_level="minimal",
    )
    provider_config_hash = sha256_json(asdict(provider_config))
    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )
    request = _openwebui_request(env_path.resolve())
    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )
    provider = PdfGridExperimentProviderFactory(
        provider_config
    ).create_for_openwebui(request)
    claim["provider_calls_started"] = True
    claim["claim_checksum"] = sha256_json(
        {key: value for key, value in claim.items() if key != "claim_checksum"}
    )
    _write_json(claim_path, claim)
    try:
        qualification = provider.qualify()
        _validate_provider_qualification(qualification, provider_config)
    except HoldoutBoundaryError:
        raise
    except (PdfGridProviderError, OSError, TypeError, ValueError) as exc:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_provider_qualification_invalid"
        ) from exc
    structural_runtime = PdfStructuralRepairRuntimeFactory().create(
        provider=provider
    )
    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )

    journal: list[dict[str, Any]] = []
    journal_path = private_dir / "journal.private.json"
    previous_attempt_ids: dict[str, list[str]] = {
        target_id: [] for target_id in sorted(targets)
    }
    window_runtime_results: dict[str, dict[str, Any]] = {}
    for target_id in sorted(targets):
        target = targets[target_id]
        package = _object(target.get("visual_package"))
        execution = _object(target.get("execution_contract"))
        if execution.get("execution_mode") == "vertical_atom_windows":
            window_result = structural_runtime.run_windowed_target(
                target_id=target_id,
                parser_observation=_object(target.get("parser_observation")),
                parser_geometry_observation=_object(
                    target.get("parser_geometry_observation")
                ),
                visual_package=package,
                window_plan=_object(execution.get("window_plan")),
                window_inputs=_thaw_window_inputs(execution),
                provider_qualification=qualification,
            )
            window_runtime_results[target_id] = window_result
            journal.extend(_holdout_window_journal(window_result))
            _write_json(journal_path, journal)
            continue
        png_bytes = _decode_target_png(target)
        evidence_revision = sha256_json(
            {
                "package_hash": package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(package.get("model_facing")),
                "output_schema_hash": sha256_json(package.get("output_schema")),
                "holdout_id": preregistration.get("holdout_id"),
            }
        )
        task_id = "pdfvisualtopotask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "holdout_id": preregistration.get("holdout_id"),
                    "target_id": target_id,
                    "package_hash": package.get("package_hash"),
                    "evidence_revision": evidence_revision,
                    "model_id": provider_config.model_id,
                }
            )
        ).hexdigest()[:24]
        for attempt_number in ATTEMPTS:
            print(
                "["
                + str(preregistration.get("execution_class") or "unknown")
                + f" {target_id} a{attempt_number}]",
                flush=True,
            )
            counted: dict[str, Any] = {}
            provider_result: dict[str, Any] = {}
            provider_attempt: dict[str, Any] = {}
            topology_response: dict[str, Any] | None = None
            assembly: dict[str, Any] | None = None
            failure_code: str | None = None
            failure_class: str | None = None
            generate_call_performed = False
            try:
                if len(previous_attempt_ids[target_id]) != attempt_number - 1:
                    raise HoldoutError(
                        "pdf_structural_holdout_previous_attempt_not_started"
                    )
                _verify_frozen_boundary(
                    preregistration=preregistration,
                    preregistration_path=preregistration_path,
                    preregistration_file_sha256=preregistration_file_sha256,
                    runtime_output_dir=output_dir,
                )
                counted = provider.count_tokens(
                    model_view=package["model_facing"],
                    output_schema=package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=package["crop_identity"]["crop_sha256"],
                )
                _validate_count_tokens(counted, provider_config=provider_config)
                _verify_frozen_boundary(
                    preregistration=preregistration,
                    preregistration_path=preregistration_path,
                    preregistration_file_sha256=preregistration_file_sha256,
                    runtime_output_dir=output_dir,
                )
                provider_result = provider.invoke(
                    task_id=task_id,
                    model_view=package["model_facing"],
                    output_schema=package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=package["crop_identity"]["crop_sha256"],
                    attempt_number=attempt_number,
                    attempt_lineage=list(previous_attempt_ids[target_id]),
                )
                generate_call_performed = bool(
                    _object(provider_result.get("attempt")).get("started_at")
                )
                _verify_frozen_boundary(
                    preregistration=preregistration,
                    preregistration_path=preregistration_path,
                    preregistration_file_sha256=preregistration_file_sha256,
                    runtime_output_dir=output_dir,
                )
                provider_attempt = _object(provider_result.get("attempt"))
                _validate_provider_attempt_result(
                    provider_result=provider_result,
                    provider_attempt=provider_attempt,
                    counted=counted,
                    package=package,
                    provider_config=provider_config,
                    task_id=task_id,
                    attempt_number=attempt_number,
                    attempt_lineage=list(previous_attempt_ids[target_id]),
                )
                previous_attempt_ids[target_id].append(
                    str(provider_attempt["attempt_id"])
                )
                topology_value = provider_result.get("json_output")
                if isinstance(topology_value, dict):
                    topology_response = topology_value
                terminal_failure = provider_attempt.get("terminal_failure_class")
                if (
                    terminal_failure is not None
                    or provider_attempt.get("finish_reason") != "STOP"
                    or provider_attempt.get("hidden_retry") is not False
                    or provider_attempt.get("provider_failover") is not False
                    or provider_attempt.get("model_requested")
                    != provider_config.model_id
                    or provider_attempt.get("model_resolved")
                    != provider_config.model_id
                    or topology_response is None
                ):
                    failure_code = "pdf_structural_holdout_provider_attempt_failed"
                    failure_class = str(
                        terminal_failure or "provider_non_terminal"
                    )
                else:
                    if len(png_bytes) > 8 * 1024 * 1024:
                        raise HoldoutError(
                            "pdf_structural_holdout_provider_accounting_invalid"
                        )
                    assembly = assembler.assemble(
                        parser_observation=target["parser_observation"],
                        parser_geometry_observation=target[
                            "parser_geometry_observation"
                        ],
                        visual_package=package,
                        topology_response=topology_response,
                        attempt_evidence={
                            "attempt_id": str(
                                provider_attempt.get("attempt_id") or ""
                            ),
                            "attempt_number": attempt_number,
                            "evidence_revision": evidence_revision,
                            "provider": "google",
                            "model": provider_config.model_id,
                            "provider_config_hash": provider_config_hash,
                        },
                        hypothesis_id_prefix=(
                            f"fresh_{target_id}_a{attempt_number}"
                        ),
                    )
                    assembly_errors = assembler.validate_result(assembly)
                    if assembly_errors:
                        raise HoldoutError(assembly_errors[0])
            except HoldoutBoundaryError:
                raise
            except (
                PdfGridProviderError,
                PdfVisualTopologyError,
                PdfParserGeometryError,
                PdfTopologyAssemblyError,
                HoldoutError,
                OSError,
            ) as exc:
                if not counted:
                    counted = _budget_count_observation(exc)
                failure_code = str(
                    getattr(exc, "code", str(exc) or type(exc).__name__)
                )
                failure_class = str(
                    getattr(exc, "failure_class", "contract_or_terminal_failure")
                )
                if not provider_attempt:
                    provider_attempt = _object(provider_result.get("attempt"))

            entry = {
                "schema_version": PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA,
                "target_id": target_id,
                "attempt_number": attempt_number,
                "task_id": task_id,
                "job_key": f"{task_id}|a{attempt_number}",
                "evidence_revision": evidence_revision,
                "provider_config_hash": provider_config_hash,
                "count_tokens": counted,
                "provider_attempt": provider_attempt,
                "provider_result": provider_result,
                "topology_response": topology_response,
                "assembly": assembly,
                "failure_code": failure_code,
                "failure_class": failure_class,
                "provider_generate_call_performed": generate_call_performed,
            }
            journal.append(entry)
            _write_json(journal_path, journal)

    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )
    terminal_targets: dict[str, dict[str, Any]] = {}
    for target_id in sorted(targets):
        target = targets[target_id]
        package = _object(target.get("visual_package"))
        execution = _object(target.get("execution_contract"))
        entries = [
            item for item in journal if item.get("target_id") == target_id
        ]
        if target_id in window_runtime_results:
            window_result = window_runtime_results[target_id]
            consensus = window_result.get("consensus_result")
            if not isinstance(consensus, dict):
                consensus = _window_fallback_consensus(
                    target_id=target_id,
                    window_result=window_result,
                )
            terminal_targets[target_id] = {
                "scope": {
                    "target_id": target_id,
                    "document_id": target["document_id"],
                    "page_number": target["page_number"],
                    "parser_ordinal": target["parser_ordinal"],
                },
                "parser_observation": target["parser_observation"],
                "parser_geometry_observation": target[
                    "parser_geometry_observation"
                ],
                "visual_package": package,
                "assemblies": [
                    item["assembly"]
                    for item in entries
                    if isinstance(item.get("assembly"), dict)
                ],
                "hypothesis_set": (
                    copy.deepcopy(window_result.get("hypothesis_set"))
                    if isinstance(window_result.get("hypothesis_set"), dict)
                    else {
                        "windowed_runtime_terminal_status": window_result.get(
                            "runtime_terminal_status"
                        )
                    }
                ),
                "repeatability": (
                    copy.deepcopy(window_result.get("repeatability"))
                    if isinstance(window_result.get("repeatability"), dict)
                    else {"passed": False}
                ),
                "consensus_result": copy.deepcopy(consensus),
                "accepted_binding": copy.deepcopy(
                    window_result.get("accepted_binding")
                ),
                "materialization": copy.deepcopy(
                    window_result.get("materialization")
                ),
                "execution_contract": copy.deepcopy(execution),
                "window_stitches": copy.deepcopy(
                    window_result.get("window_stitches") or []
                ),
                "window_runtime_result_checksum": window_result.get(
                    "result_checksum"
                ),
            }
            if preregistration.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES:
                terminal_targets[target_id]["eligibility_observation"] = (
                    copy.deepcopy(target.get("eligibility_observation"))
                )
            continue
        assemblies = [
            item["assembly"]
            for item in entries
            if isinstance(item.get("assembly"), dict)
        ]
        binding_inputs = [
            hypothesis
            for assembly in assemblies
            for hypothesis in _dicts(assembly.get("binding_hypotheses"))
        ]
        rejected = [
            evidence
            for assembly in assemblies
            for evidence in _dicts(assembly.get("rejected_evidence"))
        ]
        for entry in entries:
            if entry.get("failure_code"):
                rejected.append(
                    {
                        "evidence_id": "failed_"
                        + hashlib.sha256(
                            str(entry.get("job_key") or "").encode("utf-8")
                        ).hexdigest()[:24],
                        "reason_codes": [
                            _safe_code(entry.get("failure_code"))
                            or "provider_attempt_failed"
                        ],
                    }
                )
        successful_entries = [
            item for item in entries if isinstance(item.get("assembly"), dict)
        ]
        complete = bool(
            len(successful_entries) == 2
            and all(
                _object(item.get("topology_response")).get(
                    "alternatives_complete"
                )
                is True
                for item in successful_entries
            )
        )
        exact_accounting = bool(
            len(successful_entries) == 2
            and all(
                _nonnegative_int(
                    _object(item.get("count_tokens")).get("total_tokens")
                )
                and _nonnegative_int(
                    _object(_object(item.get("provider_attempt")).get("usage")).get(
                        "input_tokens"
                    )
                )
                and _nonnegative_int(
                    _object(_object(item.get("provider_attempt")).get("usage")).get(
                        "output_tokens"
                    )
                )
                for item in successful_entries
            )
        )
        candidate_ownership = bool(
            len(assemblies) == 2
            and all(
                _object(assembly.get("source_accounting")).get(
                    "all_bound_alternatives_exactly_once"
                )
                is True
                for assembly in assemblies
            )
        )
        output_tokens = [
            int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "output_tokens"
                )
                or 0
            )
            for item in successful_entries
        ]
        model_context = {
            "provider": "google",
            "model": provider_config.model_id,
            "configuration_hash": provider_config_hash,
            "bounded_row_windows": True,
            "provider_calls_replayed": 0,
            "new_provider_calls": sum(
                item.get("provider_generate_call_performed") is True
                for item in entries
            ),
            "topology_input_basis": "visual_crop_without_parser_grid",
            "topology_dimensions_source": "vlm_visual_observation",
            "alternative_generation_contract": (
                "explicit_exhaustive_bounded_alternatives"
            ),
            "topology_prompt_contract_hash": sha256_json(
                _object(package.get("model_facing")).get("task")
            ),
            "crop_manifest_hash": _object(package.get("crop_identity")).get(
                "manifest_hash"
            ),
            "observed_image_bytes": _object(package.get("crop_identity")).get(
                "png_bytes"
            ),
            "maximum_image_bytes": 8 * 1024 * 1024,
            "observed_output_tokens": max(output_tokens, default=0),
            "maximum_output_tokens": 8192,
            "provider_token_accounting_exact": exact_accounting,
            "candidate_ownership_exact": candidate_ownership,
            "no_silent_truncation": bool(
                len(successful_entries) == 2
                and all(
                    _object(item.get("provider_attempt")).get("finish_reason")
                    == "STOP"
                    for item in successful_entries
                )
            ),
            "column_splitting_used": False,
            "hidden_provider_failover": False,
            "alternative_topology_hypotheses_complete": complete,
        }
        hypothesis_set = parser_contracts.build_vlm_hypothesis_set(
            parser_observation=target["parser_observation"],
            binding_hypotheses=binding_inputs,
            rejected_evidence=rejected,
            model_context=model_context,
        )
        hypothesis_errors = parser_contracts.validate_vlm_hypothesis_set(
            parser_observation=target["parser_observation"],
            hypothesis_set=hypothesis_set,
        )
        if hypothesis_errors:
            raise HoldoutError(hypothesis_errors[0])
        repeatability = solver.build_repeatability_record(
            parser_observation=target["parser_observation"],
            vlm_hypothesis_set=hypothesis_set,
        )
        first = solver.solve(
            parser_observation=target["parser_observation"],
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )
        second = solver.solve(
            parser_observation=copy.deepcopy(target["parser_observation"]),
            vlm_hypothesis_set=copy.deepcopy(hypothesis_set),
            historical_repeatability=copy.deepcopy(repeatability),
        )
        if first != second:
            raise HoldoutError(
                f"pdf_structural_holdout_solver_nondeterministic:{target_id}"
            )
        accepted_binding = None
        materialization = None
        if first.get("terminal_status") == "accepted_supplied_consensus":
            accepted_binding = solver.binding_from_accepted_consensus(
                parser_observation=target["parser_observation"],
                consensus_result=first,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=package,
            )
            materialization = materializer.materialize(
                evidence_package=package,
                binding_output=accepted_binding,
            )
        terminal_targets[target_id] = {
            "scope": {
                "target_id": target_id,
                "document_id": target["document_id"],
                "page_number": target["page_number"],
                "parser_ordinal": target["parser_ordinal"],
            },
            "parser_observation": target["parser_observation"],
            "parser_geometry_observation": target[
                "parser_geometry_observation"
            ],
            "visual_package": package,
            "assemblies": assemblies,
            "hypothesis_set": hypothesis_set,
            "repeatability": repeatability,
            "consensus_result": first,
            "accepted_binding": accepted_binding,
            "materialization": materialization,
        }
        if execution:
            terminal_targets[target_id].update(
                {
                    "execution_contract": copy.deepcopy(execution),
                    "window_stitches": [],
                    "window_runtime_result_checksum": None,
                }
            )
        if preregistration.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES:
            terminal_targets[target_id]["eligibility_observation"] = (
                copy.deepcopy(target.get("eligibility_observation"))
            )

    new_generate_calls = sum(
        item.get("provider_generate_call_performed") is True for item in journal
    )
    new_count_token_calls = _journal_count_token_calls(journal)
    expected_count_token_calls = sum(
        _object(target.get("execution_contract")).get(
            "expected_count_token_calls", 2
        )
        for target in targets.values()
    )
    expected_generate_calls = sum(
        _object(target.get("execution_contract")).get(
            "expected_generate_calls", 2
        )
        for target in targets.values()
    )
    terminal = {
        "schema_version": (
            PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3
            if execution_freeze
            else (
                PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2
                if preregistration.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES
                else PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA
            )
        ),
        "policy_version": preregistration["policy_version"],
        "holdout_id": preregistration["holdout_id"],
        "execution_class": preregistration["execution_class"],
        "certification_eligible": preregistration["certification_eligible"],
        "corpus_policy": preregistration["corpus_policy"],
        "preregistration_file_sha256": preregistration_file_sha256,
        "source_freeze": copy.deepcopy(preregistration["frozen_source"]),
        "provider_qualification": qualification,
        "provider_config": asdict(provider_config),
        "journal": journal,
        "targets": terminal_targets,
        "new_provider_generate_calls": new_generate_calls,
        **(
            {
                "new_provider_count_token_calls": new_count_token_calls,
                "expected_provider_count_token_calls": (
                    expected_count_token_calls
                ),
                "expected_provider_generate_calls": expected_generate_calls,
            }
            if execution_freeze
            else {}
        ),
        "reference_process_started": False,
    }
    terminal_seal = holdout_contract.terminal_seal(
        preregistration_file_sha256=preregistration_file_sha256,
        source_freeze=terminal["source_freeze"],
        execution_class=terminal["execution_class"],
        certification_eligible=terminal["certification_eligible"],
        corpus_policy=terminal["corpus_policy"],
        provider_qualification=terminal["provider_qualification"],
        provider_config=terminal["provider_config"],
        journal=terminal["journal"],
        targets=terminal_targets,
        new_provider_generate_calls=new_generate_calls,
        new_provider_count_token_calls=(
            new_count_token_calls if execution_freeze else None
        ),
        expected_provider_count_token_calls=(
            expected_count_token_calls if execution_freeze else None
        ),
        expected_provider_generate_calls=(
            expected_generate_calls if execution_freeze else None
        ),
        reference_process_started=terminal["reference_process_started"],
    )
    terminal["terminal_seal"] = terminal_seal
    terminal["terminal_seal_hash"] = sha256_json(terminal_seal)
    terminal["artifact_checksum"] = sha256_json(terminal)
    _verify_frozen_boundary(
        preregistration=preregistration,
        preregistration_path=preregistration_path,
        preregistration_file_sha256=preregistration_file_sha256,
        runtime_output_dir=output_dir,
    )
    terminal_errors = holdout_contract.validate_terminal_against_preregistration(
        terminal=terminal,
        preregistration=preregistration,
        preregistration_file_sha256=preregistration_file_sha256,
    )
    if terminal_errors:
        raise HoldoutBoundaryError(terminal_errors[0])
    terminal_path = private_dir / "holdout.terminal.private.json"
    _write_json(terminal_path, terminal)
    terminal_readback, terminal_file_sha256 = _load_json(
        terminal_path, dict, "terminal"
    )
    if terminal_readback != terminal:
        raise HoldoutBoundaryError("pdf_structural_holdout_terminal_readback")
    terminal_errors = holdout_contract.validate_terminal_against_preregistration(
        terminal=terminal_readback,
        preregistration=preregistration,
        preregistration_file_sha256=preregistration_file_sha256,
    )
    if terminal_errors:
        raise HoldoutBoundaryError(terminal_errors[0])
    safe = _safe_terminal(
        preregistration=preregistration,
        terminal=terminal,
        terminal_file_sha256=terminal_file_sha256,
    )
    _assert_safe_payload(safe)
    _write_json(output_dir / "holdout.terminal.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _validate_target_state(
    target: dict[str, Any],
    *,
    parser_contracts: Any | None = None,
    parser_geometry: Any | None = None,
    visual: Any | None = None,
) -> None:
    parser_contracts = parser_contracts or PdfDualOracleContractFactory().create()
    parser_geometry = parser_geometry or PdfParserGeometryFactory().create()
    visual = visual or PdfVisualTopologyFactory().create()
    parser_observation = _object(target.get("parser_observation"))
    geometry_observation = _object(
        target.get("parser_geometry_observation")
    )
    visual_package = _object(target.get("visual_package"))
    execution_contract = _object(target.get("execution_contract"))
    parser_errors = parser_contracts.validate_parser_observation(
        parser_observation
    )
    geometry_errors = parser_geometry.validate_observation(
        geometry_observation
    )
    execution_mode = str(execution_contract.get("execution_mode") or "")
    if execution_mode == "vertical_atom_windows":
        ledger_visual = PdfVisualTopologyFactory(
            PdfVisualTopologyConfig(
                maximum_model_json_bytes=512 * 1024,
                maximum_static_input_tokens=150_000,
            )
        ).create()
        visual_errors = ledger_visual.validate_ledger_package(
            parser_observation=parser_observation,
            package=visual_package,
        )
    else:
        visual_errors = visual.validate_package(
            parser_observation=parser_observation,
            package=visual_package,
        )
    execution_errors = (
        PdfStructuralRepairHoldoutContractFactory()
        .create()
        .validate_target_execution_contract(
            parser_observation=parser_observation,
            visual_package=visual_package,
            contract=execution_contract,
        )
        if execution_contract
        else []
    )
    if parser_errors or geometry_errors or visual_errors or execution_errors:
        raise HoldoutBoundaryError(
            (
                parser_errors
                or geometry_errors
                or visual_errors
                or execution_errors
            )[0]
        )
    png_bytes = _decode_target_png(target)
    crop = _object(visual_package.get("crop_identity"))
    if (
        crop.get("dpi") != 150
        or crop.get("padding_points") != 0.0
        or crop.get("png_bytes") != len(png_bytes)
        or crop.get("crop_sha256")
        != hashlib.sha256(png_bytes).hexdigest()
        or len(png_bytes) > 8 * 1024 * 1024
        or parser_observation.get("page_number") != target.get("page_number")
        or geometry_observation.get("page_number") != target.get("page_number")
        or visual_package.get("page_number") != target.get("page_number")
    ):
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_target_state_invalid"
        )
    if execution_mode == "vertical_atom_windows":
        plan = _object(execution_contract.get("window_plan"))
        plan_windows = _dicts(plan.get("windows"))
        frozen_windows = _dicts(execution_contract.get("window_inputs"))
        for window, frozen in zip(plan_windows, frozen_windows, strict=True):
            package = _object(frozen.get("window_package"))
            if visual.validate_window_package(
                parser_observation=parser_observation,
                full_package=visual_package,
                window_plan=plan,
                window=window,
                package=package,
            ):
                raise HoldoutBoundaryError(
                    "pdf_structural_holdout_window_package_invalid"
                )


def _target_execution_freeze(
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for target_id in sorted(targets):
        execution = _object(targets[target_id].get("execution_contract"))
        if not execution:
            return []
        result.append(
            {
                "target_id": target_id,
                "execution_mode": execution.get("execution_mode"),
                "candidate_atoms": execution.get("candidate_atoms"),
                "plan_hash": execution.get("plan_hash"),
                "window_count": execution.get("window_count"),
                "expected_count_token_calls": execution.get(
                    "expected_count_token_calls"
                ),
                "expected_generate_calls": execution.get(
                    "expected_generate_calls"
                ),
                "execution_contract_checksum": execution.get(
                    "execution_contract_checksum"
                ),
                "window_artifacts": [
                    {
                        "window_id": item.get("window_id"),
                        "crop_sha256": item.get("crop_sha256"),
                        "package_id": item.get("package_id"),
                        "package_hash": item.get("package_hash"),
                    }
                    for item in _dicts(execution.get("window_inputs"))
                ],
            }
        )
    return result


def _thaw_window_inputs(
    execution_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _dicts(execution_contract.get("window_inputs")):
        try:
            png_bytes = base64.b64decode(
                str(item.get("private_png_base64") or ""), validate=True
            )
        except (TypeError, ValueError) as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_window_crop_invalid"
            ) from exc
        result.append(
            {
                "window_id": item.get("window_id"),
                "window_package": copy.deepcopy(item.get("window_package")),
                "png_bytes": png_bytes,
            }
        )
    return result


def _holdout_window_journal(
    runtime_result: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _dicts(runtime_result.get("journal")):
        failure_code = item.get("failure_code")
        counted = _object(item.get("count_tokens"))
        if counted.get("budget_exceeded") is True:
            counted = _budget_count_observation_from_values(
                observed=counted.get("total_tokens"),
                maximum=counted.get("maximum_counted_input_tokens"),
            )
        result.append(
            {
                "schema_version": PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA,
                "target_id": item.get("target_id"),
                "attempt_number": item.get("attempt_number"),
                "task_id": item.get("task_id"),
                "job_key": item.get("job_key"),
                "evidence_revision": item.get("evidence_revision"),
                "provider_config_hash": item.get("provider_config_hash"),
                "count_tokens": copy.deepcopy(counted),
                "provider_attempt": copy.deepcopy(item.get("provider_attempt")),
                "provider_result": copy.deepcopy(item.get("provider_result")),
                "topology_response": copy.deepcopy(
                    item.get("topology_response")
                ),
                "assembly": copy.deepcopy(item.get("assembly")),
                "failure_code": failure_code,
                "failure_class": (
                    "contract_or_terminal_failure" if failure_code else None
                ),
                "provider_generate_call_performed": item.get(
                    "provider_generate_call_performed"
                ),
                "window_id": item.get("window_id"),
                "window_package_id": item.get("window_package_id"),
                "provider_count_token_call_performed": item.get(
                    "provider_count_token_call_performed"
                ),
            }
        )
    return result


def _journal_count_token_calls(items: list[dict[str, Any]]) -> int:
    performed = 0
    prior_allows_next_by_target: dict[str, bool] = {}
    for item in items:
        if (
            item.get("schema_version")
            == PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA
        ):
            performed += (
                item.get("provider_count_token_call_performed") is True
            )
            continue
        target_id = str(item.get("target_id") or "")
        if prior_allows_next_by_target.get(target_id, True):
            performed += 1
        attempt = _object(item.get("provider_attempt"))
        prior_allows_next_by_target[target_id] = bool(
            item.get("provider_generate_call_performed") is True
            and attempt.get("terminal_failure_class") is None
            and attempt.get("finish_reason") == "STOP"
            and attempt.get("hidden_retry") is False
            and attempt.get("provider_failover") is False
            and attempt.get("model_requested")
            == attempt.get("model_resolved")
        )
    return performed


def _budget_count_observation(exc: BaseException) -> dict[str, int]:
    if str(getattr(exc, "code", "")) != (
        "pdf_grid_provider_counted_input_budget_exceeded"
    ):
        return {}
    details = _object(getattr(exc, "safe_details", None))
    return _budget_count_observation_from_values(
        observed=details.get("observed_total_tokens"),
        maximum=details.get("maximum_counted_input_tokens"),
    )


def _budget_count_observation_from_values(
    *, observed: Any, maximum: Any
) -> dict[str, int]:
    if (
        not _nonnegative_int(observed)
        or not _nonnegative_int(maximum)
        or observed <= maximum
    ):
        return {}
    return {
        "observed_total_tokens": observed,
        "maximum_counted_input_tokens": maximum,
    }


def _decode_target_png(target: dict[str, Any]) -> bytes:
    try:
        value = base64.b64decode(
            str(target.get("private_png_base64") or ""), validate=True
        )
    except (ValueError, TypeError) as exc:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_private_crop_invalid"
        ) from exc
    if not value:
        raise HoldoutBoundaryError("pdf_structural_holdout_private_crop_empty")
    return value


def _validate_provider_qualification(
    qualification: dict[str, Any], provider_config: PdfGridProviderConfig
) -> None:
    if (
        set(qualification) != QUALIFICATION_KEYS
        or qualification.get("status") != "qualified"
        or qualification.get("provider_profile")
        != provider_config.provider_profile
        or not isinstance(qualification.get("provider_profile_revision"), str)
        or not qualification.get("provider_profile_revision")
        or qualification.get("requested_model_id") != provider_config.model_id
        or qualification.get("resolved_model_id") != provider_config.model_id
        or qualification.get("exact_model_match") is not True
        or qualification.get("image_input_supported") is not True
        or qualification.get("structured_output_supported") is not True
        or qualification.get("native_provider_transport") is not True
        or qualification.get("credentials_from_openwebui_connection") is not True
        or qualification.get("hidden_retry") is not False
        or qualification.get("provider_failover") is not False
        or not _positive_int(qualification.get("maximum_input_tokens"))
        or qualification.get("maximum_input_tokens")
        < provider_config.maximum_counted_input_tokens
        or not _positive_int(qualification.get("maximum_output_tokens"))
        or qualification.get("maximum_output_tokens")
        < provider_config.maximum_output_tokens
        or qualification.get("http_status") != 200
        or not _sha256_string(qualification.get("response_hash"))
    ):
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_provider_not_qualified"
        )


def _validate_count_tokens(
    counted: dict[str, Any], *, provider_config: PdfGridProviderConfig
) -> None:
    details = counted.get("prompt_tokens_details")
    if (
        set(counted) != COUNT_TOKENS_KEYS
        or not _nonnegative_int(counted.get("total_tokens"))
        or counted.get("total_tokens")
        > provider_config.maximum_counted_input_tokens
        or not isinstance(details, list)
        or len(_dicts(details)) != len(details)
        or counted.get("http_status") != 200
        or not _sha256_string(counted.get("request_hash"))
        or not _sha256_string(counted.get("response_hash"))
        or not _sha256_string(counted.get("canonical_schema_hash"))
        or not _sha256_string(counted.get("adapted_schema_hash"))
        or not _nonnegative_int(counted.get("schema_transform_count"))
        or counted.get("model_requested") != provider_config.model_id
        or counted.get("transport_identity")
        != "gemini_count_tokens_generate_content_request"
        or counted.get("within_hard_guard") is not True
    ):
        raise HoldoutError("pdf_structural_holdout_count_tokens_invalid")


def _validate_provider_attempt_result(
    *,
    provider_result: dict[str, Any],
    provider_attempt: dict[str, Any],
    counted: dict[str, Any],
    package: dict[str, Any],
    provider_config: PdfGridProviderConfig,
    task_id: str,
    attempt_number: int,
    attempt_lineage: list[str],
) -> None:
    usage = _object(provider_attempt.get("usage"))
    tokens = (
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )
    tokens_absent = all(value is None for value in tokens)
    tokens_valid = all(_nonnegative_int(value) for value in tokens)
    successful = provider_attempt.get("terminal_failure_class") is None
    crop = _object(package.get("crop_identity"))
    if (
        set(provider_attempt) != PROVIDER_ATTEMPT_KEYS
        or provider_attempt.get("task_id") != task_id
        or provider_attempt.get("attempt_id")
        != f"{task_id}_a{attempt_number}"
        or provider_attempt.get("attempt_number") != attempt_number
        or provider_attempt.get("attempt_lineage") != attempt_lineage
        or provider_attempt.get("provider") != "google"
        or provider_attempt.get("provider_profile")
        != provider_config.provider_profile
        or not isinstance(
            provider_attempt.get("provider_profile_revision"), str
        )
        or not provider_attempt.get("provider_profile_revision")
        or provider_attempt.get("model_requested") != provider_config.model_id
        or not isinstance(provider_attempt.get("adapter_identity"), str)
        or not provider_attempt.get("adapter_identity")
        or provider_attempt.get("transport_identity")
        != "gemini_generate_content_native_table_crop_json_schema"
        or not _sha256_string(provider_attempt.get("request_hash"))
        or provider_attempt.get("crop_sha256") != crop.get("crop_sha256")
        or provider_attempt.get("model_view_hash")
        != sha256_json(package.get("model_facing"))
        or provider_attempt.get("canonical_schema_hash")
        != counted.get("canonical_schema_hash")
        or provider_attempt.get("adapted_schema_hash")
        != counted.get("adapted_schema_hash")
        or provider_attempt.get("schema_transform_count")
        != counted.get("schema_transform_count")
        or not isinstance(provider_attempt.get("started_at"), str)
        or not provider_attempt.get("started_at")
        or not isinstance(provider_attempt.get("ended_at"), str)
        or not provider_attempt.get("ended_at")
        or not isinstance(provider_attempt.get("duration_ms"), (int, float))
        or isinstance(provider_attempt.get("duration_ms"), bool)
        or float(provider_attempt.get("duration_ms") or 0) < 0
        or not (
            provider_attempt.get("http_status") is None
            or _nonnegative_int(provider_attempt.get("http_status"))
        )
        or set(usage) != {"input_tokens", "output_tokens", "total_tokens"}
        or not (tokens_absent or tokens_valid)
        or provider_attempt.get("thinking_level") != "minimal"
        or not isinstance(provider_attempt.get("parse_result"), str)
        or not (
            provider_attempt.get("terminal_failure_class") is None
            or provider_attempt.get("terminal_failure_class")
            in PROVIDER_FAILURE_CLASSES
        )
        or provider_attempt.get("hidden_retry") is not False
        or provider_attempt.get("provider_failover") is not False
    ):
        raise HoldoutError(
            "pdf_structural_holdout_provider_attempt_lineage_invalid"
        )
    if tokens_valid and (
        usage.get("input_tokens") != counted.get("total_tokens")
        or usage.get("total_tokens")
        < usage.get("input_tokens") + usage.get("output_tokens")
    ):
        raise HoldoutError("pdf_structural_holdout_provider_usage_invalid")
    if successful and (
        provider_attempt.get("model_resolved") != provider_config.model_id
        or provider_attempt.get("finish_reason") != "STOP"
        or not tokens_valid
        or usage.get("output_tokens") > provider_config.maximum_output_tokens
    ):
        raise HoldoutError("pdf_structural_holdout_provider_usage_invalid")
    if (
        set(provider_result) != PROVIDER_RESULT_KEYS
        or provider_result.get("attempt") != provider_attempt
        or not isinstance(provider_result.get("raw_private_response"), dict)
        or not _nonnegative_int(provider_result.get("response_bytes"))
        or provider_result.get("response_bytes") > 2 * 1024 * 1024
        or not _sha256_string(provider_result.get("response_hash"))
        or not _nonnegative_int(provider_result.get("visible_output_bytes"))
        or provider_result.get("visible_output_bytes") > 512 * 1024
        or not (
            provider_result.get("visible_output_hash") is None
            or _sha256_string(provider_result.get("visible_output_hash"))
        )
        or not isinstance(provider_result.get("json_output"), (dict, type(None)))
    ):
        raise HoldoutError("pdf_structural_holdout_provider_result_invalid")


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _sha256_string(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _source_freeze() -> dict[str, Any]:
    paths = set((SERVICE_ROOT / "broker_reports_gate1").rglob("*.py"))
    paths.add(Path(__file__).resolve())
    scorer = SCRIPT_DIR / "local_pdf_structural_repair_holdout_score.py"
    if scorer.is_file():
        paths.add(scorer.resolve())
    inventory: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.relative_to(REPO_ROOT).as_posix()):
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(REPO_ROOT).as_posix()
        except ValueError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_source_outside_repository"
            ) from exc
        raw = resolved.read_bytes()
        inventory.append(
            {
                "repo_relative_path": relative,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "git_revision": _git_revision(),
        "inventory": inventory,
        "inventory_checksum": sha256_json(inventory),
    }


def _verify_source_freeze(frozen: dict[str, Any]) -> None:
    current = _source_freeze()
    if current != frozen:
        raise HoldoutBoundaryError("pdf_structural_holdout_source_freeze_mismatch")


def _verify_frozen_boundary(
    *,
    preregistration: dict[str, Any],
    preregistration_path: Path,
    preregistration_file_sha256: str,
    runtime_output_dir: Path,
) -> None:
    if _sha256_file(preregistration_path) != preregistration_file_sha256:
        raise HoldoutBoundaryError(
            "pdf_structural_holdout_preregistration_file_drift"
        )
    contracts = PdfStructuralRepairHoldoutContractFactory().create()
    errors = contracts.validate_preregistration(preregistration)
    if errors:
        raise HoldoutBoundaryError(errors[0])
    _verify_source_freeze(_object(preregistration.get("frozen_source")))
    _verify_freshness_scan(
        _object(preregistration.get("freshness_scan")),
        runtime_output_dir=runtime_output_dir,
    )
    documents = _dicts(preregistration.get("documents"))
    policy = PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES.get(
        str(preregistration.get("execution_class") or ""), {}
    )
    expected_hashes = set(policy.get("sha256") or set())
    if len(documents) != int(policy.get("document_count") or 0):
        raise HoldoutBoundaryError("pdf_structural_holdout_corpus_drift")
    observed_hashes: set[str] = set()
    for document in documents:
        path = (REPO_ROOT / str(document.get("repo_relative_path") or "")).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise HoldoutBoundaryError(
                "pdf_structural_holdout_document_path_invalid"
            ) from exc
        if not path.is_file():
            raise HoldoutBoundaryError("pdf_structural_holdout_document_missing")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        observed_hashes.add(digest)
        if (
            digest != document.get("pdf_sha256")
            or len(raw) != document.get("size_bytes")
        ):
            raise HoldoutBoundaryError("pdf_structural_holdout_document_drift")
    if observed_hashes != expected_hashes:
        raise HoldoutBoundaryError("pdf_structural_holdout_corpus_hash_drift")


def _safe_preregistration(preregistration: dict[str, Any]) -> dict[str, Any]:
    selection = _object(preregistration.get("selection_contract"))
    safe = {
        "schema_version": PREREGISTRATION_SAFE_SCHEMA,
        "policy_version": preregistration.get("policy_version"),
        "holdout_id": preregistration.get("holdout_id"),
        "execution_class": preregistration.get("execution_class"),
        "certification_eligible": preregistration.get(
            "certification_eligible"
        ),
        "corpus_policy": preregistration.get("corpus_policy"),
        "corpus_role": preregistration.get("execution_class"),
        "corpus_documents": len(_dicts(preregistration.get("documents"))),
        "selection": {
            "rule": selection.get("rule"),
            "targets": selection.get("table_limit"),
            "manual_target_substitution_allowed": False,
            "parser_only_eligibility": (
                preregistration.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES
            ),
            "eligibility_policy_checksum": selection.get(
                "eligibility_policy_checksum"
            ),
        },
        "execution_policy": copy.deepcopy(
            preregistration.get("execution_policy")
        ),
        "target_execution": [
            {
                "target_id": target.get("target_id"),
                "execution_mode": _object(
                    target.get("execution_contract")
                ).get("execution_mode", "whole_table"),
                "candidate_atoms": _object(
                    target.get("execution_contract")
                ).get("candidate_atoms"),
                "window_count": _object(
                    target.get("execution_contract")
                ).get("window_count", 1),
                "expected_provider_count_token_calls": _object(
                    target.get("execution_contract")
                ).get("expected_count_token_calls", 2),
                "expected_provider_generate_calls": _object(
                    target.get("execution_contract")
                ).get("expected_generate_calls", 2),
            }
            for target in _dicts(preregistration.get("targets"))
        ],
        "source_inventory_checksum": _object(
            preregistration.get("frozen_source")
        ).get("inventory_checksum"),
        "freshness_inventory_checksum": _object(
            preregistration.get("freshness_scan")
        ).get("inventory_checksum"),
        "reference_available_at_preregistration": False,
        "reference_material_accessed": False,
        "provider_calls_started": False,
    }
    safe["artifact_checksum"] = sha256_json(safe)
    return safe


def _window_fallback_consensus(
    *, target_id: str, window_result: dict[str, Any]
) -> dict[str, Any]:
    return {
        "terminal_status": "blocked_no_valid_evidence",
        "reason_codes": _safe_codes(
            _object(window_result.get("safe_summary")).get("reason_codes")
        ),
        "review_codes": [],
        "result_checksum": sha256_json(
            {
                "target_id": target_id,
                "runtime_terminal_status": window_result.get(
                    "runtime_terminal_status"
                ),
                "runtime_result_checksum": window_result.get(
                    "result_checksum"
                ),
            }
        ),
    }


def _safe_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    selection = _object(preflight.get("selection_contract"))
    safe = {
        "schema_version": PREFLIGHT_SAFE_SCHEMA,
        "private_schema_version": (
            PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA_V2
            if preflight.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES
            else PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA
        ),
        "policy_version": preflight.get("policy_version"),
        "holdout_id": preflight.get("holdout_id"),
        "execution_class": preflight.get("execution_class"),
        "certification_eligible": preflight.get("certification_eligible"),
        "corpus_policy": preflight.get("corpus_policy"),
        "corpus": {
            "role": preflight.get("execution_class"),
            "documents": len(_dicts(preflight.get("documents"))),
            "targets_predeclared": len(_dicts(preflight.get("target_scopes"))),
            "manual_target_substitution_performed": False,
        },
        "selection": {
            "rule": selection.get("rule"),
            "targets": selection.get("table_limit"),
            "parser_only_eligibility": (
                preflight.get("execution_class") in PARSER_ONLY_HOLDOUT_CLASSES
            ),
            "eligibility_policy_checksum": selection.get(
                "eligibility_policy_checksum"
            ),
        },
        "source_inventory_checksum": _object(
            preflight.get("frozen_source")
        ).get("inventory_checksum"),
        "freshness_inventory_checksum": _object(
            preflight.get("freshness_scan")
        ).get("inventory_checksum"),
        "failed_target_id": preflight.get("failed_target_id"),
        "failure_code": _safe_code(preflight.get("failure_code")),
        "provider_calls_started": False,
        "new_provider_generate_calls": 0,
        "reference_material_accessed": False,
        "terminal_status": (
            "fresh_holdout_preflight_blocked"
            if preflight.get("execution_class")
            in FRESH_HOLDOUT_CLASSES
            else "development_regression_preflight_blocked_non_certifying"
        ),
        "meaning": "automatic_request_construction_not_completed",
    }
    safe["artifact_checksum"] = sha256_json(safe)
    return safe


def _safe_terminal(
    *,
    preregistration: dict[str, Any],
    terminal: dict[str, Any],
    terminal_file_sha256: str,
) -> dict[str, Any]:
    safe_targets: list[dict[str, Any]] = []
    terminal_targets = _object(terminal.get("targets"))
    journal = _dicts(terminal.get("journal"))
    for target_id in sorted(terminal_targets):
        target = _object(terminal_targets.get(target_id))
        execution = _object(target.get("execution_contract"))
        assemblies = _dicts(target.get("assemblies"))
        consensus = _object(target.get("consensus_result"))
        repeatability = _object(target.get("repeatability"))
        materialization = target.get("materialization")
        entries = [
            item for item in journal if item.get("target_id") == target_id
        ]
        execution_mode = str(
            execution.get("execution_mode") or "whole_table"
        )
        target_count_calls = _journal_count_token_calls(entries)
        safe_targets.append(
            {
                "target_id": target_id,
                "certification_eligible": terminal.get(
                    "certification_eligible"
                ),
                "attempts_planned": 2,
                "execution_mode": execution_mode,
                "window_count": int(execution.get("window_count") or 1),
                "raw_provider_attempts_planned": int(
                    execution.get("expected_generate_calls") or 2
                ),
                "provider_count_token_calls": target_count_calls,
                "provider_generate_calls": sum(
                    item.get("provider_generate_call_performed") is True
                    for item in entries
                ),
                "stitched_oracle_observations": len(
                    _dicts(target.get("window_stitches"))
                ),
                "successful_assemblies": len(assemblies),
                "reconstruction_statuses": [
                    item.get("reconstruction_status") for item in assemblies
                ],
                "certification_status": consensus.get("terminal_status"),
                "reason_codes": _safe_codes(consensus.get("reason_codes")),
                "review_codes": _safe_codes(consensus.get("review_codes")),
                "row_count": consensus.get("row_count"),
                "column_count": consensus.get("column_count"),
                "atom_count": _object(
                    _object(target.get("parser_observation")).get(
                        "source_accounting"
                    )
                ).get("candidates"),
                "all_atoms_exactly_once": bool(
                    len(assemblies) == 2
                    and all(
                        _object(item.get("source_accounting")).get(
                            "all_bound_alternatives_exactly_once"
                        )
                        is True
                        for item in assemblies
                    )
                ),
                "repeatability_passed": repeatability.get("passed") is True,
                "valid_distinct_grid_count": consensus.get(
                    "valid_distinct_grid_count"
                ),
                "supplied_hypotheses_exhausted": consensus.get(
                    "supplied_hypotheses_exhausted"
                ),
                "structural_domain_complete": consensus.get(
                    "structural_domain_complete"
                ),
                "uniqueness_proven": consensus.get("uniqueness_proven"),
                "ambiguity_proven": consensus.get("ambiguity_proven"),
                "domain_incomplete": consensus.get("domain_incomplete"),
                "search_not_certifiable": consensus.get(
                    "search_not_certifiable"
                ),
                "search_scope": consensus.get("search_scope"),
                "safe_explanation": consensus.get("safe_explanation"),
                "model_invented_values_total": (
                    _object(materialization).get("model_invented_values_total")
                    if isinstance(materialization, dict)
                    else 0
                ),
                "omitted_candidates": (
                    len(_object(materialization).get("omitted_candidate_ids") or [])
                    if isinstance(materialization, dict)
                    else 0
                ),
                "result_checksum": consensus.get("result_checksum"),
            }
        )
    accepted = sum(
        item.get("certification_status") == "accepted_supplied_consensus"
        for item in safe_targets
    )
    generate_calls = int(terminal.get("new_provider_generate_calls") or 0)
    count_token_calls = int(
        terminal.get("new_provider_count_token_calls")
        if terminal.get("new_provider_count_token_calls") is not None
        else len(journal)
    )
    expected_calls = int(
        terminal.get("expected_provider_generate_calls")
        if terminal.get("expected_provider_generate_calls") is not None
        else len(safe_targets) * 2
    )
    expected_count_token_calls = int(
        terminal.get("expected_provider_count_token_calls")
        if terminal.get("expected_provider_count_token_calls") is not None
        else len(safe_targets) * 2
    )
    if terminal.get("execution_class") == "development_regression":
        overall_status = "DEVELOPMENT_REGRESSION_NON_CERTIFYING"
    else:
        overall_status = (
            "FRESH_HOLDOUT_ALL_THREE_ACCEPTED"
            if (
                accepted == 3
                and generate_calls == expected_calls
                and count_token_calls == expected_count_token_calls
            )
            else (
                "FRESH_HOLDOUT_INCOMPLETE_PROVIDER_CALLS"
                if (
                    generate_calls != expected_calls
                    or count_token_calls != expected_count_token_calls
                )
                else "FRESH_HOLDOUT_COMPLETED_WITH_TYPED_NONACCEPTANCE"
            )
        )
    qualification = _object(terminal.get("provider_qualification"))
    safe = {
        "schema_version": TERMINAL_SAFE_SCHEMA,
        "policy_version": terminal.get("policy_version"),
        "holdout_id": terminal.get("holdout_id"),
        "execution_class": terminal.get("execution_class"),
        "certification_eligible": terminal.get("certification_eligible"),
        "corpus_policy": terminal.get("corpus_policy"),
        "terminal_file_sha256": terminal_file_sha256,
        "terminal_seal_hash": terminal.get("terminal_seal_hash"),
        "source_inventory_checksum": _object(
            terminal.get("source_freeze")
        ).get("inventory_checksum"),
        "freshness_inventory_checksum": _object(
            preregistration.get("freshness_scan")
        ).get("inventory_checksum"),
        "corpus": {
            "role": terminal.get("execution_class"),
            "documents": len(_dicts(preregistration.get("documents"))),
            "targets": len(safe_targets),
            "reference_accessed_before_terminal": False,
            "manual_target_substitution_performed": False,
        },
        "provider_qualification": {
            "status": qualification.get("status"),
            "provider_profile": qualification.get("provider_profile"),
            "requested_model_id": qualification.get("requested_model_id"),
            "resolved_model_id": qualification.get("resolved_model_id"),
            "exact_model_match": qualification.get("exact_model_match"),
            "image_input_supported": qualification.get("image_input_supported"),
            "structured_output_supported": qualification.get(
                "structured_output_supported"
            ),
            "native_provider_transport": qualification.get(
                "native_provider_transport"
            ),
            "hidden_retry": qualification.get("hidden_retry"),
            "provider_failover": qualification.get("provider_failover"),
        },
        "targets": safe_targets,
        "terminal_counts": dict(
            sorted(
                Counter(
                    str(item.get("certification_status") or "unknown")
                    for item in safe_targets
                ).items()
            )
        ),
        "metrics": {
            "accepted_supplied_consensus": accepted,
            "all_atoms_exactly_once_tables": sum(
                item.get("all_atoms_exactly_once") is True
                for item in safe_targets
            ),
            "repeatability_passed_tables": sum(
                item.get("repeatability_passed") is True
                for item in safe_targets
            ),
            "invented_values_total": sum(
                int(item.get("model_invented_values_total") or 0)
                for item in safe_targets
            ),
            "provider_generate_calls": generate_calls,
            "expected_provider_generate_calls": expected_calls,
            "provider_count_token_calls": count_token_calls,
            "expected_provider_count_token_calls": (
                expected_count_token_calls
            ),
            "raw_provider_calls": generate_calls,
            "stitched_oracle_observations": sum(
                int(item.get("stitched_oracle_observations") or 0)
                for item in safe_targets
            ),
            "hidden_retries": sum(
                _object(item.get("provider_attempt")).get("hidden_retry") is True
                for item in journal
            ),
            "provider_failovers": sum(
                _object(item.get("provider_attempt")).get("provider_failover")
                is True
                for item in journal
            ),
        },
        "declared_execution_scope": {
            "production_pdf_pipeline_integration_performed": False,
            "production_gate2_selection_integration_performed": False,
            "openwebui_core_edit_in_scope": False,
            "knowledge_rag_vector_used": False,
            "ocr_used": False,
            "raw_values_in_safe_output": False,
            "raw_candidate_or_source_identifiers_in_safe_output": False,
            "private_paths_in_safe_output": False,
            "crop_bytes_in_safe_output": False,
            "provider_responses_in_safe_output": False,
            "reference_answer_used_by_solver": False,
        },
        "overall_status": overall_status,
    }
    safe["artifact_checksum"] = sha256_json(safe)
    return safe


def _assert_safe_payload(value: Any) -> None:
    corpus_hashes = (
        set(FRESH_CORPUS_SHA256)
        | set(FRESH_CORPUS_V2_SHA256)
        | set(FRESH_CORPUS_V3_SHA256)
        | set(FRESH_CORPUS_V4_SHA256)
        | set(FRESH_CORPUS_V5_SHA256)
        | set(EXPOSED_DEVELOPMENT_CORPUS_SHA256)
    )

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            forbidden = {str(key) for key in current} & FORBIDDEN_SAFE_KEYS
            if forbidden:
                raise HoldoutBoundaryError(
                    "pdf_structural_holdout_safe_forbidden_key:"
                    + sorted(forbidden)[0]
                )
            for item in current.values():
                walk(item)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str):
            if re.search(r"(?:[A-Za-z]:\\|/Users/|/home/|\\Users\\)", current):
                raise HoldoutBoundaryError(
                    "pdf_structural_holdout_safe_private_path"
                )
            if current in corpus_hashes:
                raise HoldoutBoundaryError(
                    "pdf_structural_holdout_safe_document_hash"
                )

    walk(value)


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    email = str(
        env.get("WEBUI_ADMIN_EMAIL")
        or env.get("OPENWEBUI_ADMIN_EMAIL")
        or env.get("ADMIN_EMAIL")
        or ""
    )
    password = str(
        env.get("WEBUI_ADMIN_PASSWORD")
        or env.get("OPENWEBUI_ADMIN_PASSWORD")
        or env.get("ADMIN_PASSWORD")
        or ""
    )
    if not all((host, email, password)):
        raise HoldoutBoundaryError("openwebui_live_credentials_missing")
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "")
    if not token:
        raise HoldoutBoundaryError("openwebui_live_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    config_object = SimpleNamespace(
        OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
        OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
        OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
    )
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=config_object))
    )


def _read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _load_json(
    path: Path, expected_type: type, subject: str
) -> tuple[Any, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_strict_pairs(subject),
            parse_constant=lambda item: _raise_nonfinite(subject, item),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HoldoutBoundaryError(
            f"pdf_structural_holdout_json_invalid:{subject}"
        ) from exc
    if not isinstance(value, expected_type):
        raise HoldoutBoundaryError(
            f"pdf_structural_holdout_json_root_invalid:{subject}"
        )
    return value, hashlib.sha256(raw).hexdigest()


def _strict_pairs(subject: str):
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise HoldoutBoundaryError(
                    f"pdf_structural_holdout_json_duplicate_key:{subject}:{key}"
                )
            result[key] = value
        return result

    return pairs


def _raise_nonfinite(subject: str, value: str) -> Any:
    raise HoldoutBoundaryError(
        f"pdf_structural_holdout_json_nonfinite:{subject}:{value}"
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _require_absent(path: Path, code: str) -> None:
    if path.exists():
        raise HoldoutBoundaryError(code)


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_string(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise HoldoutError(f"pdf_structural_holdout_required_string:{subject}")
    return value


def _valid_bbox(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in value
        )
        and float(value[2]) > float(value[0])
        and float(value[3]) > float(value[1])
    )


def _safe_code(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]{0,127}", value
    ):
        return "unknown_failure"
    if value in SAFE_LITERAL_CODES or value.startswith(SAFE_CODE_PREFIXES):
        return value
    return "unknown_failure"


def _safe_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {
            rendered
            for item in value
            if (rendered := _safe_code(item)) is not None
        }
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


if __name__ == "__main__":
    raise SystemExit(main())
