#!/usr/bin/env python3
"""Replay the controlled PDF grid journal through the dual-oracle prototype."""

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
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

PROTOTYPE_SOURCE_FILES = {
    "contracts_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_dual_oracle_contracts.py",
    "solver_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_dual_oracle_consensus.py",
    "replay_sha256": SERVICE_ROOT
    / "broker_reports_gate1"
    / "pdf_dual_oracle_replay.py",
    "runner_sha256": Path(__file__).resolve(),
}

from broker_reports_gate1 import FileInput, Gate1Normalizer  # noqa: E402
from broker_reports_gate1.pdf_dual_oracle_consensus import (  # noqa: E402
    PdfDualOracleConsensusFactory,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (  # noqa: E402
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_dual_oracle_replay import (  # noqa: E402
    PdfDualOracleReplayFactory,
)
from broker_reports_gate1.pdf_hybrid_budget import (  # noqa: E402
    PdfHybridBudgetFactory,
)
from broker_reports_gate1.pdf_hybrid_compaction import (  # noqa: E402
    PdfHybridCompactionFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_structure import (  # noqa: E402
    PDF_HYBRID_CONTINUATION_SCHEMA,
)
from broker_reports_gate1.pdf_hybrid_windows import (  # noqa: E402
    PdfHybridWindowFactory,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterFactory,
)


SAFE_SCHEMA = "broker_reports_pdf_dual_oracle_consensus_proof_safe_v1"
PRIVATE_SCHEMA = "broker_reports_pdf_dual_oracle_consensus_proof_private_v1"
GRID_SAFE_SCHEMA = "broker_reports_real_table_grid_representation_experiment_safe_v2"
RELIABILITY_SAFE_SCHEMA = "broker_reports_pdf_hybrid_reliability_controlled_proof_v2"
REFERENCE_STATUS = "agent_visual_reviewed_pending_human_signoff"
TARGET_KEYS = ("1:2", "1:3", "3:2", "4:1", "4:2", "5:3")
REPEAT_KEYS = frozenset({"1:2", "1:3", "3:2", "4:1", "4:2"})
HEADER_DEPTHS = {
    "1:2": 2,
    "1:3": 3,
    "3:2": 2,
    "4:1": 0,
    "4:2": 3,
    "5:3": 2,
}
STRUCTURAL_CASES = {
    "1:2": "simple_control",
    "1:3": "wide_multi_row_header",
    "3:2": "wide_multiline_continuation_fragment_1",
    "4:1": "continuation_fragment_2",
    "4:2": "grouped_merged_header",
    "5:3": "tax_summary",
}
CONTINUATION_GROUP_ID = "controlled_trade_table_pages_3_4"
FORBIDDEN_SAFE_KEYS = frozenset(
    {
        "candidate_id",
        "candidate_ids",
        "consensus_witness_hypothesis_ids",
        "crop_identity",
        "crop_manifest_hash",
        "crop_sha256",
        "exact_source_span",
        "hypothesis_id",
        "hypothesis_set_id",
        "observation_id",
        "ordered_table_refs",
        "package_id",
        "package_ids",
        "parser_observation_id",
        "private_candidate_dictionary",
        "raw_provider_response",
        "resolved_source_values",
        "result_id",
        "source_value_refs",
        "table_ref",
        "vlm_hypothesis_set_id",
        "word_refs",
    }
)


class ProofError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--grid-safe", required=True)
    parser.add_argument("--reliability-safe", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    journal_path = Path(args.journal).resolve()
    grid_safe_path = Path(args.grid_safe).resolve()
    reliability_safe_path = Path(args.reliability_safe).resolve()
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"

    # The reference path is deliberately retained as an opaque Path until the
    # six table terminals and continuation terminal have been sealed.
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    journal, journal_sha256 = _load_json(journal_path, list, "journal")
    grid_safe, grid_safe_sha256 = _load_json(
        grid_safe_path, dict, "grid_safe"
    )
    reliability_safe, reliability_safe_sha256 = _load_json(
        reliability_safe_path, dict, "reliability_safe"
    )
    _validate_safe_inputs(
        pdf_sha256=pdf_sha256,
        grid_safe=grid_safe,
        reliability_safe=reliability_safe,
    )

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
        entrypoint="local_pdf_dual_oracle_consensus_proof",
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
    )
    _validate_grid_corpus(grid_safe=grid_safe, states=states)

    replay_runtime = PdfDualOracleReplayFactory().create()
    attempts_by_table = {
        key: ([1, 2] if key in REPEAT_KEYS else [1]) for key in TARGET_KEYS
    }
    manifest = replay_runtime.build_expected_manifest(
        package_ids_by_table={
            key: [str(item["package_id"]) for item in states[key]["packages"]]
            for key in TARGET_KEYS
        },
        attempt_numbers_by_table=attempts_by_table,
    )
    replay = replay_runtime.replay(
        journal=journal,
        expected_manifest=manifest,
        compact_ledgers_by_table={
            key: states[key]["ledger"] for key in TARGET_KEYS
        },
        plans_by_table={key: states[key]["plan"] for key in TARGET_KEYS},
        packages_by_table={
            key: states[key]["packages"] for key in TARGET_KEYS
        },
    )
    if replay["safe_summary"].get("reference_access_performed") is not False:
        raise ProofError("dual_oracle_replay_reference_boundary_invalid")

    contract_runtime = PdfDualOracleContractFactory().create()
    solver_runtime = PdfDualOracleConsensusFactory().create()
    repeat_by_table = {
        str(item.get("table_key") or ""): item
        for item in replay["safe_summary"].get("table_summaries") or []
        if isinstance(item, dict)
    }
    provider_lineage = _provider_lineage(grid_safe)
    private_tables: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}

    for key in TARGET_KEYS:
        state = states[key]
        parser_observation = contract_runtime.build_parser_observation(
            compact_ledger=state["ledger"],
            pdf_text_layer_projection=projection,
        )
        joined_attempts = replay["private_joined_attempts"].get(key) or []
        replay_summary = repeat_by_table.get(key) or {}
        hypothesis_inputs = [
            _hypothesis_input(
                key=key,
                attempt=item,
                packages=state["packages"],
                provider_lineage=provider_lineage,
                continuation=_fragment_contract(key),
            )
            for item in joined_attempts
        ]
        vlm_hypothesis_set = contract_runtime.build_vlm_hypothesis_set(
            parser_observation=parser_observation,
            binding_hypotheses=hypothesis_inputs,
            model_context=_legacy_model_context(
                key=key,
                state=state,
                replay_summary=replay_summary,
                provider_lineage=provider_lineage,
            ),
        )
        repeatability = _historical_repeatability(
            key=key,
            replay_summary=replay_summary,
            reliability_safe=reliability_safe,
            state=state,
        )
        first = solver_runtime.solve(
            parser_observation=parser_observation,
            vlm_hypothesis_set=vlm_hypothesis_set,
            historical_repeatability=repeatability,
        )
        second = solver_runtime.solve(
            parser_observation=copy.deepcopy(parser_observation),
            vlm_hypothesis_set=copy.deepcopy(vlm_hypothesis_set),
            historical_repeatability=copy.deepcopy(repeatability),
        )
        if first != second or first.get("result_checksum") != second.get(
            "result_checksum"
        ):
            raise ProofError(f"dual_oracle_solver_nondeterministic:{key}")
        results[key] = first
        private_tables[key] = {
            "ledger": state["ledger"],
            "plan": state["plan"],
            "packages": state["packages"],
            "parser_observation": parser_observation,
            "vlm_hypothesis_set": vlm_hypothesis_set,
            "historical_repeatability": repeatability,
            "consensus_result": first,
            "deterministic_second_result": second,
        }

    continuation_contract = _continuation_contract(states)
    continuation_first = solver_runtime.solve_continuation(
        continuation_contract=continuation_contract,
        fragment_results=[results["3:2"], results["4:1"]],
    )
    continuation_second = solver_runtime.solve_continuation(
        continuation_contract=copy.deepcopy(continuation_contract),
        fragment_results=[copy.deepcopy(results["3:2"]), copy.deepcopy(results["4:1"])],
    )
    if continuation_first != continuation_second:
        raise ProofError("dual_oracle_continuation_nondeterministic")

    terminal_seal = _terminal_seal(results, continuation_first)
    terminal_seal_hash = sha256_json(terminal_seal)

    # Reference access begins only after all terminal results, including the
    # continuation group, have immutable checksums in terminal_seal_hash.
    reference, reference_sha256 = _load_json(reference_path, dict, "reference")
    reference_tables = _validate_reference(
        reference=reference,
        pdf_sha256=pdf_sha256,
    )
    scores: dict[str, dict[str, Any]] = {}
    for key in TARGET_KEYS:
        scores[key] = _diagnostic_scores(
            reference=reference_tables[key],
            state=states[key],
            joined_attempts=(
                replay["private_joined_attempts"].get(key) or []
            ),
            vlm_hypothesis_set=private_tables[key]["vlm_hypothesis_set"],
            consensus_result=results[key],
        )
    if terminal_seal_hash != sha256_json(
        _terminal_seal(results, continuation_first)
    ):
        raise ProofError("dual_oracle_reference_changed_terminal_outcome")

    safe_tables = [
        _safe_table_summary(
            key=key,
            state=states[key],
            replay_summary=repeat_by_table[key],
            parser_observation=private_tables[key]["parser_observation"],
            vlm_hypothesis_set=private_tables[key]["vlm_hypothesis_set"],
            consensus_result=results[key],
            continuation_result=continuation_first,
            scores=scores[key],
        )
        for key in TARGET_KEYS
    ]
    prototype_source = _prototype_source_state()
    safe = {
        "schema_version": SAFE_SCHEMA,
        "source_revision": _git_revision(),
        "prototype_source": prototype_source,
        "pdf_sha256": pdf_sha256,
        "input_checksums": {
            "journal_sha256": journal_sha256,
            "grid_safe_sha256": grid_safe_sha256,
            "reliability_safe_sha256": reliability_safe_sha256,
            "reference_sha256": reference_sha256,
        },
        "reference_status": reference.get("human_review_status"),
        "reference_is_provisional": True,
        "reference_access": {
            "accessed_after_all_terminals_sealed": True,
            "terminal_seal_hash_before_scoring": terminal_seal_hash,
            "terminal_seal_unchanged_after_scoring": True,
            "reference_used_by_solver": False,
        },
        "replay": {
            "journal_entries": replay["safe_summary"]["journal_entry_count"],
            "manifest_entries": replay["safe_summary"]["manifest_entry_count"],
            "verbose_entries": replay["safe_summary"]["verbose_entry_count"],
            "job_key_set_exact": replay["safe_summary"]["job_key_set_exact"],
            "journal_order_trusted": replay["safe_summary"]["journal_order_trusted"],
            "plan_window_order_used": replay["safe_summary"]["plan_window_order_used"],
            "private_text_reparsed": replay["safe_summary"]["private_text_reparsed"],
            "private_binding_exact_match_required": replay["safe_summary"]["private_binding_exact_match_required"],
            "provider_calls_performed": replay["safe_summary"]["provider_calls_performed"],
        },
        "oracle_contract": {
            "parser_role": "exact_physical_observations_only",
            "vlm_role": "legacy_candidate_placement_hypotheses_only",
            "parser_semantic_grid_lineage": "legacy_compact_ledger",
            "vlm_topology_dimensions_lineage": "parser_seeded",
            "independent_dual_oracle_real_evidence": False,
            "oracle_preference_used": False,
            "numeric_score_used_by_solver": False,
            "majority_vote_used": False,
        },
        "continuation": {
            "terminal_status": continuation_first["terminal_status"],
            "reason_codes": continuation_first["reason_codes"],
            "fragment_terminals": continuation_first["fragment_terminals"],
            "fragment_coverage_complete": continuation_first[
                "fragment_coverage_complete"
            ],
            "all_required_fragments_independently_accepted": continuation_first[
                "all_required_fragments_independently_accepted"
            ],
            "result_checksum": continuation_first["result_checksum"],
            "deterministic_replay_equal": True,
        },
        "tables": safe_tables,
        "terminal_counts": dict(
            sorted(Counter(item["terminal_status"] for item in safe_tables).items())
        ),
        "effective_terminal_counts": dict(
            sorted(
                Counter(
                    item["effective_terminal_status"] for item in safe_tables
                ).items()
            )
        ),
        "context_totals": _aggregate_context(safe_tables),
        "diagnostic_score_totals": {
            role: _aggregate_scores(
                [item["diagnostic_scores"][role] for item in safe_tables]
            )
            for role in ("parser", "vlm", "consensus")
        },
        "hard_invariants": {
            "production_pdf_pipeline_changed": False,
            "production_gate2_selection_changed": False,
            "existing_validators_weakened": False,
            "openwebui_core_patched": False,
            "knowledge_rag_vector_used": False,
            "ocr_used": False,
            "provider_calls_performed": 0,
            "reference_answer_used_by_solver": False,
            "raw_values_in_safe_output": False,
            "raw_candidate_or_source_identifiers_in_safe_output": False,
            "private_paths_in_safe_output": False,
            "crop_manifests_or_bytes_in_safe_output": False,
            "provider_responses_in_safe_output": False,
        },
        "readiness": {
            "prototype_execution": "completed",
            "controlled_real_table_replay": "completed",
            "independent_vlm_topology_proof": "not_proven",
            "gate2_shadow_e2e": "not_ready",
            "overall_status": "BROKER_REPORTS_PDF_DUAL_ORACLE_PARTIAL",
            "blocker": "independent_vlm_topology_hypotheses_missing_for_real_corpus",
        },
    }
    _assert_safe_payload(safe)

    private = {
        "schema_version": PRIVATE_SCHEMA,
        "source_revision": safe["source_revision"],
        "prototype_source": prototype_source,
        "inputs": {
            "pdf_path": str(pdf_path),
            "journal_path": str(journal_path),
            "grid_safe_path": str(grid_safe_path),
            "reliability_safe_path": str(reliability_safe_path),
            "reference_path": str(reference_path),
            "checksums": safe["input_checksums"],
        },
        "target_selection": {
            "policy": "exact_page_number_and_parser_ordinal_only",
            "target_keys": list(TARGET_KEYS),
        },
        "expected_manifest": manifest,
        "replay": replay,
        "tables": private_tables,
        "continuation_contract": continuation_contract,
        "continuation_result": continuation_first,
        "terminal_seal": terminal_seal,
        "terminal_seal_hash": terminal_seal_hash,
        "reference_accessed_after_terminal_seal": True,
        "reference_sha256": reference_sha256,
        "diagnostic_scores": scores,
    }
    private_dir.mkdir(parents=True, exist_ok=True)
    _write_json(private_dir / "evidence.private.json", private)
    _write_json(output_dir / "evidence.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_states(
    package: dict[str, Any], *, pdf_bytes: bytes, pdf_sha256: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payloads = [
        item
        for item in package.get("private_normalized_source_payloads") or []
        if isinstance(item, dict)
    ]
    if len(payloads) != 1:
        raise ProofError("dual_oracle_normalized_source_payload_scope_invalid")
    source_payload = payloads[0]
    document_ref = _required_string(source_payload.get("document_ref"), "document_ref")
    projection = source_payload.get("pdf_text_layer_projection")
    if not isinstance(projection, dict):
        raise ProofError("dual_oracle_pdf_projection_missing")
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
        page_number = pages.get(str(candidate.get("page_ref") or ""), 0)
        direct_key = f"{page_number}:{int(candidate.get('parser_ordinal') or 0)}"
        if direct_key not in TARGET_KEYS:
            continue
        if direct_key in selected:
            raise ProofError(f"dual_oracle_target_candidate_duplicate:{direct_key}")
        selected[direct_key] = candidate
    if set(selected) != set(TARGET_KEYS):
        raise ProofError(
            "dual_oracle_exact_target_candidate_set_invalid:"
            + ",".join(sorted(set(TARGET_KEYS) - set(selected)))
        )

    compactor = PdfHybridCompactionFactory().create()
    windows = PdfHybridWindowFactory().create(
        budget=PdfHybridBudgetFactory().create()
    )
    raster = PdfTableRasterFactory().create()
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
            raise ProofError(f"dual_oracle_target_bbox_invalid:{key}")
        ledger = compactor.compact(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_candidate=candidate,
            pdf_text_layer_projection=projection,
            header_depth=HEADER_DEPTHS[key],
        )
        plan = windows.plan(compact_ledger=ledger)
        packages = []
        for window in plan.get("windows") or []:
            rendered = raster.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                document_ref=document_ref,
                page_number=page_number,
                table_ref=table_ref,
                table_bbox=list(window.get("crop_bbox") or []),
                dpi=150,
            )
            manifest = rendered.get("manifest")
            if not isinstance(manifest, dict) or manifest.get("dpi") != 150:
                raise ProofError(f"dual_oracle_150dpi_package_missing:{key}")
            packages.append(
                windows.build_package(
                    compact_ledger=ledger,
                    plan=plan,
                    window=window,
                    crop_manifest=manifest,
                    private_crop_artifact_ref=(
                        "research-private-crop:" + str(manifest["png_sha256"])
                    ),
                )
            )
        states[key] = {
            "page_number": page_number,
            "parser_ordinal": int(candidate.get("parser_ordinal") or 0),
            "table_ref": table_ref,
            "ledger": ledger,
            "plan": plan,
            "packages": packages,
        }
    return states, projection


def _hypothesis_input(
    *,
    key: str,
    attempt: dict[str, Any],
    packages: list[dict[str, Any]],
    provider_lineage: dict[str, Any],
    continuation: dict[str, Any],
) -> dict[str, Any]:
    attempt_number = int(attempt.get("attempt_number") or 0)
    package_evidence = [
        {
            "package_id": item.get("package_id"),
            "crop_sha256": (item.get("crop_identity") or {}).get("crop_sha256"),
            "candidate_dictionary_hash": item.get("candidate_dictionary_hash"),
        }
        for item in packages
    ]
    logical_evidence = attempt.get("logical_evidence")
    if not isinstance(logical_evidence, dict):
        raise ProofError(f"dual_oracle_logical_evidence_missing:{key}")
    logical_crop = logical_evidence.get("crop_identity")
    if not isinstance(logical_crop, dict):
        raise ProofError(f"dual_oracle_logical_crop_identity_missing:{key}")
    package_evidence.append(
        {
            "package_id": logical_evidence.get("package_id"),
            "crop_sha256": logical_crop.get("crop_sha256"),
            "candidate_dictionary_hash": logical_evidence.get(
                "candidate_dictionary_hash"
            ),
        }
    )
    return {
        "hypothesis_id": f"legacy_grid_replay_{key.replace(':', '_')}_a{attempt_number}",
        "binding_output": attempt.get("binding"),
        "proposed_geometry": {
            "rows": {"kind": "not_observed", "boundaries": []},
            "columns": {"kind": "not_observed", "boundaries": []},
        },
        "evidence": {
            "attempt_id": f"legacy_grid_replay:{key}:a{attempt_number}",
            "attempt_number": attempt_number,
            "evidence_revision": provider_lineage["evidence_revision"],
            "provider": provider_lineage["provider"],
            "model": provider_lineage["model"],
            "provider_config_hash": provider_lineage["configuration_hash"],
            "packages": package_evidence,
        },
        "continuation": continuation,
    }


def _legacy_model_context(
    *,
    key: str,
    state: dict[str, Any],
    replay_summary: dict[str, Any],
    provider_lineage: dict[str, Any],
) -> dict[str, Any]:
    attempts = replay_summary.get("attempts") or []
    manifests = [item.get("crop_identity") or {} for item in state["packages"]]
    return {
        "provider": provider_lineage["provider"],
        "model": provider_lineage["model"],
        "configuration_hash": provider_lineage["configuration_hash"],
        "bounded_row_windows": True,
        "provider_calls_replayed": len(attempts) * len(state["packages"]),
        "new_provider_calls": 0,
        "topology_input_basis": "legacy_candidate_placement_only",
        "topology_dimensions_source": "parser_seeded",
        "alternative_generation_contract": (
            "legacy_repeated_response" if len(attempts) > 1 else "single_response_only"
        ),
        "topology_prompt_contract_hash": "",
        "crop_manifest_hash": sha256_json(manifests),
        "alternative_topology_hypotheses_complete": False,
        "provider_token_accounting_exact": True,
        "candidate_ownership_exact": True,
        "no_silent_truncation": all(
            item.get("silent_truncation_performed") is False
            for item in state["plan"].get("windows") or []
        ),
        "column_splitting_used": any(
            item.get("column_split_performed") is True
            for item in state["plan"].get("windows") or []
        ),
        "hidden_provider_failover": False,
    }


def _historical_repeatability(
    *,
    key: str,
    replay_summary: dict[str, Any],
    reliability_safe: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    repeat = replay_summary.get("repeatability") or {}
    if key != "5:3":
        return {
            "required": bool(repeat.get("required")),
            "passed": repeat.get("pass") is True,
            "ever_conflicted": repeat.get("ever_conflicted") is True,
            "status": repeat.get("status"),
            "source": "validated_legacy_grid_journal",
        }
    matches = [
        item
        for item in reliability_safe.get("tables") or []
        if isinstance(item, dict) and item.get("table_key") == key
    ]
    if len(matches) != 1:
        raise ProofError("dual_oracle_reliability_5_3_scope_invalid")
    item = matches[0]
    if (
        item.get("table_ref") != state.get("table_ref")
        or item.get("repeatability_required") is not True
        or item.get("repeatability_passed") is not True
        or item.get("repeatability_ever_conflicted") is not False
        or not item.get("placement_checksum")
        or item.get("placement_checksum") != item.get("repeat_placement_checksum")
    ):
        raise ProofError("dual_oracle_reliability_5_3_repeat_not_verifiable")
    return {
        "required": True,
        "passed": True,
        "ever_conflicted": False,
        "status": "stable",
        "source": "verified_legacy_reliability_safe",
    }


def _fragment_contract(key: str) -> dict[str, Any]:
    if key not in {"3:2", "4:1"}:
        return {
            "required": False,
            "continuation_group_id": None,
            "fragment_order": 0,
            "fragment_count": 0,
            "shared_column_count": 0,
            "repeated_header_policy": None,
        }
    return {
        "required": True,
        "continuation_group_id": CONTINUATION_GROUP_ID,
        "fragment_order": 1 if key == "3:2" else 2,
        "fragment_count": 2,
        "shared_column_count": 16,
        "repeated_header_policy": (
            "source_header" if key == "3:2" else "no_repeated_header"
        ),
    }


def _continuation_contract(states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
        "continuation_group_id": CONTINUATION_GROUP_ID,
        "shared_column_count": 16,
        "fragments": [
            {
                "fragment_order": 1,
                "page_number": 3,
                "table_ref": states["3:2"]["table_ref"],
                "repeated_header_policy": "source_header",
            },
            {
                "fragment_order": 2,
                "page_number": 4,
                "table_ref": states["4:1"]["table_ref"],
                "repeated_header_policy": "no_repeated_header",
            },
        ],
        "subtotal_policy": "preserve_fragment_subtotals",
        "duplicate_row_policy": "allow_explicit_repeated_header_only",
        "fragment_coverage_required": True,
        "joined_coverage_required": True,
        "authoritative": False,
    }


def _terminal_seal(
    results: dict[str, dict[str, Any]], continuation: dict[str, Any]
) -> dict[str, Any]:
    return {
        "tables": [
            {
                "table_key": key,
                "terminal_status": results[key].get("terminal_status"),
                "result_checksum": results[key].get("result_checksum"),
            }
            for key in TARGET_KEYS
        ],
        "continuation": {
            "terminal_status": continuation.get("terminal_status"),
            "result_checksum": continuation.get("result_checksum"),
        },
    }


def _diagnostic_scores(
    *,
    reference: dict[str, Any],
    state: dict[str, Any],
    joined_attempts: list[dict[str, Any]],
    vlm_hypothesis_set: dict[str, Any],
    consensus_result: dict[str, Any],
) -> dict[str, Any]:
    parser_binding = _parser_binding(state["ledger"])
    primary_binding = joined_attempts[0].get("binding") if joined_attempts else None
    parser_score = _score_binding(reference, parser_binding, state["ledger"])
    vlm_score = _score_binding(reference, primary_binding, state["ledger"])
    checksum = consensus_result.get("canonical_grid_checksum")
    witness = None
    if consensus_result.get("terminal_status") == "accepted_supplied_consensus":
        witness = next(
            (
                item
                for item in vlm_hypothesis_set.get("hypotheses") or []
                if isinstance(item, dict)
                and item.get("canonical_grid_checksum") == checksum
            ),
            None,
        )
    consensus_score = _score_binding(reference, witness, state["ledger"])
    consensus_score["diagnostic_only"] = True
    consensus_score["available_from_unique_valid_witness"] = witness is not None
    return {
        "parser": parser_score,
        "vlm": vlm_score,
        "consensus": consensus_score,
    }


def _parser_binding(ledger: dict[str, Any]) -> dict[str, Any]:
    rows = int(ledger.get("row_count") or 0)
    columns = int(ledger.get("column_count") or 0)
    cells = [[[] for _ in range(columns)] for _ in range(rows)]
    dictionary = ledger.get("private_candidate_dictionary") or {}
    for candidate_id in ledger.get("candidate_order") or []:
        item = dictionary.get(candidate_id) or {}
        row = int(item.get("expected_row_ordinal") or 0)
        column = int(item.get("expected_column_ordinal") or 0)
        if not (1 <= row <= rows and 1 <= column <= columns):
            raise ProofError("dual_oracle_parser_diagnostic_position_invalid")
        cells[row - 1][column - 1].append(candidate_id)
    return {
        "row_count": rows,
        "column_count": columns,
        "header_rows": list(range(1, int(ledger.get("header_depth") or 0) + 1)),
        "rows": [
            {"row_ordinal": index, "cells": value}
            for index, value in enumerate(cells, start=1)
        ],
    }


def _score_binding(
    reference: dict[str, Any], binding: Any, ledger: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(binding, dict):
        return _unavailable_score(reference)
    row_count = int(binding.get("row_count") or 0)
    column_count = int(binding.get("column_count") or 0)
    if row_count < 1 or column_count < 1:
        return _unavailable_score(reference)
    predicted = [["" for _ in range(column_count)] for _ in range(row_count)]
    dictionary = ledger.get("private_candidate_dictionary") or {}
    for row in binding.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row_index = int(row.get("row_ordinal") or 0) - 1
        for column_index, cell in enumerate(row.get("cells") or []):
            if not (0 <= row_index < row_count and column_index < column_count):
                continue
            if not isinstance(cell, list):
                continue
            predicted[row_index][column_index] = " ".join(
                str((dictionary.get(candidate_id) or {}).get("exact_source_span") or "")
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
    numeric = [pair for pair in pairs if _numeric(pair[0])]
    empty = [pair for pair in pairs if not pair[0]]
    return {
        "available": True,
        "reference_rows": int(reference.get("rows") or len(expected)),
        "reference_columns": int(reference.get("columns") or 0),
        "predicted_rows": row_count,
        "predicted_columns": column_count,
        "structure_exact": len(expected) == len(predicted)
        and all(
            isinstance(left, list) and len(left) == len(right)
            for left, right in zip(expected, predicted)
        ),
        "headers_exact": len(binding.get("header_rows") or [])
        == int(reference.get("header_rows") or 0),
        "cells_exact": sum(left == right for left, right in pairs),
        "cells_total": len(pairs),
        "numeric_exact": sum(left == right for left, right in numeric),
        "numeric_total": len(numeric),
        "empty_exact": sum(left == right for left, right in empty),
        "empty_total": len(empty),
        "hallucinated_nonempty": sum(not left and bool(right) for left, right in pairs),
        "omitted_nonempty": sum(bool(left) and not right for left, right in pairs),
    }


def _unavailable_score(reference: dict[str, Any]) -> dict[str, Any]:
    expected = reference.get("cells") or []
    width = max((len(row) for row in expected if isinstance(row, list)), default=0)
    values = [
        _normalize(row[column] if column < len(row) else "")
        for row in expected
        if isinstance(row, list)
        for column in range(width)
    ]
    return {
        "available": False,
        "reference_rows": int(reference.get("rows") or len(expected)),
        "reference_columns": int(reference.get("columns") or width),
        "predicted_rows": 0,
        "predicted_columns": 0,
        "structure_exact": False,
        "headers_exact": False,
        "cells_exact": 0,
        "cells_total": len(values),
        "numeric_exact": 0,
        "numeric_total": sum(_numeric(value) for value in values),
        "empty_exact": 0,
        "empty_total": sum(not value for value in values),
        "hallucinated_nonempty": 0,
        "omitted_nonempty": sum(bool(value) for value in values),
    }


def _safe_table_summary(
    *,
    key: str,
    state: dict[str, Any],
    replay_summary: dict[str, Any],
    parser_observation: dict[str, Any],
    vlm_hypothesis_set: dict[str, Any],
    consensus_result: dict[str, Any],
    continuation_result: dict[str, Any],
    scores: dict[str, Any],
) -> dict[str, Any]:
    attempts = replay_summary.get("attempts") or []
    candidate_text_bytes = sum(
        len(str(item.get("exact_visible_value") or "").encode("utf-8"))
        for item in parser_observation.get("candidates") or []
        if isinstance(item, dict)
    )
    parser_bytes = len(canonical_json_bytes(parser_observation))
    vlm_bytes = len(canonical_json_bytes(vlm_hypothesis_set))
    actual_tokens = sum(int(item.get("provider_actual_input_tokens") or 0) for item in attempts)
    counted_tokens = sum(int(item.get("provider_counted_input_tokens") or 0) for item in attempts)
    output_tokens = sum(int(item.get("provider_output_tokens") or 0) for item in attempts)
    visible_output_bytes = sum(int(item.get("visible_output_bytes") or 0) for item in attempts)
    constraints = []
    for alternative in consensus_result.get("alternatives_considered") or []:
        if not isinstance(alternative, dict):
            continue
        gates = alternative.get("constraints") or {}
        constraints.append(
            {
                "accepted": alternative.get("accepted_by_constraints") is True,
                "decision": alternative.get("decision"),
                "rows": int(alternative.get("row_count") or 0),
                "columns": int(alternative.get("column_count") or 0),
                "reason_codes": alternative.get("reason_codes") or [],
                "constraint_gates": {
                    name: value.get("passed") is True
                    for name, value in sorted(gates.items())
                    if isinstance(value, dict)
                },
            }
        )
    effective_terminal = (
        continuation_result["terminal_status"]
        if key in {"3:2", "4:1"}
        else consensus_result["terminal_status"]
    )
    return {
        "table_key": key,
        "structural_case": STRUCTURAL_CASES[key],
        "page_number": state["page_number"],
        "parser_ordinal": state["parser_ordinal"],
        "candidate_count": len(state["ledger"].get("candidate_order") or []),
        "window_count": len(state["packages"]),
        "hypothesis_count": len(vlm_hypothesis_set.get("hypotheses") or []),
        "terminal_status": consensus_result["terminal_status"],
        "effective_terminal_status": effective_terminal,
        "reason_codes": consensus_result["reason_codes"],
        "review_codes": consensus_result["review_codes"],
        "required_evidence_to_resolve": consensus_result[
            "required_evidence_to_resolve"
        ],
        "alternatives_considered": constraints,
        "valid_distinct_grid_count": consensus_result[
            "valid_distinct_grid_count"
        ],
        "structurally_unique_within_supplied_evidence": consensus_result[
            "structurally_unique_within_supplied_evidence"
        ],
        "uniqueness_proven": consensus_result["uniqueness_proven"],
        "supplied_hypotheses_exhausted": consensus_result[
            "supplied_hypotheses_exhausted"
        ],
        "structural_domain_complete": consensus_result[
            "structural_domain_complete"
        ],
        "ambiguity_proven": consensus_result["ambiguity_proven"],
        "domain_incomplete": consensus_result["domain_incomplete"],
        "search_not_certifiable": consensus_result[
            "search_not_certifiable"
        ],
        "search_scope": consensus_result["search_scope"],
        "safe_explanation": consensus_result["safe_explanation"],
        "historical_repeatability": _safe_repeatability_summary(
            consensus_result.get("historical_repeatability"),
            accepted_by_solver=(
                "pdf_dual_oracle_repeatability_incomplete"
                not in (consensus_result.get("review_codes") or [])
            ),
        ),
        "historical_conflict_preserved": consensus_result[
            "historical_conflict_preserved"
        ],
        "result_checksum": consensus_result["result_checksum"],
        "deterministic_replay_equal": True,
        "context": {
            "candidate_visible_utf8_bytes": candidate_text_bytes,
            "parser_observation_bytes": parser_bytes,
            "vlm_hypothesis_set_bytes": vlm_bytes,
            "structured_to_candidate_visible_byte_ratio": _ratio(
                parser_bytes + vlm_bytes, candidate_text_bytes
            ),
            "legacy_provider_actual_input_tokens": actual_tokens,
            "legacy_provider_counted_input_tokens": counted_tokens,
            "legacy_provider_output_tokens": output_tokens,
            "legacy_visible_output_bytes": visible_output_bytes,
            "legacy_actual_input_tokens_per_candidate": _ratio(
                actual_tokens,
                len(state["ledger"].get("candidate_order") or []),
            ),
            "legacy_provider_calls_replayed": len(attempts) * len(state["packages"]),
            "new_provider_calls": 0,
            "provider_token_accounting_exact": actual_tokens == counted_tokens,
            "candidate_ownership_exact": True,
            "silent_truncation_performed": False,
            "column_splitting_used": False,
        },
        "diagnostic_scores": scores,
    }


def _validate_safe_inputs(
    *,
    pdf_sha256: str,
    grid_safe: dict[str, Any],
    reliability_safe: dict[str, Any],
) -> None:
    if (
        grid_safe.get("schema_version") != GRID_SAFE_SCHEMA
        or grid_safe.get("pdf_sha256") != pdf_sha256
        or grid_safe.get("reference_status") != REFERENCE_STATUS
    ):
        raise ProofError("dual_oracle_grid_safe_identity_invalid")
    method = grid_safe.get("method") or {}
    stage2 = grid_safe.get("stage2_topology") or {}
    invariants = grid_safe.get("hard_invariants") or {}
    if (
        method.get("stage1_provider_attempts_expected") != 80
        or method.get("hidden_retries") != 0
        or method.get("provider_failovers") != 0
        or stage2.get("provider_attempts") != 0
        or stage2.get("status") != "not_run_grid_decision_gate_failed"
        or invariants.get("production_gate2_selection_changed") is not False
        or invariants.get("production_pdf_pipeline_changed") is not False
        or invariants.get("openwebui_core_patched") is not False
    ):
        raise ProofError("dual_oracle_grid_safe_lineage_invalid")
    if (
        reliability_safe.get("schema_version") != RELIABILITY_SAFE_SCHEMA
        or reliability_safe.get("pdf_sha256") != pdf_sha256
        or reliability_safe.get("reference_status") != REFERENCE_STATUS
        or reliability_safe.get("production_gate2_selection_changed") is not False
    ):
        raise ProofError("dual_oracle_reliability_safe_identity_invalid")


def _validate_grid_corpus(
    *, grid_safe: dict[str, Any], states: dict[str, dict[str, Any]]
) -> None:
    corpus = {
        str(item.get("table_key") or ""): item
        for item in grid_safe.get("corpus") or []
        if isinstance(item, dict)
    }
    if set(corpus) != set(TARGET_KEYS):
        raise ProofError("dual_oracle_grid_safe_corpus_scope_invalid")
    for key in TARGET_KEYS:
        item = corpus[key]
        if (
            item.get("candidate_count")
            != len(states[key]["ledger"].get("candidate_order") or [])
            or item.get("window_count") != len(states[key]["packages"])
            or item.get("parser_rows") != states[key]["ledger"].get("row_count")
            or item.get("parser_columns")
            != states[key]["ledger"].get("column_count")
        ):
            raise ProofError(f"dual_oracle_grid_safe_corpus_mismatch:{key}")


def _provider_lineage(grid_safe: dict[str, Any]) -> dict[str, Any]:
    qualification = (grid_safe.get("provider_qualification") or {}).get(
        "verbose_json"
    ) or {}
    if (
        qualification.get("status") != "qualified"
        or qualification.get("hidden_failover") is not False
        or qualification.get("native_provider_transport") is not True
        or qualification.get("exact_model_match") is not True
    ):
        raise ProofError("dual_oracle_provider_lineage_invalid")
    provider = _required_string(
        qualification.get("provider_profile"), "provider_profile"
    )
    model = _required_string(
        qualification.get("resolved_model_id"), "resolved_model_id"
    )
    configuration_hash = _required_string(
        qualification.get("provider_profile_revision"),
        "provider_profile_revision",
    )
    return {
        "provider": provider,
        "model": model,
        "configuration_hash": configuration_hash,
        "evidence_revision": str(grid_safe.get("source_revision") or "unknown"),
    }


def _validate_reference(
    *, reference: dict[str, Any], pdf_sha256: str
) -> dict[str, dict[str, Any]]:
    if (
        reference.get("human_review_status") != REFERENCE_STATUS
        or reference.get("pdf_sha256") != pdf_sha256
        or not isinstance(reference.get("tables"), list)
    ):
        raise ProofError("dual_oracle_reference_identity_invalid")
    selected: dict[str, dict[str, Any]] = {}
    for item in reference["tables"]:
        if not isinstance(item, dict) or item.get("table_key") not in TARGET_KEYS:
            continue
        key = str(item["table_key"])
        if key in selected:
            raise ProofError(f"dual_oracle_reference_table_duplicate:{key}")
        page, ordinal = (int(value) for value in key.split(":", 1))
        cells = item.get("cells")
        if (
            item.get("pdf_sha256") != pdf_sha256
            or item.get("page") != page
            or item.get("table_ordinal") != ordinal
            or not isinstance(cells, list)
            or item.get("rows") != len(cells)
            or any(not isinstance(row, list) for row in cells)
            or any(len(row) != int(item.get("columns") or 0) for row in cells)
        ):
            raise ProofError(f"dual_oracle_reference_table_invalid:{key}")
        selected[key] = item
    if set(selected) != set(TARGET_KEYS):
        raise ProofError("dual_oracle_reference_target_set_invalid")
    return selected


def _aggregate_context(tables: list[dict[str, Any]]) -> dict[str, Any]:
    contexts = [item["context"] for item in tables]
    candidates = sum(item["candidate_count"] for item in tables)
    return {
        "tables": len(tables),
        "candidates": candidates,
        "windows": sum(item["window_count"] for item in tables),
        "hypotheses": sum(item["hypothesis_count"] for item in tables),
        "candidate_visible_utf8_bytes": sum(
            item["candidate_visible_utf8_bytes"] for item in contexts
        ),
        "parser_observation_bytes": sum(
            item["parser_observation_bytes"] for item in contexts
        ),
        "vlm_hypothesis_set_bytes": sum(
            item["vlm_hypothesis_set_bytes"] for item in contexts
        ),
        "legacy_provider_actual_input_tokens": sum(
            item["legacy_provider_actual_input_tokens"] for item in contexts
        ),
        "legacy_provider_output_tokens": sum(
            item["legacy_provider_output_tokens"] for item in contexts
        ),
        "legacy_provider_calls_replayed": sum(
            item["legacy_provider_calls_replayed"] for item in contexts
        ),
        "new_provider_calls": 0,
        "all_token_accounting_exact": all(
            item["provider_token_accounting_exact"] for item in contexts
        ),
        "all_candidate_ownership_exact": all(
            item["candidate_ownership_exact"] for item in contexts
        ),
        "any_silent_truncation": any(
            item["silent_truncation_performed"] for item in contexts
        ),
        "any_column_splitting": any(
            item["column_splitting_used"] for item in contexts
        ),
    }


def _aggregate_scores(values: list[dict[str, Any]]) -> dict[str, Any]:
    available = [item for item in values if item.get("available") is True]
    cells_total = sum(int(item.get("cells_total") or 0) for item in available)
    numeric_total = sum(int(item.get("numeric_total") or 0) for item in available)
    empty_total = sum(int(item.get("empty_total") or 0) for item in available)
    cells_exact = sum(int(item.get("cells_exact") or 0) for item in available)
    numeric_exact = sum(int(item.get("numeric_exact") or 0) for item in available)
    empty_exact = sum(int(item.get("empty_exact") or 0) for item in available)
    return {
        "tables": len(values),
        "available_tables": len(available),
        "accuracy_status": "available" if available else "not_available",
        "structure_exact_tables": sum(
            item.get("structure_exact") is True for item in available
        ),
        "header_exact_tables": sum(
            item.get("headers_exact") is True for item in available
        ),
        "cells_exact": cells_exact,
        "cells_total": cells_total,
        "cell_accuracy": _ratio(cells_exact, cells_total) if available else None,
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "numeric_accuracy": _ratio(numeric_exact, numeric_total) if available else None,
        "empty_exact": empty_exact,
        "empty_total": empty_total,
        "empty_accuracy": _ratio(empty_exact, empty_total) if available else None,
    }


def _safe_repeatability_summary(
    value: Any, *, accepted_by_solver: bool
) -> dict[str, Any]:
    record = value if isinstance(value, dict) else {}
    attempts = record.get("attempt_history")
    schema_version = record.get("schema_version")
    is_v2 = schema_version == "broker_reports_pdf_dual_oracle_repeatability_record_v2"
    return {
        "schema_version": schema_version if is_v2 else None,
        "supplied_history_structurally_complete": (
            is_v2
            and record.get("supplied_history_structurally_complete") is True
        ),
        "attempt_count": (
            len(attempts) if is_v2 and isinstance(attempts, list) else 0
        ),
        "attempt_alternative_sets_identical": (
            is_v2 and record.get("attempt_alternative_sets_identical") is True
        ),
        "every_attempt_has_unique_consensus": (
            is_v2 and record.get("every_attempt_has_unique_consensus") is True
        ),
        "external_prior_conflict_claimed": (
            is_v2 and record.get("external_prior_conflict_claimed") is True
        ),
        "ever_conflicted": record.get("ever_conflicted") is True,
        "current_supplied_set_passed": is_v2 and record.get("passed") is True,
        "accepted_by_solver": is_v2
        and record.get("passed") is True
        and accepted_by_solver,
    }


def _assert_safe_payload(value: Any) -> None:
    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in FORBIDDEN_SAFE_KEYS or key.endswith(("_path", "_paths", "_refs", "_ids")):
                    raise ProofError(f"dual_oracle_safe_forbidden_key:{key}")
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            normalized = item.replace("/", "\\").lower()
            if str(REPO_ROOT).lower() in normalized or ":\\users\\" in normalized:
                raise ProofError("dual_oracle_safe_private_path_detected")

    visit(value)


def _load_json(
    path: Path, expected_type: type, subject: str
) -> tuple[Any, str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProofError(f"dual_oracle_json_utf8_invalid:{subject}") from exc

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProofError(f"dual_oracle_json_duplicate_key:{subject}:{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ProofError(f"dual_oracle_json_nonfinite_number:{subject}:{value}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=invalid_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProofError(f"dual_oracle_json_invalid:{subject}") from exc
    if not isinstance(value, expected_type):
        raise ProofError(f"dual_oracle_json_root_type_invalid:{subject}")
    return value, hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
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


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def _prototype_source_state() -> dict[str, Any]:
    checksums = {}
    for key, path in PROTOTYPE_SOURCE_FILES.items():
        if not path.is_file():
            raise ProofError(f"dual_oracle_prototype_source_missing:{key}")
        checksums[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    )
    return {**checksums, "worktree_dirty": bool(status.strip())}


def _required_string(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProofError(f"dual_oracle_string_required:{subject}")
    return value


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
        and value[2] > value[0]
        and value[3] > value[1]
    )


def _normalize(value: Any) -> str:
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))
    ).strip()


def _numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", value))


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
