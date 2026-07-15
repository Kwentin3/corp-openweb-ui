#!/usr/bin/env python3
"""Prepare and replay sealed visual-topology responses without provider access."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
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

from broker_reports_gate1.pdf_dual_oracle_consensus import (  # noqa: E402
    PdfDualOracleConsensusFactory,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (  # noqa: E402
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_materialization import (  # noqa: E402
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_parser_geometry import (  # noqa: E402
    PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA,
    PdfParserGeometryFactory,
)
from broker_reports_gate1.pdf_topology_assembly import (  # noqa: E402
    PdfTopologyAssemblyFactory,
)
from broker_reports_gate1.pdf_visual_topology import (  # noqa: E402
    PdfVisualTopologyFactory,
)


SOURCE_PRIVATE_SCHEMA = "broker_reports_pdf_structural_repair_proof_private_v2"
SOURCE_SAFE_SCHEMA = "broker_reports_pdf_structural_repair_proof_safe_v2"
SOURCE_JOURNAL_SCHEMA = "broker_reports_pdf_structural_repair_journal_entry_v1"
REPLAY_INPUT_SCHEMA = "broker_reports_pdf_structural_repair_replay_input_v1"
REPLAY_SAFE_SCHEMA = "broker_reports_pdf_structural_repair_replay_safe_v1"
REPLAY_PRIVATE_SCHEMA = "broker_reports_pdf_structural_repair_replay_private_v1"
REPLAY_TERMINAL_PRIVATE_SCHEMA = (
    "broker_reports_pdf_structural_repair_terminal_private_v1"
)
REPLAY_TERMINAL_SAFE_SCHEMA = "broker_reports_pdf_structural_repair_terminal_safe_v1"
TARGET_KEYS = ("1:2", "4:2", "5:3")
ATTEMPTS = (1, 2)
STRUCTURAL_CASES = {
    "1:2": "simple_control",
    "4:2": "grouped_merged_header",
    "5:3": "tax_summary",
}
EXPECTED_SOURCE_PRIVATE_KEYS = {
    "schema_version",
    "source_revision",
    "inputs",
    "provider_qualification",
    "provider_config",
    "states",
    "journal",
    "tables",
    "terminal_seal",
    "terminal_seal_hash",
    "reference_scores",
}
EXPECTED_STATE_KEYS = {
    "page_number",
    "parser_ordinal",
    "parser_observation",
    "parser_geometry_observation",
    "visual_package",
}
EXPECTED_REPLAY_INPUT_KEYS = {
    "schema_version",
    "source_evidence",
    "source_revision",
    "pdf_sha256",
    "provider_qualification",
    "provider_config",
    "states",
    "journal",
    "reference_material_excluded",
    "payload_checksum",
}
PROVIDER_CONFIG_KEYS = {
    "model_id",
    "provider_profile",
    "thinking_level",
    "maximum_output_tokens",
    "maximum_counted_input_tokens",
    "timeout_seconds",
}
PROVIDER_QUALIFICATION_FIELDS = (
    "status",
    "provider_profile",
    "provider_profile_revision",
    "requested_model_id",
    "resolved_model_id",
    "exact_model_match",
    "image_input_supported",
    "structured_output_supported",
    "native_provider_transport",
    "hidden_retry",
    "provider_failover",
)
PROVIDER_ATTEMPT_FIELDS = (
    "task_id",
    "attempt_id",
    "attempt_number",
    "attempt_lineage",
    "provider",
    "provider_profile",
    "provider_profile_revision",
    "model_requested",
    "model_resolved",
    "crop_sha256",
    "model_view_hash",
    "request_hash",
    "finish_reason",
    "terminal_failure_class",
    "hidden_retry",
    "provider_failover",
    "usage",
)
FORBIDDEN_SAFE_KEYS = frozenset(
    {
        "accepted_binding",
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
    "replay_runner_sha256": Path(__file__).resolve(),
}


class ReplayError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser(
        "prepare", help="strip reference-bearing source evidence into a sealed input"
    )
    prepare.add_argument("--source-private-evidence", required=True)
    prepare.add_argument("--source-safe-evidence", required=True)
    prepare.add_argument("--output", required=True)
    solve = subparsers.add_parser(
        "solve", help="reassemble and solve a sealed input with zero provider calls"
    )
    solve.add_argument("--replay-input", required=True)
    solve.add_argument("--output-dir", required=True)
    score = subparsers.add_parser(
        "score", help="score an immutable terminal artifact against a reference"
    )
    score.add_argument("--terminal-private-evidence", required=True)
    score.add_argument("--output-dir", required=True)
    score.add_argument("--reference", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare_replay_input(
            source_private_path=Path(args.source_private_evidence).resolve(),
            source_safe_path=Path(args.source_safe_evidence).resolve(),
            output_path=Path(args.output).resolve(),
        )
    if args.command == "solve":
        return solve_replay(
            replay_input_path=Path(args.replay_input).resolve(),
            output_dir=Path(args.output_dir).resolve(),
        )
    return score_replay(
        terminal_private_path=Path(args.terminal_private_evidence).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        reference_path=Path(args.reference).resolve(),
    )


def prepare_replay_input(
    *,
    source_private_path: Path,
    source_safe_path: Path,
    output_path: Path,
) -> int:
    if output_path.exists():
        raise ReplayError("structural_repair_replay_input_must_be_fresh")
    source_private, private_sha256 = _load_json(
        source_private_path, dict, "source_private_evidence"
    )
    source_safe, safe_sha256 = _load_json(
        source_safe_path, dict, "source_safe_evidence"
    )
    _validate_source_top_level(source_private, source_safe)

    contracts = PdfDualOracleContractFactory().create()
    geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    provider_config = _object(source_private.get("provider_config"))
    if set(provider_config) != PROVIDER_CONFIG_KEYS:
        raise ReplayError("structural_repair_replay_provider_config_invalid")
    provider_config_hash = sha256_json(provider_config)
    model_id = _required_string(provider_config.get("model_id"), "model_id")
    states = _object(source_private.get("states"))
    if set(states) != set(TARGET_KEYS):
        raise ReplayError("structural_repair_replay_source_state_set_invalid")

    sanitized_states: dict[str, dict[str, Any]] = {}
    for key in TARGET_KEYS:
        state = _object(states.get(key))
        if set(state) != EXPECTED_STATE_KEYS:
            raise ReplayError(
                f"structural_repair_replay_source_state_keys_invalid:{key}"
            )
        parser_observation = _object(state.get("parser_observation"))
        parser_errors = contracts.validate_parser_observation(parser_observation)
        if parser_errors:
            raise ReplayError(parser_errors[0])
        if parser_observation.get("pdf_sha256") != source_safe.get("pdf_sha256"):
            raise ReplayError("structural_repair_replay_source_pdf_mismatch")
        geometry_observation = _object(state.get("parser_geometry_observation"))
        geometry.upgrade_v1_observation(geometry_observation)
        visual_package = _object(state.get("visual_package"))
        package_errors = visual.validate_package(
            parser_observation=parser_observation,
            package=visual_package,
        )
        if package_errors:
            raise ReplayError(package_errors[0])
        sanitized_states[key] = copy.deepcopy(state)

    source_journal = source_private.get("journal")
    if not isinstance(source_journal, list) or len(source_journal) != 6:
        raise ReplayError("structural_repair_replay_source_journal_count_invalid")
    expected_pairs = {(key, attempt) for key in TARGET_KEYS for attempt in ATTEMPTS}
    observed_pairs: set[tuple[str, int]] = set()
    sanitized_journal: list[dict[str, Any]] = []
    lineage_by_key: dict[str, list[str]] = {key: [] for key in TARGET_KEYS}
    for wrapper in source_journal:
        wrapper = _object(wrapper)
        if set(wrapper) != {"safe", "private"}:
            raise ReplayError("structural_repair_replay_source_wrapper_invalid")
        safe_entry = _object(wrapper.get("safe"))
        private_entry = _object(wrapper.get("private"))
        key = str(private_entry.get("table_key") or "")
        attempt_number = private_entry.get("attempt_number")
        pair = (key, attempt_number)
        if pair not in expected_pairs or pair in observed_pairs:
            raise ReplayError("structural_repair_replay_source_attempt_set_invalid")
        observed_pairs.add(pair)
        state = sanitized_states[key]
        package = _object(state.get("visual_package"))
        evidence_revision = sha256_json(
            {
                "package_hash": package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(package.get("model_facing")),
                "output_schema_hash": sha256_json(package.get("output_schema")),
            }
        )
        task_id = "pdfvisualtopotask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "package_hash": package.get("package_hash"),
                    "evidence_revision": evidence_revision,
                    "model_id": model_id,
                }
            )
        ).hexdigest()[:24]
        job_key = f"{task_id}|a{attempt_number}"
        provider_attempt = _object(private_entry.get("provider_attempt"))
        count_tokens = _object(private_entry.get("count_tokens"))
        topology_response = _object(private_entry.get("topology_response"))
        provider_text = private_entry.get("provider_text")
        if (
            safe_entry.get("schema_version") != SOURCE_JOURNAL_SCHEMA
            or private_entry.get("schema_version") != SOURCE_JOURNAL_SCHEMA
            or safe_entry.get("case") != STRUCTURAL_CASES[key]
            or safe_entry.get("attempt_number") != attempt_number
            or private_entry.get("task_id") != task_id
            or private_entry.get("job_key") != job_key
            or private_entry.get("evidence_revision") != evidence_revision
            or safe_entry.get("job_key_hash")
            != hashlib.sha256(job_key.encode("utf-8")).hexdigest()
            or private_entry.get("model_view") != package.get("model_facing")
            or private_entry.get("output_schema") != package.get("output_schema")
            or safe_entry.get("model_view_hash")
            != sha256_json(package.get("model_facing"))
            or safe_entry.get("output_schema_hash")
            != sha256_json(package.get("output_schema"))
        ):
            raise ReplayError("structural_repair_replay_source_attempt_identity_invalid")
        if (
            provider_attempt.get("task_id") != task_id
            or provider_attempt.get("attempt_id") != f"{task_id}_a{attempt_number}"
            or provider_attempt.get("attempt_number") != attempt_number
            or provider_attempt.get("attempt_lineage") != lineage_by_key[key]
            or provider_attempt.get("model_requested") != model_id
            or provider_attempt.get("model_resolved") != model_id
            or provider_attempt.get("provider") != "google"
            or provider_attempt.get("crop_sha256")
            != _object(package.get("crop_identity")).get("crop_sha256")
            or provider_attempt.get("model_view_hash")
            != sha256_json(package.get("model_facing"))
        ):
            raise ReplayError("structural_repair_replay_provider_attempt_invalid")
        usage = _object(provider_attempt.get("usage"))
        if (
            provider_attempt.get("finish_reason") != "STOP"
            or provider_attempt.get("terminal_failure_class") is not None
            or provider_attempt.get("hidden_retry") is not False
            or provider_attempt.get("provider_failover") is not False
            or safe_entry.get("finish_reason") != "STOP"
            or safe_entry.get("hidden_retry") is not False
            or safe_entry.get("provider_failover") is not False
            or safe_entry.get("provider_generate_call_performed") is not True
            or safe_entry.get("counted_input_tokens") != count_tokens.get("total_tokens")
            or safe_entry.get("actual_input_tokens") != usage.get("input_tokens")
            or safe_entry.get("output_tokens") != usage.get("output_tokens")
            or count_tokens.get("within_hard_guard") is not True
        ):
            raise ReplayError("structural_repair_replay_provider_terminal_invalid")
        if (
            not isinstance(provider_text, str)
            or hashlib.sha256(provider_text.encode("utf-8")).hexdigest()
            != safe_entry.get("visible_output_hash")
        ):
            raise ReplayError("structural_repair_replay_visible_output_hash_invalid")
        try:
            decoded_response = json.loads(
                provider_text,
                object_pairs_hook=_strict_pairs("provider_text"),
                parse_constant=lambda item: _raise_nonfinite("provider_text", item),
            )
        except json.JSONDecodeError as exc:
            raise ReplayError(
                "structural_repair_replay_visible_output_json_invalid"
            ) from exc
        if decoded_response != topology_response:
            raise ReplayError("structural_repair_replay_topology_response_mismatch")
        if topology_response.get("package_id") != package.get("package_id"):
            raise ReplayError("structural_repair_replay_topology_package_mismatch")
        lineage_by_key[key].append(str(provider_attempt["attempt_id"]))
        sanitized_journal.append(
            {
                "table_key": key,
                "attempt_number": attempt_number,
                "task_id": task_id,
                "job_key": job_key,
                "evidence_revision": evidence_revision,
                "provider_attempt": {
                    field: copy.deepcopy(provider_attempt.get(field))
                    for field in PROVIDER_ATTEMPT_FIELDS
                },
                "count_tokens": {
                    "total_tokens": count_tokens.get("total_tokens"),
                    "within_hard_guard": count_tokens.get("within_hard_guard"),
                },
                "topology_response": copy.deepcopy(topology_response),
                "topology_response_hash": sha256_json(topology_response),
                "provider_text": provider_text,
                "provider_text_sha256": hashlib.sha256(
                    provider_text.encode("utf-8")
                ).hexdigest(),
                "source_safe_entry": {
                    field: copy.deepcopy(safe_entry.get(field))
                    for field in (
                        "reconstruction_status",
                        "counted_input_tokens",
                        "actual_input_tokens",
                        "output_tokens",
                        "finish_reason",
                        "hidden_retry",
                        "provider_failover",
                        "provider_generate_call_performed",
                    )
                },
            }
        )
    if observed_pairs != expected_pairs:
        raise ReplayError("structural_repair_replay_source_attempt_set_invalid")

    sanitized_journal.sort(
        key=lambda item: (
            TARGET_KEYS.index(str(item["table_key"])),
            int(item["attempt_number"]),
        )
    )
    replay_input = {
        "schema_version": REPLAY_INPUT_SCHEMA,
        "source_evidence": {
            "private_sha256": private_sha256,
            "safe_sha256": safe_sha256,
            "private_schema": source_private.get("schema_version"),
            "safe_schema": source_safe.get("schema_version"),
        },
        "source_revision": source_private.get("source_revision"),
        "pdf_sha256": source_safe.get("pdf_sha256"),
        "provider_qualification": {
            field: copy.deepcopy(
                _object(source_private.get("provider_qualification")).get(field)
            )
            for field in PROVIDER_QUALIFICATION_FIELDS
        },
        "provider_config": copy.deepcopy(provider_config),
        "states": sanitized_states,
        "journal": sanitized_journal,
        "reference_material_excluded": {
            "confirmed": True,
            "excluded_source_sections": 5,
            "reference_path_included": False,
            "reference_scores_included": False,
        },
    }
    replay_input["payload_checksum"] = sha256_json(replay_input)
    _validate_replay_input(replay_input)
    _write_json(output_path, replay_input)
    print(
        json.dumps(
            {
                "status": "prepared",
                "output": str(output_path),
                "source_private_sha256": private_sha256,
                "source_safe_sha256": safe_sha256,
                "attempts": len(sanitized_journal),
                "reference_material_excluded": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def solve_replay(
    *, replay_input_path: Path,
    output_dir: Path,
) -> int:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ReplayError("structural_repair_replay_fresh_output_directory_required")
    replay_input, replay_input_file_sha256 = _load_json(
        replay_input_path, dict, "replay_input"
    )
    _validate_replay_input(replay_input)
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir = output_dir / "private"

    contracts = PdfDualOracleContractFactory().create()
    solver = PdfDualOracleConsensusFactory().create()
    geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    assembler = PdfTopologyAssemblyFactory(
        visual_topology=visual,
        parser_geometry=geometry,
    ).create()
    materializer = PdfHybridMaterializationFactory().create()
    states = _object(replay_input.get("states"))
    provider_config = _object(replay_input.get("provider_config"))
    provider_config_hash = sha256_json(provider_config)
    model_id = _required_string(provider_config.get("model_id"), "model_id")
    journal = replay_input.get("journal")
    if not isinstance(journal, list):
        raise ReplayError("structural_repair_replay_journal_invalid")

    table_private: dict[str, dict[str, Any]] = {}
    accepted_bindings: dict[str, dict[str, Any]] = {}
    consensus_results: dict[str, dict[str, Any]] = {}
    safe_tables: list[dict[str, Any]] = []
    for key in TARGET_KEYS:
        state = _object(states.get(key))
        parser_observation = _object(state.get("parser_observation"))
        parser_errors = contracts.validate_parser_observation(parser_observation)
        if parser_errors:
            raise ReplayError(parser_errors[0])
        source_geometry = _object(state.get("parser_geometry_observation"))
        parser_geometry_observation = geometry.upgrade_v1_observation(
            source_geometry
        )
        if (
            parser_geometry_observation.get("schema_version")
            != PDF_PARSER_GEOMETRY_OBSERVATION_SCHEMA
        ):
            raise ReplayError("structural_repair_replay_geometry_upgrade_failed")
        semantic_geometry_keys = {
            "schema_version",
            "policy_version",
            "policy_configuration_hash",
            "observation_id",
            "observation_checksum",
        }
        source_geometry_semantics = {
            field: copy.deepcopy(value)
            for field, value in source_geometry.items()
            if field not in semantic_geometry_keys
        }
        upgraded_geometry_semantics = {
            field: copy.deepcopy(value)
            for field, value in parser_geometry_observation.items()
            if field not in semantic_geometry_keys
        }
        if source_geometry_semantics != upgraded_geometry_semantics:
            raise ReplayError("structural_repair_replay_geometry_semantics_changed")
        geometry_upgrade = {
            "source_schema": source_geometry.get("schema_version"),
            "target_schema": parser_geometry_observation.get("schema_version"),
            "source_observation_id": source_geometry.get("observation_id"),
            "target_observation_id": parser_geometry_observation.get(
                "observation_id"
            ),
            "source_observation_checksum": source_geometry.get(
                "observation_checksum"
            ),
            "target_observation_checksum": parser_geometry_observation.get(
                "observation_checksum"
            ),
            "semantic_fields_unchanged": True,
            "new_parser_run_performed": False,
        }
        package = _object(state.get("visual_package"))
        package_errors = visual.validate_package(
            parser_observation=parser_observation,
            package=package,
        )
        if package_errors:
            raise ReplayError(package_errors[0])
        entries = [item for item in journal if _object(item).get("table_key") == key]
        if [item.get("attempt_number") for item in entries] != [1, 2]:
            raise ReplayError("structural_repair_replay_attempt_order_invalid")

        assemblies: list[dict[str, Any]] = []
        for entry in entries:
            entry = _object(entry)
            provider_attempt = _object(entry.get("provider_attempt"))
            response = _object(entry.get("topology_response"))
            if entry.get("topology_response_hash") != sha256_json(response):
                raise ReplayError("structural_repair_replay_topology_hash_invalid")
            assembly = assembler.assemble(
                parser_observation=parser_observation,
                parser_geometry_observation=parser_geometry_observation,
                visual_package=package,
                topology_response=response,
                attempt_evidence={
                    "attempt_id": str(provider_attempt.get("attempt_id") or ""),
                    "attempt_number": int(entry.get("attempt_number") or 0),
                    "evidence_revision": str(entry.get("evidence_revision") or ""),
                    "provider": "google",
                    "model": model_id,
                    "provider_config_hash": provider_config_hash,
                },
                hypothesis_id_prefix=(
                    f"replay_{STRUCTURAL_CASES[key]}_a{entry['attempt_number']}"
                ),
            )
            assemblies.append(assembly)

        binding_inputs = [
            hypothesis
            for assembly in assemblies
            for hypothesis in assembly.get("binding_hypotheses") or []
            if isinstance(hypothesis, dict)
        ]
        rejected = [
            evidence
            for assembly in assemblies
            for evidence in assembly.get("rejected_evidence") or []
            if isinstance(evidence, dict)
        ]
        successful_entries = [
            entry
            for entry, assembly in zip(entries, assemblies)
            if assembly.get("reconstruction_status") == "assembled"
        ]
        actual_outputs = [
            int(_object(_object(entry).get("source_safe_entry")).get("output_tokens") or 0)
            for entry in successful_entries
        ]
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
        exact_accounting = bool(
            len(entries) == 2
            and all(
                isinstance(_object(entry.get("count_tokens")).get("total_tokens"), int)
                and isinstance(
                    _object(_object(entry.get("provider_attempt")).get("usage")).get(
                        "input_tokens"
                    ),
                    int,
                )
                and isinstance(
                    _object(_object(entry.get("provider_attempt")).get("usage")).get(
                        "output_tokens"
                    ),
                    int,
                )
                for entry in entries
            )
        )
        model_context = {
            "provider": "google",
            "model": model_id,
            "configuration_hash": provider_config_hash,
            "bounded_row_windows": True,
            "provider_calls_replayed": 2,
            "new_provider_calls": 0,
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
            "observed_output_tokens": max(actual_outputs, default=0),
            "maximum_output_tokens": 8192,
            "provider_token_accounting_exact": exact_accounting,
            "candidate_ownership_exact": candidate_ownership,
            "no_silent_truncation": all(
                _object(entry.get("provider_attempt")).get("finish_reason") == "STOP"
                for entry in entries
            ),
            "column_splitting_used": False,
            "hidden_provider_failover": False,
            "alternative_topology_hypotheses_complete": all(
                _object(entry.get("topology_response")).get("alternatives_complete")
                is True
                for entry in entries
            ),
        }
        hypothesis_set = contracts.build_vlm_hypothesis_set(
            parser_observation=parser_observation,
            binding_hypotheses=binding_inputs,
            rejected_evidence=rejected,
            model_context=model_context,
        )
        repeatability = solver.build_repeatability_record(
            parser_observation=parser_observation,
            vlm_hypothesis_set=hypothesis_set,
        )
        first = solver.solve(
            parser_observation=parser_observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )
        second = solver.solve(
            parser_observation=copy.deepcopy(parser_observation),
            vlm_hypothesis_set=copy.deepcopy(hypothesis_set),
            historical_repeatability=copy.deepcopy(repeatability),
        )
        if first != second:
            raise ReplayError(f"structural_repair_replay_solver_nondeterministic:{key}")
        accepted_binding = None
        materialization = None
        if first.get("terminal_status") == "accepted_supplied_consensus":
            accepted_binding = solver.binding_from_accepted_consensus(
                parser_observation=parser_observation,
                consensus_result=first,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=package,
            )
            materialization = materializer.materialize(
                evidence_package=package,
                binding_output=accepted_binding,
            )
            accepted_bindings[key] = accepted_binding
        consensus_results[key] = first
        source_statuses = [
            _object(entry.get("source_safe_entry")).get("reconstruction_status")
            for entry in entries
        ]
        safe_tables.append(
            {
                "case": STRUCTURAL_CASES[key],
                "source_live_reconstruction_statuses": source_statuses,
                "replay_reconstruction_statuses": [
                    assembly.get("reconstruction_status") for assembly in assemblies
                ],
                "certification_status": first.get("terminal_status"),
                "reason_codes": first.get("reason_codes") or [],
                "review_codes": first.get("review_codes") or [],
                "row_count": first.get("row_count"),
                "column_count": first.get("column_count"),
                "atom_count": _object(parser_observation.get("source_accounting")).get(
                    "candidates"
                ),
                "all_atoms_exactly_once": candidate_ownership,
                "repeatability_passed": repeatability.get("passed") is True,
                "repeatability_scope": (
                    "canonical_post_assembly_not_raw_vlm_output_identity"
                ),
                "structural_adjustments": sum(
                    len(assembly.get("structural_adjustments") or [])
                    for assembly in assemblies
                ),
                "structural_adjustment_operations": sorted(
                    {
                        str(adjustment.get("operation") or "")
                        for assembly in assemblies
                        for adjustment in assembly.get("structural_adjustments") or []
                        if isinstance(adjustment, dict) and adjustment.get("operation")
                    }
                ),
                "parser_geometry_upgrade": {
                    "source_schema": geometry_upgrade["source_schema"],
                    "target_schema": geometry_upgrade["target_schema"],
                    "semantic_fields_unchanged": True,
                    "new_parser_run_performed": False,
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
                "omitted_candidates": (
                    len(materialization.get("omitted_candidate_ids") or [])
                    if isinstance(materialization, dict)
                    else 0
                ),
                "valid_distinct_grid_count": first.get("valid_distinct_grid_count"),
                "supplied_hypotheses_exhausted": first.get(
                    "supplied_hypotheses_exhausted"
                ),
                "structural_domain_complete": first.get(
                    "structural_domain_complete"
                ),
                "uniqueness_proven": first.get("uniqueness_proven"),
                "ambiguity_proven": first.get("ambiguity_proven"),
                "domain_incomplete": first.get("domain_incomplete"),
                "search_not_certifiable": first.get(
                    "search_not_certifiable"
                ),
                "search_scope": first.get("search_scope"),
                "safe_explanation": first.get("safe_explanation"),
                "result_checksum": first.get("result_checksum"),
            }
        )
        table_private[key] = {
            "parser_observation": parser_observation,
            "source_parser_geometry_observation": source_geometry,
            "upgraded_parser_geometry_observation": parser_geometry_observation,
            "geometry_upgrade": geometry_upgrade,
            "visual_package": package,
            "assemblies": assemblies,
            "hypothesis_set": hypothesis_set,
            "repeatability": repeatability,
            "consensus_result": first,
            "accepted_binding": accepted_binding,
            "materialization": materialization,
        }

    terminal_seal = _build_terminal_seal(
        table_private, replay_input_file_sha256
    )
    terminal_private = {
        "schema_version": REPLAY_TERMINAL_PRIVATE_SCHEMA,
        "source_revision": _git_revision(),
        "prototype_source": _source_state(),
        "pdf_sha256": replay_input.get("pdf_sha256"),
        "replay_input_file_sha256": replay_input_file_sha256,
        "source_evidence": replay_input.get("source_evidence"),
        "provider_qualification": replay_input.get("provider_qualification"),
        "provider_config": provider_config,
        "safe_tables": safe_tables,
        "tables": table_private,
        "new_provider_calls": 0,
        "provider_calls_replayed": 6,
        "reference_process_started": False,
        "terminal_seal": terminal_seal,
        "terminal_seal_hash": sha256_json(terminal_seal),
    }
    terminal_private["artifact_checksum"] = sha256_json(terminal_private)
    _validate_terminal_artifact(terminal_private)
    terminal_private_path = private_dir / "terminal.private.json"
    _write_json(terminal_private_path, terminal_private)
    terminal_private_file_sha256 = _sha256_file(terminal_private_path)
    terminal_safe = {
        "schema_version": REPLAY_TERMINAL_SAFE_SCHEMA,
        "source_revision": terminal_private["source_revision"],
        "prototype_source": terminal_private["prototype_source"],
        "pdf_sha256": terminal_private["pdf_sha256"],
        "sealed_source": {
            **_object(replay_input.get("source_evidence")),
            "replay_input_file_sha256": replay_input_file_sha256,
            "reference_material_excluded_before_solver": True,
        },
        "reference_loaded": False,
        "evidence_scope": (
            "post_hoc_development_target_replay_after_assembly_v4"
        ),
        "terminal_private_file_sha256": terminal_private_file_sha256,
        "terminal_seal_hash": terminal_private["terminal_seal_hash"],
        "tables": safe_tables,
        "terminal_counts": dict(
            sorted(
                Counter(
                    str(item.get("certification_status")) for item in safe_tables
                ).items()
            )
        ),
        "journal": {
            "sealed_provider_attempts": 6,
            "provider_calls_replayed": 6,
            "new_provider_generate_calls": 0,
            "hidden_retries": 0,
            "provider_failovers": 0,
        },
        "hard_invariants": {
            "reference_process_not_started": True,
            "reference_answer_used_by_solver": False,
            "production_pdf_pipeline_changed": False,
            "production_gate2_selection_changed": False,
        },
    }
    _assert_safe_payload(terminal_safe)
    _write_json(output_dir / "terminal.safe.json", terminal_safe)
    print(json.dumps(terminal_safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def score_replay(
    *,
    terminal_private_path: Path,
    output_dir: Path,
    reference_path: Path,
) -> int:
    expected_terminal_path = (output_dir / "private" / "terminal.private.json").resolve()
    if terminal_private_path != expected_terminal_path:
        raise ReplayError("structural_repair_replay_terminal_path_invalid")
    if (output_dir / "evidence.safe.json").exists() or (
        output_dir / "private" / "evidence.private.json"
    ).exists():
        raise ReplayError("structural_repair_replay_score_output_already_exists")
    terminal, terminal_private_file_sha256 = _load_json(
        terminal_private_path, dict, "terminal_private_evidence"
    )
    _validate_terminal_artifact(terminal)
    if terminal.get("source_revision") != _git_revision() or terminal.get(
        "prototype_source"
    ) != _source_state():
        raise ReplayError("structural_repair_replay_source_changed_after_terminal")

    # This process never invokes the assembler or solver. It opens the reference
    # only after validating the immutable terminal artifact from the solve process.
    reference, reference_sha256 = _load_json(reference_path, dict, "reference")
    if reference.get("pdf_sha256") != terminal.get("pdf_sha256"):
        raise ReplayError("structural_repair_replay_reference_pdf_mismatch")
    reference_by_key = _validate_reference(reference)
    tables = _object(terminal.get("tables"))
    reference_scores = {
        key: _score_binding(
            reference_by_key[key],
            _object(tables.get(key)).get("accepted_binding"),
            _object(_object(tables.get(key)).get("visual_package")),
        )
        for key in TARGET_KEYS
    }
    terminal_after_scoring, terminal_sha256_after_scoring = _load_json(
        terminal_private_path, dict, "terminal_private_evidence_after_scoring"
    )
    _validate_terminal_artifact(terminal_after_scoring)
    if (
        terminal_sha256_after_scoring != terminal_private_file_sha256
        or terminal_after_scoring != terminal
    ):
        raise ReplayError("structural_repair_replay_terminal_changed_during_scoring")

    safe_tables = copy.deepcopy(terminal.get("safe_tables"))
    if not isinstance(safe_tables, list):
        raise ReplayError("structural_repair_replay_terminal_tables_invalid")
    safe_by_case = {
        str(item.get("case") or ""): item
        for item in safe_tables
        if isinstance(item, dict)
    }
    for key in TARGET_KEYS:
        safe_by_case[STRUCTURAL_CASES[key]]["diagnostic_reference_score"] = (
            reference_scores[key]
        )
    accepted_count = sum(
        item.get("certification_status") == "accepted_supplied_consensus"
        for item in safe_tables
    )
    reference_exact_count = sum(
        _object(item.get("diagnostic_reference_score")).get("structure_exact")
        is True
        and _object(item.get("diagnostic_reference_score")).get("headers_exact")
        is True
        and _object(item.get("diagnostic_reference_score")).get("all_cells_exact")
        is True
        for item in safe_tables
    )
    overall = (
        "BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_SEALED_REPLAY_GOAL_MET"
        if accepted_count == 3 and reference_exact_count == 3
        else "BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_SEALED_REPLAY_PARTIAL"
    )
    safe = {
        "schema_version": REPLAY_SAFE_SCHEMA,
        "source_revision": terminal.get("source_revision"),
        "prototype_source": terminal.get("prototype_source"),
        "pdf_sha256": terminal.get("pdf_sha256"),
        "sealed_source": {
            **_object(terminal.get("source_evidence")),
            "replay_input_file_sha256": terminal.get("replay_input_file_sha256"),
            "terminal_private_file_sha256": terminal_private_file_sha256,
            "reference_material_excluded_before_solver": True,
        },
        "reference_status": str(reference.get("human_review_status") or "unknown"),
        "reference_is_provisional": True,
        "reference_sha256": reference_sha256,
        "reference_access": {
            "scoring_ran_in_separate_process_after_solver_exit": True,
            "terminal_private_file_sha256": terminal_private_file_sha256,
            "terminal_seal_hash_before_scoring": terminal.get("terminal_seal_hash"),
            "reference_used_by_solver": False,
        },
        "provider_qualification": {
            "qualification_scope": "historical_source_run_not_refreshed",
            **{
                key: _object(terminal.get("provider_qualification")).get(key)
                for key in (
                    "status",
                    "provider_profile",
                    "requested_model_id",
                    "resolved_model_id",
                    "exact_model_match",
                    "image_input_supported",
                    "structured_output_supported",
                    "native_provider_transport",
                    "hidden_retry",
                    "provider_failover",
                )
            },
        },
        "execution_path": {
            "parser_value_role": "immutable_raw_word_atoms_and_provenance_only",
            "parser_geometry_role": (
                "raw_vector_lines_for_boundary_and_span_certification"
            ),
            "vlm_role": "sealed_visual_topology_without_parser_grid",
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
            sorted(
                Counter(
                    str(item.get("certification_status")) for item in safe_tables
                ).items()
            )
        ),
        "goal_metrics": {
            "target_tables": 3,
            "accepted_supplied_consensus": accepted_count,
            "reference_exact_tables": reference_exact_count,
            "all_atoms_exactly_once_tables": sum(
                item.get("all_atoms_exactly_once") is True for item in safe_tables
            ),
            "invented_values_total": sum(
                int(item.get("model_invented_values_total") or 0)
                for item in safe_tables
            ),
            "repeatability_passed_tables": sum(
                item.get("repeatability_passed") is True for item in safe_tables
            ),
        },
        "journal": {
            "historical_provider_generate_calls": 6,
            "sealed_provider_attempts": 6,
            "provider_calls_replayed": 6,
            "new_provider_generate_calls": 0,
            "hidden_retries": 0,
            "provider_failovers": 0,
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
            "fresh_provider_qualification_performed": False,
        },
        "readiness": {
            "prototype_execution": "completed_by_sealed_response_replay",
            "three_table_control": "completed_by_sealed_response_replay",
            "fresh_provider_rerun_after_refactor": "not_performed",
            "evidence_scope": (
                "post_hoc_development_target_replay_after_assembly_v4"
            ),
            "generalization_proven": False,
            "raw_vlm_output_repeatability_claimed": False,
            "overall_status": overall,
            "production_gate2_shadow": (
                "not_ready_continuation_and_broader_corpus_pending"
            ),
        },
    }
    _assert_safe_payload(safe)
    private = {
        "schema_version": REPLAY_PRIVATE_SCHEMA,
        "source_revision": terminal.get("source_revision"),
        "terminal_private_file_sha256": terminal_private_file_sha256,
        "source_evidence": terminal.get("source_evidence"),
        "terminal_seal_hash": terminal.get("terminal_seal_hash"),
        "reference_scores": reference_scores,
    }
    _write_json(output_dir / "private" / "evidence.private.json", private)
    _write_json(output_dir / "evidence.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_terminal_seal(
    tables: dict[str, Any], replay_input_file_sha256: str | None = None
) -> dict[str, Any]:
    table_seals: dict[str, dict[str, Any]] = {}
    for key in TARGET_KEYS:
        table = _object(tables.get(key))
        consensus = _object(table.get("consensus_result"))
        accepted_binding = table.get("accepted_binding")
        materialization = table.get("materialization")
        assemblies = table.get("assemblies")
        if not isinstance(assemblies, list):
            raise ReplayError("structural_repair_replay_terminal_assemblies_invalid")
        table_seals[STRUCTURAL_CASES[key]] = {
            "terminal_status": consensus.get("terminal_status"),
            "result_checksum": consensus.get("result_checksum"),
            "consensus_result_sha256": sha256_json(consensus),
            "parser_observation_sha256": sha256_json(
                table.get("parser_observation")
            ),
            "source_parser_geometry_sha256": sha256_json(
                table.get("source_parser_geometry_observation")
            ),
            "upgraded_parser_geometry_sha256": sha256_json(
                table.get("upgraded_parser_geometry_observation")
            ),
            "assembly_result_sha256s": [
                sha256_json(assembly) for assembly in assemblies
            ],
            "hypothesis_set_sha256": sha256_json(table.get("hypothesis_set")),
            "repeatability_sha256": sha256_json(table.get("repeatability")),
            "accepted_binding_sha256": (
                sha256_json(accepted_binding)
                if isinstance(accepted_binding, dict)
                else None
            ),
            "materialization_sha256": (
                sha256_json(materialization)
                if isinstance(materialization, dict)
                else None
            ),
            "geometry_upgrade_sha256": sha256_json(table.get("geometry_upgrade")),
        }
    return {
        "replay_input_file_sha256": replay_input_file_sha256,
        "tables": table_seals,
    }


def _validate_terminal_artifact(value: Any) -> None:
    data = _object(value)
    expected_keys = {
        "schema_version",
        "source_revision",
        "prototype_source",
        "pdf_sha256",
        "replay_input_file_sha256",
        "source_evidence",
        "provider_qualification",
        "provider_config",
        "safe_tables",
        "tables",
        "new_provider_calls",
        "provider_calls_replayed",
        "reference_process_started",
        "terminal_seal",
        "terminal_seal_hash",
        "artifact_checksum",
    }
    if (
        set(data) != expected_keys
        or data.get("schema_version") != REPLAY_TERMINAL_PRIVATE_SCHEMA
        or data.get("new_provider_calls") != 0
        or data.get("provider_calls_replayed") != 6
        or data.get("reference_process_started") is not False
        or set(_object(data.get("tables"))) != set(TARGET_KEYS)
        or not isinstance(data.get("safe_tables"), list)
        or len(data.get("safe_tables")) != 3
    ):
        raise ReplayError("structural_repair_replay_terminal_contract_invalid")
    unsigned = dict(data)
    stored_checksum = unsigned.pop("artifact_checksum", None)
    if stored_checksum != sha256_json(unsigned):
        raise ReplayError("structural_repair_replay_terminal_checksum_invalid")
    expected_seal = _build_terminal_seal(
        _object(data.get("tables")),
        str(data.get("replay_input_file_sha256") or ""),
    )
    if (
        data.get("terminal_seal") != expected_seal
        or data.get("terminal_seal_hash") != sha256_json(expected_seal)
    ):
        raise ReplayError("structural_repair_replay_terminal_seal_invalid")
    safe_by_case = {
        str(item.get("case") or ""): item
        for item in data.get("safe_tables")
        if isinstance(item, dict)
    }
    if set(safe_by_case) != set(STRUCTURAL_CASES.values()):
        raise ReplayError("structural_repair_replay_terminal_safe_table_set_invalid")
    for key in TARGET_KEYS:
        table = _object(_object(data.get("tables")).get(key))
        safe_table = _object(safe_by_case.get(STRUCTURAL_CASES[key]))
        consensus = _object(table.get("consensus_result"))
        geometry_upgrade = _object(table.get("geometry_upgrade"))
        if (
            safe_table.get("certification_status")
            != consensus.get("terminal_status")
            or safe_table.get("result_checksum") != consensus.get("result_checksum")
            or geometry_upgrade.get("semantic_fields_unchanged") is not True
            or geometry_upgrade.get("new_parser_run_performed") is not False
        ):
            raise ReplayError("structural_repair_replay_terminal_table_invalid")


def _validate_source_top_level(
    source_private: dict[str, Any], source_safe: dict[str, Any]
) -> None:
    if (
        set(source_private) != EXPECTED_SOURCE_PRIVATE_KEYS
        or source_private.get("schema_version") != SOURCE_PRIVATE_SCHEMA
        or source_safe.get("schema_version") != SOURCE_SAFE_SCHEMA
        or source_private.get("source_revision") != source_safe.get("source_revision")
    ):
        raise ReplayError("structural_repair_replay_source_contract_invalid")
    qualification = _object(source_private.get("provider_qualification"))
    safe_journal = _object(source_safe.get("journal"))
    reference_access = _object(source_safe.get("reference_access"))
    hard_invariants = _object(source_safe.get("hard_invariants"))
    if (
        qualification.get("status") != "qualified"
        or qualification.get("exact_model_match") is not True
        or qualification.get("hidden_retry") is not False
        or qualification.get("provider_failover") is not False
        or safe_journal.get("entries") != 6
        or safe_journal.get("expected_entries") != 6
        or safe_journal.get("new_provider_generate_calls") != 6
        or safe_journal.get("hidden_retries") != 0
        or safe_journal.get("provider_failovers") != 0
        or reference_access.get("reference_used_by_solver") is not False
        or hard_invariants.get("reference_answer_used_by_solver") is not False
    ):
        raise ReplayError("structural_repair_replay_source_proof_invalid")


def _validate_replay_input(value: Any) -> None:
    data = _object(value)
    exclusion = _object(data.get("reference_material_excluded"))
    if (
        set(data) != EXPECTED_REPLAY_INPUT_KEYS
        or data.get("schema_version") != REPLAY_INPUT_SCHEMA
        or set(_object(data.get("states"))) != set(TARGET_KEYS)
        or not isinstance(data.get("journal"), list)
        or len(data.get("journal")) != 6
        or set(exclusion)
        != {
            "confirmed",
            "excluded_source_sections",
            "reference_path_included",
            "reference_scores_included",
        }
        or exclusion.get("confirmed") is not True
        or exclusion.get("excluded_source_sections") != 5
        or exclusion.get("reference_path_included") is not False
        or exclusion.get("reference_scores_included") is not False
        or set(_object(data.get("provider_config"))) != PROVIDER_CONFIG_KEYS
        or set(_object(data.get("provider_qualification")))
        != set(PROVIDER_QUALIFICATION_FIELDS)
    ):
        raise ReplayError("structural_repair_replay_input_contract_invalid")
    unsigned = dict(data)
    stored_checksum = unsigned.pop("payload_checksum", None)
    if stored_checksum != sha256_json(unsigned):
        raise ReplayError("structural_repair_replay_input_checksum_invalid")
    pairs = [
        (str(_object(item).get("table_key") or ""), _object(item).get("attempt_number"))
        for item in data.get("journal")
    ]
    expected_pairs = [(key, attempt) for key in TARGET_KEYS for attempt in ATTEMPTS]
    if pairs != expected_pairs:
        raise ReplayError("structural_repair_replay_input_attempt_order_invalid")
    _assert_reference_free_replay_content(
        {
            "source_evidence": data.get("source_evidence"),
            "provider_qualification": data.get("provider_qualification"),
            "provider_config": data.get("provider_config"),
            "states": data.get("states"),
            "journal": data.get("journal"),
        }
    )
    provider_config = _object(data.get("provider_config"))
    provider_config_hash = sha256_json(provider_config)
    model_id = _required_string(provider_config.get("model_id"), "model_id")
    states = _object(data.get("states"))
    lineage_by_key: dict[str, list[str]] = {key: [] for key in TARGET_KEYS}
    expected_entry_keys = {
        "table_key",
        "attempt_number",
        "task_id",
        "job_key",
        "evidence_revision",
        "provider_attempt",
        "count_tokens",
        "topology_response",
        "topology_response_hash",
        "provider_text",
        "provider_text_sha256",
        "source_safe_entry",
    }
    expected_safe_entry_keys = {
        "reconstruction_status",
        "counted_input_tokens",
        "actual_input_tokens",
        "output_tokens",
        "finish_reason",
        "hidden_retry",
        "provider_failover",
        "provider_generate_call_performed",
    }
    for entry_value in data.get("journal"):
        entry = _object(entry_value)
        if set(entry) != expected_entry_keys:
            raise ReplayError("structural_repair_replay_input_entry_keys_invalid")
        key = str(entry.get("table_key") or "")
        attempt_number = entry.get("attempt_number")
        state = _object(states.get(key))
        if set(state) != EXPECTED_STATE_KEYS:
            raise ReplayError("structural_repair_replay_input_state_keys_invalid")
        package = _object(state.get("visual_package"))
        expected_revision = sha256_json(
            {
                "package_hash": package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(package.get("model_facing")),
                "output_schema_hash": sha256_json(package.get("output_schema")),
            }
        )
        expected_task_id = "pdfvisualtopotask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "package_hash": package.get("package_hash"),
                    "evidence_revision": expected_revision,
                    "model_id": model_id,
                }
            )
        ).hexdigest()[:24]
        provider_attempt = _object(entry.get("provider_attempt"))
        count_tokens = _object(entry.get("count_tokens"))
        safe_entry = _object(entry.get("source_safe_entry"))
        response = _object(entry.get("topology_response"))
        provider_text = entry.get("provider_text")
        if (
            set(provider_attempt) != set(PROVIDER_ATTEMPT_FIELDS)
            or set(count_tokens) != {"total_tokens", "within_hard_guard"}
            or set(safe_entry) != expected_safe_entry_keys
            or entry.get("evidence_revision") != expected_revision
            or entry.get("task_id") != expected_task_id
            or entry.get("job_key") != f"{expected_task_id}|a{attempt_number}"
            or provider_attempt.get("task_id") != expected_task_id
            or provider_attempt.get("attempt_id")
            != f"{expected_task_id}_a{attempt_number}"
            or provider_attempt.get("attempt_number") != attempt_number
            or provider_attempt.get("attempt_lineage") != lineage_by_key[key]
            or provider_attempt.get("model_requested") != model_id
            or provider_attempt.get("model_resolved") != model_id
            or provider_attempt.get("finish_reason") != "STOP"
            or provider_attempt.get("terminal_failure_class") is not None
            or provider_attempt.get("hidden_retry") is not False
            or provider_attempt.get("provider_failover") is not False
            or count_tokens.get("within_hard_guard") is not True
            or safe_entry.get("finish_reason") != "STOP"
            or safe_entry.get("hidden_retry") is not False
            or safe_entry.get("provider_failover") is not False
            or safe_entry.get("provider_generate_call_performed") is not True
            or response.get("package_id") != package.get("package_id")
            or entry.get("topology_response_hash") != sha256_json(response)
            or not isinstance(provider_text, str)
            or entry.get("provider_text_sha256")
            != hashlib.sha256(str(provider_text).encode("utf-8")).hexdigest()
        ):
            raise ReplayError("structural_repair_replay_input_entry_invalid")
        try:
            parsed_text = json.loads(
                provider_text,
                object_pairs_hook=_strict_pairs("replay_provider_text"),
                parse_constant=lambda item: _raise_nonfinite(
                    "replay_provider_text", item
                ),
            )
        except json.JSONDecodeError as exc:
            raise ReplayError(
                "structural_repair_replay_input_provider_text_invalid"
            ) from exc
        if not isinstance(parsed_text, dict) or parsed_text != response:
            raise ReplayError("structural_repair_replay_input_response_mismatch")
        lineage_by_key[key].append(str(provider_attempt.get("attempt_id") or ""))


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
    pairs: list[tuple[str, str]] = []
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


def _validate_reference(reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tables = reference.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ReplayError("structural_repair_replay_reference_tables_invalid")
    result: dict[str, dict[str, Any]] = {}
    for item in tables:
        if not isinstance(item, dict):
            raise ReplayError("structural_repair_replay_reference_table_invalid")
        key = str(item.get("table_key") or "")
        if not key or key in result:
            raise ReplayError("structural_repair_replay_reference_table_key_invalid")
        result[key] = item
    if not set(TARGET_KEYS) <= set(result):
        raise ReplayError("structural_repair_replay_reference_target_set_incomplete")
    for key in TARGET_KEYS:
        table = result[key]
        rows = table.get("rows")
        columns = table.get("columns")
        header_rows = table.get("header_rows")
        cells = table.get("cells")
        if (
            not isinstance(rows, int)
            or isinstance(rows, bool)
            or rows < 1
            or not isinstance(columns, int)
            or isinstance(columns, bool)
            or columns < 1
            or not isinstance(header_rows, int)
            or isinstance(header_rows, bool)
            or not 0 <= header_rows <= rows
            or not isinstance(cells, list)
            or len(cells) != rows
            or any(not isinstance(row, list) or len(row) != columns for row in cells)
        ):
            raise ReplayError("structural_repair_replay_reference_shape_invalid")
    return result


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
                raise ReplayError(
                    "structural_repair_replay_safe_forbidden_key:"
                    + sorted(forbidden)[0]
                )
            for item in current.values():
                walk(item)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str) and re.search(
            r"(?:[A-Za-z]:\\|/Users/|/home/|\\Users\\)", current
        ):
            raise ReplayError("structural_repair_replay_safe_private_path")

    walk(value)


def _assert_reference_free_replay_content(value: Any) -> None:
    forbidden_keys = {
        "accepted_binding",
        "answer",
        "expected_answer",
        "gold",
        "inputs",
        "materialization",
        "reference",
        "reference_path",
        "reference_scores",
        "score",
        "tables",
        "terminal_seal",
        "truth",
    }

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            overlap = {str(key).lower() for key in current} & forbidden_keys
            if overlap:
                raise ReplayError(
                    "structural_repair_replay_input_reference_key_present:"
                    + sorted(overlap)[0]
                )
            for item in current.values():
                walk(item)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str) and re.search(
            r"(?:[A-Za-z]:\\|/Users/|/home/|\\Users\\)", current
        ):
            raise ReplayError("structural_repair_replay_input_private_path_present")

    walk(value)


def _load_json(path: Path, expected_type: type, subject: str) -> tuple[Any, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_strict_pairs(subject),
            parse_constant=lambda item: _raise_nonfinite(subject, item),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"structural_repair_replay_json_invalid:{subject}") from exc
    if not isinstance(value, expected_type):
        raise ReplayError(f"structural_repair_replay_json_root_invalid:{subject}")
    return value, hashlib.sha256(raw).hexdigest()


def _strict_pairs(subject: str):
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ReplayError(
                    f"structural_repair_replay_json_duplicate_key:{subject}:{key}"
                )
            result[key] = value
        return result

    return pairs


def _raise_nonfinite(subject: str, value: str) -> Any:
    raise ReplayError(f"structural_repair_replay_json_nonfinite:{subject}:{value}")


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
        key: _sha256_file(path) for key, path in SOURCE_FILES.items()
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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_string(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReplayError(f"structural_repair_replay_required_string:{subject}")
    return value


def _normalize(value: Any) -> str:
    rendered = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(rendered.split()).strip()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
