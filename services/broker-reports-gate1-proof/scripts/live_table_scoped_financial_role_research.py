#!/usr/bin/env python3
"""Run one clean role-mapping call on the repaired T-Bank table scope."""

from __future__ import annotations

import argparse
import asyncio
import copy
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
sys.path[:0] = [str(SCRIPT_DIR), str(SERVICE_ROOT)]

from broker_reports_gate1.canonical_artifact import (  # noqa: E402
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.full_source import FullSourceArtifactFactory  # noqa: E402
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
)
from broker_reports_gate1.logical_row_table_recovery import (  # noqa: E402
    LogicalRowStructuralProposal,
    LogicalRowTableFactory,
)
from broker_reports_gate1.table_scoped_role_research import (  # noqa: E402
    TableScopedRoleResearchFactory,
)
from broker_reports_gate1.visual_role_context_research import (  # noqa: E402
    VisualRoleContextResearchFactory,
    enrich_role_request,
)
from broker_reports_gate1.visual_table_structure_research import (  # noqa: E402
    VisualTableStructureProjectionFactory,
)
from canonical_financial_role_mapping_research import (  # noqa: E402
    apply_contract,
    compose_request,
    extract_tables,
    safe_result,
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
from visual_logical_column_live_research import (  # noqa: E402
    _bind_response,
    _projection_parser_page,
)


FREEZE_SCHEMA = "broker_reports_table_scoped_role_freeze_private_rd_v1"
RESULT_SCHEMA = "broker_reports_table_scoped_role_result_safe_rd_v1"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"


class LiveTableScopedRoleError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--pdf", type=Path, required=True)
    prepare.add_argument("--visual-result", type=Path, required=True)
    prepare.add_argument("--logical-freeze", type=Path, required=True)
    prepare.add_argument("--logical-result", type=Path, required=True)
    prepare.add_argument("--private-output-root", type=Path, required=True)
    execute = commands.add_parser("execute")
    execute.add_argument("--freeze", type=Path, required=True)
    execute.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    execute.add_argument("--private-output-root", type=Path, required=True)
    execute.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    return _prepare(args) if args.command == "prepare" else _execute(args)


def _prepare(args: argparse.Namespace) -> int:
    _require_clean_head()
    output_root = args.private_output_root.resolve()
    _require_new_root(output_root)
    pdf_path = args.pdf.resolve()
    pdf_bytes = pdf_path.read_bytes()
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    logical_freeze_path = args.logical_freeze.resolve()
    logical_result_path = args.logical_result.resolve()
    visual_result_path = args.visual_result.resolve()
    logical_freeze = _read_json(logical_freeze_path)
    logical_result = _read_json(logical_result_path)
    visual_result = _read_json(visual_result_path)
    case_ref = logical_freeze.get("case_ref")
    if (
        source_sha256 != logical_freeze.get("source_sha256")
        or not isinstance(case_ref, str)
        or logical_result.get("provider_value") is None
    ):
        raise LiveTableScopedRoleError("table_scope_input_binding_invalid")

    normalization_run_id = "visual-logical-column-" + case_ref
    full_source = FullSourceArtifactFactory().create().build(
        normalization_run_id=normalization_run_id,
        document_id=normalization_run_id,
        profile_id="visual-logical-column-live-research",
        container_format="pdf",
        content_bytes=pdf_bytes,
        source_checksum_sha256=source_sha256,
    )
    if len(full_source.payloads) != 1:
        raise LiveTableScopedRoleError("table_scope_full_source_invalid")
    payload = full_source.payloads[0]
    projection = payload.get("pdf_text_layer_projection")
    parser_page = _projection_parser_page(
        projection=projection,
        page_number=1,
        source_sha256=source_sha256,
    )
    projector = VisualTableStructureProjectionFactory().create()
    visual_run = next(
        (
            item
            for item in visual_result.get("runs", [])
            if isinstance(item, dict) and item.get("case_ref") == "tbank_page_1"
        ),
        None,
    )
    if not isinstance(visual_run, dict):
        raise LiveTableScopedRoleError("table_scope_visual_run_missing")
    bound_visual = projector.bind(
        provider_value=visual_run.get("provider_value"),
        parser_page=parser_page,
    )
    prepared = logical_freeze.get("prepared_crop_scope")
    if not isinstance(prepared, dict):
        raise LiveTableScopedRoleError("table_scope_logical_freeze_invalid")
    rebound_leaves = _bind_response(
        projector=projector,
        provider_value=logical_result.get("provider_value"),
        prepared=prepared,
    )
    proposal = LogicalRowStructuralProposal(
        source_checksum_sha256=source_sha256,
        page_number=1,
        page_leaf_box_pdf_points=tuple(
            tuple(item["page_leaf_box_pdf_points"])
            for item in rebound_leaves["leaf_columns"]
        ),
        header_word_refs=tuple(
            ref
            for item in rebound_leaves["leaf_columns"]
            for ref in item["header_word_refs"]
        ),
        shared_header_word_refs=tuple(
            rebound_leaves["shared_or_non_leaf_header_word_refs"]
        ),
    )
    recovery = LogicalRowTableFactory().create().recover(
        projection,
        source_checksum_sha256=source_sha256,
        private_evidence_ref="table-scoped-role-current-rebind",
        structural_proposal=proposal,
    )
    scope_service = TableScopedRoleResearchFactory().create()
    scoped = scope_service.build(
        recovery=recovery,
        payloads=[payload],
        source_units=full_source.units,
        bound_visual_projection=bound_visual,
        source_checksum_sha256=source_sha256,
    )
    canonical = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version="table-scoped-financial-role-research-v1"
        )
    ).create().build(
        tenant_id="table-scoped-role-research",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": source_sha256,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref="source-table-scoped-role-research",
        source_payloads=[payload],
        source_units=scoped.canonical_source_units,
        table_projections=scoped.projection_result.projections,
    )
    envelope = scope_service.bind_canonical(
        scope_binding=scoped.scope_binding,
        canonical=canonical,
    )
    scope_service.validate_envelope(envelope=envelope, canonical=canonical)
    context = VisualRoleContextResearchFactory().create().build_from_table_projection(
        parser_page=parser_page,
        bound_structure=scoped.bound_structure,
        table_projection=scoped.projection_result.projections[0],
        expected_source_sha256=source_sha256,
    )
    tables = extract_tables(canonical)
    if len(tables) != 1:
        raise LiveTableScopedRoleError("table_scope_canonical_table_invalid")
    table = tables[0]
    if (
        len(table["rows"]) != 6
        or len(table["columns"]) != 32
        or table["rows"][1]["cells"][7]["literal"] != "Покупка"
        or table["rows"][1]["cells"][8]["literal"]
        != "Ozon Holdings PLC ORD SHS ADR"
    ):
        raise LiveTableScopedRoleError("table_scope_repaired_table_invalid")
    baseline_request = compose_request(
        table=table,
        table_ref="table_1",
        variant="header_plus_profiles",
    )
    request = enrich_role_request(
        baseline_request=baseline_request,
        visual_context=context,
    )
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "source_head": _git_head(),
        "source_worktree_clean": True,
        "model_id": MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE,
        "source_sha256": source_sha256,
        "input_files": {
            "pdf_sha256": _file_sha256(pdf_path),
            "visual_result_sha256": _file_sha256(visual_result_path),
            "logical_freeze_sha256": _file_sha256(logical_freeze_path),
            "logical_result_sha256": _file_sha256(logical_result_path),
        },
        "rebound_visual_sha256": stable_sha256(bound_visual),
        "rebound_logical_columns_sha256": stable_sha256(rebound_leaves),
        "recovery_tables_total": len(recovery.tables),
        "recovery_unowned_words_total": len(recovery.unowned_word_refs),
        "recovery_multiple_owners_total": recovery.diagnostics.get(
            "multiple_word_owners_total"
        ),
        "canonical_root_hash": canonical["canonical_root_hash"],
        "scope_envelope": envelope,
        "visual_context_sha256": stable_sha256(context),
        "table": table,
        "table_sha256": stable_sha256(table),
        "request": request,
        "request_sha256": stable_sha256(request),
        "scheduled_model_calls": 1,
        "provider_submissions_before_freeze": 0,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "canonical_mutated": False,
        "facts_published": 0,
        "private_values_committed": False,
        "product_activation": False,
    }
    freeze["freeze_sha256"] = stable_sha256(freeze)
    output_root.mkdir(parents=True)
    _write_json(output_root / "freeze.private.json", freeze)
    safe = {
        key: copy.deepcopy(freeze[key])
        for key in (
            "schema_version",
            "source_head",
            "source_worktree_clean",
            "model_id",
            "provider_profile_id",
            "source_sha256",
            "input_files",
            "rebound_visual_sha256",
            "rebound_logical_columns_sha256",
            "recovery_tables_total",
            "recovery_unowned_words_total",
            "recovery_multiple_owners_total",
            "canonical_root_hash",
            "scope_envelope",
            "table_sha256",
            "request_sha256",
            "scheduled_model_calls",
            "provider_submissions_before_freeze",
            "retry",
            "repair",
            "best_of_n",
            "manual_output_edit",
            "canonical_mutated",
            "facts_published",
            "private_values_committed",
            "product_activation",
            "freeze_sha256",
        )
    }
    safe["table_shape"] = {"rows": 6, "columns": 32}
    safe["terminal"] = "FROZEN_READY_FOR_ONE_CALL"
    _write_json(output_root / "freeze.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _execute(args: argparse.Namespace) -> int:
    freeze = _read_json(args.freeze.resolve())
    unsigned = {key: value for key, value in freeze.items() if key != "freeze_sha256"}
    if (
        freeze.get("schema_version") != FREEZE_SCHEMA
        or freeze.get("source_head") != _git_head()
        or freeze.get("source_worktree_clean") is not True
        or freeze.get("freeze_sha256") != stable_sha256(unsigned)
        or freeze.get("scheduled_model_calls") != 1
        or freeze.get("facts_published") != 0
        or freeze.get("scope_envelope", {}).get("publication_allowed") is not False
    ):
        raise LiveTableScopedRoleError("table_scope_freeze_invalid_or_drifted")
    _require_clean_head()
    output_root = args.private_output_root.resolve()
    _require_new_root(output_root)
    output_root.mkdir(parents=True)
    profile = gate2_provider_profile(PROVIDER_PROFILE)
    if MODEL_ID not in profile.approved_model_ids:
        raise LiveTableScopedRoleError("table_scope_model_not_approved")
    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if MODEL_ID not in _published_model_ids(session, base_url):
        raise LiveTableScopedRoleError("table_scope_model_not_published")
    user_id = str(_current_user(session, base_url).get("id") or "")
    if not user_id:
        raise LiveTableScopedRoleError("table_scope_user_missing")
    submissions = {"count": 0}
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def counted_completion(*, form_data, **kwargs):
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            counted_completion,
            SimpleNamespace(id=user_id),
        ),
    ).create()
    request = freeze["request"]
    if stable_sha256(request) != freeze["request_sha256"]:
        raise LiveTableScopedRoleError("table_scope_request_drift")
    started = time.perf_counter()
    error = None
    contract = None
    application = None
    execution_metadata = None
    try:
        result = asyncio.run(
            client.extract(
                prompt=SimpleNamespace(
                    content=request["messages"][0]["content"],
                    prompt_ref="research:table-scoped-financial-role-v1",
                    hash=stable_sha256(request["messages"][0]["content"]),
                ),
                package=json.loads(request["messages"][1]["content"]),
                model_id=MODEL_ID,
                response_format=request["response_format"],
            )
        )
        execution_metadata = _jsonable(result.execution_metadata)
        _write_json(
            output_root / "provider-response.private.json",
            {
                "freeze_sha256": freeze["freeze_sha256"],
                "source_head": freeze["source_head"],
                "provider_submissions": submissions["count"],
                "content": _jsonable(result.content),
                "execution_metadata": execution_metadata,
            },
        )
        contract = validate_response(
            raw_response=result.content,
            table=freeze["table"],
            table_ref="table_1",
        )
        application = apply_contract(
            table=freeze["table"],
            contract=contract,
            table_ref="table_1",
        )
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    elapsed = time.perf_counter() - started
    validated = contract is not None and application is not None
    private = {
        "schema_version": RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "provider_submissions": submissions["count"],
        "scheduled_model_calls": 1,
        "contract": contract,
        "application": application,
        "execution_metadata": execution_metadata,
        "error": error,
        "elapsed_seconds": elapsed,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "canonical_mutated": False,
        "facts_published": 0,
        "private_values_committed": False,
        "product_activation": False,
    }
    safe_application = (
        safe_result(
            table=freeze["table"],
            surface_variant="header_plus_profiles_with_source_bound_visual_context",
            request=request,
            contract=contract,
            application=application,
            metrics=execution_metadata,
        )
        if validated
        else None
    )
    safe = {
        "schema_version": RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "source_sha256": freeze["source_sha256"],
        "canonical_root_hash": freeze["canonical_root_hash"],
        "table_shape": {"rows": 6, "columns": 32},
        "scope_envelope": freeze["scope_envelope"],
        "terminal": (
            "TABLE_SCOPED_ROLE_MAPPING_" + application["terminal"]
            if validated
            else "VALIDATOR_OR_PROVIDER_FAILED"
        ),
        "role_application": safe_application,
        "provider_submissions": submissions["count"],
        "scheduled_model_calls": 1,
        "error": error,
        "elapsed_seconds": elapsed,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "document_complete": False,
        "publication_allowed": False,
        "canonical_mutated": False,
        "facts_published": 0,
        "private_values_committed": False,
        "product_activation": False,
    }
    safe["receipt_sha256"] = stable_sha256(safe)
    _write_json(output_root / "result.private.json", private)
    _write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if validated and submissions["count"] == 1 else 2


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "snapshot"):
        return _jsonable(value.snapshot())
    return str(value)


def _require_clean_head() -> None:
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise LiveTableScopedRoleError("table_scope_worktree_not_clean")


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_new_root(path: Path) -> None:
    if path.exists() or REPO_ROOT == path or REPO_ROOT in path.parents:
        raise LiveTableScopedRoleError("table_scope_output_root_invalid")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiveTableScopedRoleError("table_scope_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
