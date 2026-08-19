#!/usr/bin/env python3
"""Run the proof-only G5.98 visual-breadcrumb addressability experiment.

The provider may describe where a visible table is, but never its body values
or coordinates.  This harness resolves that proposal only against the actual
PDF line/word inventory produced by the maintained parser factory.  It does
not materialize a table, change Canonical, or participate in product runtime.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pypdf
import requests

from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "addressable_visual_breadcrumb_g598"
    / "manifest.json"
)
MANIFEST_SCHEMA = "broker_reports_addressable_visual_breadcrumb_g598_manifest_v1"
PRIVATE_CONTRACT_SCHEMA = (
    "broker_reports_addressable_visual_breadcrumb_g598_contract_private_v1"
)
PRIVATE_EVALUATION_SCHEMA = (
    "broker_reports_addressable_visual_breadcrumb_g598_evaluation_private_v1"
)
PRIVATE_FREEZE_SCHEMA = "broker_reports_addressable_visual_breadcrumb_g598_freeze_private_v1"
PRIVATE_HOLDOUT_SCHEMA = (
    "broker_reports_addressable_visual_breadcrumb_g598_holdout_private_v1"
)
SAFE_SCHEMA = "broker_reports_addressable_visual_breadcrumb_g598_safe_v1"

RESOLVED = "RESOLVED"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"
CONTRACT_NOT_VERIFIED = "CONTRACT_NOT_VERIFIED"

PROVEN = "ADDRESSABLE_VISUAL_BREADCRUMB_CONTRACT_PROVEN"
UNIQUE_PROVEN = "UNIQUE_SOURCE_REGION_RESOLUTION_PROVEN"
ZERO_FALSE = "FALSE_LOCALIZATION_ZERO"
ENGINE_NEUTRAL = "ENGINE_NEUTRAL_ADDRESSABILITY_PROVEN"
PARTIAL = "ADDRESSABILITY_CONTRACT_PROMISING_BUT_INCOMPLETE"
EXCESSIVE = "BREADCRUMB_ADDRESSABILITY_REQUIRES_EXCESSIVE_HEURISTICS"
INSUFFICIENT = "TEXTUAL_STRUCTURAL_BREADCRUMBS_INSUFFICIENT"

_BEFORE_RELATIONS = {"page_start", "immediately_after", "first_table_after"}
_AFTER_BOUNDARIES = {"next_anchor", "page_footer", "page_end"}
_FORBIDDEN_KEYS = {
    "amount",
    "bbox",
    "bboxes",
    "body",
    "body_rows",
    "body_values",
    "canonical_id",
    "canonical_ids",
    "cells",
    "date",
    "engine",
    "engine_config",
    "finance",
    "financial_semantics",
    "quantity",
    "rows",
    "security",
    "table_settings",
    "values",
}
_DIGIT_RE = re.compile(r"\d")
_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)

PROMPT = (
    "Inspect this one rendered PDF page only to identify every visible data table "
    "or table continuation, in top-to-bottom order. Return only address breadcrumbs, "
    "never table body rows or values. For each table: choose a before relation "
    "page_start, immediately_after, or first_table_after; provide short exact visible "
    "word tokens from the nearest preceding section/title anchor unless page_start, "
    "using at most five non-numeric words. Prefer two to four short, jointly distinctive "
    "header token groups for the whole table; a very wide header may require more. "
    "A bordered row fragment at the very top "
    "of a page is a table continuation even when it has no visible header. Include it; "
    "that headerless case must use an empty header, continuation_from_previous_page "
    "true, and page_start; never substitute a body or subtotal label for the absent "
    "header. Choose an after boundary next_anchor, page_footer, or "
    "page_end. For next_anchor provide at most five short exact words from the following "
    "section/title. For a textual footer provide at most three non-numeric footer words; "
    "if the footer is only a page number, choose page_footer with empty tokens. Use "
    "table_ordinal_in_scope only to distinguish repeated tables under the same anchor. "
    "Every token must contain a word and no digit. Do not return any number, date, "
    "amount, body literal, row, cell, bounding box, Canonical ID, parser or vendor "
    "setting, financial interpretation, summary, correction, or commentary. If the "
    "page has prose or a list but no visual data table, return an empty tables array."
)

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tables"],
    "properties": {
        "tables": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "before_anchor",
                    "header_token_groups",
                    "after_anchor",
                    "table_ordinal_in_scope",
                    "continuation_from_previous_page",
                ],
                "properties": {
                    "before_anchor": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["relation", "tokens"],
                        "properties": {
                            "relation": {
                                "type": "string",
                                "enum": sorted(_BEFORE_RELATIONS),
                            },
                            "tokens": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 5,
                            },
                        },
                    },
                    "header_token_groups": {
                        "type": "array",
                        "maxItems": 20,
                        "items": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 8,
                            "items": {"type": "string"},
                        },
                    },
                    "after_anchor": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["boundary", "tokens"],
                        "properties": {
                            "boundary": {
                                "type": "string",
                                "enum": sorted(_AFTER_BOUNDARIES),
                            },
                            "tokens": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 5,
                            },
                        },
                    },
                    "table_ordinal_in_scope": {"type": "integer", "minimum": 1},
                    "continuation_from_previous_page": {"type": "boolean"},
                },
            },
        }
    },
}


class G598Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke")

    generate = sub.add_parser("generate-development")
    _add_common_inputs(generate)
    generate.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    generate.add_argument("--private-output", required=True)
    generate.add_argument("--safe-output", required=True)

    evaluate = sub.add_parser("evaluate-development")
    _add_common_inputs(evaluate)
    evaluate.add_argument("--contracts", required=True)
    evaluate.add_argument("--adjudication", required=True)
    evaluate.add_argument("--private-output", required=True)
    evaluate.add_argument("--safe-output", required=True)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    freeze.add_argument("--contracts", required=True)
    freeze.add_argument("--evaluation", required=True)
    freeze.add_argument("--private-output", required=True)
    freeze.add_argument("--safe-output", required=True)

    holdout = sub.add_parser("execute-holdout")
    _add_common_inputs(holdout)
    holdout.add_argument("--freeze", required=True)
    holdout.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    holdout.add_argument("--private-output", required=True)
    holdout.add_argument("--safe-output", required=True)

    finalize = sub.add_parser("finalize-holdout")
    finalize.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    finalize.add_argument("--freeze", required=True)
    finalize.add_argument("--holdout", required=True)
    finalize.add_argument("--adjudication", required=True)
    finalize.add_argument("--private-output", required=True)
    finalize.add_argument("--safe-output", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "smoke":
            result = smoke()
        elif args.command == "generate-development":
            result = generate_contracts(
                split="development",
                manifest_path=Path(args.manifest),
                g594_private_dir=Path(args.g594_private_dir),
                env_path=Path(args.env_file),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        elif args.command == "evaluate-development":
            result = evaluate_development(
                manifest_path=Path(args.manifest),
                source_map_path=Path(args.source_map),
                contracts_path=Path(args.contracts),
                adjudication_path=Path(args.adjudication),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        elif args.command == "freeze":
            result = freeze_candidate(
                manifest_path=Path(args.manifest),
                contracts_path=Path(args.contracts),
                evaluation_path=Path(args.evaluation),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        elif args.command == "execute-holdout":
            result = execute_holdout(
                manifest_path=Path(args.manifest),
                source_map_path=Path(args.source_map),
                g594_private_dir=Path(args.g594_private_dir),
                freeze_path=Path(args.freeze),
                env_path=Path(args.env_file),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        else:
            result = finalize_holdout(
                manifest_path=Path(args.manifest),
                freeze_path=Path(args.freeze),
                holdout_path=Path(args.holdout),
                adjudication_path=Path(args.adjudication),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, G598Error) else type(exc).__name__
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--source-map", required=False)
    parser.add_argument("--g594-private-dir", required=False)


def smoke() -> dict[str, Any]:
    page = {
        "page_number": 7,
        "height": 100.0,
        "layout_projection_status": "complete",
        "line_inventory": [
            _synthetic_line(1, 5, "Unique title"),
            _synthetic_line(2, 15, "Alpha Beta Gamma"),
            _synthetic_line(3, 25, "body hidden"),
            _synthetic_line(4, 35, "Repeated title"),
            _synthetic_line(5, 45, "Alpha Beta Gamma"),
            _synthetic_line(6, 55, "body hidden"),
            _synthetic_line(7, 65, "Repeated title"),
            _synthetic_line(8, 75, "Alpha Beta Gamma"),
            _synthetic_line(9, 85, "body hidden"),
            _synthetic_line(10, 96, "footer words"),
        ],
        "word_inventory": [],
        "table_candidate_inventory": [],
    }
    contract = {
        "tables": [
            {
                "before_anchor": {
                    "relation": "immediately_after",
                    "tokens": ["Unique", "title"],
                },
                "header_token_groups": [["Alpha"], ["Gamma"]],
                "after_anchor": {
                    "boundary": "page_footer",
                    "tokens": ["footer", "words"],
                },
                "table_ordinal_in_scope": 1,
                "continuation_from_previous_page": False,
            }
        ]
    }
    validate_page_contract(contract)
    result = resolve_page_contract(page=page, page_number=7, contract=contract)
    if result["tables"][0]["terminal"] != RESOLVED:
        raise G598Error("g598_smoke_unique_composition_failed")
    bad = copy.deepcopy(contract)
    bad["tables"][0]["header_token_groups"] = [["missing"], ["absent"]]
    if resolve_page_contract(page=page, page_number=7, contract=bad)["tables"][0][
        "terminal"
    ] != NOT_FOUND:
        raise G598Error("g598_smoke_not_found_failed")
    ambiguous = copy.deepcopy(contract)
    ambiguous["tables"][0]["before_anchor"] = {
        "relation": "immediately_after",
        "tokens": ["Repeated", "title"],
    }
    if resolve_page_contract(
        page=page, page_number=7, contract=ambiguous
    )["tables"][0]["terminal"] != AMBIGUOUS:
        raise G598Error("g598_smoke_ambiguous_failed")
    return {
        "status": "passed",
        "factory_required": "PdfTextLayerParserFactory.create",
        "forbidden_direct_adapter": "PdfPlumberLayoutAdapter",
        "terminals": [RESOLVED, NOT_FOUND, AMBIGUOUS, CONTRACT_NOT_VERIFIED],
    }


def generate_contracts(
    *,
    split: str,
    manifest_path: Path,
    g594_private_dir: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    _require_fresh(private_output, safe_output)
    cases = manifest[split]
    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G598Error("g598_provider_not_qualified")
    results = []
    for case in cases:
        page_path = _page_png(g594_private_dir, case)
        png = page_path.read_bytes()
        if _sha256_bytes(png) != case["page_png_sha256"]:
            raise G598Error("g598_page_png_hash_drift")
        outcome = provider.invoke(
            task_id=f"g598_{case['case_id']}",
            model_view={"task": PROMPT},
            output_schema=copy.deepcopy(RESPONSE_SCHEMA),
            png_bytes=png,
            crop_sha256=case["page_png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        proposed = outcome.get("json_output")
        validation_error = None
        try:
            validate_page_contract(proposed)
        except G598Error as exc:
            validation_error = exc.code
            proposed = None
        results.append(
            {
                "case_id": case["case_id"],
                "document_id": case["document_id"],
                "page": int(case["page"]),
                "page_png_sha256": case["page_png_sha256"],
                "contract": proposed,
                "validation_error": validation_error,
                "attempt": outcome.get("attempt"),
                "raw_private_response": outcome.get("raw_private_response"),
                "response_hash": outcome.get("response_hash"),
            }
        )
    private = {
        "schema_version": PRIVATE_CONTRACT_SCHEMA,
        "goal": "G5.98",
        "split": split,
        "manifest_file_sha256": _sha256_file(manifest_path),
        "prompt_sha256": _sha256_json(PROMPT),
        "response_schema_sha256": _sha256_json(RESPONSE_SCHEMA),
        "provider_policy": {
            "calls": len(cases),
            "attempts_per_page": 1,
            "retry": False,
            "best_of_n": False,
            "body_values": 0,
            "exact_bboxes": 0,
            "canonical_ids": 0,
        },
        "qualification": qualification,
        "results": results,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_SCHEMA,
        "goal": "G5.98",
        "phase": f"{split}_contract_generation",
        "provider_calls": len(cases),
        "valid_contracts": sum(item["contract"] is not None for item in results),
        "invalid_contracts": sum(item["contract"] is None for item in results),
        "proposed_tables": sum(
            len((item["contract"] or {}).get("tables") or []) for item in results
        ),
        "attempts": [_safe_attempt(item["attempt"]) for item in results],
        "private_file_sha256": _sha256_file(private_output),
        "privacy": _privacy(),
    }
    _write_json(safe_output, safe)
    return {"status": "complete", "provider_calls": len(cases)}


def evaluate_development(
    *,
    manifest_path: Path,
    source_map_path: Path,
    contracts_path: Path,
    adjudication_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    _require_fresh(private_output, safe_output)
    contracts = _read_object(contracts_path)
    if contracts.get("schema_version") != PRIVATE_CONTRACT_SCHEMA:
        raise G598Error("g598_development_contract_receipt_invalid")
    adjudication = _load_adjudication(adjudication_path, "development")
    sources = _load_source_map(source_map_path, manifest)
    by_case = {item["case_id"]: item for item in contracts["results"]}
    truth = {item["case_id"]: item["expected_regions"] for item in adjudication["cases"]}
    evaluated = []
    parser_evidence = []
    for case in manifest["development"]:
        proposal = by_case[case["case_id"]]
        page, evidence = _parse_page(sources, case)
        resolution = (
            resolve_page_contract(
                page=page,
                page_number=int(case["page"]),
                contract=proposal["contract"],
            )
            if proposal["contract"] is not None
            else {"page_number": int(case["page"]), "tables": []}
        )
        metrics = _score_case(resolution, truth[case["case_id"]])
        evaluated.append(
            {
                "case_id": case["case_id"],
                "document_id": case["document_id"],
                "page": int(case["page"]),
                "expected_regions": truth[case["case_id"]],
                "resolution": resolution,
                "metrics": metrics,
                "contract_validation_error": proposal["validation_error"],
            }
        )
        parser_evidence.append(evidence)
    totals = _sum_metrics(evaluated)
    private = {
        "schema_version": PRIVATE_EVALUATION_SCHEMA,
        "goal": "G5.98",
        "phase": "development",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "contract_file_sha256": _sha256_file(contracts_path),
        "adjudication_file_sha256": _sha256_file(adjudication_path),
        "implementation_sha256": _sha256_file(SCRIPT_PATH),
        "parser_evidence": parser_evidence,
        "cases": evaluated,
        "metrics": totals,
    }
    _write_json(private_output, private)
    safe = _safe_evaluation("development_evaluation", totals)
    safe["implementation_sha256"] = private["implementation_sha256"]
    safe["private_file_sha256"] = _sha256_file(private_output)
    _write_json(safe_output, safe)
    return {"status": "complete", "metrics": totals}


def freeze_candidate(
    *,
    manifest_path: Path,
    contracts_path: Path,
    evaluation_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    _load_manifest(manifest_path)
    _require_fresh(private_output, safe_output)
    contracts = _read_object(contracts_path)
    evaluation = _read_object(evaluation_path)
    if (
        contracts.get("schema_version") != PRIVATE_CONTRACT_SCHEMA
        or contracts.get("split") != "development"
        or evaluation.get("schema_version") != PRIVATE_EVALUATION_SCHEMA
        or evaluation.get("phase") != "development"
        or contracts.get("manifest_file_sha256") != _sha256_file(manifest_path)
        or contracts.get("prompt_sha256") != _sha256_json(PROMPT)
        or contracts.get("response_schema_sha256") != _sha256_json(RESPONSE_SCHEMA)
        or evaluation.get("manifest_file_sha256") != _sha256_file(manifest_path)
        or evaluation.get("contract_file_sha256") != _sha256_file(contracts_path)
        or evaluation.get("implementation_sha256") != _sha256_file(SCRIPT_PATH)
    ):
        raise G598Error("g598_development_evidence_invalid")
    private = {
        "schema_version": PRIVATE_FREEZE_SCHEMA,
        "goal": "G5.98",
        "frozen": True,
        "manifest_file_sha256": _sha256_file(manifest_path),
        "development_contract_file_sha256": _sha256_file(contracts_path),
        "development_evaluation_file_sha256": _sha256_file(evaluation_path),
        "implementation_sha256": _sha256_file(SCRIPT_PATH),
        "prompt_sha256": _sha256_json(PROMPT),
        "response_schema_sha256": _sha256_json(RESPONSE_SCHEMA),
        "resolver_contract": {
            "composition": [
                "resolve_before_anchor_scope",
                "verify_header_fingerprint",
                "resolve_after_anchor_scope",
                "intersect_scopes",
                "require_exactly_one_region",
            ],
            "ranking": False,
            "fuzzy_winner": False,
            "terminals": [RESOLVED, NOT_FOUND, AMBIGUOUS, CONTRACT_NOT_VERIFIED],
        },
        "development_metrics": evaluation["metrics"],
        "post_freeze_tuning": False,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_SCHEMA,
        "goal": "G5.98",
        "phase": "schema_and_resolver_freeze",
        "frozen": True,
        "implementation_sha256": private["implementation_sha256"],
        "prompt_sha256": private["prompt_sha256"],
        "response_schema_sha256": private["response_schema_sha256"],
        "development_metrics": private["development_metrics"],
        "private_file_sha256": _sha256_file(private_output),
        "privacy": _privacy(),
    }
    _write_json(safe_output, safe)
    return {"status": "frozen", "implementation_sha256": private["implementation_sha256"]}


def execute_holdout(
    *,
    manifest_path: Path,
    source_map_path: Path,
    g594_private_dir: Path,
    freeze_path: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    _require_fresh(private_output, safe_output)
    frozen = _validate_freeze(freeze_path, manifest_path)
    sources = _load_source_map(source_map_path, manifest)
    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G598Error("g598_provider_not_qualified")
    outcomes = []
    for case in manifest["unseen_holdout"]:
        path = _page_png(g594_private_dir, case)
        png = path.read_bytes()
        if _sha256_bytes(png) != case["page_png_sha256"]:
            raise G598Error("g598_holdout_png_hash_drift")
        outcome = provider.invoke(
            task_id=f"g598_{case['case_id']}",
            model_view={"task": PROMPT},
            output_schema=copy.deepcopy(RESPONSE_SCHEMA),
            png_bytes=png,
            crop_sha256=case["page_png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        proposal = outcome.get("json_output")
        validation_error = None
        try:
            validate_page_contract(proposal)
        except G598Error as exc:
            validation_error = exc.code
            proposal = None
        page, parser_evidence = _parse_page(sources, case)
        resolution = (
            resolve_page_contract(
                page=page, page_number=int(case["page"]), contract=proposal
            )
            if proposal is not None
            else {"page_number": int(case["page"]), "tables": []}
        )
        outcomes.append(
            {
                "case_id": case["case_id"],
                "document_id": case["document_id"],
                "page": int(case["page"]),
                "contract": proposal,
                "validation_error": validation_error,
                "resolution": resolution,
                "attempt": outcome.get("attempt"),
                "raw_private_response": outcome.get("raw_private_response"),
                "response_hash": outcome.get("response_hash"),
                "parser_evidence": parser_evidence,
            }
        )
    private = {
        "schema_version": PRIVATE_HOLDOUT_SCHEMA,
        "goal": "G5.98",
        "phase": "frozen_unseen_holdout_execution",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "freeze_file_sha256": _sha256_file(freeze_path),
        "implementation_sha256": frozen["implementation_sha256"],
        "provider_policy": {
            "calls": len(outcomes),
            "attempts_per_page": 1,
            "retry": False,
            "best_of_n": False,
            "post_open_tuning": False,
        },
        "qualification": qualification,
        "cases": outcomes,
    }
    _write_json(private_output, private)
    terminals = Counter(
        table["terminal"]
        for case in outcomes
        for table in case["resolution"]["tables"]
    )
    safe = {
        "schema_version": SAFE_SCHEMA,
        "goal": "G5.98",
        "phase": "frozen_unseen_holdout_execution",
        "provider_calls": len(outcomes),
        "attempts_per_page": 1,
        "retry": False,
        "best_of_n": False,
        "post_holdout_tuning": False,
        "proposed_tables": sum(
            len((case["contract"] or {}).get("tables") or []) for case in outcomes
        ),
        "resolver_terminals": dict(sorted(terminals.items())),
        "implementation_sha256": frozen["implementation_sha256"],
        "attempts": [_safe_attempt(case["attempt"]) for case in outcomes],
        "private_file_sha256": _sha256_file(private_output),
        "privacy": _privacy(),
    }
    _write_json(safe_output, safe)
    return {"status": "executed_once", "provider_calls": len(outcomes)}


def finalize_holdout(
    *,
    manifest_path: Path,
    freeze_path: Path,
    holdout_path: Path,
    adjudication_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    _load_manifest(manifest_path)
    _require_fresh(private_output, safe_output)
    frozen = _validate_freeze(freeze_path, manifest_path)
    holdout = _read_object(holdout_path)
    if (
        holdout.get("schema_version") != PRIVATE_HOLDOUT_SCHEMA
        or holdout.get("implementation_sha256") != frozen["implementation_sha256"]
    ):
        raise G598Error("g598_holdout_receipt_invalid")
    adjudication = _load_adjudication(adjudication_path, "holdout")
    truth = {item["case_id"]: item["expected_regions"] for item in adjudication["cases"]}
    evaluated = []
    for case in holdout["cases"]:
        metrics = _score_case(case["resolution"], truth[case["case_id"]])
        evaluated.append(
            {
                "case_id": case["case_id"],
                "document_id": case["document_id"],
                "page": case["page"],
                "expected_regions": truth[case["case_id"]],
                "resolution": case["resolution"],
                "metrics": metrics,
            }
        )
    totals = _sum_metrics(evaluated)
    layout_families = {
        case["document_id"] for case in evaluated if case["metrics"]["unique_correct"]
    }
    terminals = _verdict(totals, len(layout_families))
    private = {
        "schema_version": PRIVATE_EVALUATION_SCHEMA,
        "goal": "G5.98",
        "phase": "holdout_final",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "freeze_file_sha256": _sha256_file(freeze_path),
        "holdout_file_sha256": _sha256_file(holdout_path),
        "adjudication_file_sha256": _sha256_file(adjudication_path),
        "implementation_sha256": frozen["implementation_sha256"],
        "implementation_unchanged_after_holdout": _sha256_file(SCRIPT_PATH)
        == frozen["implementation_sha256"],
        "cases": evaluated,
        "metrics": totals,
        "resolved_layout_families": sorted(layout_families),
        "terminals": terminals,
    }
    if not private["implementation_unchanged_after_holdout"]:
        raise G598Error("g598_post_freeze_implementation_drift")
    _write_json(private_output, private)
    safe = _safe_evaluation("holdout_final", totals)
    safe.update(
        {
            "terminals": terminals,
            "resolved_layout_families": len(layout_families),
            "implementation_sha256": frozen["implementation_sha256"],
            "implementation_unchanged_after_holdout": True,
            "private_file_sha256": _sha256_file(private_output),
        }
    )
    _write_json(safe_output, safe)
    return {"status": "complete", "terminals": terminals, "metrics": totals}


def validate_page_contract(value: Any) -> None:
    _reject_forbidden_keys(value)
    if not isinstance(value, dict) or set(value) != {"tables"}:
        raise G598Error("g598_contract_shape_invalid")
    tables = value["tables"]
    if not isinstance(tables, list) or len(tables) > 12:
        raise G598Error("g598_contract_tables_invalid")
    required = {
        "before_anchor",
        "header_token_groups",
        "after_anchor",
        "table_ordinal_in_scope",
        "continuation_from_previous_page",
    }
    for table in tables:
        if not isinstance(table, dict) or set(table) != required:
            raise G598Error("g598_table_contract_shape_invalid")
        before = table["before_anchor"]
        after = table["after_anchor"]
        if not isinstance(before, dict) or set(before) != {"relation", "tokens"}:
            raise G598Error("g598_before_anchor_invalid")
        if before["relation"] not in _BEFORE_RELATIONS:
            raise G598Error("g598_before_relation_invalid")
        _validate_tokens(
            before["tokens"],
            allow_empty=before["relation"] == "page_start",
            maximum=5,
        )
        if before["relation"] == "page_start" and before["tokens"]:
            raise G598Error("g598_page_start_tokens_forbidden")
        if not isinstance(after, dict) or set(after) != {"boundary", "tokens"}:
            raise G598Error("g598_after_anchor_invalid")
        if after["boundary"] not in _AFTER_BOUNDARIES:
            raise G598Error("g598_after_boundary_invalid")
        _validate_tokens(
            after["tokens"],
            allow_empty=after["boundary"] != "next_anchor",
            maximum=5,
        )
        if after["boundary"] == "page_end" and after["tokens"]:
            raise G598Error("g598_page_end_tokens_forbidden")
        groups = table["header_token_groups"]
        if not isinstance(groups, list) or len(groups) > 20:
            raise G598Error("g598_header_groups_invalid")
        for group in groups:
            _validate_tokens(group, allow_empty=False, maximum=8)
        continuation = table["continuation_from_previous_page"]
        if not isinstance(continuation, bool):
            raise G598Error("g598_continuation_invalid")
        if not groups and not (continuation and before["relation"] == "page_start"):
            raise G598Error("g598_headerless_noncontinuation_forbidden")
        if groups and len(groups) < 2 and not continuation:
            raise G598Error("g598_header_groups_invalid")
        ordinal = table["table_ordinal_in_scope"]
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or not 1 <= ordinal <= 12:
            raise G598Error("g598_table_ordinal_invalid")


def resolve_page_contract(
    *, page: dict[str, Any], page_number: int, contract: dict[str, Any]
) -> dict[str, Any]:
    validate_page_contract(contract)
    if page.get("layout_projection_status") != "complete":
        return {
            "page_number": page_number,
            "tables": [
                {"terminal": CONTRACT_NOT_VERIFIED, "reason": "layout_incomplete"}
                for _ in contract["tables"]
            ],
        }
    return {
        "page_number": page_number,
        "tables": [_resolve_one(page, item) for item in contract["tables"]],
    }


def _resolve_one(page: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    lines = page.get("line_inventory") or []
    if not lines:
        return {"terminal": CONTRACT_NOT_VERIFIED, "reason": "line_inventory_empty"}
    before = contract["before_anchor"]
    if before["relation"] == "page_start":
        before_ordinals = [0]
    else:
        before_ordinals = _matching_lines(lines, before["tokens"])
    if not before_ordinals:
        return {"terminal": NOT_FOUND, "reason": "before_anchor_not_found"}
    after = contract["after_anchor"]
    if after["boundary"] == "page_end":
        after_ordinals = [len(lines) + 1]
    elif after["boundary"] == "page_footer":
        after_ordinals = _footer_lines(page, after["tokens"])
        if not after_ordinals:
            return {
                "terminal": CONTRACT_NOT_VERIFIED,
                "reason": "page_footer_not_verified",
            }
    else:
        after_ordinals = _matching_lines(lines, after["tokens"])
        if not after_ordinals:
            return {"terminal": NOT_FOUND, "reason": "after_anchor_not_found"}
    groups = contract["header_token_groups"]
    header_windows = _header_windows(lines, groups) if groups else []
    regions: dict[tuple[int, int], dict[str, Any]] = {}
    for before_ordinal in before_ordinals:
        eligible_after = [ordinal for ordinal in after_ordinals if ordinal > before_ordinal]
        if after["boundary"] == "next_anchor" and eligible_after:
            eligible_after = [min(eligible_after)]
        for after_ordinal in eligible_after:
            if after_ordinal <= before_ordinal + 1:
                continue
            if not groups:
                candidates = [(before_ordinal + 1, before_ordinal + 1)]
            else:
                candidates = [
                    window
                    for window in header_windows
                    if before_ordinal < window[0] < after_ordinal
                ]
                if before["relation"] == "immediately_after":
                    candidates = [
                        window for window in candidates if window[0] == before_ordinal + 1
                    ]
            candidates = sorted(set(candidates))
            ordinal = contract["table_ordinal_in_scope"]
            if ordinal > len(candidates):
                continue
            start = candidates[ordinal - 1][0]
            end = after_ordinal - 1
            if end < start:
                continue
            regions[(start, end)] = _region(page, start, end)
    ordered = [regions[key] for key in sorted(regions)]
    if not ordered:
        return {"terminal": NOT_FOUND, "reason": "composed_region_not_found"}
    if len(ordered) > 1:
        return {
            "terminal": AMBIGUOUS,
            "reason": "multiple_composed_regions",
            "candidate_regions": ordered,
        }
    return {"terminal": RESOLVED, "reason": None, "region": ordered[0]}


def _header_windows(
    lines: list[dict[str, Any]], groups: list[list[str]]
) -> list[tuple[int, int]]:
    windows = []
    for start in range(1, len(lines) + 1):
        for end in range(start, min(len(lines), start + 5) + 1):
            text = " ".join(str(line.get("text") or "") for line in lines[start - 1 : end])
            if all(_window_contains_group(text, group) for group in groups):
                windows.append((start, end))
    return [
        window
        for window in windows
        if not any(
            other != window
            and window[0] <= other[0]
            and other[1] <= window[1]
            for other in windows
        )
    ]


def _matching_lines(lines: list[dict[str, Any]], tokens: list[str]) -> list[int]:
    return [
        int(line["parser_ordinal"])
        for line in lines
        if _line_matches(str(line.get("text") or ""), tokens)
    ]


def _line_matches(text: str, tokens: list[str]) -> bool:
    source = [_normalized(item) for item in text.split()]
    target = [
        piece
        for token in tokens
        for item in str(token).split()
        if (piece := _normalized(item))
    ]
    if not target:
        return False
    iterator = iter(source)
    return all(any(item == wanted for item in iterator) for wanted in target)


def _window_contains_group(text: str, tokens: list[str]) -> bool:
    source = Counter(_normalized(item) for item in text.split() if _normalized(item))
    target = Counter(
        piece
        for token in tokens
        for item in str(token).split()
        if (piece := _normalized(item))
    )
    return bool(target) and all(source[token] >= count for token, count in target.items())


def _footer_lines(page: dict[str, Any], tokens: list[str]) -> list[int]:
    lines = page.get("line_inventory") or []
    if tokens:
        return [
            ordinal
            for ordinal in _matching_lines(lines, tokens)
            if float(lines[ordinal - 1]["bbox"][1]) >= float(page["height"]) * 0.90
        ]
    return [
        int(line["parser_ordinal"])
        for line in lines
        if float(line["bbox"][1]) >= float(page["height"]) * 0.95
    ]


def _region(page: dict[str, Any], start: int, end: int) -> dict[str, Any]:
    selected = [
        line
        for line in page.get("line_inventory") or []
        if start <= int(line["parser_ordinal"]) <= end
    ]
    bbox = [
        min(float(line["bbox"][0]) for line in selected),
        min(float(line["bbox"][1]) for line in selected),
        max(float(line["bbox"][2]) for line in selected),
        max(float(line["bbox"][3]) for line in selected),
    ]
    word_ordinals = sorted(
        {
            int(ordinal)
            for line in selected
            for ordinal in line.get("word_parser_ordinals") or []
        }
    )
    overlaps = []
    for index, candidate in enumerate(page.get("table_candidate_inventory") or [], 1):
        if _bbox_overlap(bbox, candidate["bbox"]):
            overlaps.append(index)
    return {
        "first_line_ordinal": start,
        "last_line_ordinal": end,
        "line_ordinals": list(range(start, end + 1)),
        "word_parser_ordinals": word_ordinals,
        "bbox": [round(value, 3) for value in bbox],
        "overlapping_parser_candidate_ordinals": overlaps,
    }


def _parse_page(
    sources: dict[str, dict[str, Any]], case: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = sources[case["document_id"]]
    content = Path(source["path"]).read_bytes()
    if _sha256_bytes(content) != source["sha256"]:
        raise G598Error("g598_source_pdf_hash_drift")
    reader = pypdf.PdfReader(BytesIO(content), strict=False)
    page_number = int(case["page"])
    if not 1 <= page_number <= len(reader.pages):
        raise G598Error("g598_page_out_of_range")
    writer = pypdf.PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    sliced = BytesIO()
    writer.write(sliced)
    started = time.perf_counter()
    parser = PdfTextLayerParserFactory().create(
        PdfParserCapabilityRequest(capability="table_candidates")
    )
    result = parser.parse(sliced.getvalue())
    if result.layout_projection_status != "complete" or len(result.pages) != 1:
        raise G598Error("g598_parser_layout_incomplete")
    page = result.pages[0]
    page["page_number"] = page_number
    return page, {
        "case_id": case["case_id"],
        "factory_entrypoint": "PdfTextLayerParserFactory.create",
        "engine": result.parser_engine,
        "engine_version": result.parser_engine_version,
        "config_ref": result.parser_config_ref,
        "source_pdf_hash_verified_before_lossless_slice": True,
        "line_inventory_total": len(page.get("line_inventory") or []),
        "word_inventory_total": len(page.get("word_inventory") or []),
        "table_candidates_total": len(page.get("table_candidate_inventory") or []),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _score_case(resolution: dict[str, Any], expected: list[list[int]]) -> dict[str, int]:
    expected_pairs = [tuple(map(int, item)) for item in expected]
    unmatched = list(expected_pairs)
    unique_correct = false_localization = ambiguous = not_found = unverified = 0
    false_table_admitted = 0
    for table in resolution.get("tables") or []:
        terminal = table["terminal"]
        if terminal == RESOLVED:
            region = table["region"]
            pair = (region["first_line_ordinal"], region["last_line_ordinal"])
            if pair in unmatched:
                unique_correct += 1
                unmatched.remove(pair)
            else:
                false_localization += 1
                if not expected_pairs:
                    false_table_admitted += 1
        elif terminal == AMBIGUOUS:
            ambiguous += 1
        elif terminal == NOT_FOUND:
            not_found += 1
        else:
            unverified += 1
    return {
        "expected_regions": len(expected_pairs),
        "proposed_tables": len(resolution.get("tables") or []),
        "unique_correct": unique_correct,
        "ambiguous": ambiguous,
        "not_found": not_found,
        "missed_expected": len(unmatched),
        "contract_not_verified": unverified,
        "false_localization": false_localization,
        "false_table_admitted": false_table_admitted,
        "exact_case": int(
            unique_correct == len(expected_pairs)
            and not any((ambiguous, not_found, unverified, false_localization))
        ),
    }


def _sum_metrics(evaluated: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "expected_regions",
        "proposed_tables",
        "unique_correct",
        "ambiguous",
        "not_found",
        "missed_expected",
        "contract_not_verified",
        "false_localization",
        "false_table_admitted",
        "exact_case",
    )
    totals = {key: sum(item["metrics"][key] for item in evaluated) for key in keys}
    totals["cases"] = len(evaluated)
    return totals


def _verdict(metrics: dict[str, int], layout_families: int) -> list[str]:
    exact = (
        metrics["unique_correct"] == metrics["expected_regions"]
        and metrics["false_localization"] == 0
        and metrics["false_table_admitted"] == 0
        and metrics["ambiguous"] == 0
        and metrics["not_found"] == 0
        and metrics["contract_not_verified"] == 0
    )
    if exact and layout_families >= 2:
        return [PROVEN, UNIQUE_PROVEN, ZERO_FALSE, ENGINE_NEUTRAL]
    if metrics["false_localization"] == 0 and metrics["unique_correct"] > 0:
        return [PARTIAL, ZERO_FALSE]
    if metrics["false_localization"] > 0:
        return [EXCESSIVE]
    return [INSUFFICIENT]


def _safe_evaluation(phase: str, metrics: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": SAFE_SCHEMA,
        "goal": "G5.98",
        "phase": phase,
        "metrics": metrics,
        "privacy": _privacy(),
    }


def _provider(env_path: Path) -> Any:
    return PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile="google_gemini",
            model_id="models/gemini-3.5-flash",
            timeout_seconds=240,
            maximum_output_tokens=4096,
            maximum_counted_input_tokens=24000,
            thinking_level="minimal",
        )
    ).create_for_openwebui(_openwebui_request(env_path.resolve()))


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(env.get("OPENWEBUI_HOST") or "").rstrip("/")
    email = str(env.get("WEBUI_ADMIN_EMAIL") or "")
    password = str(env.get("WEBUI_ADMIN_PASSWORD") or "")
    if not all((host, email, password)):
        raise G598Error("g598_openwebui_credentials_missing")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str((response.json() or {}).get("token") or "")
    if not token:
        raise G598Error("g598_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json() or {}
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


def _load_manifest(path: Path) -> dict[str, Any]:
    value = _read_object(path)
    if value.get("schema_version") != MANIFEST_SCHEMA or value.get("frozen") is not True:
        raise G598Error("g598_manifest_invalid")
    if any(
        case["document_id"] == "document_04" and int(case["page"]) == 29
        for split in ("development", "unseen_holdout")
        for case in value[split]
    ):
        raise G598Error("g598_p029_forbidden")
    return value


def _load_source_map(path: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = _read_object(path)
    expected = {item["document_id"]: item["pdf_sha256"] for item in manifest["source_documents"]}
    sources = value.get("documents")
    if not isinstance(sources, dict) or set(sources) != set(expected):
        raise G598Error("g598_source_map_invalid")
    for document_id, digest in expected.items():
        item = sources[document_id]
        if not isinstance(item, dict) or item.get("sha256") != digest or not item.get("path"):
            raise G598Error("g598_source_map_entry_invalid")
    return sources


def _load_adjudication(path: Path, phase: str) -> dict[str, Any]:
    value = _read_object(path)
    if value.get("goal") != "G5.98" or value.get("phase") != phase:
        raise G598Error("g598_adjudication_invalid")
    return value


def _validate_freeze(path: Path, manifest_path: Path) -> dict[str, Any]:
    value = _read_object(path)
    if (
        value.get("schema_version") != PRIVATE_FREEZE_SCHEMA
        or value.get("frozen") is not True
        or value.get("manifest_file_sha256") != _sha256_file(manifest_path)
        or value.get("implementation_sha256") != _sha256_file(SCRIPT_PATH)
        or value.get("prompt_sha256") != _sha256_json(PROMPT)
        or value.get("response_schema_sha256") != _sha256_json(RESPONSE_SCHEMA)
    ):
        raise G598Error("g598_freeze_invalid_or_drifted")
    return value


def _validate_tokens(
    value: Any, *, allow_empty: bool, maximum: int = 8
) -> None:
    if not isinstance(value, list) or len(value) > maximum or (not value and not allow_empty):
        raise G598Error("g598_tokens_invalid")
    for token in value:
        if (
            not isinstance(token, str)
            or not token.strip()
            or len(token) > 80
            or _DIGIT_RE.search(token)
            or not any(char.isalpha() for char in token)
        ):
            raise G598Error("g598_token_invalid")


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in _FORBIDDEN_KEYS:
                raise G598Error("g598_contract_domain_leakage")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested)


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = _DIGIT_RE.sub("", normalized)
    return _TOKEN_RE.sub("", normalized)


def _bbox_overlap(left: list[float], right: list[float]) -> bool:
    return (
        min(float(left[2]), float(right[2])) > max(float(left[0]), float(right[0]))
        and min(float(left[3]), float(right[3])) > max(float(left[1]), float(right[1]))
    )


def _synthetic_line(ordinal: int, top: float, value: str) -> dict[str, Any]:
    return {
        "parser_ordinal": ordinal,
        "bbox": [0.0, top, 50.0, top + 5.0],
        "text": value,
        "word_parser_ordinals": [],
    }


def _page_png(root: Path, case: dict[str, Any]) -> Path:
    return (
        root
        / "documents"
        / str(case["document_id"])
        / "pages"
        / f"p{int(case['page']):03d}.private.png"
    )


def _safe_attempt(value: Any) -> dict[str, Any]:
    attempt = value if isinstance(value, dict) else {}
    return {
        key: attempt.get(key)
        for key in (
            "attempt_number",
            "provider",
            "provider_profile",
            "model_requested",
            "model_resolved",
            "duration_ms",
            "http_status",
            "usage",
            "finish_reason",
            "parse_result",
            "terminal_failure_class",
            "hidden_retry",
            "provider_failover",
        )
    }


def _privacy() -> dict[str, bool]:
    return {
        "customer_literals_in_safe_output": False,
        "customer_paths_in_safe_output": False,
        "source_coordinates_in_safe_output": False,
        "provider_payloads_in_safe_output": False,
        "private_evidence_outside_git": True,
    }


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise G598Error("g598_env_file_missing")
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _require_fresh(*paths: Path) -> None:
    if any(path.exists() for path in paths):
        raise G598Error("g598_output_must_be_fresh")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G598Error("g598_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(payload)


if __name__ == "__main__":
    raise SystemExit(main())
