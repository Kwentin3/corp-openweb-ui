#!/usr/bin/env python3
"""Freeze, execute and score the research-only Canonical role-mapping stand."""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    Gate2SourceFactRuntimeError,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from canonical_financial_role_mapping_research import (  # noqa: E402
    PROMPT_VERSION,
    SURFACE_VARIANTS,
    apply_contract,
    compose_request,
    extract_tables,
    safe_result,
    score_contract,
    stable_sha256,
    validate_response,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
DEFAULT_PROVIDER_PROFILE = "google_gemini"
FREEZE_SCHEMA = "broker_reports_research_table_role_freeze_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=(
            "inventory",
            "freeze",
            "inspect",
            "development",
            "select-final",
            "holdout",
            "score",
        ),
        required=True,
    )
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--private-evidence-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--inspect-case")
    parser.add_argument("--final-variant", choices=SURFACE_VARIANTS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    root = args.private_evidence_root.resolve()
    corpus_root = args.corpus_root.resolve()
    if _is_within(root, REPO_ROOT.resolve()):
        raise SystemExit("research_private_evidence_must_be_outside_repository")
    if not corpus_root.is_dir():
        raise SystemExit("research_corpus_root_missing")
    if args.phase == "inventory":
        return _inventory(corpus_root, root)
    if args.phase == "freeze":
        return _freeze(args, corpus_root, root)
    if args.phase == "inspect":
        return _inspect(args, root)
    if args.phase == "select-final":
        return _select_final(args, root)
    if args.phase == "score":
        return _score(args, root)
    if args.phase in {"development", "holdout"}:
        return _execute(args, corpus_root, root)
    raise SystemExit("research_phase_invalid")


def _inventory(corpus_root: Path, output_root: Path) -> int:
    if output_root.exists():
        raise SystemExit("research_inventory_output_exists")
    output_root.mkdir(parents=True)
    cases = []
    for case_root in sorted(corpus_root.glob("doc_*")):
        loaded = _load_case(case_root)
        if loaded is None:
            continue
        manifest, store_root, artifact, _store = loaded
        tables = extract_tables(artifact)
        cases.append(
            {
                "corpus_case": case_root.name,
                "source_sha256": manifest["source_sha256"],
                "canonical_root_sha256": manifest["canonical_root_sha256"],
                "canonical_version_id": manifest["canonical_version_id"],
                "tables": [
                    {
                        "table_ordinal": ordinal,
                        "rows": len(table["rows"]),
                        "columns": len(table["columns"]),
                        "cells": len(table["rows"]) * len(table["columns"]),
                        "table_sha256": stable_sha256(table),
                    }
                    for ordinal, table in enumerate(tables, start=1)
                ],
                "store_tree_sha256": stable_sha256(_store_snapshot(store_root)),
            }
        )
    safe = {
        "schema_version": "broker_reports_research_table_role_inventory_safe_v1",
        "documents": len(cases),
        "tables": sum(len(case["tables"]) for case in cases),
        "rows": sum(
            table["rows"] for case in cases for table in case["tables"]
        ),
        "cases": cases,
        "private_values_committed": False,
    }
    _write_json(output_root / "inventory.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _freeze(args: argparse.Namespace, corpus_root: Path, root: Path) -> int:
    if args.spec is None:
        raise SystemExit("research_spec_required")
    if root.exists() and any(root.iterdir()):
        raise SystemExit("research_evidence_root_must_be_new_or_empty")
    root.mkdir(parents=True, exist_ok=True)
    spec = _read_json(args.spec.resolve())
    _validate_spec(spec)
    source_head = _git_head()
    if _git_status_porcelain():
        raise SystemExit("research_freeze_requires_clean_worktree")
    module_path = SCRIPT_DIR / "canonical_financial_role_mapping_research.py"
    runner_path = Path(__file__).resolve()
    cases_private: dict[str, Any] = {}
    frozen_cases = []
    store_snapshots = {}
    for case in spec["cases"]:
        case_root = corpus_root / case["corpus_case"]
        loaded = _load_case(case_root)
        if loaded is None:
            raise SystemExit(f"research_case_unavailable:{case['case_id']}")
        manifest, store_root, artifact, _store = loaded
        tables = extract_tables(artifact)
        ordinal = case["table_ordinal"]
        if ordinal < 1 or ordinal > len(tables):
            raise SystemExit(f"research_table_ordinal_invalid:{case['case_id']}")
        table = tables[ordinal - 1]
        table_ref = "table_1"
        requests_by_variant = {
            variant: compose_request(
                table=table, table_ref=table_ref, variant=variant
            )
            for variant in spec["development_variants"]
        }
        if case["split"] == "holdout":
            requests_by_variant = {
                variant: compose_request(
                    table=table, table_ref=table_ref, variant=variant
                )
                for variant in SURFACE_VARIANTS
            }
        cases_private[case["case_id"]] = {
            "table": table,
            "requests": requests_by_variant,
            "manifest": manifest,
            "store_root": str(store_root),
        }
        frozen_cases.append(
            {
                **copy.deepcopy(case),
                "source_sha256": manifest["source_sha256"],
                "canonical_root_sha256": manifest["canonical_root_sha256"],
                "canonical_version_id": manifest["canonical_version_id"],
                "table_sha256": stable_sha256(table),
                "rows": len(table["rows"]),
                "columns": len(table["columns"]),
                "request_sha256_by_variant": {
                    variant: stable_sha256(request)
                    for variant, request in requests_by_variant.items()
                },
            }
        )
        store_snapshots[case["case_id"]] = _store_snapshot(store_root)
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "status": "FROZEN_BEFORE_PROVIDER",
        "prompt_version": PROMPT_VERSION,
        "module_sha256": _file_sha256(module_path),
        "runner_sha256": _file_sha256(runner_path),
        "source_head": source_head,
        "source_worktree_clean": True,
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "model_policy": {
            "temperature_override": None,
            "seed_override": None,
            "semantic_retry": False,
            "best_of_n": False,
            "manual_output_repair": False,
            "calls_per_case_variant": 1,
        },
        "development_variants": spec["development_variants"],
        "cases": frozen_cases,
        "provider_submissions_before_freeze": 0,
    }
    freeze["freeze_sha256"] = stable_sha256(freeze)
    _write_json(root / "freeze.private.json", freeze)
    _write_json(root / "cases.private.json", cases_private)
    _write_json(root / "store-snapshots.before.private.json", store_snapshots)
    _write_json(
        root / "freeze.safe.json",
        {
            "schema_version": "broker_reports_research_table_role_freeze_safe_v1",
            "status": freeze["status"],
            "freeze_sha256": freeze["freeze_sha256"],
            "prompt_version": freeze["prompt_version"],
            "module_sha256": freeze["module_sha256"],
            "runner_sha256": freeze["runner_sha256"],
            "source_head": freeze["source_head"],
            "source_worktree_clean": freeze["source_worktree_clean"],
            "provider_profile_id": freeze["provider_profile_id"],
            "model_id": freeze["model_id"],
            "model_policy": freeze["model_policy"],
            "development_cases": sum(
                case["split"] == "development" for case in frozen_cases
            ),
            "holdout_cases": sum(case["split"] == "holdout" for case in frozen_cases),
            "development_variants": freeze["development_variants"],
            "private_values_committed": False,
        },
    )
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "freeze_sha256": freeze["freeze_sha256"],
                "cases": len(frozen_cases),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _inspect(args: argparse.Namespace, root: Path) -> int:
    if not args.inspect_case:
        raise SystemExit("research_inspect_case_required")
    cases = _read_json(root / "cases.private.json")
    case = cases.get(args.inspect_case)
    if not isinstance(case, dict):
        raise SystemExit("research_inspect_case_unknown")
    print(json.dumps(case["table"], ensure_ascii=False, indent=2))
    return 0


def _execute(args: argparse.Namespace, corpus_root: Path, root: Path) -> int:
    if not args.execute:
        raise SystemExit("research_explicit_execute_flag_required")
    phase = args.phase
    result_path = root / f"{phase}.private.json"
    if result_path.exists():
        raise SystemExit("research_phase_already_executed")
    freeze = _read_json(root / "freeze.private.json")
    cases_private = _read_json(root / "cases.private.json")
    before = _read_json(root / "store-snapshots.before.private.json")
    _verify_freeze(freeze, args)
    selected = [case for case in freeze["cases"] if case["split"] == phase]
    if phase == "development":
        variants = freeze["development_variants"]
    else:
        selection = _read_json(root / "final-selection.private.json")
        _verify_selection(selection, freeze)
        variants = [selection["final_variant"]]
    profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in profile.approved_model_ids:
        raise SystemExit("research_model_not_approved")
    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if args.model_id not in _published_model_ids(session, base_url):
        raise SystemExit("research_model_not_published")
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("research_authenticated_user_missing")
    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session, base_url=base_url, timeout=args.timeout_seconds
    )

    def counted_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=args.provider_profile_id,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            counted_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()
    outcomes = []
    for frozen_case in selected:
        private_case = cases_private[frozen_case["case_id"]]
        for variant in variants:
            request = private_case["requests"][variant]
            if stable_sha256(request) != frozen_case["request_sha256_by_variant"][variant]:
                raise SystemExit("research_request_drift")
            schema = request["response_format"]["json_schema"]["schema"]
            calls_before = submissions["count"]
            started = time.perf_counter()
            try:
                result = asyncio.run(
                    client.label_gate3_once(
                        model_visible_request=request,
                        canonical_schema=schema,
                        model_id=args.model_id,
                    )
                )
            except Gate2SourceFactRuntimeError as exc:
                outcome = {
                    "case_id": frozen_case["case_id"],
                    "variant": variant,
                    "status": "PROVIDER_FAILED",
                    "error": _error_receipt(exc),
                    "transport_submissions": submissions["count"] - calls_before,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            else:
                raw = {
                    "case_id": frozen_case["case_id"],
                    "variant": variant,
                    "raw_model_output": _jsonable(result.adapter_extracted_output),
                    "raw_provider_response": _jsonable(result.raw_provider_response),
                    "execution_metadata": _jsonable(result.execution_metadata),
                    "metrics": _jsonable(result.metrics),
                    "operational_retry_receipt": _jsonable(
                        result.operational_retry_receipt
                    ),
                    "transport_submissions": submissions["count"] - calls_before,
                    "elapsed_seconds": time.perf_counter() - started,
                }
                raw_path = root / (
                    f"{phase}-{frozen_case['case_id']}-{variant}-raw.private.json"
                )
                _write_json(raw_path, raw)
                try:
                    contract = validate_response(
                        raw_response=result.adapter_extracted_output,
                        table=private_case["table"],
                        table_ref="table_1",
                    )
                    application = apply_contract(
                        table=private_case["table"],
                        contract=contract,
                        table_ref="table_1",
                    )
                except Exception as exc:
                    outcome = {
                        "case_id": frozen_case["case_id"],
                        "variant": variant,
                        "status": "VALIDATOR_FAILED",
                        "error": _error_receipt(exc),
                        "raw_evidence_file": raw_path.name,
                        "transport_submissions": submissions["count"] - calls_before,
                    }
                else:
                    outcome = {
                        "case_id": frozen_case["case_id"],
                        "variant": variant,
                        "status": "VALIDATED",
                        "contract": contract,
                        "application": application,
                        "safe": safe_result(
                            table=private_case["table"],
                            surface_variant=variant,
                            request=request,
                            contract=contract,
                            application=application,
                            metrics=_jsonable(result.metrics),
                        ),
                        "raw_evidence_file": raw_path.name,
                        "transport_submissions": submissions["count"] - calls_before,
                    }
            outcomes.append(outcome)
            _write_json(
                root / f"{phase}-{frozen_case['case_id']}-{variant}.private.json",
                outcome,
            )
    unchanged = all(
        _store_snapshot(Path(cases_private[case["case_id"]]["store_root"]))
        == before[case["case_id"]]
        for case in selected
    )
    result = {
        "schema_version": "broker_reports_research_table_role_phase_result_v1",
        "phase": phase,
        "freeze_sha256": freeze["freeze_sha256"],
        "provider_submissions": submissions["count"],
        "scheduled_calls": len(selected) * len(variants),
        "semantic_retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "source_stores_unchanged": unchanged,
        "outcomes": outcomes,
    }
    _write_json(result_path, result)
    _write_json(root / f"{phase}.safe.json", _safe_phase(result))
    print(json.dumps(_safe_phase(result), ensure_ascii=False, indent=2))
    return 0 if unchanged and submissions["count"] == result["scheduled_calls"] else 2


def _select_final(args: argparse.Namespace, root: Path) -> int:
    if args.final_variant is None:
        raise SystemExit("research_final_variant_required")
    target = root / "final-selection.private.json"
    if target.exists():
        raise SystemExit("research_final_selection_exists")
    freeze = _read_json(root / "freeze.private.json")
    development = _read_json(root / "development.private.json")
    if args.final_variant not in freeze["development_variants"]:
        raise SystemExit("research_final_variant_not_developed")
    if development.get("source_stores_unchanged") is not True:
        raise SystemExit("research_development_not_complete")
    selection = {
        "schema_version": "broker_reports_research_table_role_final_selection_v1",
        "freeze_sha256": freeze["freeze_sha256"],
        "final_variant": args.final_variant,
        "prompt_version": freeze["prompt_version"],
        "module_sha256": freeze["module_sha256"],
        "selected_after_development": True,
        "selected_before_holdout": True,
        "holdout_provider_submissions_before_selection": 0,
    }
    selection["selection_sha256"] = stable_sha256(selection)
    _write_json(target, selection)
    print(json.dumps(selection, ensure_ascii=False, indent=2))
    return 0


def _score(args: argparse.Namespace, root: Path) -> int:
    if args.reference is None:
        raise SystemExit("research_reference_required")
    reference = _read_json(args.reference.resolve())
    if reference.get("schema_version") != "broker_reports_research_table_role_reference_v1":
        raise SystemExit("research_reference_invalid")
    freeze = _read_json(root / "freeze.private.json")
    cases = _read_json(root / "cases.private.json")
    all_outcomes = []
    for phase in ("development", "holdout"):
        result = _read_json(root / f"{phase}.private.json")
        for outcome in result["outcomes"]:
            case_id = outcome["case_id"]
            expected = reference["cases"].get(case_id)
            if not isinstance(expected, dict):
                raise SystemExit(f"research_reference_case_missing:{case_id}")
            validated_reference = validate_response(
                raw_response=expected,
                table=cases[case_id]["table"],
                table_ref="table_1",
            )
            scored = (
                score_contract(
                    candidate=outcome["contract"], reference=validated_reference
                )
                if outcome["status"] == "VALIDATED"
                else {
                    "table_kind_exact": False,
                    "header_row_exact": False,
                    "column_roles_correct": 0,
                    "column_roles_total": len(validated_reference["columns"]),
                    "categorical_exact": False,
                    "amount_currency_bindings_exact": False,
                    "contract_exact": False,
                }
            )
            all_outcomes.append(
                {
                    "phase": phase,
                    "case_id": case_id,
                    "variant": outcome["variant"],
                    "status": outcome["status"],
                    "score": scored,
                    "safe": copy.deepcopy(outcome.get("safe")),
                }
            )
    aggregates = []
    for phase in ("development", "holdout"):
        variants = sorted(
            {item["variant"] for item in all_outcomes if item["phase"] == phase}
        )
        for variant in variants:
            selected = [
                item
                for item in all_outcomes
                if item["phase"] == phase and item["variant"] == variant
            ]
            aggregates.append(
                {
                    "phase": phase,
                    "variant": variant,
                    "cases": len(selected),
                    "validated": sum(item["status"] == "VALIDATED" for item in selected),
                    "contract_exact": sum(item["score"]["contract_exact"] for item in selected),
                    "table_kind_exact": sum(item["score"]["table_kind_exact"] for item in selected),
                    "header_row_exact": sum(item["score"]["header_row_exact"] for item in selected),
                    "column_roles_correct": sum(item["score"]["column_roles_correct"] for item in selected),
                    "column_roles_total": sum(item["score"]["column_roles_total"] for item in selected),
                    "categorical_exact": sum(item["score"]["categorical_exact"] for item in selected),
                    "amount_currency_bindings_exact": sum(
                        item["score"]["amount_currency_bindings_exact"] for item in selected
                    ),
                    "input_tokens": sum(
                        int((item.get("safe") or {}).get("input_tokens") or 0)
                        for item in selected
                    ),
                    "output_tokens": sum(
                        int((item.get("safe") or {}).get("output_tokens") or 0)
                        for item in selected
                    ),
                    "duration_ms": sum(
                        int((item.get("safe") or {}).get("duration_ms") or 0)
                        for item in selected
                    ),
                }
            )
    scored = {
        "schema_version": "broker_reports_research_table_role_score_private_v1",
        "freeze_sha256": freeze["freeze_sha256"],
        "reference_sha256": stable_sha256(reference),
        "aggregates": aggregates,
        "outcomes": all_outcomes,
    }
    safe = {
        "schema_version": "broker_reports_research_table_role_score_safe_v1",
        "freeze_sha256": freeze["freeze_sha256"],
        "reference_sha256": scored["reference_sha256"],
        "aggregates": aggregates,
        "private_values_committed": False,
    }
    safe["receipt_sha256"] = stable_sha256(safe)
    _write_json(root / "score.private.json", scored)
    _write_json(root / "score.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _load_case(case_root: Path):
    result_paths = sorted(case_root.glob("attempt_*/result.private.json"))
    if not result_paths:
        return None
    result_path = result_paths[-1]
    result = _read_json(result_path)
    manifest = result.get("canonical_manifest")
    if not isinstance(manifest, dict):
        raise SystemExit(f"research_canonical_manifest_invalid:{case_root.name}")
    store_root = result_path.parent / "store.private"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context_values = copy.deepcopy(manifest["context"])
    context_values["allow_private"] = True
    context = ArtifactAccessContext(**context_values)
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active(manifest["document_id"], context)
    )
    if (
        artifact.get("artifact_id") != manifest["canonical_version_id"]
        or artifact.get("canonical_root_hash") != manifest["canonical_root_sha256"]
    ):
        raise SystemExit(f"research_canonical_binding_stale:{case_root.name}")
    return manifest, store_root, artifact, store


def _validate_spec(spec: dict[str, Any]) -> None:
    cases = spec.get("cases")
    variants = spec.get("development_variants")
    if (
        spec.get("schema_version") != "broker_reports_research_table_role_spec_v1"
        or not isinstance(cases, list)
        or not cases
        or not isinstance(variants, list)
        or not variants
        or any(variant not in SURFACE_VARIANTS for variant in variants)
        or len(set(variants)) != len(variants)
    ):
        raise SystemExit("research_spec_invalid")
    ids = []
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "corpus_case", "table_ordinal", "split"}
            or not isinstance(case.get("case_id"), str)
            or not isinstance(case.get("corpus_case"), str)
            or not isinstance(case.get("table_ordinal"), int)
            or case["table_ordinal"] < 1
            or case.get("split") not in {"development", "holdout"}
        ):
            raise SystemExit("research_spec_invalid")
        ids.append(case["case_id"])
    if len(set(ids)) != len(ids) or not {case["split"] for case in cases} == {
        "development",
        "holdout",
    }:
        raise SystemExit("research_spec_invalid")


