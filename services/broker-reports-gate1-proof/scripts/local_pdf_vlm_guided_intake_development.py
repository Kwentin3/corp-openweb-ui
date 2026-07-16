#!/usr/bin/env python3
"""Run and score the frozen VLM-guided PDF intake development corpus.

``run`` has no reference argument and seals a private terminal.  ``gate``
launches ``run`` first, waits for the seal, and only then launches the separate
scorer process with the human reference.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
DEFAULT_REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_BUNDLE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
DEFAULT_SCORER = SCRIPT_DIR / "local_pdf_vlm_guided_intake_development_score.py"
TERMINAL_SCHEMA = "broker_reports_pdf_vlm_guided_intake_development_terminal_v1"
SEAL_SCHEMA = "broker_reports_pdf_vlm_guided_intake_terminal_seal_v1"
MANIFEST_SCHEMA = "broker_reports_pdf_vlm_guided_intake_development_manifest_v1"
PROCESS_SCHEMA = "broker_reports_pdf_vlm_guided_intake_gate_processes_v1"
RESULT_SCHEMAS = {
    "broker_reports_pdf_vlm_guided_candidate_intake_result_v1",
    "broker_reports_pdf_vlm_guided_page_intake_result_v1",
    "broker_reports_pdf_vlm_guided_intake_result_v1",
    "broker_reports_pdf_vlm_guided_upstream_terminal_v1",
    "broker_reports_pdf_vlm_guided_skip_terminal_v1",
}
ROUTING_ROUTES = {
    "candidate_crop",
    "page_level",
    "skip_obvious_non_table",
    "upstream_failure",
}
PROVIDER_ROUTES = {"candidate_crop", "page_level"}
PRE_PROVIDER_ZERO_CALL_REASONS = {
    "pdf_visual_topology_atom_bbox_invalid",
    "pdf_visual_topology_atom_contract_invalid",
    "pdf_visual_topology_atom_normalization_defect",
    "pdf_visual_topology_atom_outside_selected_source_region",
    "pdf_visual_topology_coordinate_transform_defect",
    "pdf_visual_topology_provider_package_construction_invalid",
}
PROVIDER_ACCOUNTING_FIELDS = (
    "count_token_calls",
    "generate_calls",
    "journal_count_token_calls",
    "journal_generate_calls",
    "counted_input_tokens",
    "actual_input_tokens",
    "output_tokens",
    "package_id",
    "package_hash",
    "request_hash",
    "task_id",
    "attempt_id",
    "provider_profile",
    "provider_profile_revision",
    "model_requested",
    "model_resolved",
    "image_sha256",
    "image_bytes",
    "hidden_retry",
    "provider_failover",
    "journal_checksum",
)
LABEL_KEYS = {
    "accepted",
    "expected",
    "expected_kind",
    "expected_regions",
    "expected_route",
    "ground_truth",
    "is_table",
    "label",
    "negative",
    "positive",
    "truth",
}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
)
from broker_reports_gate1.artifact_models import ArtifactAccessContext  # noqa: E402
from broker_reports_gate1.artifact_retention import (  # noqa: E402
    build_retention_policy,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    sha256_json,
)
from broker_reports_gate1.pdf_structural_repair_runtime import (  # noqa: E402
    PdfStructuralRepairRuntimeConfig,
)
from broker_reports_gate1.pdf_structural_repair_shadow import (  # noqa: E402
    PdfStructuralRepairShadowConfig,
    PdfStructuralRepairShadowFactory,
)


class DevelopmentGateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_command(args)
    if args.command == "gate":
        return _gate_command(args)
    parser.error("command_required")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run without human reference")
    _add_run_arguments(run)

    gate = subparsers.add_parser(
        "gate", help="run, seal, then score in a separate process"
    )
    _add_run_arguments(gate)
    gate.add_argument("--reference", required=True)
    gate.add_argument("--scorer-script", default=str(DEFAULT_SCORER))
    return parser


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--corpus-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(DEFAULT_REPO_ROOT / ".env"))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))


def _run_command(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        print("development_fresh_output_directory_required", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = output_dir / "terminal.private.json"
    seal_path = output_dir / "terminal.private.sha256.json"
    terminal = {
        "schema_version": TERMINAL_SCHEMA,
        "runner": {
            "pid": os.getpid(),
            "entrypoint": "local_pdf_vlm_guided_intake_development.py run",
            "reference_argument_supported": False,
            "canonical_provider_factory": (
                "PdfGridExperimentProviderFactory.create_for_openwebui"
            ),
            "canonical_shadow_factory": "PdfStructuralRepairShadowFactory.create",
        },
        "reference_accessed": False,
        "manifest_sha256": None,
        "target_manifest": None,
        "manifest_case_ids": [],
        "source_revision": {},
        "normalization_accounting": {
            "cases_total": 0,
            "unique_pdf_sha256_total": 0,
            "cache_hits": 0,
        },
        "cases": [],
        "failures": [],
        "run_status": "failed_before_execution",
        "production_authority": False,
        "production_gate2_selection_changed": False,
        "ocr_performed": False,
        "knowledge_or_rag_used": False,
    }
    try:
        manifest_path = Path(args.manifest).resolve()
        manifest_bytes = manifest_path.read_bytes()
        manifest = _parse_json(manifest_bytes, "development_manifest_json_invalid")
        _validate_manifest(manifest)
        terminal["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        terminal["target_manifest"] = manifest
        terminal["manifest_case_ids"] = [
            str(item["case_id"]) for item in manifest["cases"]
        ]

        repo_root = Path(args.repo_root).resolve()
        bundle_path = Path(args.bundle).resolve()
        terminal["source_revision"] = _verify_source_revision(
            manifest=manifest,
            repo_root=repo_root,
            bundle_path=bundle_path,
        )
        corpus_root = Path(args.corpus_root).resolve()
        sources = _verify_sources(manifest=manifest, corpus_root=corpus_root)
        _require_product_routing_config()

        provider_contract = _object(manifest.get("provider_contract"))
        model_id = str(provider_contract["model_id"])
        provider = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                model_id=model_id,
                maximum_output_tokens=int(provider_contract["maximum_output_tokens"]),
                maximum_counted_input_tokens=int(
                    provider_contract["maximum_counted_input_tokens"]
                ),
            )
        ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
        runtime_config = PdfStructuralRepairRuntimeConfig(
            model_id=model_id,
            maximum_output_tokens=int(provider_contract["maximum_output_tokens"]),
            maximum_counted_input_tokens=int(
                provider_contract["maximum_counted_input_tokens"]
            ),
        )

        package_cache: dict[str, dict[str, Any]] = {}
        pdf_bytes_cache: dict[str, bytes] = {}
        cache_hits = 0
        for manifest_case in manifest["cases"]:
            case_id = str(manifest_case["case_id"])
            if str(manifest_case["pdf_sha256"]) in package_cache:
                cache_hits += 1
            try:
                terminal["cases"].append(
                    _run_case(
                        manifest_case=manifest_case,
                        pdf_path=sources[case_id],
                        output_dir=output_dir,
                        provider=provider,
                        runtime_config=runtime_config,
                        package_cache=package_cache,
                        pdf_bytes_cache=pdf_bytes_cache,
                        provider_contract=provider_contract,
                    )
                )
            except Exception as exc:  # terminal must survive every case failure
                code = _error_code(exc, "development_case_unexpected_failure")
                terminal["cases"].append(_failed_case_terminal(manifest_case, code))
                terminal["failures"].append({"case_id": case_id, "code": code})
        terminal["normalization_accounting"] = {
            "cases_total": len(manifest["cases"]),
            "unique_pdf_sha256_total": len(package_cache),
            "cache_hits": cache_hits,
        }
        terminal["run_status"] = (
            "completed" if not terminal["failures"] else "completed_with_failures"
        )
    except Exception as exc:
        terminal["failures"].append(
            {
                "case_id": None,
                "code": _error_code(exc, "development_runner_unexpected_failure"),
            }
        )
        terminal["run_status"] = "failed_before_case_completion"

    terminal_bytes = _canonical_json_bytes(terminal)
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": SEAL_SCHEMA,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
    }
    seal_path.write_bytes(_canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "run_status": terminal["run_status"],
                "terminal": str(terminal_path),
                "seal": str(seal_path),
                "terminal_sha256": seal["terminal_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _gate_command(args: argparse.Namespace) -> int:
    output_root = Path(args.output_dir).resolve()
    return run_gate_processes(
        manifest=Path(args.manifest).resolve(),
        corpus_root=Path(args.corpus_root).resolve(),
        output_root=output_root,
        env_file=Path(args.env_file).resolve(),
        repo_root=Path(args.repo_root).resolve(),
        bundle=Path(args.bundle).resolve(),
        reference=Path(args.reference).resolve(),
        runner_script=SCRIPT_PATH,
        scorer_script=Path(args.scorer_script).resolve(),
    )


def run_gate_processes(
    *,
    manifest: Path,
    corpus_root: Path,
    output_root: Path,
    env_file: Path,
    repo_root: Path,
    bundle: Path,
    reference: Path,
    runner_script: Path,
    scorer_script: Path,
) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        print("development_fresh_output_directory_required", file=sys.stderr)
        return 2
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / "run"
    score_path = output_root / "score.json"
    terminal_path = run_dir / "terminal.private.json"
    seal_path = run_dir / "terminal.private.sha256.json"
    run_command = [
        sys.executable,
        str(runner_script),
        "run",
        "--manifest",
        str(manifest),
        "--corpus-root",
        str(corpus_root),
        "--output-dir",
        str(run_dir),
        "--env-file",
        str(env_file),
        "--repo-root",
        str(repo_root),
        "--bundle",
        str(bundle),
    ]
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    run_process = subprocess.Popen(
        run_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=child_env,
    )
    run_stdout, run_stderr = run_process.communicate()

    terminal_sealed_before_scorer_started = (
        terminal_path.is_file() and seal_path.is_file()
    )
    gate_blocker_codes: list[str] = []
    if run_process.returncode != 0:
        gate_blocker_codes.append("development_runner_failed")
    if not terminal_sealed_before_scorer_started:
        gate_blocker_codes.append("development_terminal_not_sealed")

    score_command: list[str] = []
    score_process: subprocess.Popen[str] | None = None
    score_stdout = ""
    score_stderr = ""
    if not gate_blocker_codes:
        score_command = [
            sys.executable,
            str(scorer_script),
            "--terminal",
            str(terminal_path),
            "--seal",
            str(seal_path),
            "--reference",
            str(reference),
            "--output",
            str(score_path),
        ]
        score_process = subprocess.Popen(
            score_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=child_env,
        )
        score_stdout, score_stderr = score_process.communicate()
    process_evidence = {
        "schema_version": PROCESS_SCHEMA,
        "gate_pid": os.getpid(),
        "run_pid": run_process.pid,
        "scorer_pid": score_process.pid if score_process is not None else None,
        "scorer_started": score_process is not None,
        "separate_processes": score_process is not None
        and len({os.getpid(), run_process.pid, score_process.pid}) == 3,
        "run_returncode": run_process.returncode,
        "scorer_returncode": (
            score_process.returncode if score_process is not None else None
        ),
        "gate_blocker_codes": gate_blocker_codes,
        "terminal_sealed_before_scorer_started": (
            terminal_sealed_before_scorer_started
        ),
        "reference_argument_passed_to_run": "--reference" in run_command,
        "reference_argument_passed_to_scorer": "--reference" in score_command,
        "run_command_argument_names": _argument_names(run_command),
        "scorer_command_argument_names": _argument_names(score_command),
        "run_stderr": run_stderr[-4000:],
        "scorer_stderr": score_stderr[-4000:],
    }
    process_evidence["process_checksum"] = sha256_json(process_evidence)
    (output_root / "gate_processes.safe.json").write_bytes(
        _canonical_json_bytes(process_evidence)
    )
    if run_stdout:
        print(run_stdout.rstrip(), file=sys.stderr)
    if run_stderr and gate_blocker_codes:
        print(run_stderr.rstrip(), file=sys.stderr)
    if score_stdout:
        print(score_stdout.rstrip())
    elif score_stderr:
        print(score_stderr.rstrip(), file=sys.stderr)
    if run_process.returncode != 0:
        return int(run_process.returncode)
    if not terminal_sealed_before_scorer_started:
        return 1
    if score_process is None:
        raise RuntimeError("development_gate_scorer_not_started")
    return int(score_process.returncode or 0)


def _run_case(
    *,
    manifest_case: dict[str, Any],
    pdf_path: Path,
    output_dir: Path,
    provider: Any,
    runtime_config: PdfStructuralRepairRuntimeConfig,
    package_cache: dict[str, dict[str, Any]],
    pdf_bytes_cache: dict[str, bytes],
    provider_contract: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(manifest_case["case_id"])
    pdf_sha256 = str(manifest_case["pdf_sha256"])
    pdf_bytes = pdf_bytes_cache.get(pdf_sha256)
    if pdf_bytes is None:
        pdf_bytes = pdf_path.read_bytes()
        if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256:
            raise DevelopmentGateError("development_manifest_source_sha_mismatch")
        pdf_bytes_cache[pdf_sha256] = pdf_bytes
    cached_package = package_cache.get(pdf_sha256)
    if cached_package is None:
        normalized = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref=f"development-corpus:{pdf_sha256}",
                    filename=pdf_path.name,
                    content=pdf_bytes,
                    mime_type=mimetypes.guess_type(pdf_path.name)[0]
                    or "application/pdf",
                    source_kind="local_private_development_corpus",
                )
            ],
            entrypoint="local_pdf_vlm_guided_intake_development",
            trigger_type="frozen_development_corpus",
            input_context={
                "pdf_layout_slice2_enabled": True,
                "pdf_compact_canonical_dual_write": False,
                "pdf_hybrid_shadow_enabled": False,
                "pdf_hybrid_reliability_shadow_enabled": False,
            },
        )
        cached_package = copy.deepcopy(normalized.package)
        package_cache[pdf_sha256] = cached_package
    package = copy.deepcopy(cached_package)
    selection = _select_manifest_target(
        package=package,
        manifest_case=manifest_case,
    )
    config_fields = {
        item.name for item in dataclasses.fields(PdfStructuralRepairShadowConfig)
    }
    # The manifest selects a page/case only.  It cannot select the route: the
    # product router receives the whole page evidence and is the sole chooser
    # of candidate_crop, page_level, skip, or upstream_failure.
    config_values: dict[str, Any] = {
        "enabled": True,
        "vlm_guided_intake_enabled": True,
        "semantic_header_shadow_enabled": False,
        "vlm_guided_product_routing_enabled": True,
        "maximum_tables": 1,
        "table_allowlist": (),
        "page_allowlist": (f"{selection['document_ref']}::{selection['page_ref']}",),
    }
    config = PdfStructuralRepairShadowConfig(
        **{key: value for key, value in config_values.items() if key in config_fields}
    )
    runtime = PdfStructuralRepairShadowFactory(
        config,
        runtime_config=runtime_config,
    ).create(provider=provider)

    case_store_root = output_dir / "artifact_store" / case_id
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=case_store_root / "artifacts.sqlite3",
            payload_root=case_store_root / "payloads",
        )
    ).create()
    run_id = str(_object(package.get("normalization_run")).get("run_id") or "")
    if not run_id:
        raise DevelopmentGateError("development_normalization_run_id_missing")
    context = ArtifactAccessContext(
        user_id="user_vlm_guided_development",
        case_id=f"case_{case_id}",
        chat_id=f"chat_{case_id}",
        workspace_model_id="broker_reports_gate1",
        normalization_run_id=run_id,
        allow_private=True,
    )
    result = runtime.run(
        store=store,
        package=package,
        context=context,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
    )
    records = store.list_by_run(run_id)
    artifacts = [_artifact_snapshot(store, record) for record in records]
    target = _target_terminal(
        result=result,
        artifacts=artifacts,
        provider_contract=provider_contract,
    )
    return {
        "case_id": case_id,
        "source": {
            "relative_pdf": manifest_case["relative_pdf"],
            "pdf_sha256": pdf_sha256,
            "page_number": selection["page_number"],
            "parser_ordinal": selection.get("parser_ordinal"),
            "selector_anchor": selection["selector_anchor"],
            "document_ref": selection["document_ref"],
            "page_ref": selection["page_ref"],
            "table_ref": selection.get("table_ref"),
            "retained_prefix_evidence": selection["retained_prefix_evidence"],
        },
        "target_terminal": target,
        "artifact_store": {
            "mode": "sqlite",
            "records_total": len(artifacts),
            "artifact_refs": [item["artifact_id"] for item in artifacts],
            "artifacts": artifacts,
        },
    }


def _target_terminal(
    *,
    result: dict[str, Any],
    artifacts: list[dict[str, Any]],
    provider_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _object(result.get("summary"))
    outcomes = [
        item for item in summary.get("target_outcomes") or [] if isinstance(item, dict)
    ]
    target_payloads = [
        _object(item.get("payload"))
        for item in artifacts
        if _object(item.get("payload")).get("target_id")
    ]
    result_payloads = [
        item for item in target_payloads if item.get("schema_version") in RESULT_SCHEMAS
    ]
    state_payloads = [
        item
        for item in target_payloads
        if item.get("schema_version")
        == "broker_reports_pdf_structural_repair_target_state_v1"
    ]
    routing_terminal_payloads = [
        item
        for item in target_payloads
        if item not in result_payloads
        and item not in state_payloads
        and isinstance(
            item.get("runtime_terminal_status") or item.get("terminal_status"),
            str,
        )
        and (
            isinstance(item.get("finalized_intake_decisions"), dict)
            or isinstance(item.get("intake_decisions"), dict)
        )
        and (
            isinstance(item.get("product_routing"), dict)
            or isinstance(item.get("routing_decision"), dict)
        )
    ]
    terminal_payloads = [*result_payloads, *routing_terminal_payloads]
    primary = terminal_payloads[0] if len(terminal_payloads) == 1 else {}
    state = state_payloads[0] if len(state_payloads) == 1 else {}
    outcome = outcomes[0] if len(outcomes) == 1 else {}
    target_ids = {
        str(value)
        for value in (
            primary.get("target_id"),
            state.get("target_id"),
            outcome.get("target_id"),
        )
        if isinstance(value, str) and value
    }
    target_id = next(iter(target_ids)) if len(target_ids) == 1 else ""
    routing = _routing_evidence(primary)
    safe = _object(primary.get("safe_summary"))
    decision_projection = _intake_decision_projection(
        terminal_payloads=terminal_payloads,
        state_payloads=state_payloads,
    )
    decisions = decision_projection["decisions"]
    decision_totals = decision_projection["unique_totals"]
    binding = _object(primary.get("binding_result"))
    proposal = _object(primary.get("proposal")) or _object(
        _object(primary.get("proposal_result")).get("proposal")
    )
    proposal_projection = _outcome_projection(
        payloads=[*terminal_payloads, *state_payloads],
        terminal_payloads=terminal_payloads,
        state_payloads=state_payloads,
        kind="proposal",
    )
    binding_projection = _outcome_projection(
        payloads=[*terminal_payloads, *state_payloads],
        terminal_payloads=terminal_payloads,
        state_payloads=state_payloads,
        kind="binding",
    )
    count_calls, count_conflict = _integer_consensus(
        primary.get("new_provider_count_token_calls"),
        safe.get("count_token_calls"),
        outcome.get("count_token_calls"),
        _object(primary.get("provider_accounting")).get("count_token_calls"),
        _object(state.get("provider_accounting")).get("count_token_calls"),
        _object(
            _object(primary.get("upstream_terminal")).get("provider_accounting")
        ).get("count_token_calls"),
        _object(_object(state.get("upstream_terminal")).get("provider_accounting")).get(
            "count_token_calls"
        ),
    )
    generate_calls, generate_conflict = _integer_consensus(
        primary.get("new_provider_generate_calls"),
        safe.get("generate_calls"),
        outcome.get("generate_calls"),
        _object(primary.get("provider_accounting")).get("generate_calls"),
        _object(state.get("provider_accounting")).get("generate_calls"),
        _object(
            _object(primary.get("upstream_terminal")).get("provider_accounting")
        ).get("generate_calls"),
        _object(_object(state.get("upstream_terminal")).get("provider_accounting")).get(
            "generate_calls"
        ),
    )
    terminal_status = str(
        primary.get("runtime_terminal_status")
        or primary.get("terminal_status")
        or outcome.get("terminal_status")
        or ""
    )
    reason_codes = primary.get("reason_codes")
    if not isinstance(reason_codes, list):
        primary_reason = primary.get("reason_code")
        outcome_reason = outcome.get("reason_code")
        reason_codes = (
            [str(primary_reason or outcome_reason)]
            if primary_reason or outcome_reason
            else []
        )
    reason_codes = [str(item) for item in reason_codes]
    provider_accounting, provider_verification = _provider_accounting(
        primary=primary,
        state=state,
        count_calls=count_calls,
        generate_calls=generate_calls,
        route=str(routing.get("route") or ""),
        terminal_status=terminal_status,
        reason_codes=reason_codes,
        provider_contract=_object(provider_contract),
        count_conflict=count_conflict,
        generate_conflict=generate_conflict,
    )
    cardinality_failure_codes: list[str] = []
    if len(outcomes) != 1:
        cardinality_failure_codes.append(
            "development_target_outcome_cardinality_invalid"
        )
    if len(terminal_payloads) != 1:
        cardinality_failure_codes.append("development_terminal_cardinality_invalid")
    if len(state_payloads) != 1:
        cardinality_failure_codes.append("development_target_state_cardinality_invalid")
    if len(target_ids) != 1:
        cardinality_failure_codes.append("development_target_identity_conflict")
    cardinality_failure_codes.extend(proposal_projection["failure_codes"])
    cardinality_failure_codes.extend(binding_projection["failure_codes"])
    cardinality_failure_codes.extend(decision_projection["failure_codes"])
    cardinality_failure_codes = sorted(set(cardinality_failure_codes))
    return {
        "target_id": target_id,
        "target_outcomes_total": len(outcomes),
        "result_payloads_total": len(result_payloads),
        "routing_terminal_payloads_total": len(routing_terminal_payloads),
        "terminal_payloads_total": len(terminal_payloads),
        "target_state_payloads_total": len(state_payloads),
        "proposal_outcomes_total": proposal_projection["unique_total"],
        "proposal_outcome_views_total": proposal_projection["views_total"],
        "proposal_outcome": proposal_projection["outcome"],
        "binding_outcomes_total": binding_projection["unique_total"],
        "binding_outcome_views_total": binding_projection["views_total"],
        "binding_outcome": binding_projection["outcome"],
        "detection_decisions_total": decision_totals["detection"],
        "processability_decisions_total": decision_totals["processability"],
        "holdout_decisions_total": decision_totals["holdout"],
        "intake_decision_terminal_views_total": decision_projection[
            "terminal_views_total"
        ],
        "intake_decision_state_views_total": decision_projection[
            "state_views_total"
        ],
        "cardinality_failure_codes": cardinality_failure_codes,
        "terminal_cardinality_verified": not cardinality_failure_codes,
        "terminal_status": terminal_status,
        "reason_codes": reason_codes,
        "route_selected": routing.get("route"),
        "routing_evidence": routing,
        "routing_evidence_verified": _routing_evidence_verified(routing),
        "count_tokens_calls": count_calls,
        "generate_calls": generate_calls,
        "hidden_retry": _object(provider_accounting).get("hidden_retry"),
        "provider_failover": _object(provider_accounting).get("provider_failover"),
        "provider_accounting": provider_accounting,
        "provider_accounting_verification": provider_verification,
        "proposal": proposal or None,
        "binding_result": binding or None,
        "validation": _validation_projection(binding),
        "materialization": primary.get("materialization"),
        "intake_decisions": decisions or None,
        "private_diagnostic_refs": list(result.get("private_diagnostic_refs") or []),
        "runtime_result_refs": list(result.get("runtime_result_refs") or []),
        "routing_terminal_refs": [
            *list(result.get("guided_upstream_terminal_refs") or []),
            *list(result.get("guided_skip_terminal_refs") or []),
        ],
        "target_state_refs": list(result.get("private_target_state_refs") or []),
        "raw_result": primary or None,
    }


def _routing_evidence(primary: dict[str, Any]) -> dict[str, Any]:
    candidates: tuple[Any, ...] = (
        primary.get("product_routing"),
        primary.get("routing_decision"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _routing_evidence_verified(value: dict[str, Any]) -> bool:
    if (
        not isinstance(value, dict)
        or value.get("route") not in ROUTING_ROUTES
        or not isinstance(value.get("schema_version"), str)
        or not isinstance(
            value.get("detection_decision") or value.get("detection"), str
        )
        or not isinstance(value.get("reason_codes"), list)
        or not isinstance(value.get("observations"), dict)
    ):
        return False
    unsigned = dict(value)
    stored = unsigned.pop("routing_checksum", None)
    return isinstance(stored, str) and stored == sha256_json(unsigned)


def _validation_projection(binding: dict[str, Any]) -> dict[str, Any] | None:
    if not binding:
        return None
    return {
        "runtime_terminal_status": binding.get("runtime_terminal_status"),
        "reason_codes": binding.get("reason_codes"),
        "regions_proposed": _object(binding.get("source_accounting")).get(
            "regions_proposed"
        ),
        "regions_accepted": _object(binding.get("source_accounting")).get(
            "regions_accepted"
        ),
        "result_checksum": binding.get("result_checksum"),
    }


def _provider_accounting(
    *,
    primary: dict[str, Any],
    state: dict[str, Any],
    count_calls: int | None,
    generate_calls: int | None,
    route: str,
    terminal_status: str,
    reason_codes: list[str],
    provider_contract: dict[str, Any],
    count_conflict: bool,
    generate_conflict: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    terminal_proposal_result = _payload_proposal_result(primary)
    state_proposal_result = _payload_proposal_result(state)
    terminal_journal = _provider_journal(terminal_proposal_result)
    state_journal = _provider_journal(state_proposal_result)
    explicit_terminal = _payload_provider_accounting(primary)
    explicit_state = _payload_provider_accounting(state)
    views: dict[str, dict[str, Any]] = {}
    journal_views: dict[str, dict[str, Any]] = {}
    failures: list[str] = []

    if explicit_terminal:
        views["terminal"] = explicit_terminal
    elif terminal_journal:
        views["terminal"] = _journal_provider_accounting(
            primary=primary,
            state=state,
            proposal_result=terminal_proposal_result,
            journal=terminal_journal,
        )
    else:
        failures.append("development_provider_accounting_terminal_view_missing")
    if explicit_state:
        views["state"] = explicit_state
    else:
        failures.append("development_provider_accounting_state_view_missing")

    journal_required = bool(
        count_calls or generate_calls or terminal_journal or state_journal
    )
    for label, proposal_result, journal in (
        ("terminal", terminal_proposal_result, terminal_journal),
        ("state", state_proposal_result, state_journal),
    ):
        if journal:
            journal_views[label] = _journal_provider_accounting(
                primary=primary,
                state=state,
                proposal_result=proposal_result,
                journal=journal,
            )
        elif journal_required:
            failures.append(
                f"development_provider_accounting_{label}_journal_view_missing"
            )

    unique_journal_views = {
        _canonical_json_bytes(value): value for value in journal_views.values()
    }
    journal_conflict = len(unique_journal_views) > 1
    journal_verified = not journal_required
    if journal_conflict:
        failures.append("development_provider_accounting_journal_view_conflict")
    elif (
        journal_required
        and set(journal_views) == {"state", "terminal"}
        and len(unique_journal_views) == 1
    ):
        views["journal"] = next(iter(unique_journal_views.values()))
        journal_verified = True
    elif journal_required:
        failures.append("development_provider_accounting_journal_view_missing")

    for label, value in views.items():
        failures.extend(_provider_accounting_view_failures(value, label=label))
    unique_views = {_canonical_json_bytes(value): value for value in views.values()}
    if len(unique_views) > 1:
        failures.append("development_provider_accounting_view_conflict")
    accounting = (
        next(iter(unique_views.values()))
        if len(unique_views) == 1 and journal_verified
        else None
    )
    if count_conflict:
        failures.append("development_provider_accounting_count_token_view_conflict")
    if generate_conflict:
        failures.append("development_provider_accounting_generate_view_conflict")
    failures.extend(
        _provider_accounting_contract_failures(
            accounting=accounting,
            count_calls=count_calls,
            generate_calls=generate_calls,
            route=route,
            terminal_status=terminal_status,
            reason_codes=reason_codes,
            provider_contract=provider_contract,
        )
    )
    failures = sorted(set(failures))
    verification = {
        "schema_version": "broker_reports_pdf_vlm_guided_provider_accounting_verification_v1",
        "views_observed": sorted(views),
        "view_checksums": {
            label: value.get("accounting_checksum")
            for label, value in sorted(views.items())
        },
        "unique_views_total": len(unique_views),
        "journal_views_observed": sorted(journal_views),
        "journal_view_checksums": {
            label: value.get("accounting_checksum")
            for label, value in sorted(journal_views.items())
        },
        "journal_unique_views_total": len(unique_journal_views),
        "pre_provider_zero_call_allowed": _pre_provider_zero_call_allowed(
            route=route,
            terminal_status=terminal_status,
            reason_codes=reason_codes,
            count_calls=count_calls,
            generate_calls=generate_calls,
        ),
        "failure_codes": failures,
        "verified": not failures,
    }
    verification["verification_checksum"] = sha256_json(verification)
    return accounting, verification


def _intake_decision_projection(
    *,
    terminal_payloads: list[dict[str, Any]],
    state_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    terminal_views = _intake_decision_views(terminal_payloads)
    state_views = _intake_decision_views(state_payloads)
    selected: dict[str, Any] = {}
    unique_totals: dict[str, int] = {}
    failures: list[str] = []

    if len(terminal_views) != 1 or len(state_views) != 1:
        failures.append("development_intake_decision_view_cardinality_invalid")
    for name in ("detection", "processability", "holdout"):
        terminal_values = [
            value for value in (_object(item.get(name)) for item in terminal_views) if value
        ]
        state_values = [
            value for value in (_object(item.get(name)) for item in state_views) if value
        ]
        unique = {
            _canonical_json_bytes(value): value
            for value in (*terminal_values, *state_values)
        }
        unique_totals[name] = len(unique)
        if len(terminal_values) != 1 or len(state_values) != 1:
            failures.append(f"development_{name}_decision_cardinality_invalid")
            failures.append("development_intake_decision_view_cardinality_invalid")
            continue
        if _canonical_json_bytes(terminal_values[0]) != _canonical_json_bytes(
            state_values[0]
        ):
            failures.append(f"development_{name}_decision_cardinality_invalid")
            failures.append("development_intake_decision_cross_view_conflict")
            continue
        selected[name] = terminal_values[0]

    return {
        "decisions": selected,
        "unique_totals": unique_totals,
        "terminal_views_total": len(terminal_views),
        "state_views_total": len(state_views),
        "failure_codes": sorted(set(failures)),
    }


def _intake_decision_views(
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        value
        for payload in payloads
        for value in (
            payload.get("finalized_intake_decisions"),
            payload.get("intake_decisions"),
        )
        if isinstance(value, dict)
    ]


def _outcome_projection(
    *,
    payloads: list[dict[str, Any]],
    terminal_payloads: list[dict[str, Any]],
    state_payloads: list[dict[str, Any]],
    kind: str,
) -> dict[str, Any]:
    getter = _proposal_outcome_view if kind == "proposal" else _binding_outcome_view
    views = [value for value in (getter(item) for item in payloads) if value]
    unique = {_canonical_json_bytes(value): value for value in views}
    expected_views = len(terminal_payloads) + len(state_payloads)
    failures: list[str] = []
    if len(unique) != 1:
        failures.append(f"development_{kind}_outcome_cardinality_invalid")
    if len(views) != expected_views or expected_views != 2:
        failures.append(f"development_{kind}_outcome_view_cardinality_invalid")
    if any(not _outcome_checksum_verified(value) for value in views):
        failures.append(f"development_{kind}_outcome_checksum_invalid")
    return {
        "views_total": len(views),
        "unique_total": len(unique),
        "outcome": next(iter(unique.values())) if len(unique) == 1 else None,
        "failure_codes": failures,
    }


def _proposal_outcome_view(payload: dict[str, Any]) -> dict[str, Any] | None:
    explicit = _object(payload.get("proposal_outcome")) or _object(
        _object(payload.get("upstream_terminal")).get("proposal_outcome")
    )
    if explicit:
        return explicit
    proposal_result = _object(payload.get("proposal_result"))
    proposal = _object(payload.get("proposal")) or _object(
        proposal_result.get("proposal")
    )
    journal = [
        item for item in proposal_result.get("journal") or [] if isinstance(item, dict)
    ]
    raw_proposals = [
        _object(item.get("topology_response"))
        for item in journal
        if _object(item.get("topology_response"))
    ]
    if not proposal_result and not proposal:
        return None
    raw = raw_proposals[0] if len(raw_proposals) == 1 else {}
    generate_calls, _ = _integer_consensus(
        payload.get("new_provider_generate_calls"),
        _object(payload.get("safe_summary")).get("generate_calls"),
    )
    status = (
        "persisted"
        if proposal
        else ("invalid" if raw else ("missing" if generate_calls else "not_attempted"))
    )
    binding = _object(payload.get("binding_result"))
    value = {
        "status": status,
        "proposal_scope": (
            payload.get("proposal_scope")
            or proposal.get("proposal_scope")
            or _object(payload.get("visual_package")).get("proposal_scope")
        ),
        "proposal_checksum": (binding.get("proposal_checksum") if proposal else None)
        or (sha256_json(proposal) if proposal else None),
        "raw_proposal_checksum": sha256_json(raw) if raw else None,
        "reason_codes": (
            []
            if status in {"persisted", "not_attempted"}
            else _payload_reason_codes(payload)
        ),
    }
    value["outcome_checksum"] = sha256_json(value)
    return value


def _binding_outcome_view(payload: dict[str, Any]) -> dict[str, Any] | None:
    explicit = _object(payload.get("binding_outcome")) or _object(
        _object(payload.get("upstream_terminal")).get("binding_outcome")
    )
    if explicit:
        return explicit
    binding = _object(payload.get("binding_result"))
    proposal_result = _object(payload.get("proposal_result"))
    if not binding and not proposal_result:
        return None
    reason_codes = _payload_reason_codes(payload)
    attempted_failed = bool(
        not binding
        and any(code.startswith("pdf_vlm_region_binding_") for code in reason_codes)
    )
    if binding:
        binding_reasons = sorted(
            set(str(item) for item in binding.get("reason_codes") or [])
        )
    elif attempted_failed:
        binding_reasons = reason_codes
    else:
        failure_reason = _proposal_failure_reason_for_binding(payload)
        binding_reasons = [failure_reason] if failure_reason else []
    value = {
        "status": "completed"
        if binding
        else ("attempted_failed" if attempted_failed else "not_applicable"),
        "binding_checksum": binding.get("result_checksum") if binding else None,
        "reason_codes": binding_reasons,
    }
    value["outcome_checksum"] = sha256_json(value)
    return value


def _proposal_failure_reason_for_binding(payload: dict[str, Any]) -> str | None:
    proposal_result = _object(payload.get("proposal_result"))
    terminal = str(proposal_result.get("runtime_terminal_status") or "")
    reasons = [
        str(item)
        for item in _object(proposal_result.get("safe_summary")).get("reason_codes")
        or []
        if isinstance(item, str) and item
    ]
    scope = str(payload.get("proposal_scope") or "")
    failed = (
        terminal in {"preflight_blocked", "provider_failed"}
        if scope == "candidate_crop"
        else terminal != "proposal_persisted"
    )
    return reasons[0] if failed and reasons else None


def _outcome_checksum_verified(value: dict[str, Any]) -> bool:
    unsigned = dict(value)
    stored = unsigned.pop("outcome_checksum", None)
    return isinstance(stored, str) and stored == sha256_json(unsigned)


def _payload_reason_codes(payload: dict[str, Any]) -> list[str]:
    values = payload.get("reason_codes")
    if isinstance(values, list):
        return sorted(set(str(item) for item in values))
    value = payload.get("reason_code")
    return [str(value)] if value else []


def _integer_consensus(*values: Any) -> tuple[int | None, bool]:
    integers = {
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
    }
    return (next(iter(integers)) if len(integers) == 1 else None, len(integers) > 1)


def _payload_provider_accounting(payload: dict[str, Any]) -> dict[str, Any]:
    return _object(payload.get("provider_accounting")) or _object(
        _object(payload.get("upstream_terminal")).get("provider_accounting")
    )


def _payload_proposal_result(payload: dict[str, Any]) -> dict[str, Any]:
    direct = _object(payload.get("proposal_result")) or _object(
        _object(payload.get("upstream_terminal")).get("proposal_result")
    )
    if direct:
        return direct
    return payload if isinstance(payload.get("journal"), list) else {}


def _provider_journal(proposal_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in proposal_result.get("journal") or []
        if isinstance(item, dict)
    ]


def _journal_provider_accounting(
    *,
    primary: dict[str, Any],
    state: dict[str, Any],
    proposal_result: dict[str, Any],
    journal: list[dict[str, Any]],
) -> dict[str, Any]:
    count_entries = [
        item
        for item in journal
        if item.get("provider_count_token_call_performed") is True
    ]
    generate_entries = [
        item for item in journal if item.get("provider_generate_call_performed") is True
    ]
    attempts = [
        _object(item.get("provider_attempt"))
        for item in generate_entries
        if _object(item.get("provider_attempt"))
    ]
    count_record = (
        _object(count_entries[0].get("count_tokens")) if len(count_entries) == 1 else {}
    )
    attempt = attempts[0] if len(attempts) == 1 else {}
    usage = _object(attempt.get("usage"))
    visual = _object(primary.get("visual_package")) or _object(
        state.get("visual_package")
    )
    crop = _object(visual.get("crop_identity"))
    journal_entry = journal[0] if len(journal) == 1 else {}
    value = {
        "count_token_calls": len(count_entries),
        "generate_calls": len(generate_entries),
        "journal_count_token_calls": len(count_entries),
        "journal_generate_calls": len(generate_entries),
        "counted_input_tokens": count_record.get("total_tokens"),
        "actual_input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "package_id": proposal_result.get("package_id") or visual.get("package_id"),
        "package_hash": proposal_result.get("package_hash")
        or visual.get("package_hash"),
        "request_hash": count_record.get("request_hash") or attempt.get("request_hash"),
        "task_id": journal_entry.get("task_id") or attempt.get("task_id"),
        "attempt_id": attempt.get("attempt_id"),
        "provider_profile": attempt.get("provider_profile"),
        "provider_profile_revision": attempt.get("provider_profile_revision"),
        "model_requested": attempt.get("model_requested")
        or count_record.get("model_requested"),
        "model_resolved": attempt.get("model_resolved"),
        "image_sha256": attempt.get("crop_sha256") or crop.get("crop_sha256"),
        "image_bytes": crop.get("png_bytes"),
        "hidden_retry": any(item.get("hidden_retry") is True for item in attempts),
        "provider_failover": any(
            item.get("provider_failover") is True for item in attempts
        ),
        "journal_checksum": sha256_json(journal),
    }
    value["accounting_checksum"] = sha256_json(value)
    return value


def _provider_accounting_view_failures(
    value: dict[str, Any], *, label: str
) -> list[str]:
    failures: list[str] = []
    expected = {*PROVIDER_ACCOUNTING_FIELDS, "accounting_checksum"}
    if set(value) != expected:
        failures.append(f"development_provider_accounting_{label}_view_invalid")
    unsigned = dict(value)
    stored = unsigned.pop("accounting_checksum", None)
    if not isinstance(stored, str) or stored != sha256_json(unsigned):
        failures.append(f"development_provider_accounting_{label}_checksum_invalid")
    return failures


def _provider_accounting_contract_failures(
    *,
    accounting: dict[str, Any] | None,
    count_calls: int | None,
    generate_calls: int | None,
    route: str,
    terminal_status: str,
    reason_codes: list[str],
    provider_contract: dict[str, Any],
) -> list[str]:
    if accounting is None:
        return ["development_provider_accounting_authoritative_view_missing"]
    failures: list[str] = []
    if (
        accounting.get("count_token_calls") != count_calls
        or accounting.get("generate_calls") != generate_calls
        or accounting.get("journal_count_token_calls") != count_calls
        or accounting.get("journal_generate_calls") != generate_calls
    ):
        failures.append("development_provider_accounting_counter_mismatch")
    if accounting.get("hidden_retry") is not False:
        failures.append("development_provider_accounting_hidden_retry_detected")
    if accounting.get("provider_failover") is not False:
        failures.append("development_provider_accounting_provider_failover_detected")

    pre_provider = _pre_provider_zero_call_allowed(
        route=route,
        terminal_status=terminal_status,
        reason_codes=reason_codes,
        count_calls=count_calls,
        generate_calls=generate_calls,
    )
    if route in PROVIDER_ROUTES and not pre_provider:
        if count_calls != 1:
            failures.append("development_provider_count_token_call_cardinality_invalid")
        if generate_calls not in {0, 1}:
            failures.append("development_provider_generate_call_cardinality_invalid")
        counted = accounting.get("counted_input_tokens")
        if not isinstance(counted, int) or isinstance(counted, bool) or counted <= 0:
            failures.append("development_provider_counted_input_tokens_missing")
        if generate_calls == 1:
            actual = accounting.get("actual_input_tokens")
            output = accounting.get("output_tokens")
            if not isinstance(actual, int) or isinstance(actual, bool) or actual <= 0:
                failures.append("development_provider_actual_input_tokens_missing")
            elif actual != counted:
                failures.append("development_provider_input_token_count_mismatch")
            if not isinstance(output, int) or isinstance(output, bool) or output < 0:
                failures.append("development_provider_output_tokens_missing")
            if not _nonempty_string(accounting.get("attempt_id")):
                failures.append("development_provider_attempt_identity_missing")
            if any(
                not _nonempty_string(accounting.get(field))
                for field in ("provider_profile", "provider_profile_revision")
            ):
                failures.append("development_provider_identity_missing")
            if not _nonempty_string(accounting.get("model_resolved")):
                failures.append("development_provider_model_identity_missing")
        elif (
            accounting.get("actual_input_tokens") is not None
            or accounting.get("output_tokens") is not None
        ):
            failures.append("development_provider_unexpected_generate_usage")
        for fields, code in (
            (
                ("package_id", "package_hash"),
                "development_provider_package_identity_missing",
            ),
            (
                ("request_hash", "task_id"),
                "development_provider_request_identity_missing",
            ),
            (("model_requested",), "development_provider_model_identity_missing"),
            (("image_sha256",), "development_provider_image_identity_missing"),
        ):
            if any(not _nonempty_string(accounting.get(field)) for field in fields):
                failures.append(code)
        image_bytes = accounting.get("image_bytes")
        if (
            not isinstance(image_bytes, int)
            or isinstance(image_bytes, bool)
            or image_bytes <= 0
        ):
            failures.append("development_provider_image_identity_missing")
        expected_profile = provider_contract.get("provider_profile")
        expected_model = provider_contract.get("model_id")
        if (
            generate_calls == 1
            and expected_profile
            and accounting.get("provider_profile") != expected_profile
        ):
            failures.append("development_provider_manifest_profile_mismatch")
        if expected_model and (
            accounting.get("model_requested") != expected_model
            or (
                generate_calls == 1
                and accounting.get("model_resolved") != expected_model
            )
        ):
            failures.append("development_provider_manifest_model_mismatch")
    else:
        if count_calls != 0 or generate_calls != 0:
            failures.append("development_provider_zero_call_contract_invalid")
        if any(
            accounting.get(field) is not None
            for field in (
                "counted_input_tokens",
                "actual_input_tokens",
                "output_tokens",
            )
        ):
            failures.append("development_provider_zero_call_usage_invalid")
    if route in PROVIDER_ROUTES and count_calls == 0 and not pre_provider:
        failures.append("development_provider_pre_provider_reason_invalid")
    return failures


def _pre_provider_zero_call_allowed(
    *,
    route: str,
    terminal_status: str,
    reason_codes: list[str],
    count_calls: int | None,
    generate_calls: int | None,
) -> bool:
    observed = set(reason_codes)
    return bool(
        route in PROVIDER_ROUTES
        and terminal_status == "guided_upstream_blocked"
        and count_calls == 0
        and generate_calls == 0
        and observed
        and observed <= PRE_PROVIDER_ZERO_CALL_REASONS
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _artifact_snapshot(store: Any, record: Any) -> dict[str, Any]:
    return {
        "artifact_id": record.artifact_id,
        "artifact_type": record.artifact_type,
        "schema_version": record.schema_version,
        "document_id": record.document_id,
        "visibility": record.visibility,
        "validation_status": record.validation_status,
        "lifecycle_status": record.lifecycle_status,
        "payload_snapshot_sha256": _record_checksum(store, record),
        "payload": store.read_payload(record),
        "warning_codes": list(record.warning_codes),
    }


def _record_checksum(store: Any, record: Any) -> str | None:
    value = store.read_payload(record)
    if value is None:
        return None
    artifact_bytes = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(artifact_bytes).hexdigest()


def _select_manifest_target(
    *, package: dict[str, Any], manifest_case: dict[str, Any]
) -> dict[str, Any]:
    payloads = [
        item
        for item in package.get("private_normalized_source_payloads") or []
        if isinstance(item, dict)
    ]
    if len(payloads) != 1:
        raise DevelopmentGateError("development_source_projection_scope_invalid")
    source = payloads[0]
    projection = source.get("pdf_text_layer_projection")
    if not isinstance(projection, dict):
        raise DevelopmentGateError("development_source_projection_missing")
    selector = _object(manifest_case.get("selector"))
    page_number = int(selector["page_number"])
    pages = [
        item
        for item in projection.get("page_inventory") or []
        if isinstance(item, dict) and item.get("page_number") == page_number
    ]
    if len(pages) != 1:
        raise DevelopmentGateError("development_manifest_page_selector_unresolved")
    page_ref = str(pages[0].get("page_ref") or "")
    parser_ordinal_value = selector.get("parser_ordinal")
    result = {
        "selector_anchor": (
            "parser_candidate" if parser_ordinal_value is not None else "page"
        ),
        "document_ref": str(source.get("document_ref") or ""),
        "page_ref": page_ref,
        "page_number": page_number,
        "table_ref": None,
        "parser_ordinal": None,
        "retained_prefix_evidence": _retained_prefix_evidence(
            projection=projection,
            selected_page=pages[0],
            selected_page_number=page_number,
        ),
    }
    if parser_ordinal_value is not None:
        parser_ordinal = int(parser_ordinal_value)
        candidates = [
            item
            for item in projection.get("table_candidate_inventory") or []
            if isinstance(item, dict)
            and item.get("page_ref") == page_ref
            and item.get("parser_ordinal") == parser_ordinal
        ]
        if len(candidates) != 1:
            raise DevelopmentGateError(
                "development_manifest_candidate_selector_unresolved"
            )
        result["table_ref"] = str(candidates[0].get("table_candidate_ref") or "")
        result["parser_ordinal"] = parser_ordinal
    if not result["document_ref"] or not page_ref:
        raise DevelopmentGateError("development_source_identity_missing")
    return result


def _retained_prefix_evidence(
    *,
    projection: dict[str, Any],
    selected_page: dict[str, Any],
    selected_page_number: int,
) -> dict[str, Any]:
    diagnostics = _object(projection.get("layout_parser_diagnostics"))
    source_pages = diagnostics.get("source_pages_total")
    completed_pages = diagnostics.get("completed_pages_total")
    missing_tail = diagnostics.get("missing_tail_pages_total")
    first_missing = diagnostics.get("first_missing_page_number")
    retained = diagnostics.get("inventory_objects_retained_total")
    would_be = diagnostics.get("inventory_objects_would_be_total")
    limit = diagnostics.get("inventory_objects_limit")
    document_status = projection.get("layout_projection_status")
    document_reasons = [
        str(item) for item in projection.get("layout_reason_codes") or []
    ]
    page_status = selected_page.get("layout_projection_status")
    page_reasons = [
        str(item) for item in selected_page.get("layout_reason_codes") or []
    ]
    accounted = bool(
        document_status == "partial"
        and "pdf_layout_document_inventory_budget_exceeded" in document_reasons
        and _positive_int(source_pages)
        and _positive_int(completed_pages)
        and isinstance(missing_tail, int)
        and not isinstance(missing_tail, bool)
        and missing_tail > 0
        and completed_pages + missing_tail == source_pages
        and first_missing == completed_pages + 1
        and selected_page_number <= completed_pages
        and page_status == "complete"
        and isinstance(retained, int)
        and not isinstance(retained, bool)
        and isinstance(would_be, int)
        and not isinstance(would_be, bool)
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and 0 <= retained <= limit < would_be
    )
    evidence = {
        "document_projection_status": document_status,
        "document_reason_codes": document_reasons,
        "source_pages_total": source_pages,
        "completed_pages_total": completed_pages,
        "missing_tail_pages_total": missing_tail,
        "first_missing_page_number": first_missing,
        "inventory_objects_limit": limit,
        "inventory_objects_retained_total": retained,
        "inventory_objects_would_be_total": would_be,
        "selected_page_number": selected_page_number,
        "selected_page_projection_status": page_status,
        "selected_page_reason_codes": page_reasons,
        "retained_prefix_accounted": accounted,
    }
    evidence["evidence_checksum"] = sha256_json(evidence)
    return evidence


def _verify_source_revision(
    *, manifest: dict[str, Any], repo_root: Path, bundle_path: Path
) -> dict[str, Any]:
    revision = _object(manifest.get("source_revision"))
    expected_commit = str(revision.get("repository_commit_sha") or "")
    expected_bundle = str(revision.get("gate1_bundle_sha256") or "")
    actual_commit = _git(repo_root, "rev-parse", "HEAD").strip()
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if actual_commit != expected_commit:
        raise DevelopmentGateError("development_source_commit_sha_mismatch")
    if revision.get("require_clean_worktree", True) is True and status.strip():
        raise DevelopmentGateError("development_source_worktree_not_clean")
    if not bundle_path.is_file():
        raise DevelopmentGateError("development_gate1_bundle_missing")
    bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    if bundle_sha != expected_bundle:
        raise DevelopmentGateError("development_gate1_bundle_sha_mismatch")
    return {
        "repository_commit_sha": actual_commit,
        "gate1_bundle_sha256": bundle_sha,
        "worktree_clean": not bool(status.strip()),
        "bundle_path": str(bundle_path.relative_to(repo_root)),
    }


def _verify_sources(*, manifest: dict[str, Any], corpus_root: Path) -> dict[str, Path]:
    resolved_root = corpus_root.resolve()
    sources: dict[str, Path] = {}
    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        path = (resolved_root / str(case["relative_pdf"])).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise DevelopmentGateError(
                "development_manifest_source_path_escape"
            ) from exc
        if not path.is_file():
            raise DevelopmentGateError("development_manifest_source_missing")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != case["pdf_sha256"]:
            raise DevelopmentGateError("development_manifest_source_sha_mismatch")
        sources[case_id] = path
    return sources


def _validate_manifest(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != MANIFEST_SCHEMA:
        raise DevelopmentGateError("development_manifest_schema_invalid")
    leaked = sorted(_label_keys(value))
    if leaked:
        raise DevelopmentGateError("development_manifest_contains_reference_labels")
    revision = _object(value.get("source_revision"))
    if (
        HEX_40.fullmatch(str(revision.get("repository_commit_sha") or "")) is None
        or HEX_64.fullmatch(str(revision.get("gate1_bundle_sha256") or "")) is None
        or not isinstance(revision.get("require_clean_worktree", True), bool)
    ):
        raise DevelopmentGateError("development_manifest_source_revision_invalid")
    provider = _object(value.get("provider_contract"))
    if (
        provider.get("provider_profile") != "google_gemini"
        or provider.get("model_id") != "models/gemini-3.5-flash"
        or provider.get("maximum_counted_input_tokens") != 20_000
        or provider.get("maximum_output_tokens") != 8_192
        or provider.get("hidden_retry") is not False
        or provider.get("provider_failover") is not False
    ):
        raise DevelopmentGateError("development_manifest_provider_contract_invalid")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise DevelopmentGateError("development_manifest_cases_invalid")
    ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise DevelopmentGateError("development_manifest_case_invalid")
        case_id = str(case.get("case_id") or "")
        relative = case.get("relative_pdf")
        selector = _object(case.get("selector"))
        selector_keys = set(selector)
        if (
            not case_id
            or len(case_id) > 128
            or not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or HEX_64.fullmatch(str(case.get("pdf_sha256") or "")) is None
            or selector_keys not in ({"page_number"}, {"page_number", "parser_ordinal"})
            or not _positive_int(selector.get("page_number"))
            or (
                "parser_ordinal" in selector
                and not _positive_int(selector.get("parser_ordinal"))
            )
        ):
            raise DevelopmentGateError("development_manifest_case_invalid")
        ids.append(case_id)
    if len(ids) != len(set(ids)):
        raise DevelopmentGateError("development_manifest_case_duplicate")


def _require_product_routing_config() -> None:
    fields = {item.name for item in dataclasses.fields(PdfStructuralRepairShadowConfig)}
    if "vlm_guided_product_routing_enabled" not in fields:
        raise DevelopmentGateError("development_product_routing_contract_unavailable")


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
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
        raise DevelopmentGateError("development_openwebui_credentials_missing")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(_object(response.json()).get("token") or "")
    if not token:
        raise DevelopmentGateError("development_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = _object(config_response.json())
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
                    OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
                    OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
                )
            )
        )
    )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise DevelopmentGateError("development_env_file_missing")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _failed_case_terminal(manifest_case: dict[str, Any], code: str) -> dict[str, Any]:
    selector = _object(manifest_case.get("selector"))
    return {
        "case_id": manifest_case.get("case_id"),
        "source": {
            "relative_pdf": manifest_case.get("relative_pdf"),
            "pdf_sha256": manifest_case.get("pdf_sha256"),
            "page_number": selector.get("page_number"),
            "parser_ordinal": selector.get("parser_ordinal"),
            "selector_anchor": (
                "parser_candidate"
                if selector.get("parser_ordinal") is not None
                else "page"
            ),
        },
        "target_terminal": {
            "target_id": None,
            "target_outcomes_total": 0,
            "result_payloads_total": 0,
            "routing_terminal_payloads_total": 0,
            "terminal_payloads_total": 0,
            "target_state_payloads_total": 0,
            "proposal_outcomes_total": 0,
            "proposal_outcome_views_total": 0,
            "proposal_outcome": None,
            "binding_outcomes_total": 0,
            "binding_outcome_views_total": 0,
            "binding_outcome": None,
            "detection_decisions_total": 0,
            "processability_decisions_total": 0,
            "holdout_decisions_total": 0,
            "cardinality_failure_codes": [
                "development_target_outcome_cardinality_invalid",
                "development_terminal_cardinality_invalid",
                "development_target_state_cardinality_invalid",
                "development_proposal_outcome_cardinality_invalid",
                "development_binding_outcome_cardinality_invalid",
                "development_detection_decision_cardinality_invalid",
                "development_processability_decision_cardinality_invalid",
                "development_holdout_decision_cardinality_invalid",
            ],
            "terminal_cardinality_verified": False,
            "terminal_status": code,
            "reason_codes": [code],
            "route_selected": None,
            "routing_evidence": None,
            "routing_evidence_verified": False,
            "count_tokens_calls": None,
            "generate_calls": None,
            "hidden_retry": None,
            "provider_failover": None,
            "provider_accounting": None,
            "provider_accounting_verification": None,
            "proposal": None,
            "binding_result": None,
            "validation": None,
            "materialization": None,
            "intake_decisions": None,
            "private_diagnostic_refs": [],
            "runtime_result_refs": [],
            "routing_terminal_refs": [],
            "target_state_refs": [],
            "raw_result": None,
        },
        "artifact_store": {
            "mode": "sqlite",
            "records_total": 0,
            "artifact_refs": [],
            "artifacts": [],
        },
    }


def _label_keys(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in LABEL_KEYS or lowered.startswith("expected_"):
                findings.append(f"{prefix}.{key}")
            findings.extend(_label_keys(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_label_keys(child, f"{prefix}[{index}]"))
    return findings


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _parse_json(value: bytes, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DevelopmentGateError(code) from exc
    if not isinstance(parsed, dict):
        raise DevelopmentGateError(code)
    return parsed


def _error_code(exc: BaseException, fallback: str) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    if isinstance(exc, requests.RequestException):
        return "development_openwebui_transport_failed"
    if isinstance(exc, subprocess.CalledProcessError):
        return "development_source_revision_command_failed"
    return f"{fallback}:{exc.__class__.__name__}"


def _argument_names(command: list[str]) -> list[str]:
    return [item for item in command if item.startswith("--")]


def _first_integer(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
