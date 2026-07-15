#!/usr/bin/env python3
"""Run the independent visual-topology and deterministic raw-atom binding slice."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
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
    PdfParserGeometryFactory,
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
    PdfVisualTopologyError,
    PdfVisualTopologyFactory,
)


SAFE_SCHEMA = "broker_reports_pdf_structural_repair_proof_safe_v2"
PRIVATE_SCHEMA = "broker_reports_pdf_structural_repair_proof_private_v2"
JOURNAL_SCHEMA = "broker_reports_pdf_structural_repair_journal_entry_v1"
TARGET_KEYS = ("1:2", "4:2", "5:3")
STRUCTURAL_CASES = {
    "1:2": "simple_control",
    "4:2": "grouped_merged_header",
    "5:3": "tax_summary",
}
ATTEMPTS = (1, 2)
MAXIMUM_IMAGE_BYTES = 8 * 1024 * 1024
MAXIMUM_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
FORBIDDEN_SAFE_KEYS = frozenset(
    {
        "candidate_id",
        "candidate_ids",
        "crop_identity",
        "crop_manifest_hash",
        "crop_sha256",
        "exact_source_span",
        "hypothesis_id",
        "hypothesis_set_id",
        "model_facing",
        "neutral_atom_to_candidate_id",
        "observation_id",
        "package_id",
        "parser_observation_id",
        "private_candidate_dictionary",
        "raw_private_response",
        "raw_provider_response",
        "resolved_source_values",
        "source_value_refs",
        "table_key",
        "table_ref",
        "word_refs",
    }
)
SOURCE_FILES = {
    "visual_topology_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_visual_topology.py",
    "assembly_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_topology_assembly.py",
    "parser_geometry_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_parser_geometry.py",
    "contracts_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_dual_oracle_contracts.py",
    "solver_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_dual_oracle_consensus.py",
    "runner_sha256": Path(__file__).resolve(),
}


class ProofError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    parser.add_argument("--targets", default=",".join(TARGET_KEYS))
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--maximum-counted-input-tokens", type=int, default=20_000)
    parser.add_argument("--maximum-output-tokens", type=int, default=8192)
    args = parser.parse_args()

    requested_targets = tuple(
        item.strip() for item in str(args.targets).split(",") if item.strip()
    )
    if requested_targets != TARGET_KEYS:
        raise ProofError("structural_repair_exact_target_set_required")
    if args.attempts != 2:
        raise ProofError("structural_repair_exact_two_attempts_required")
    if args.dpi != 150:
        raise ProofError("structural_repair_primary_150_dpi_required")
    if args.maximum_counted_input_tokens != 20_000:
        raise ProofError("structural_repair_counted_input_cap_invalid")
    if args.maximum_output_tokens != 8192:
        raise ProofError("structural_repair_output_cap_invalid")

    pdf_path = Path(args.pdf).resolve()
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    journal_path = private_dir / "journal.private.json"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ProofError("structural_repair_fresh_output_directory_required")

    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref=f"controlled-private-pdf:{pdf_sha256}",
                filename="controlled.pdf",
                content=pdf_bytes,
                mime_type=mimetypes.guess_type("controlled.pdf")[0]
                or "application/pdf",
                source_kind="local_private_test",
            )
        ],
        entrypoint="local_pdf_structural_repair_proof",
        trigger_type="controlled_private_research",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": False,
            "pdf_hybrid_shadow_enabled": False,
            "pdf_hybrid_reliability_shadow_enabled": False,
        },
    )
    states, projection = _build_states(
        normalized.package,
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        dpi=args.dpi,
    )

    provider_config = PdfGridProviderConfig(
        model_id=args.model_id,
        maximum_output_tokens=args.maximum_output_tokens,
        maximum_counted_input_tokens=args.maximum_counted_input_tokens,
    )
    request = _openwebui_request(Path(args.env_file))
    provider = PdfGridExperimentProviderFactory(
        provider_config
    ).create_for_openwebui(request)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise ProofError("structural_repair_provider_not_qualified")
    if qualification.get("requested_model_id") != args.model_id:
        raise ProofError("structural_repair_provider_model_identity_invalid")

    provider_config_hash = sha256_json(asdict(provider_config))
    journal: list[dict[str, Any]] = []
    previous_attempt_ids: dict[str, list[str]] = {key: [] for key in TARGET_KEYS}
    private_dir.mkdir(parents=True, exist_ok=True)
    for key in TARGET_KEYS:
        state = states[key]
        package = state["visual_package"]
        png_bytes = state["png_bytes"]
        evidence_revision = sha256_json(
            {
                "package_hash": package["package_hash"],
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(package["model_facing"]),
                "output_schema_hash": sha256_json(package["output_schema"]),
            }
        )
        task_id = "pdfvisualtopotask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "package_hash": package["package_hash"],
                    "evidence_revision": evidence_revision,
                    "model_id": args.model_id,
                }
            )
        ).hexdigest()[:24]
        for attempt_number in ATTEMPTS:
            print(
                f"[visual-topology {key} a{attempt_number}]",
                flush=True,
            )
            job_key = f"{task_id}|a{attempt_number}"
            counted: dict[str, Any] = {}
            result: dict[str, Any] = {}
            assembly: dict[str, Any] | None = None
            failure_code: str | None = None
            failure_class: str | None = None
            try:
                counted = provider.count_tokens(
                    model_view=package["model_facing"],
                    output_schema=package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=package["crop_identity"]["crop_sha256"],
                )
                if int(counted.get("total_tokens") or -1) > 20_000:
                    raise ProofError(
                        "structural_repair_counted_input_budget_exceeded"
                    )
                result = provider.invoke(
                    task_id=task_id,
                    model_view=package["model_facing"],
                    output_schema=package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=package["crop_identity"]["crop_sha256"],
                    attempt_number=attempt_number,
                    attempt_lineage=list(previous_attempt_ids[key]),
                )
                attempt = _object(result.get("attempt"))
                if (
                    attempt.get("terminal_failure_class") is not None
                    or attempt.get("finish_reason") != "STOP"
                    or attempt.get("hidden_retry") is not False
                    or attempt.get("provider_failover") is not False
                    or not isinstance(result.get("json_output"), dict)
                ):
                    raise ProofError("structural_repair_provider_attempt_failed")
                usage = _object(attempt.get("usage"))
                if (
                    not isinstance(usage.get("input_tokens"), int)
                    or not isinstance(usage.get("output_tokens"), int)
                    or int(usage.get("output_tokens") or 0) > 8192
                    or int(result.get("visible_output_bytes") or 0)
                    > 512 * 1024
                    or int(result.get("response_bytes") or 0)
                    > MAXIMUM_PROVIDER_RESPONSE_BYTES
                ):
                    raise ProofError(
                        "structural_repair_provider_accounting_invalid"
                    )
                assembly = state["assembler"].assemble(
                    parser_observation=state["parser_observation"],
                    parser_geometry_observation=state[
                        "parser_geometry_observation"
                    ],
                    visual_package=package,
                    topology_response=result["json_output"],
                    attempt_evidence={
                        "attempt_id": str(attempt.get("attempt_id") or ""),
                        "attempt_number": attempt_number,
                        "evidence_revision": evidence_revision,
                        "provider": "google",
                        "model": args.model_id,
                        "provider_config_hash": provider_config_hash,
                    },
                    hypothesis_id_prefix=(
                        f"visual_{STRUCTURAL_CASES[key]}_a{attempt_number}"
                    ),
                )
                previous_attempt_ids[key].append(str(attempt["attempt_id"]))
            except (
                PdfGridProviderError,
                PdfVisualTopologyError,
                PdfTopologyAssemblyError,
                ProofError,
                OSError,
            ) as exc:
                failure_code = str(getattr(exc, "code", str(exc) or type(exc).__name__))
                failure_class = str(
                    getattr(exc, "failure_class", "contract_or_terminal_failure")
                )
                attempt = _object(result.get("attempt"))
                if attempt.get("attempt_id"):
                    previous_attempt_ids[key].append(str(attempt["attempt_id"]))

            attempt = _object(result.get("attempt"))
            safe_entry = {
                "schema_version": JOURNAL_SCHEMA,
                "job_key_hash": hashlib.sha256(job_key.encode("utf-8")).hexdigest(),
                "case": STRUCTURAL_CASES[key],
                "attempt_number": attempt_number,
                "artifact_status": (
                    assembly.get("reconstruction_status")
                    if isinstance(assembly, dict)
                    else "failed"
                ),
                "failure_code": _safe_code(failure_code),
                "failure_class": _safe_code(failure_class),
                "counted_input_tokens": counted.get("total_tokens"),
                "actual_input_tokens": _object(attempt.get("usage")).get(
                    "input_tokens"
                ),
                "output_tokens": _object(attempt.get("usage")).get(
                    "output_tokens"
                ),
                "maximum_counted_input_tokens": 20_000,
                "maximum_output_tokens": 8192,
                "image_bytes": package["crop_identity"]["png_bytes"],
                "maximum_image_bytes": MAXIMUM_IMAGE_BYTES,
                "response_bytes": result.get("response_bytes"),
                "maximum_response_bytes": MAXIMUM_PROVIDER_RESPONSE_BYTES,
                "model_view_hash": sha256_json(package["model_facing"]),
                "output_schema_hash": sha256_json(package["output_schema"]),
                "request_hash": attempt.get("request_hash"),
                "response_hash": result.get("response_hash"),
                "visible_output_hash": result.get("visible_output_hash"),
                "finish_reason": attempt.get("finish_reason"),
                "provider_generate_call_performed": bool(
                    attempt.get("started_at")
                ),
                "hidden_retry": attempt.get("hidden_retry", False),
                "provider_failover": attempt.get("provider_failover", False),
                "reconstruction_status": (
                    assembly.get("reconstruction_status")
                    if isinstance(assembly, dict)
                    else "failed"
                ),
                "binding_hypotheses": len(
                    assembly.get("binding_hypotheses") or []
                )
                if isinstance(assembly, dict)
                else 0,
                "regional_issues": len(assembly.get("regional_issues") or [])
                if isinstance(assembly, dict)
                else 0,
                "structural_adjustments": len(
                    assembly.get("structural_adjustments") or []
                )
                if isinstance(assembly, dict)
                else 0,
                "all_atoms_exactly_once": bool(
                    _object(assembly.get("source_accounting")).get(
                        "all_bound_alternatives_exactly_once"
                    )
                )
                if isinstance(assembly, dict)
                else False,
                "value_mutation_performed": (
                    assembly.get("value_mutation_performed")
                    if isinstance(assembly, dict)
                    else False
                ),
                "nearest_cell_fallback_used": (
                    assembly.get("nearest_cell_fallback_used")
                    if isinstance(assembly, dict)
                    else False
                ),
                "legacy_grid_consumed": False,
            }
            private_entry = {
                "schema_version": JOURNAL_SCHEMA,
                "table_key": key,
                "task_id": task_id,
                "job_key": job_key,
                "attempt_number": attempt_number,
                "evidence_revision": evidence_revision,
                "provider_attempt": attempt,
                "count_tokens": counted,
                "model_view": package["model_facing"],
                "output_schema": package["output_schema"],
                "topology_response": result.get("json_output"),
                "provider_text": result.get("text"),
                "raw_private_response": result.get("raw_private_response"),
                "assembly": assembly,
                "failure_code": failure_code,
                "failure_class": failure_class,
            }
            journal.append({"safe": safe_entry, "private": private_entry})
            _write_json(journal_path, journal)

    contract_runtime = PdfDualOracleContractFactory().create()
    solver_runtime = PdfDualOracleConsensusFactory().create()
    results: dict[str, dict[str, Any]] = {}
    accepted_bindings: dict[str, dict[str, Any]] = {}
    table_private: dict[str, dict[str, Any]] = {}
    safe_tables: list[dict[str, Any]] = []
    for key in TARGET_KEYS:
        state = states[key]
        entries = [
            item
            for item in journal
            if _object(item.get("private")).get("table_key") == key
        ]
        assemblies = [
            _object(_object(item.get("private")).get("assembly"))
            for item in entries
            if isinstance(_object(item.get("private")).get("assembly"), dict)
        ]
        binding_inputs = [
            item
            for assembly in assemblies
            for item in assembly.get("binding_hypotheses") or []
            if isinstance(item, dict)
        ]
        rejected = [
            item
            for assembly in assemblies
            for item in assembly.get("rejected_evidence") or []
            if isinstance(item, dict)
        ]
        for entry in entries:
            private_entry = _object(entry.get("private"))
            if private_entry.get("failure_code"):
                rejected.append(
                    {
                        "evidence_id": "failed_"
                        + hashlib.sha256(
                            str(private_entry.get("job_key") or "").encode("utf-8")
                        ).hexdigest()[:24],
                        "reason_codes": [
                            _safe_code(private_entry.get("failure_code"))
                            or "provider_attempt_failed"
                        ],
                    }
                )
        successful_entries = [
            item
            for item in entries
            if isinstance(_object(_object(item.get("private")).get("assembly")), dict)
        ]
        actual_outputs = [
            int(_object(item.get("safe")).get("output_tokens") or 0)
            for item in successful_entries
        ]
        complete = bool(
            len(successful_entries) == 2
            and all(
                _object(_object(item.get("private")).get("topology_response")).get(
                    "alternatives_complete"
                )
                is True
                for item in successful_entries
            )
        )
        exact_accounting = bool(
            len(successful_entries) == 2
            and all(
                isinstance(_object(item.get("safe")).get("counted_input_tokens"), int)
                and isinstance(_object(item.get("safe")).get("actual_input_tokens"), int)
                and isinstance(_object(item.get("safe")).get("output_tokens"), int)
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
        model_context = {
            "provider": "google",
            "model": args.model_id,
            "configuration_hash": provider_config_hash,
            "bounded_row_windows": True,
            "provider_calls_replayed": 0,
            "new_provider_calls": sum(
                _object(item.get("safe")).get(
                    "provider_generate_call_performed"
                )
                is True
                for item in entries
            ),
            "topology_input_basis": "visual_crop_without_parser_grid",
            "topology_dimensions_source": "vlm_visual_observation",
            "alternative_generation_contract": "explicit_exhaustive_bounded_alternatives",
            "topology_prompt_contract_hash": sha256_json(
                state["visual_package"]["model_facing"]["task"]
            ),
            "crop_manifest_hash": state["visual_package"]["crop_identity"][
                "manifest_hash"
            ],
            "observed_image_bytes": state["visual_package"]["crop_identity"][
                "png_bytes"
            ],
            "maximum_image_bytes": MAXIMUM_IMAGE_BYTES,
            "observed_output_tokens": max(actual_outputs, default=0),
            "maximum_output_tokens": 8192,
            "provider_token_accounting_exact": exact_accounting,
            "candidate_ownership_exact": candidate_ownership,
            "no_silent_truncation": bool(
                len(successful_entries) == 2
                and all(
                    _object(item.get("safe")).get("finish_reason") == "STOP"
                    for item in successful_entries
                )
            ),
            "column_splitting_used": False,
            "hidden_provider_failover": False,
            "alternative_topology_hypotheses_complete": complete,
        }
        hypothesis_set = contract_runtime.build_vlm_hypothesis_set(
            parser_observation=state["parser_observation"],
            binding_hypotheses=binding_inputs,
            rejected_evidence=rejected,
            model_context=model_context,
        )
        repeatability = solver_runtime.build_repeatability_record(
            parser_observation=state["parser_observation"],
            vlm_hypothesis_set=hypothesis_set,
        )
        first = solver_runtime.solve(
            parser_observation=state["parser_observation"],
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )
        second = solver_runtime.solve(
            parser_observation=copy.deepcopy(state["parser_observation"]),
            vlm_hypothesis_set=copy.deepcopy(hypothesis_set),
            historical_repeatability=copy.deepcopy(repeatability),
        )
        if first != second:
            raise ProofError(f"structural_repair_solver_nondeterministic:{key}")
        materialization = None
        accepted_binding = None
        if first.get("terminal_status") == "accepted_unique_consensus":
            accepted_binding = solver_runtime.binding_from_accepted_consensus(
                parser_observation=state["parser_observation"],
                consensus_result=first,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=state["visual_package"],
            )
            materialization = PdfHybridMaterializationFactory().create().materialize(
                evidence_package=state["visual_package"],
                binding_output=accepted_binding,
            )
            accepted_bindings[key] = accepted_binding
        results[key] = first
        table_private[key] = {
            "parser_observation": state["parser_observation"],
            "parser_geometry_observation": state[
                "parser_geometry_observation"
            ],
            "visual_package": state["visual_package"],
            "hypothesis_set": hypothesis_set,
            "repeatability": repeatability,
            "consensus_result": first,
            "accepted_binding": accepted_binding,
            "materialization": materialization,
        }
        safe_tables.append(
            {
                "case": STRUCTURAL_CASES[key],
                "reconstruction_statuses": [
                    assembly.get("reconstruction_status") for assembly in assemblies
                ],
                "certification_status": first.get("terminal_status"),
                "reason_codes": first.get("reason_codes") or [],
                "review_codes": first.get("review_codes") or [],
                "row_count": first.get("row_count"),
                "column_count": first.get("column_count"),
                "atom_count": state["parser_observation"]["source_accounting"][
                    "candidates"
                ],
                "all_atoms_exactly_once": candidate_ownership,
                "repeatability_passed": repeatability.get("passed") is True,
                "structural_adjustments": sum(
                    len(assembly.get("structural_adjustments") or [])
                    for assembly in assemblies
                ),
                "structural_adjustment_operations": sorted(
                    {
                        str(item.get("operation") or "")
                        for assembly in assemblies
                        for item in assembly.get("structural_adjustments") or []
                        if isinstance(item, dict) and item.get("operation")
                    }
                ),
                "parser_geometry_signals": {
                    "horizontal": len(
                        state["parser_geometry_observation"].get(
                            "horizontal_signals"
                        )
                        or []
                    ),
                    "vertical": len(
                        state["parser_geometry_observation"].get(
                            "vertical_signals"
                        )
                        or []
                    ),
                    "vector_lines_only_for_certification": True,
                    "rect_edges_diagnostic_only": True,
                },
                "regional_issues": sum(
                    len(assembly.get("regional_issues") or [])
                    for assembly in assemblies
                ),
                "model_invented_values_total": (
                    materialization.get("model_invented_values_total")
                    if isinstance(materialization, dict)
                    else 0
                ),
                "omitted_candidates": len(
                    materialization.get("omitted_candidate_ids") or []
                )
                if isinstance(materialization, dict)
                else 0,
                "valid_distinct_grid_count": first.get(
                    "valid_distinct_grid_count"
                ),
                "solver_search_complete": first.get("solver_search_complete"),
                "uniqueness_proven": first.get("uniqueness_proven"),
                "result_checksum": first.get("result_checksum"),
            }
        )

    terminal_seal = {
        STRUCTURAL_CASES[key]: {
            "terminal_status": results[key]["terminal_status"],
            "result_checksum": results[key]["result_checksum"],
        }
        for key in TARGET_KEYS
    }
    terminal_seal_hash = sha256_json(terminal_seal)

    reference_scores: dict[str, dict[str, Any]] = {}
    reference_sha256 = None
    reference_status = "not_supplied"
    if args.reference:
        reference, reference_sha256 = _load_json(
            Path(args.reference).resolve(), dict, "reference"
        )
        reference_status = str(reference.get("human_review_status") or "unknown")
        if reference.get("pdf_sha256") != pdf_sha256:
            raise ProofError("structural_repair_reference_pdf_mismatch")
        reference_by_key = {
            str(item.get("table_key") or ""): item
            for item in reference.get("tables") or []
            if isinstance(item, dict)
        }
        if not set(TARGET_KEYS) <= set(reference_by_key):
            raise ProofError("structural_repair_reference_target_set_incomplete")
        for key in TARGET_KEYS:
            reference_scores[key] = _score_binding(
                reference_by_key[key],
                accepted_bindings.get(key),
                states[key]["visual_package"],
            )
        if terminal_seal_hash != sha256_json(terminal_seal):
            raise ProofError("structural_repair_reference_changed_terminal")

    safe_by_case = {item["case"]: item for item in safe_tables}
    for key in TARGET_KEYS:
        safe_by_case[STRUCTURAL_CASES[key]]["diagnostic_reference_score"] = (
            reference_scores.get(key) or _unavailable_score()
        )
    accepted_count = sum(
        item["certification_status"] == "accepted_unique_consensus"
        for item in safe_tables
    )
    reference_exact_count = sum(
        _object(item.get("diagnostic_reference_score")).get("all_cells_exact")
        is True
        and _object(item.get("diagnostic_reference_score")).get("headers_exact")
        is True
        for item in safe_tables
    )
    overall = (
        "BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_THREE_TABLE_GOAL_MET"
        if accepted_count == 3
        and (not args.reference or reference_exact_count == 3)
        else "BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_PARTIAL"
    )
    safe = {
        "schema_version": SAFE_SCHEMA,
        "source_revision": _git_revision(),
        "prototype_source": _source_state(),
        "pdf_sha256": pdf_sha256,
        "reference_status": reference_status,
        "reference_is_provisional": bool(args.reference),
        "reference_sha256": reference_sha256,
        "reference_access": {
            "accessed_after_all_terminals_sealed": bool(args.reference),
            "terminal_seal_hash_before_scoring": terminal_seal_hash,
            "reference_used_by_solver": False,
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
        "execution_path": {
            "parser_value_role": "immutable_raw_word_atoms_and_provenance_only",
            "parser_geometry_role": (
                "raw_vector_lines_for_boundary_and_span_certification"
            ),
            "vlm_role": "visual_topology_without_parser_grid",
            "assembler_role": (
                "deterministic_geometry_calibration_span_adjudication_and_atom_binding"
            ),
            "solver_role": "strict_final_constraint_auditor",
            "legacy_compactor_used": False,
            "legacy_window_planner_used": False,
            "legacy_structure_validator_used": False,
            "nearest_cell_fallback_used": False,
            "value_repair_allowed": False,
            "rect_edges_used_for_certification": False,
            "geometry_ambiguity_policy": "typed_block_without_guessing",
        },
        "tables": safe_tables,
        "terminal_counts": dict(
            sorted(Counter(item["certification_status"] for item in safe_tables).items())
        ),
        "goal_metrics": {
            "target_tables": 3,
            "accepted_unique_consensus": accepted_count,
            "reference_exact_tables": reference_exact_count,
            "all_atoms_exactly_once_tables": sum(
                item["all_atoms_exactly_once"] is True for item in safe_tables
            ),
            "invented_values_total": sum(
                int(item["model_invented_values_total"] or 0)
                for item in safe_tables
            ),
            "repeatability_passed_tables": sum(
                item["repeatability_passed"] is True for item in safe_tables
            ),
        },
        "journal": {
            "entries": len(journal),
            "expected_entries": len(TARGET_KEYS) * len(ATTEMPTS),
            "new_provider_generate_calls": sum(
                _object(item.get("safe")).get(
                    "provider_generate_call_performed"
                )
                is True
                for item in journal
            ),
            "hidden_retries": sum(
                _object(item.get("safe")).get("hidden_retry") is True
                for item in journal
            ),
            "provider_failovers": sum(
                _object(item.get("safe")).get("provider_failover") is True
                for item in journal
            ),
        },
        "hard_invariants": {
            "production_pdf_pipeline_changed": False,
            "production_gate2_selection_changed": False,
            "existing_validators_weakened": False,
            "openwebui_core_patched": False,
            "knowledge_rag_vector_used": False,
            "ocr_used": False,
            "raw_values_in_safe_output": False,
            "raw_candidate_or_source_identifiers_in_safe_output": False,
            "private_paths_in_safe_output": False,
            "crop_bytes_in_safe_output": False,
            "provider_responses_in_safe_output": False,
            "reference_answer_used_by_solver": False,
        },
        "readiness": {
            "prototype_execution": "completed",
            "three_table_control": "completed",
            "overall_status": overall,
            "production_gate2_shadow": (
                "not_ready_continuation_and_broader_corpus_pending"
            ),
        },
    }
    _assert_safe_payload(safe)
    private = {
        "schema_version": PRIVATE_SCHEMA,
        "source_revision": safe["source_revision"],
        "inputs": {
            "pdf_path": str(pdf_path),
            "reference_path": str(Path(args.reference).resolve())
            if args.reference
            else None,
            "env_file": str(Path(args.env_file).resolve()),
        },
        "provider_qualification": qualification,
        "provider_config": asdict(provider_config),
        "states": {
            key: {
                "page_number": states[key]["page_number"],
                "parser_ordinal": states[key]["parser_ordinal"],
                "parser_observation": states[key]["parser_observation"],
                "parser_geometry_observation": states[key][
                    "parser_geometry_observation"
                ],
                "visual_package": states[key]["visual_package"],
            }
            for key in TARGET_KEYS
        },
        "journal": journal,
        "tables": table_private,
        "terminal_seal": terminal_seal,
        "terminal_seal_hash": terminal_seal_hash,
        "reference_scores": reference_scores,
    }
    _write_json(private_dir / "evidence.private.json", private)
    _write_json(output_dir / "evidence.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_states(
    package: dict[str, Any],
    *,
    pdf_bytes: bytes,
    pdf_sha256: str,
    dpi: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payloads = [
        item
        for item in package.get("private_normalized_source_payloads") or []
        if isinstance(item, dict)
    ]
    if len(payloads) != 1:
        raise ProofError("structural_repair_normalized_source_scope_invalid")
    source = payloads[0]
    projection = source.get("pdf_text_layer_projection")
    if not isinstance(projection, dict):
        raise ProofError("structural_repair_pdf_projection_missing")
    document_ref = _required_string(source.get("document_ref"), "document_ref")
    pages = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in projection.get("page_inventory") or []
        if isinstance(item, dict)
    }
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in projection.get("bbox_inventory") or []
        if isinstance(item, dict)
    }
    selected: dict[str, dict[str, Any]] = {}
    for candidate in projection.get("table_candidate_inventory") or []:
        if not isinstance(candidate, dict):
            continue
        page_ref = str(candidate.get("page_ref") or "")
        key = f"{pages.get(page_ref, 0)}:{int(candidate.get('parser_ordinal') or 0)}"
        if key in TARGET_KEYS:
            if key in selected:
                raise ProofError(f"structural_repair_target_duplicate:{key}")
            selected[key] = candidate
    if set(selected) != set(TARGET_KEYS):
        raise ProofError("structural_repair_target_set_missing")

    contracts = PdfDualOracleContractFactory().create()
    parser_geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    assembler = PdfTopologyAssemblyFactory(visual_topology=visual).create()
    raster = PdfTableRasterFactory(
        PdfTableRasterConfig(padding_points=0.0)
    ).create()
    states: dict[str, dict[str, Any]] = {}
    for key in TARGET_KEYS:
        candidate = selected[key]
        page_ref = _required_string(candidate.get("page_ref"), f"{key}:page_ref")
        page_number = pages[page_ref]
        table_ref = _required_string(
            candidate.get("table_candidate_ref"), f"{key}:table_ref"
        )
        table_bbox = bboxes.get(str(candidate.get("bbox_ref") or ""))
        if not _valid_bbox(table_bbox):
            raise ProofError(f"structural_repair_table_bbox_invalid:{key}")
        parser_observation = contracts.build_parser_observation_from_word_atoms(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=list(table_bbox),
            pdf_text_layer_projection=projection,
        )
        parser_geometry_observation = parser_geometry.build_observation(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=list(table_bbox),
            pdf_text_layer_projection=projection,
        )
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
            raise ProofError(f"structural_repair_crop_manifest_missing:{key}")
        import base64

        png_bytes = base64.b64decode(
            str(rendered.get("private_png_base64") or ""), validate=True
        )
        if hashlib.sha256(png_bytes).hexdigest() != manifest.get("png_sha256"):
            raise ProofError(f"structural_repair_crop_hash_mismatch:{key}")
        visual_package = visual.build_package(
            parser_observation=parser_observation,
            crop_manifest=manifest,
        )
        states[key] = {
            "page_number": page_number,
            "parser_ordinal": int(candidate.get("parser_ordinal") or 0),
            "parser_observation": parser_observation,
            "parser_geometry_observation": parser_geometry_observation,
            "visual_package": visual_package,
            "png_bytes": png_bytes,
            "assembler": assembler,
        }
    return states, projection


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
        raise ProofError("openwebui_live_credentials_missing")
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "")
    if not token:
        raise ProofError("openwebui_live_token_missing")
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


def _score_binding(
    reference: dict[str, Any], binding: Any, package: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(binding, dict):
        return _unavailable_score()
    rows = int(binding.get("row_count") or 0)
    columns = int(binding.get("column_count") or 0)
    dictionary = _object(package.get("private_candidate_dictionary"))
    predicted = [["" for _ in range(columns)] for _ in range(rows)]
    for row in binding.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row_index = int(row.get("row_ordinal") or 0) - 1
        for column_index, cell in enumerate(row.get("cells") or []):
            if 0 <= row_index < rows and column_index < columns and isinstance(cell, list):
                predicted[row_index][column_index] = " ".join(
                    str(_object(dictionary.get(candidate_id)).get("exact_source_span") or "")
                    for candidate_id in cell
                )
    expected = reference.get("cells") or []
    height = max(len(expected), len(predicted))
    width = max(
        max((len(row) for row in expected if isinstance(row, list)), default=0),
        max((len(row) for row in predicted), default=0),
    )
    pairs = []
    for row in range(height):
        for column in range(width):
            left = (
                expected[row][column]
                if row < len(expected)
                and isinstance(expected[row], list)
                and column < len(expected[row])
                else ""
            )
            right = (
                predicted[row][column]
                if row < len(predicted) and column < len(predicted[row])
                else ""
            )
            pairs.append((_normalize(left), _normalize(right)))
    return {
        "available": True,
        "structure_exact": rows == int(reference.get("rows") or 0)
        and columns == int(reference.get("columns") or 0),
        "headers_exact": len(binding.get("header_rows") or [])
        == int(reference.get("header_rows") or 0),
        "cells_exact": sum(left == right for left, right in pairs),
        "cells_total": len(pairs),
        "all_cells_exact": bool(pairs and all(left == right for left, right in pairs)),
        "hallucinated_nonempty": sum(not left and bool(right) for left, right in pairs),
        "omitted_nonempty": sum(bool(left) and not right for left, right in pairs),
    }


def _unavailable_score() -> dict[str, Any]:
    return {
        "available": False,
        "structure_exact": False,
        "headers_exact": False,
        "cells_exact": 0,
        "cells_total": 0,
        "all_cells_exact": False,
        "hallucinated_nonempty": 0,
        "omitted_nonempty": 0,
    }


def _assert_safe_payload(value: Any) -> None:
    def walk(current: Any) -> None:
        if isinstance(current, dict):
            forbidden = set(str(key) for key in current) & FORBIDDEN_SAFE_KEYS
            if forbidden:
                raise ProofError(
                    "structural_repair_safe_forbidden_key:"
                    + sorted(forbidden)[0]
                )
            for item in current.values():
                walk(item)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str):
            if re.search(r"(?:[A-Za-z]:\\|/Users/|/home/|\\Users\\)", current):
                raise ProofError("structural_repair_safe_private_path")

    walk(value)


def _read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _load_json(path: Path, expected_type: type, subject: str) -> tuple[Any, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_strict_pairs(subject),
            parse_constant=lambda item: (_raise_nonfinite(subject, item)),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProofError(f"structural_repair_json_invalid:{subject}") from exc
    if not isinstance(value, expected_type):
        raise ProofError(f"structural_repair_json_root_invalid:{subject}")
    return value, hashlib.sha256(raw).hexdigest()


def _strict_pairs(subject: str):
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ProofError(
                    f"structural_repair_json_duplicate_key:{subject}:{key}"
                )
            result[key] = value
        return result

    return pairs


def _raise_nonfinite(subject: str, value: str) -> Any:
    raise ProofError(f"structural_repair_json_nonfinite:{subject}:{value}")


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


def _source_state() -> dict[str, Any]:
    checksums = {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in SOURCE_FILES.items()
    }
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    )
    return {**checksums, "worktree_dirty": bool(status.strip())}


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def _required_string(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProofError(f"structural_repair_required_string:{subject}")
    return value


def _valid_bbox(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and float(value[2]) > float(value[0])
        and float(value[3]) > float(value[1])
    )


def _safe_code(value: Any) -> str | None:
    if value is None:
        return None
    rendered = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return rendered[:96] or "unknown_failure"


def _normalize(value: Any) -> str:
    rendered = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(rendered.split()).strip()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
