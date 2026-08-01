#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import fitz

from broker_reports_gate1.managed_document_contracts import ManagedDocumentContractValidator
from broker_reports_gate1.managed_document_llm_view import ManagedDocumentLlmViewFactory

from broker_reports_gate1.pdf_view_semantic_adjudication import (
    PdfViewSemanticAdjudicationFactory,
    PdfViewSemanticComparator,
    PdfViewSemanticResultFactory,
    compare_stability_replay,
    validate_doc4_context_preflight,
)
from broker_reports_gate1.pdf_view_semantic_contracts import (
    CORPUS_IDS,
    EXPERIMENT_PROTOCOL_VERSION,
    RUN_ORDER,
    Doc4ContractError,
    canonical_json_bytes,
    integrity_sha256,
    read_json,
    sha256_bytes,
    validate_provider_authorization,
    validate_json_contract,
    validate_semantic_response,
)
from broker_reports_gate1.pdf_view_semantic_experiment import (
    MODEL_PROVIDER,
    REQUEST_MODEL_ID,
    CorpusSource,
    ModelCandidate,
    OpenAiDoc4Transport,
    PdfViewSemanticExperimentRunner,
    authorized_request_keys,
    build_arm_request,
    connection_from_env_file,
    context_preflight_request_sha256s,
    hash_bound_private_payload,
    pdf_pages_total,
    pdf_page_texts,
    provider_usage_from_traces,
    view_pointer_registry,
    write_immutable_json,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DOCS_ROOT = REPOSITORY_ROOT / "docs" / "stage2"
DEFAULT_RESPONSE_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_DOC4_SEMANTIC_RESPONSE.v1.schema.json"
DEFAULT_GOLD_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_DOC4_GOLD_CHECKLIST.v1.schema.json"
DEFAULT_COMPARISON_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_DOC4_SEMANTIC_COMPARISON.v1.schema.json"
DEFAULT_ADJUDICATION_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_DOC4_ADJUDICATION.v1.schema.json"
DEFAULT_RESULT_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_DOC4_SEMANTIC_RESULT.v1.schema.json"
DEFAULT_SYSTEM_PROMPT = DOCS_ROOT / "prompts" / "BROKER_REPORTS_DOC4_SEMANTIC_SYSTEM_PROMPT.v1.md"
DEFAULT_TASK_PROMPT = DOCS_ROOT / "prompts" / "BROKER_REPORTS_DOC4_SEMANTIC_TASK_PROMPT.v1.md"
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
MANAGED_DOCUMENT_SCHEMA = DOCS_ROOT / "contracts" / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
DOC3_COVERAGE = DOCS_ROOT / "BROKER_REPORTS_DOC1_TO_DOC3_VIEW_COVERAGE.v1.json"
MANAGED_DOCUMENT_FIXTURES = SERVICE_ROOT / "tests" / "fixtures" / "broker_reports_managed_document_v1_corpus.safe.json"
SECURITY_FIXTURE = SERVICE_ROOT / "tests" / "fixtures" / "broker_reports_doc4_security_fixture.safe.json"

PDF_WRAPPER = "SOURCE_MODE=PDF. Use only native PDF pages. Emit PDF source pointers."
VIEW_WRAPPER = "SOURCE_MODE=LLM_VIEW. Use only the complete tagged LLM Document View. Emit LLM_VIEW source pointers."


def main() -> int:
    parser = argparse.ArgumentParser(description="Inactive DOC4 PDF-vs-LLM-View semantic experiment runner.")
    parser.add_argument("--mode", required=True, choices=("freeze-plan", "seal-gold", "preflight", "run", "compare", "seal-adjudication", "finalize", "validate-response"))
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--run-plan", type=Path)
    parser.add_argument("--context-preflight", type=Path)
    parser.add_argument("--gold-dir", type=Path)
    parser.add_argument("--gold-draft", type=Path)
    parser.add_argument("--adjudication-draft", type=Path)
    parser.add_argument("--pdf-response", type=Path)
    parser.add_argument("--view-response", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--stability-comparison", type=Path)
    parser.add_argument("--run-results-dir", type=Path)
    parser.add_argument("--adjudication-dir", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--source-mode", choices=("PDF", "LLM_VIEW"))
    parser.add_argument("--safe-id", choices=CORPUS_IDS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--task-prompt", type=Path, default=DEFAULT_TASK_PROMPT)
    parser.add_argument("--response-schema", type=Path, default=DEFAULT_RESPONSE_SCHEMA)
    parser.add_argument("--gold-schema", type=Path, default=DEFAULT_GOLD_SCHEMA)
    parser.add_argument("--comparison-schema", type=Path, default=DEFAULT_COMPARISON_SCHEMA)
    parser.add_argument("--adjudication-schema", type=Path, default=DEFAULT_ADJUDICATION_SCHEMA)
    parser.add_argument("--result-schema", type=Path, default=DEFAULT_RESULT_SCHEMA)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _run(args)
    except Doc4ContractError as exc:
        _print_safe(
            {
                "status": "BLOCKED",
                "reason": str(exc),
                "provider_calls_total": None,
                "provider_calls_status": "NOT_RECONCILED_AFTER_FAILURE",
            }
        )
        return 3


def _run(args: argparse.Namespace) -> int:
    response_schema = read_json(_required_file(args.response_schema, "--response-schema"))
    runner = PdfViewSemanticExperimentRunner()
    if args.mode == "freeze-plan":
        sources = _sources(_required_file(args.source_manifest, "--source-manifest"))
        gold_hashes = _gold_hashes(args.gold_dir) if args.gold_dir else None
        plan = runner.freeze_plan(
            sources=sources,
            system_prompt=_repository_lf_bytes(_required_file(args.system_prompt, "--system-prompt")),
            task_prompt=_repository_lf_bytes(_required_file(args.task_prompt, "--task-prompt")),
            pdf_wrapper=PDF_WRAPPER,
            view_wrapper=VIEW_WRAPPER,
            response_schema=response_schema,
            base_commit=_git("merge-base", "HEAD", "origin/main"),
            implementation_commit=_git("rev-parse", "HEAD"),
            gold_checklist_sha256_by_safe_id=gold_hashes,
        )
        output = args.output_dir / "run_plan.private.json"
        digest = write_immutable_json(output, plan)
        _print_safe({"status": "PASSED", "mode": args.mode, "run_plan_sha256": digest, "documents_total": len(plan["sources"]), "gold_checklists_bound": bool(gold_hashes), "provider_calls_total": 0})
        return 0

    if args.mode == "seal-gold":
        safe_id = _required_text(args.safe_id, "--safe-id")
        source = _source_by_id(_sources(_required_file(args.source_manifest, "--source-manifest")), safe_id)
        draft = read_json(_required_file(args.gold_draft, "--gold-draft"))
        sealed = PdfViewSemanticAdjudicationFactory().seal_gold(
            draft,
            gold_schema=read_json(_required_file(args.gold_schema, "--gold-schema")),
            expected_pdf_sha256=sha256_bytes(source.pdf_path.read_bytes()),
            expected_pdf_page_texts=pdf_page_texts(source.pdf_path.read_bytes()),
            provider_calls_started=False,
            expected_pdf_pages=pdf_pages_total(source.pdf_path),
        )
        digest = write_immutable_json(args.output_dir / "gold_checklist.private.json", sealed)
        _print_safe({"status": "PASSED", "mode": args.mode, "safe_id": safe_id, "gold_items_total": len(sealed["items"]), "critical_items_total": len(sealed["critical_fact_ids"]), "checklist_sha256": digest, "provider_calls_total": 0})
        return 0

    if args.mode == "validate-response":
        response = read_json(_required_file(args.response, "--response"))
        source_mode = _required_text(args.source_mode, "--source-mode")
        safe_id = _required_text(args.safe_id, "--safe-id")
        source = _source_by_id(
            _sources(_required_file(args.source_manifest, "--source-manifest")),
            safe_id,
        )
        validate_semantic_response(
            response,
            response_schema,
            expected_source_mode=source_mode,
            pdf_pages_total=(
                pdf_pages_total(source.pdf_path) if source_mode == "PDF" else None
            ),
            pdf_page_texts=(
                pdf_page_texts(source.pdf_path.read_bytes())
                if source_mode == "PDF"
                else None
            ),
            view_registry=(
                view_pointer_registry(source.llm_view_path.read_text(encoding="utf-8"))
                if source_mode == "LLM_VIEW"
                else None
            ),
        )
        _print_safe({"status": "PASSED", "mode": args.mode, "safe_id": safe_id, "provider_calls_total": 0})
        return 0
    plan = _validated_plan(_required_file(args.run_plan, "--run-plan"))
    _verify_plan_protocol_bindings(args, plan=plan, response_schema=response_schema)
    sources = _sources(_required_file(args.source_manifest, "--source-manifest"))
    _verify_plan_source_bindings(plan, sources)
    if args.mode == "finalize":
        preflight = read_json(
            _required_file(args.context_preflight, "--context-preflight")
        )
        run_results_dir = _required_dir(args.run_results_dir, "--run-results-dir")
        adjudication_dir = _required_dir(
            args.adjudication_dir, "--adjudication-dir"
        )
        gold_dir = _required_dir(args.gold_dir, "--gold-dir")
        _verify_gold_hashes(plan, gold_dir)
        gold_schema = read_json(_required_file(args.gold_schema, "--gold-schema"))
        adjudication_schema = read_json(
            _required_file(args.adjudication_schema, "--adjudication-schema")
        )
        adjudications: dict[str, dict[str, Any]] = {}
        comparisons: dict[str, dict[str, Any]] = {}
        gold_checklists: dict[str, dict[str, Any]] = {}
        pdf_responses: dict[str, dict[str, Any]] = {}
        view_responses: dict[str, dict[str, Any]] = {}
        validated_receipts: dict[str, dict[str, dict[str, Any]]] = {}
        run_traces: dict[str, dict[str, dict[str, Any]]] = {}
        expected_request_sha256_by_safe_id: dict[str, dict[str, str]] = {}
        expected_preflight_request_sha256_by_safe_id: dict[
            str, dict[str, tuple[str, ...]]
        ] = {}
        expected_pdf_sha256_by_safe_id: dict[str, str] = {}
        pdf_page_texts_by_safe_id: dict[str, tuple[str, ...]] = {}
        view_registries: dict[str, Any] = {}
        critical_stability_conflicts_by_safe_id: dict[str, int] = {}
        system_prompt, task_prompt = _prompts(args, plan)
        for safe_id in CORPUS_IDS:
            source = _source_by_id(sources, safe_id)
            pdf_response = read_json(
                _required_file(
                    run_results_dir
                    / safe_id
                    / "pdf_arm"
                    / "pdf_arm_response.private.json",
                    "PDF arm response",
                )
            )
            view_response = read_json(
                _required_file(
                    run_results_dir
                    / safe_id
                    / "view_arm"
                    / "view_arm_response.private.json",
                    "View arm response",
                )
            )
            validate_semantic_response(
                pdf_response,
                response_schema,
                expected_source_mode="PDF",
                pdf_pages_total=pdf_pages_total(source.pdf_path),
                pdf_page_texts=pdf_page_texts(source.pdf_path.read_bytes()),
            )
            validate_semantic_response(
                view_response,
                response_schema,
                expected_source_mode="LLM_VIEW",
                view_registry=view_pointer_registry(
                    source.llm_view_path.read_text(encoding="utf-8")
                ),
            )
            adjudication = read_json(
                _required_file(
                    adjudication_dir / safe_id / "source_adjudication.private.json",
                    "source adjudication",
                )
            )
            validate_json_contract(
                adjudication,
                adjudication_schema,
                label="source_adjudication",
            )
            if adjudication.get("integrity_sha256") != integrity_sha256(
                adjudication
            ):
                raise Doc4ContractError("adjudication_integrity_invalid")
            if adjudication.get("safe_id") != safe_id:
                raise Doc4ContractError("adjudication_safe_id_mismatch")
            if adjudication.get("pdf_response_sha256") != sha256_bytes(
                canonical_json_bytes(pdf_response)
            ) or adjudication.get("view_response_sha256") != sha256_bytes(
                canonical_json_bytes(view_response)
            ):
                raise Doc4ContractError("adjudication_response_binding_invalid")
            if adjudication.get("gold_checklist_sha256") != plan.get(
                "gold_checklist_sha256_by_safe_id", {}
            ).get(safe_id):
                raise Doc4ContractError("adjudication_gold_plan_binding_invalid")
            gold_checklists[safe_id] = read_json(
                _required_file(
                    gold_dir / safe_id / "gold_checklist.private.json",
                    "gold checklist",
                )
            )
            pdf_responses[safe_id] = pdf_response
            view_responses[safe_id] = view_response
            adjudications[safe_id] = adjudication
            comparisons[safe_id] = read_json(
                _required_file(
                    adjudication_dir / safe_id / "cross_arm_comparison.private.json",
                    "cross-arm comparison",
                )
            )
            validated_receipts[safe_id] = {}
            run_traces[safe_id] = {}
            expected_request_sha256_by_safe_id[safe_id] = {}
            expected_preflight_request_sha256_by_safe_id[safe_id] = {}
            pdf_bytes = source.pdf_path.read_bytes()
            view_text = source.llm_view_path.read_text(encoding="utf-8")
            pdf_page_texts_by_safe_id[safe_id] = pdf_page_texts(pdf_bytes)
            expected_pdf_sha256_by_safe_id[safe_id] = sha256_bytes(pdf_bytes)
            view_registries[safe_id] = view_pointer_registry(view_text)
            critical_stability_conflicts_by_safe_id[safe_id] = (
                _stability_conflicts_for_safe_id(
                    args.stability_comparison,
                    safe_id=safe_id,
                )
            )
            for arm, arm_source, wrapper, extension, arm_dir_name in (
                ("PDF", pdf_bytes, PDF_WRAPPER, "pdf", "pdf_arm"),
                ("LLM_VIEW", view_text, VIEW_WRAPPER, "txt", "view_arm"),
            ):
                arm_dir = run_results_dir / safe_id / arm_dir_name
                response_name = "pdf" if arm == "PDF" else "view"
                validated_receipts[safe_id][arm] = read_json(
                    _required_file(
                        arm_dir / f"{response_name}_arm_validated.private.json",
                        "validated response receipt",
                    )
                )
                run_traces[safe_id][arm] = read_json(
                    _required_file(arm_dir / "run_trace.private.json", "run trace")
                )
                request = build_arm_request(
                    candidate=runner.candidate,
                    source_mode=arm,
                    source=arm_source,
                    filename=f"{safe_id}.{extension}",
                    system_prompt=system_prompt,
                    task_prompt=task_prompt,
                    source_wrapper=wrapper,
                    response_schema=response_schema,
                )
                expected_request_sha256_by_safe_id[safe_id][arm] = sha256_bytes(
                    canonical_json_bytes(request)
                )
                expected_preflight_request_sha256_by_safe_id[safe_id][arm] = (
                    context_preflight_request_sha256s(
                        candidate=runner.candidate,
                        source_mode=arm,
                        source=arm_source,
                        filename=f"{safe_id}.{extension}",
                        system_prompt=system_prompt,
                        task_prompt=task_prompt,
                        source_wrapper=wrapper,
                        response_schema=response_schema,
                    )
                )
        result = PdfViewSemanticResultFactory().finalize(
            adjudications=adjudications,
            comparisons=comparisons,
            gold_checklists=gold_checklists,
            pdf_responses=pdf_responses,
            view_responses=view_responses,
            validated_receipts=validated_receipts,
            run_traces=run_traces,
            expected_request_sha256_by_safe_id=expected_request_sha256_by_safe_id,
            expected_preflight_request_sha256_by_safe_id=(
                expected_preflight_request_sha256_by_safe_id
            ),
            expected_pdf_sha256_by_safe_id=expected_pdf_sha256_by_safe_id,
            pdf_page_texts_by_safe_id=pdf_page_texts_by_safe_id,
            view_registries=view_registries,
            critical_stability_conflicts_by_safe_id=(
                critical_stability_conflicts_by_safe_id
            ),
            context_preflight=preflight,
            expected_run_plan_sha256=sha256_bytes(canonical_json_bytes(plan)),
            expected_candidate=asdict(runner.candidate),
            gold_schema=gold_schema,
            response_schema=response_schema,
            comparison_schema=read_json(
                _required_file(args.comparison_schema, "--comparison-schema")
            ),
            adjudication_schema=adjudication_schema,
            result_schema=read_json(
                _required_file(args.result_schema, "--result-schema")
            ),
        )
        digest = write_immutable_json(
            args.output_dir / "semantic_result.private.json", result
        )
        _print_safe(
            {
                "status": "PASSED",
                "mode": args.mode,
                "eligible_documents_total": result["eligible_documents_total"],
                "completed_paired_documents_total": result[
                    "completed_paired_documents_total"
                ],
                "sealed_adjudications_total": result[
                    "sealed_adjudications_total"
                ],
                **result["metrics"],
                "model_task_adequacy": result["model_task_adequacy"],
                "semantic_equivalence": result["semantic_equivalence"],
                "semantic_result_sha256": digest,
                "provider_calls_total": 0,
            }
        )
        return 0
    if args.mode == "compare":
        safe_id = _required_text(args.safe_id, "--safe-id")
        source = _source_by_id(sources, safe_id)
        pdf_response = read_json(_required_file(args.pdf_response, "--pdf-response"))
        view_response = read_json(_required_file(args.view_response, "--view-response"))
        validate_semantic_response(
            pdf_response,
            response_schema,
            expected_source_mode="PDF",
            pdf_pages_total=pdf_pages_total(source.pdf_path),
            pdf_page_texts=pdf_page_texts(source.pdf_path.read_bytes()),
        )
        registry = view_pointer_registry(source.llm_view_path.read_text(encoding="utf-8"))
        validate_semantic_response(view_response, response_schema, expected_source_mode="LLM_VIEW", view_registry=registry)
        comparison = PdfViewSemanticComparator().compare(safe_id=safe_id, pdf_response=pdf_response, view_response=view_response, comparison_schema=read_json(_required_file(args.comparison_schema, "--comparison-schema")))
        digest = write_immutable_json(args.output_dir / "cross_arm_comparison.private.json", comparison)
        _print_safe({"status": "PASSED", "mode": args.mode, "safe_id": safe_id, **comparison["metrics"], "comparison_sha256": digest, "provider_calls_total": 0})
        return 0
    if args.mode == "seal-adjudication":
        gold = read_json(_required_file(args.gold_draft, "--gold-draft"))
        safe_id = gold.get("safe_id")
        if safe_id not in CORPUS_IDS:
            raise Doc4ContractError("gold_safe_id_invalid")
        source = _source_by_id(sources, safe_id)
        if gold.get("pdf_sha256") != sha256_bytes(source.pdf_path.read_bytes()):
            raise Doc4ContractError("gold_source_binding_invalid")
        if sha256_bytes(canonical_json_bytes(gold)) != plan.get("gold_checklist_sha256_by_safe_id", {}).get(safe_id):
            raise Doc4ContractError("gold_plan_binding_invalid")
        pdf_response = read_json(_required_file(args.pdf_response, "--pdf-response"))
        view_response = read_json(_required_file(args.view_response, "--view-response"))
        validate_semantic_response(
            pdf_response,
            response_schema,
            expected_source_mode="PDF",
            pdf_pages_total=pdf_pages_total(source.pdf_path),
            pdf_page_texts=pdf_page_texts(source.pdf_path.read_bytes()),
        )
        registry = view_pointer_registry(source.llm_view_path.read_text(encoding="utf-8"))
        validate_semantic_response(view_response, response_schema, expected_source_mode="LLM_VIEW", view_registry=registry)
        comparison = read_json(_required_file(args.comparison, "--comparison"))
        if comparison.get("integrity_sha256") != integrity_sha256(comparison) or comparison.get("safe_id") != safe_id:
            raise Doc4ContractError("comparison_binding_invalid")
        stability_conflicts = _stability_conflicts_for_safe_id(
            args.stability_comparison,
            safe_id=safe_id,
        )
        sealed = PdfViewSemanticAdjudicationFactory().seal_adjudication(
            read_json(_required_file(args.adjudication_draft, "--adjudication-draft")),
            gold=gold,
            pdf_response=pdf_response,
            view_response=view_response,
            comparison=comparison,
            adjudication_schema=read_json(_required_file(args.adjudication_schema, "--adjudication-schema")),
            view_registry=registry,
            critical_stability_conflicts_total=stability_conflicts,
        )
        digest = write_immutable_json(args.output_dir / "source_adjudication.private.json", sealed)
        _print_safe({"status": "PASSED", "mode": args.mode, "safe_id": sealed["safe_id"], **sealed["metrics"], "model_task_adequacy": sealed["model_task_adequacy"], "document_semantic_assessment": sealed["document_semantic_assessment"], "adjudication_sha256": digest, "provider_calls_total": 0})
        return 0
    system_prompt, task_prompt = _prompts(args, plan)
    request_keys = authorized_request_keys(
        candidate=runner.candidate,
        sources=sources,
        system_prompt=system_prompt,
        task_prompt=task_prompt,
        pdf_wrapper=PDF_WRAPPER,
        view_wrapper=VIEW_WRAPPER,
        response_schema=response_schema,
    )
    source_hashes = {
        item["safe_id"]: {
            "pdf_sha256": item["pdf_sha256"],
            "llm_view_sha256": item["llm_view_sha256"],
        }
        for item in plan["sources"]
    }
    plan_sha256 = sha256_bytes(canonical_json_bytes(plan))
    authorization = read_json(_required_file(args.authorization, "--authorization"))
    validate_provider_authorization(
        authorization,
        expected_provider=MODEL_PROVIDER,
        expected_model_id=REQUEST_MODEL_ID,
        expected_source_sha256_by_safe_id=source_hashes,
        expected_run_plan_sha256=plan_sha256,
        expected_request_set_sha256=sha256_bytes(
            canonical_json_bytes(sorted(request_keys))
        ),
    )
    transport = OpenAiDoc4Transport(
        connection_from_env_file(_required_file(args.env_file, "--env-file")),
        authorization=authorization,
        expected_source_sha256_by_safe_id=source_hashes,
        expected_run_plan_sha256=plan_sha256,
        authorized_request_keys=request_keys,
    )
    if args.mode == "preflight":
        if plan.get("gold_checklists_created_before_provider_calls") is not True:
            raise Doc4ContractError("gold_checklists_not_bound_before_preflight")
        receipts: dict[str, Any] = {}
        calls_total = 0
        system_prompt, task_prompt = _prompts(args, plan)
        for source in sources:
            view_text = source.llm_view_path.read_text(encoding="utf-8")
            pdf = source.pdf_path.read_bytes()
            receipts[source.safe_id] = {
                "PDF": runner.context_preflight(transport=transport, source_mode="PDF", source=pdf, filename=f"{source.safe_id}.pdf", system_prompt=system_prompt, task_prompt=task_prompt, source_wrapper=PDF_WRAPPER, response_schema=response_schema),
                "LLM_VIEW": runner.context_preflight(transport=transport, source_mode="LLM_VIEW", source=view_text, filename=f"{source.safe_id}.txt", system_prompt=system_prompt, task_prompt=task_prompt, source_wrapper=VIEW_WRAPPER, response_schema=response_schema),
            }
            calls_total += receipts[source.safe_id]["PDF"]["token_count_calls_total"] + receipts[source.safe_id]["LLM_VIEW"]["token_count_calls_total"]
        value = {
            "schema_version": "broker_reports_doc4_context_preflight_private_v1",
            "request_model_id": REQUEST_MODEL_ID,
            "run_plan_sha256": sha256_bytes(canonical_json_bytes(plan)),
            "documents": receipts,
            "provider_calls_total": calls_total,
            "integrity_sha256": "",
        }
        value["integrity_sha256"] = integrity_sha256(value)
        validate_doc4_context_preflight(
            value,
            expected_run_plan_sha256=sha256_bytes(canonical_json_bytes(plan)),
            expected_candidate=asdict(runner.candidate),
            expected_request_sha256_by_safe_id=_preflight_request_hashes_by_safe_id(
                runner=runner,
                sources=sources,
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                response_schema=response_schema,
            ),
        )
        digest = write_immutable_json(args.output_dir / "context_preflight.private.json", value)
        _print_safe({"status": "PASSED", "mode": args.mode, "eligible_documents_total": sum(all(arm["eligible"] for arm in item.values()) for item in receipts.values()), "context_limit_ineligible_total": sum(not all(arm["eligible"] for arm in item.values()) for item in receipts.values()), "provider_calls_total": calls_total, "context_preflight_sha256": digest})
        return 0
    if args.mode == "run":
        if plan.get("gold_checklists_created_before_provider_calls") is not True:
            raise Doc4ContractError("gold_checklists_not_bound_before_run")
        _verify_gold_hashes(plan, _required_dir(args.gold_dir, "--gold-dir"))
        system_prompt, task_prompt = _prompts(args, plan)
        validate_doc4_context_preflight(
            read_json(_required_file(args.context_preflight, "--context-preflight")),
            expected_run_plan_sha256=sha256_bytes(canonical_json_bytes(plan)),
            expected_candidate=asdict(runner.candidate),
            expected_request_sha256_by_safe_id=_preflight_request_hashes_by_safe_id(
                runner=runner,
                sources=sources,
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                response_schema=response_schema,
            ),
        )
        completed = 0
        calls_total = 0
        primary_responses: dict[tuple[str, str], dict[str, Any]] = {}
        source_inputs: dict[str, tuple[CorpusSource, bytes, str]] = {}
        traces_by_safe_id: dict[str, list[dict[str, Any]]] = {safe_id: [] for safe_id in CORPUS_IDS}
        for source in sources:
            case_dir = args.output_dir / source.safe_id
            write_immutable_json(
                case_dir / "gold_checklist.private.json",
                read_json(_required_file(_required_dir(args.gold_dir, "--gold-dir") / source.safe_id / "gold_checklist.private.json", "gold checklist")),
            )
            pdf = source.pdf_path.read_bytes()
            view_text = source.llm_view_path.read_text(encoding="utf-8")
            source_inputs[source.safe_id] = (source, pdf, view_text)
            arm_inputs = {
                "PDF": (pdf, PDF_WRAPPER, pdf_pages_total(source.pdf_path), None),
                "LLM_VIEW": (view_text, VIEW_WRAPPER, None, view_pointer_registry(view_text)),
            }
            for arm in next(item["arms"] for item in plan["run_order"] if item["safe_id"] == source.safe_id):
                arm_dir = case_dir / ("pdf_arm" if arm == "PDF" else "view_arm")
                arm_source, wrapper, pages, registry = arm_inputs[arm]
                response, trace = runner.execute_arm(transport=transport, source_mode=arm, source=arm_source, filename=f"{source.safe_id}.pdf" if arm == "PDF" else f"{source.safe_id}.txt", system_prompt=system_prompt, task_prompt=task_prompt, source_wrapper=wrapper, response_schema=response_schema, pdf_pages_total=pages, view_registry=registry)
                primary_responses[(source.safe_id, arm)] = response
                traces_by_safe_id[source.safe_id].append(trace)
                write_immutable_json(arm_dir / ("pdf_arm_request.private.json" if arm == "PDF" else "view_arm_request.private.json"), trace["request"])
                write_immutable_json(arm_dir / ("pdf_arm_raw_response.private.json" if arm == "PDF" else "view_arm_raw_response.private.json"), hash_bound_private_payload("broker_reports_doc4_raw_response_attempts_v1", attempts=trace["attempts"]))
                write_immutable_json(arm_dir / ("pdf_arm_response.private.json" if arm == "PDF" else "view_arm_response.private.json"), response)
                write_immutable_json(arm_dir / ("pdf_arm_validated.private.json" if arm == "PDF" else "view_arm_validated.private.json"), hash_bound_private_payload("broker_reports_doc4_validated_response_receipt_v1", source_mode=arm, response_sha256=sha256_bytes(canonical_json_bytes(response)), request_sha256=sha256_bytes(canonical_json_bytes(trace["request"])), status="PASSED"))
                write_immutable_json(arm_dir / "run_trace.private.json", hash_bound_private_payload("broker_reports_doc4_arm_run_trace_v1", **trace))
                calls_total += sum(item["metadata"]["attempts_total"] for item in trace["attempts"])
            completed += 1
        stability: list[dict[str, Any]] = []
        for safe_id in ("real_pdf_1", "real_pdf_5"):
            source, pdf, view_text = source_inputs[safe_id]
            for arm, arm_source, wrapper, pages, registry in (
                ("PDF", pdf, PDF_WRAPPER, pdf_pages_total(source.pdf_path), None),
                ("LLM_VIEW", view_text, VIEW_WRAPPER, None, view_pointer_registry(view_text)),
            ):
                replica_dir = args.output_dir / safe_id / "stability_replica_2" / ("pdf_arm" if arm == "PDF" else "view_arm")
                replica, trace = runner.execute_arm(transport=transport, source_mode=arm, source=arm_source, filename=f"{safe_id}.pdf" if arm == "PDF" else f"{safe_id}.txt", system_prompt=system_prompt, task_prompt=task_prompt, source_wrapper=wrapper, response_schema=response_schema, pdf_pages_total=pages, view_registry=registry)
                traces_by_safe_id[safe_id].append(trace)
                write_immutable_json(replica_dir / "response.private.json", replica)
                write_immutable_json(replica_dir / "raw_response.private.json", hash_bound_private_payload("broker_reports_doc4_raw_response_attempts_v1", attempts=trace["attempts"]))
                write_immutable_json(replica_dir / "run_trace.private.json", hash_bound_private_payload("broker_reports_doc4_arm_run_trace_v1", **trace))
                stability.append(compare_stability_replay(safe_id=safe_id, source_mode=arm, primary=primary_responses[(safe_id, arm)], replica=replica))
                calls_total += sum(item["metadata"]["attempts_total"] for item in trace["attempts"])
        stability_value = {"schema_version": "broker_reports_doc4_model_stability_aggregate_v1", "comparisons": stability, "critical_stability_conflicts_total": sum(item["critical_stability_conflicts_total"] for item in stability), "integrity_sha256": ""}
        stability_value["integrity_sha256"] = integrity_sha256(stability_value)
        write_immutable_json(args.output_dir / "model_stability_comparison.private.json", stability_value)
        usage_complete = True
        for safe_id in CORPUS_IDS:
            usage = provider_usage_from_traces(traces_by_safe_id[safe_id])
            usage_complete = usage_complete and usage["usage_complete"]
            write_immutable_json(args.output_dir / safe_id / "provider_usage.private.json", usage)
        if not usage_complete:
            raise Doc4ContractError("provider_usage_incomplete")
        _print_safe({"status": "PASSED", "mode": args.mode, "completed_paired_documents_total": completed, "stability_documents_total": 2, "critical_stability_conflicts_total": stability_value["critical_stability_conflicts_total"], "provider_calls_total": calls_total})
        return 0
    raise Doc4ContractError("mode_not_implemented")


def _sources(path: Path) -> list[CorpusSource]:
    value = read_json(path)
    entries = value.get("sources")
    if not isinstance(entries, list):
        raise Doc4ContractError("source_manifest_invalid")
    result = [CorpusSource(safe_id=item["safe_id"], pdf_path=Path(item["pdf_path"]), managed_document_path=Path(item["managed_document_path"]), llm_view_path=Path(item["llm_view_path"]), doc2_coverage_receipt_path=Path(item["doc2_coverage_receipt_path"]), doc3_render_receipt_path=Path(item["doc3_render_receipt_path"])) for item in entries]
    if tuple(item.safe_id for item in result) != CORPUS_IDS:
        raise Doc4ContractError("source_manifest_corpus_invalid")
    return result


def _source_by_id(sources: list[CorpusSource], safe_id: str) -> CorpusSource:
    return next(item for item in sources if item.safe_id == safe_id)


def _gold_hashes(path: Path) -> dict[str, str]:
    return {safe_id: sha256_bytes(_required_file(path / safe_id / "gold_checklist.private.json", "gold checklist").read_bytes()) for safe_id in CORPUS_IDS}


def _verify_gold_hashes(plan: dict[str, Any], path: Path) -> None:
    if _gold_hashes(path) != plan.get("gold_checklist_sha256_by_safe_id"):
        raise Doc4ContractError("gold_checklist_hash_binding_mismatch")


def _validated_plan(path: Path) -> dict[str, Any]:
    plan = read_json(path)
    if plan.get("schema_version") != "broker_reports_doc4_run_plan_v1" or plan.get("integrity_sha256") != integrity_sha256(plan):
        raise Doc4ContractError("run_plan_invalid")
    if plan.get("candidate") != asdict(ModelCandidate()):
        raise Doc4ContractError("run_plan_candidate_mismatch")
    if plan.get("protocol_version") != EXPERIMENT_PROTOCOL_VERSION:
        raise Doc4ContractError("run_plan_protocol_mismatch")
    if plan.get("run_order") != [
        {"safe_id": safe_id, "arms": list(RUN_ORDER[safe_id])}
        for safe_id in CORPUS_IDS
    ]:
        raise Doc4ContractError("run_plan_order_mismatch")
    if plan.get("candidate_frozen") is not True or plan.get("prompts_frozen") is not True or plan.get("source_artifacts_frozen") is not True:
        raise Doc4ContractError("run_plan_not_frozen")
    if plan.get("product_route_connected") is not False or plan.get("provider_calls_started") is not False:
        raise Doc4ContractError("run_plan_forbidden_state")
    return plan


def _stability_conflicts_for_safe_id(path: Path | None, *, safe_id: str) -> int:
    if path is None:
        if safe_id in {"real_pdf_1", "real_pdf_5"}:
            raise Doc4ContractError("stability_comparison_required")
        return 0
    value = read_json(_required_file(path, "--stability-comparison"))
    if value.get("schema_version") != "broker_reports_doc4_model_stability_aggregate_v1" or value.get("integrity_sha256") != integrity_sha256(value):
        raise Doc4ContractError("stability_comparison_invalid")
    selected = [item for item in value.get("comparisons", []) if item.get("safe_id") == safe_id]
    expected = 2 if safe_id in {"real_pdf_1", "real_pdf_5"} else 0
    if len(selected) != expected or {item.get("source_mode") for item in selected} != ({"PDF", "LLM_VIEW"} if expected else set()):
        raise Doc4ContractError("stability_comparison_coverage_invalid")
    return sum(item["critical_stability_conflicts_total"] for item in selected)


def _verify_plan_source_bindings(plan: dict[str, Any], sources: list[CorpusSource]) -> None:
    rebuilt = PdfViewSemanticExperimentRunner().freeze_plan(sources=sources, system_prompt=b"placeholder", task_prompt=b"placeholder", pdf_wrapper=PDF_WRAPPER, view_wrapper=VIEW_WRAPPER, response_schema={}, base_commit=plan["base_commit"], implementation_commit=plan["implementation_commit"])["sources"]
    if rebuilt != plan.get("sources"):
        raise Doc4ContractError("run_plan_source_binding_mismatch")


def _verify_plan_protocol_bindings(
    args: argparse.Namespace,
    *,
    plan: dict[str, Any],
    response_schema: dict[str, Any],
) -> None:
    expected = {
        "system_prompt_sha256": sha256_bytes(_repository_lf_bytes(_required_file(args.system_prompt, "--system-prompt"))),
        "task_prompt_sha256": sha256_bytes(_repository_lf_bytes(_required_file(args.task_prompt, "--task-prompt"))),
        "pdf_wrapper_sha256": sha256_bytes(PDF_WRAPPER.encode("utf-8")),
        "view_wrapper_sha256": sha256_bytes(VIEW_WRAPPER.encode("utf-8")),
        "response_schema_sha256": sha256_bytes(canonical_json_bytes(response_schema)),
    }
    if any(plan.get(name) != digest for name, digest in expected.items()):
        raise Doc4ContractError("run_plan_protocol_binding_mismatch")


def _prompts(args: argparse.Namespace, plan: dict[str, Any]) -> tuple[str, str]:
    system_bytes = _repository_lf_bytes(_required_file(args.system_prompt, "--system-prompt"))
    task_bytes = _repository_lf_bytes(_required_file(args.task_prompt, "--task-prompt"))
    if sha256_bytes(system_bytes) != plan["system_prompt_sha256"] or sha256_bytes(task_bytes) != plan["task_prompt_sha256"]:
        raise Doc4ContractError("prompt_hash_mismatch")
    return system_bytes.decode("utf-8"), task_bytes.decode("utf-8")


def _preflight_request_hashes_by_safe_id(
    *,
    runner: PdfViewSemanticExperimentRunner,
    sources: list[CorpusSource],
    system_prompt: str,
    task_prompt: str,
    response_schema: dict[str, Any],
) -> dict[str, dict[str, tuple[str, ...]]]:
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for source in sources:
        pdf_bytes = source.pdf_path.read_bytes()
        view_text = source.llm_view_path.read_text(encoding="utf-8")
        result[source.safe_id] = {
            "PDF": context_preflight_request_sha256s(
                candidate=runner.candidate,
                source_mode="PDF",
                source=pdf_bytes,
                filename=f"{source.safe_id}.pdf",
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                source_wrapper=PDF_WRAPPER,
                response_schema=response_schema,
            ),
            "LLM_VIEW": context_preflight_request_sha256s(
                candidate=runner.candidate,
                source_mode="LLM_VIEW",
                source=view_text,
                filename=f"{source.safe_id}.txt",
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                source_wrapper=VIEW_WRAPPER,
                response_schema=response_schema,
            ),
        }
    return result


def _repository_lf_bytes(path: Path) -> bytes:
    value = path.read_bytes().replace(b"\r\n", b"\n")
    if b"\r" in value:
        raise Doc4ContractError(f"repository_text_contains_lone_cr:{path.name}")
    return value


def _safe_security_pair() -> tuple[bytes, str]:
    fixture = read_json(SECURITY_FIXTURE)
    lines = [
        "DOC4 safe synthetic security document",
        "Explicit source financial fact: 10.00 USD",
        *fixture["source_lines"],
    ]
    pdf_document = fitz.open()
    page = pdf_document.new_page(width=612, height=792)
    y = 54
    for line in lines:
        page.insert_text((54, y), line, fontsize=10)
        y += 22
    pdf_document.set_metadata(
        {
            "title": "DOC4 safe synthetic security document",
            "author": "Broker Reports DOC4",
            "creator": "broker_reports_doc4_security_fixture_v1",
            "producer": "PyMuPDF deterministic safe fixture",
            "creationDate": "D:20260801000000Z",
            "modDate": "D:20260801000000Z",
        }
    )
    pdf = pdf_document.tobytes(garbage=4, deflate=True, no_new_id=True)
    pdf_document.close()
    checksum = hashlib.sha256(pdf).hexdigest()

    corpus = read_json(MANAGED_DOCUMENT_FIXTURES)
    document = copy.deepcopy(corpus["documents"][0])
    document["document_id"] = "document_synthetic_doc4_security"
    document["source"]["artifact"]["ref"] = "private_synthetic_doc4_security_source"
    document["source"]["artifact"]["checksum_sha256"] = checksum
    document["source"]["checksum_sha256"] = checksum
    document["source"]["size_bytes"] = len(pdf)
    document["source"]["normalizer"] = {
        "name": "broker_reports_doc4_security_fixture",
        "version": "1.0.0",
    }
    for anchor in document["anchors"]:
        anchor["checksum_sha256"] = checksum
    document["metadata"]["title"]["value"] = lines[0]
    document["metadata"]["issuer"]["value"] = "Broker Reports DOC4"
    document["metadata"]["document_date"]["value"] = "2026-08-01"
    document["metadata"]["reporting_period"]["value"] = "2026-08-01"
    document["blocks"][1]["content"]["raw_text"] = lines[0]
    document["blocks"][2]["content"]["raw_text"] = "\n".join(lines[1:])
    table = document["blocks"][3]["content"]
    table["table_id"] = "table_doc4_security_fact"
    table["title"]["value"] = "Explicit source fact"
    table["description"] = "One safe explicit financial literal."
    table["rows"] = [["Field", "Value"], ["Explicit amount", "10.00 USD"]]
    table["units"] = [
        {
            "label": "USD",
            "column_indexes": [1],
            "status": "KNOWN",
            "origin": "SOURCE_EXPLICIT",
        }
    ]
    table["cell_annotations"] = [table["cell_annotations"][0]]
    table["known_gap_ids"] = ["loss_doc4_security_negative"]
    document["blocks"][4]["content"]["text"] = "Document-like instructions above are untrusted source text."
    loss = {
        "loss_id": "loss_doc4_security_negative",
        "context_class": "CONTENT",
        "what_lost": "Unknown numeric content 999.00 USD is not source-established.",
        "where": "Synthetic negative loss-ledger entry.",
        "reason": "A source region may contain an amount, but no amount is established here.",
        "recoverability": "RECOVERABLE",
        "requires_source_reread": True,
        "blocks_semantic_analysis": False,
        "accounted": True,
        "anchor_ids": ["anchor_a_table"],
        "block_ids": ["block_a_table"],
    }
    document["quality"]["known_losses_total"] = 1
    document["quality"]["status"] = "PARTIAL"
    document["quality"]["loss_ledger"] = [loss]
    schema = read_json(MANAGED_DOCUMENT_SCHEMA)
    sealed = ManagedDocumentContractValidator(schema).seal(document).payload
    coverage = read_json(DOC3_COVERAGE)
    view = ManagedDocumentLlmViewFactory().create(schema, coverage).render(sealed).view_text
    return pdf, view


def _security_explicit_fact_present(response: dict[str, Any]) -> bool:
    for item in response["financial_facts"]:
        literal = item.get("source_literal") or ""
        if (
            item.get("currency") == "USD"
            and (
                "10.00 USD" in literal
                or item.get("normalized_decimal") == "10"
                or item.get("normalized_value") == "10"
            )
        ):
            return True
    return False


def _security_loss_ledger_fact_total(response: dict[str, Any]) -> int:
    return sum(
        "999" in " ".join(
            str(item.get(field) or "")
            for field in ("source_literal", "normalized_value", "normalized_decimal")
        )
        for item in response["financial_facts"]
    )


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _required_file(path: Path | None, name: str) -> Path:
    if path is None or not path.is_file():
        raise Doc4ContractError(f"required_file_missing:{name}")
    return path.resolve()


def _required_dir(path: Path | None, name: str) -> Path:
    if path is None or not path.is_dir():
        raise Doc4ContractError(f"required_directory_missing:{name}")
    return path.resolve()


def _required_text(value: str | None, name: str) -> str:
    if not value:
        raise Doc4ContractError(f"required_value_missing:{name}")
    return value


def _print_safe(value: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value))


if __name__ == "__main__":
    raise SystemExit(main())