def _verify_freeze(freeze: dict[str, Any], args: argparse.Namespace) -> None:
    if (
        freeze.get("schema_version") != FREEZE_SCHEMA
        or freeze.get("status") != "FROZEN_BEFORE_PROVIDER"
        or freeze.get("freeze_sha256")
        != stable_sha256({key: value for key, value in freeze.items() if key != "freeze_sha256"})
        or freeze.get("module_sha256")
        != _file_sha256(SCRIPT_DIR / "canonical_financial_role_mapping_research.py")
        or freeze.get("runner_sha256") != _file_sha256(Path(__file__).resolve())
        or freeze.get("source_head") != _git_head()
        or freeze.get("source_worktree_clean") is not True
        or bool(_git_status_porcelain())
        or freeze.get("provider_profile_id") != args.provider_profile_id
        or freeze.get("model_id") != args.model_id
        or freeze.get("provider_submissions_before_freeze") != 0
    ):
        raise SystemExit("research_freeze_invalid_or_drifted")


def _verify_selection(selection: dict[str, Any], freeze: dict[str, Any]) -> None:
    if (
        selection.get("schema_version")
        != "broker_reports_research_table_role_final_selection_v1"
        or selection.get("freeze_sha256") != freeze["freeze_sha256"]
        or selection.get("module_sha256") != freeze["module_sha256"]
        or selection.get("selected_before_holdout") is not True
        or selection.get("holdout_provider_submissions_before_selection") != 0
        or selection.get("selection_sha256")
        != stable_sha256(
            {key: value for key, value in selection.items() if key != "selection_sha256"}
        )
    ):
        raise SystemExit("research_final_selection_invalid")


