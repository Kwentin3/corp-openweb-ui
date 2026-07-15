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
    run_process = subprocess.Popen(
        run_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    run_stdout, run_stderr = run_process.communicate()

    terminal_sealed_before_scorer_started = (
        terminal_path.is_file() and seal_path.is_file()
    )
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
    )
    score_stdout, score_stderr = score_process.communicate()
    process_evidence = {
        "schema_version": PROCESS_SCHEMA,
        "gate_pid": os.getpid(),
        "run_pid": run_process.pid,
        "scorer_pid": score_process.pid,
        "separate_processes": len({os.getpid(), run_process.pid, score_process.pid})
        == 3,
        "run_returncode": run_process.returncode,
        "scorer_returncode": score_process.returncode,
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
    if score_stdout:
        print(score_stdout.rstrip())
    elif score_stderr:
        print(score_stderr.rstrip(), file=sys.stderr)
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
    target = _target_terminal(result=result, artifacts=artifacts)
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
    *, result: dict[str, Any], artifacts: list[dict[str, Any]]
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
    primary = (
        terminal_payloads[0]
        if len(terminal_payloads) == 1
        else (state_payloads[0] if len(state_payloads) == 1 else {})
    )
    outcome = outcomes[0] if len(outcomes) == 1 else {}
    target_id = str(primary.get("target_id") or outcome.get("target_id") or "")
    routing = _routing_evidence(primary, target_payloads)
    safe = _object(primary.get("safe_summary"))
    decisions = _object(
        primary.get("finalized_intake_decisions") or primary.get("intake_decisions")
    )
    if not decisions:
        for payload in target_payloads:
            decisions = _object(
                payload.get("finalized_intake_decisions")
                or payload.get("intake_decisions")
            )
            if decisions:
                break
    binding = _object(primary.get("binding_result"))
    proposal = _object(primary.get("proposal")) or _object(
        _object(primary.get("proposal_result")).get("proposal")
    )
    count_calls = _first_integer(
        primary.get("new_provider_count_token_calls"),
        safe.get("count_token_calls"),
        outcome.get("count_token_calls"),
    )
    generate_calls = _first_integer(
        primary.get("new_provider_generate_calls"),
        safe.get("generate_calls"),
        outcome.get("generate_calls"),
    )
    if routing.get("route") in {"skip_obvious_non_table", "upstream_failure"}:
        count_calls = 0 if count_calls is None else count_calls
        generate_calls = 0 if generate_calls is None else generate_calls
    provider_accounting = _provider_accounting(
        primary=primary,
        count_calls=count_calls,
        generate_calls=generate_calls,
        route=str(routing.get("route") or ""),
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
    return {
        "target_id": target_id,
        "target_outcomes_total": len(outcomes),
        "result_payloads_total": len(result_payloads),
        "routing_terminal_payloads_total": len(routing_terminal_payloads),
        "terminal_payloads_total": len(terminal_payloads),
        "target_state_payloads_total": len(state_payloads),
        "terminal_cardinality_verified": bool(
            len(outcomes) == 1
            and target_id
            and len(result_payloads) <= 1
            and len(routing_terminal_payloads) <= 1
            and len(terminal_payloads) == 1
            and len(state_payloads) <= 1
        ),
        "terminal_status": terminal_status,
        "reason_codes": [str(item) for item in reason_codes],
        "route_selected": routing.get("route"),
        "routing_evidence": routing,
        "routing_evidence_verified": _routing_evidence_verified(routing),
        "count_tokens_calls": count_calls,
        "generate_calls": generate_calls,
        "hidden_retry": safe.get("hidden_retry", False if count_calls == 0 else None),
        "provider_failover": safe.get(
            "provider_failover", False if count_calls == 0 else None
        ),
        "provider_accounting": provider_accounting,
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


def _routing_evidence(
    primary: dict[str, Any], target_payloads: list[dict[str, Any]]
) -> dict[str, Any]:
    candidates: list[Any] = [
        primary.get("product_routing"),
        primary.get("routing_decision"),
    ]
    for payload in target_payloads:
        candidates.extend(
            (payload.get("product_routing"), payload.get("routing_decision"))
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
    count_calls: int | None,
    generate_calls: int | None,
    route: str,
) -> dict[str, Any]:
    proposal_result = _object(primary.get("proposal_result")) or primary
    journal = [
        item for item in proposal_result.get("journal") or [] if isinstance(item, dict)
    ]
    counted_tokens = [
        _object(item.get("count_tokens")).get("total_tokens") for item in journal
    ]
    attempts = [
        _object(item.get("provider_attempt"))
        for item in journal
        if _object(item.get("provider_attempt"))
    ]
    actual_input_tokens = [
        _object(item.get("usage")).get("input_tokens") for item in attempts
    ]
    output_tokens = [
        _object(item.get("usage")).get("output_tokens") for item in attempts
    ]
    visual = _object(primary.get("visual_package"))
    crop = _object(visual.get("crop_identity"))
    count_flags = sum(
        item.get("provider_count_token_call_performed") is True for item in journal
    )
    generate_flags = sum(
        item.get("provider_generate_call_performed") is True for item in journal
    )
    if route in {"skip_obvious_non_table", "upstream_failure"} and not journal:
        count_flags = 0
        generate_flags = 0
    accounting = {
        "count_tokens_calls": count_calls,
        "generate_calls": generate_calls,
        "journal_count_tokens_calls": count_flags,
        "journal_generate_calls": generate_flags,
        "counted_input_tokens": counted_tokens,
        "actual_input_tokens": actual_input_tokens,
        "output_tokens": output_tokens,
        "image_bytes": crop.get("png_bytes"),
        "image_sha256": crop.get("crop_sha256"),
        "model_id": _object(proposal_result.get("provider_qualification")).get(
            "resolved_model_id"
        ),
        "hidden_retry": any(item.get("hidden_retry") is not False for item in attempts),
        "provider_failover": any(
            item.get("provider_failover") is not False for item in attempts
        ),
        "journal_checksum": sha256_json(journal),
    }
    if not attempts:
        accounting["hidden_retry"] = False
        accounting["provider_failover"] = False
    accounting["accounting_checksum"] = sha256_json(accounting)
    return accounting


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