def _safe_phase(result: dict[str, Any]) -> dict[str, Any]:
    safe_outcomes = []
    for outcome in result["outcomes"]:
        safe_outcomes.append(
            {
                "case_id": outcome["case_id"],
                "variant": outcome["variant"],
                "status": outcome["status"],
                "transport_submissions": outcome["transport_submissions"],
                "result": copy.deepcopy(outcome.get("safe")),
                "error_code": (outcome.get("error") or {}).get("code"),
            }
        )
    safe = {
        "schema_version": "broker_reports_research_table_role_phase_result_safe_v1",
        "phase": result["phase"],
        "freeze_sha256": result["freeze_sha256"],
        "provider_submissions": result["provider_submissions"],
        "scheduled_calls": result["scheduled_calls"],
        "semantic_retries": result["semantic_retries"],
        "best_of_n": result["best_of_n"],
        "manual_output_repair": result["manual_output_repair"],
        "source_stores_unchanged": result["source_stores_unchanged"],
        "outcomes": safe_outcomes,
        "private_values_committed": False,
    }
    safe["receipt_sha256"] = stable_sha256(safe)
    return safe


def _store_snapshot(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def _error_receipt(exc: Exception) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "code": getattr(exc, "code", None),
        "failure_class": getattr(exc, "failure_class", None),
        "message": str(exc),
        "execution_metadata": _jsonable(getattr(exc, "execution_metadata", None)),
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if hasattr(value, "snapshot"):
        return _jsonable(value.snapshot())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return repr(value)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _git_status_porcelain() -> str:
    return subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).strip()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"research_json_object_required:{path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
