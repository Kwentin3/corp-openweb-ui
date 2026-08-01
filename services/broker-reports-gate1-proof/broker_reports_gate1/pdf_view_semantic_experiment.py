from __future__ import annotations

import base64
import copy
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from jsonschema import Draft202012Validator
from pypdf import PdfReader

from .managed_document_contracts import ManagedDocumentContractValidator
from .managed_document_coverage import canonical_sha256 as coverage_integrity_sha256
from .managed_document_llm_view import ManagedDocumentLlmViewFactory
from .managed_document_llm_view_audit import ManagedDocumentLlmViewAuditor
from .pdf_view_semantic_contracts import (
    CORPUS_IDS,
    EXPERIMENT_PROTOCOL_VERSION,
    EXPERIMENT_RUN_PLAN_SCHEMA_VERSION,
    RUN_ORDER,
    Doc4ContractError,
    ViewPointerRegistry,
    canonical_json_bytes,
    extract_structured_response,
    integrity_sha256,
    read_json,
    sha256_bytes,
    validate_provider_authorization,
    validate_semantic_response,
)


EXPERIMENT_RUNNER_VERSION = "broker_reports_doc4_pdf_view_semantic_experiment_v1"
SEMANTIC_VALIDATOR_OWNER_VERSION = "broker_reports_doc4_semantic_validator_v1"
MODEL_PROVIDER = "openai"
REQUEST_MODEL_ID = "gpt-5.4-2026-03-05"
MODEL_CONTEXT_WINDOW = 1_050_000
MODEL_MAX_OUTPUT_TOKENS = 128_000
RESERVED_MAX_OUTPUT_TOKENS = 65_536
SAFETY_MARGIN_TOKENS = max(8_192, MODEL_CONTEXT_WINDOW // 10)
PDF_MAX_BYTES = 50 * 1024 * 1024 - 1
MAX_PROVIDER_RESPONSE_BYTES = 16 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 900
TRANSPORT_RETRIES_MAX = 2
SCHEMA_RETRIES_MAX = 1
PDF_DETAIL = "high"
REASONING_EFFORT = "none"
TEMPERATURE = 0
TOP_P = 1
FACTORY_REQUIRED = (
    "PdfViewSemanticExperimentFactory.create is the only DOC4 runner entrypoint"
)
FORBIDDEN = (
    "CLI and experiment control paths must not instantiate "
    "PdfViewSemanticExperimentRunner directly"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MANAGED_DOCUMENT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
MANAGED_DOCUMENT_COVERAGE_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT_COVERAGE.v1.schema.json"
)
LLM_VIEW_RECEIPT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_LLM_DOCUMENT_VIEW_RECEIPT.v1.schema.json"
)
DOC1_TO_DOC3_FIELD_COVERAGE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC1_TO_DOC3_VIEW_COVERAGE.v1.json"
)


@dataclass(frozen=True)
class ModelCandidate:
    provider: str = MODEL_PROVIDER
    request_model_id: str = REQUEST_MODEL_ID
    resolved_model_version_or_fingerprint: str = REQUEST_MODEL_ID
    model_identity_immutable: bool = True
    api_version: str = "OpenAI Responses API v1"
    sdk_version: str = "none; requests==2.32.5 direct HTTPS"
    context_window: int = MODEL_CONTEXT_WINDOW
    maximum_output_tokens: int = MODEL_MAX_OUTPUT_TOKENS
    reserved_max_output_tokens: int = RESERVED_MAX_OUTPUT_TOKENS
    safety_margin_tokens: int = SAFETY_MARGIN_TOKENS
    sampling_parameters: str = "omitted_provider_defaults"
    reasoning_effort: str = "omitted_provider_default_none"
    structured_output_mode: str = "responses.text.format.json_schema.strict"
    pdf_input_mode: str = "responses.input_file.inline_base64.application_pdf.detail_high"
    token_counting_mode: str = "responses.input_tokens.exact_full_request_once"
    tools_enabled: bool = False
    web_enabled: bool = False
    retrieval_enabled: bool = False
    grounding_enabled: bool = False
    response_storage_policy: str = "store_parameter_omitted_provider_default"


@dataclass(frozen=True)
class CorpusSource:
    safe_id: str
    pdf_path: Path
    managed_document_path: Path
    llm_view_path: Path
    doc2_coverage_receipt_path: Path
    doc3_render_receipt_path: Path


class ProviderHttpError(Doc4ContractError):
    """Safe exception text plus a private provider failure receipt."""

    def __init__(self, *, http_status: int, private_receipt: dict[str, Any]) -> None:
        super().__init__(f"provider_http_error:{http_status}")
        self.http_status = http_status
        self.private_receipt = copy.deepcopy(private_receipt)


@dataclass(frozen=True)
class ProviderConnection:
    base_url: str
    api_key: str

    def __repr__(self) -> str:
        return f"ProviderConnection(base_url={self.base_url!r}, api_key=<redacted>)"


class OpenAiDoc4Transport:
    """One offline DOC4 transport owner, unreachable from product entrypoints."""

    def __init__(
        self,
        connection: ProviderConnection,
        *,
        authorization: dict[str, Any],
        expected_source_sha256_by_safe_id: dict[str, dict[str, str]],
        expected_run_plan_sha256: str,
        authorized_request_keys: frozenset[str],
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        if not authorized_request_keys or any(
            not re.fullmatch(r"/responses(?:/input_tokens)?:[0-9a-f]{64}", item)
            for item in authorized_request_keys
        ):
            raise Doc4ContractError("provider_authorized_request_set_invalid")
        request_set_sha256 = sha256_bytes(
            canonical_json_bytes(sorted(authorized_request_keys))
        )
        validate_provider_authorization(
            authorization,
            expected_provider=MODEL_PROVIDER,
            expected_model_id=REQUEST_MODEL_ID,
            expected_source_sha256_by_safe_id=expected_source_sha256_by_safe_id,
            expected_run_plan_sha256=expected_run_plan_sha256,
            expected_request_set_sha256=request_set_sha256,
        )
        _validate_openai_base_url(connection.base_url)
        if not connection.api_key:
            raise Doc4ContractError("provider_api_key_missing")
        self.connection = connection
        self.timeout_seconds = timeout_seconds
        self.authorized_request_keys = authorized_request_keys

    def count_input_tokens(self, request_body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        body = _token_count_body(request_body)
        payload, metadata = self._post("/responses/input_tokens", body)
        input_tokens = payload.get("input_tokens")
        if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) or input_tokens < 0:
            raise Doc4ContractError("provider_token_count_missing")
        metadata["raw_payload"] = payload
        metadata["raw_payload_sha256"] = sha256_bytes(
            canonical_json_bytes(payload)
        )
        return input_tokens, metadata

    def submit(self, request_body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        payload, metadata = self._post("/responses", request_body)
        metadata.update(_usage_metadata(payload))
        metadata["resolved_model"] = payload.get("model")
        metadata["raw_payload_sha256"] = sha256_bytes(
            canonical_json_bytes(payload)
        )
        if payload.get("model") != REQUEST_MODEL_ID:
            raise Doc4ContractError("provider_resolved_model_mismatch")
        response = extract_structured_response(payload)
        return response, {**metadata, "raw_payload": payload}

    def _post(self, suffix: str, body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        encoded = canonical_json_bytes(body)
        request_sha256 = sha256_bytes(encoded)
        if f"{suffix}:{request_sha256}" not in self.authorized_request_keys:
            raise Doc4ContractError("provider_outbound_request_not_authorized")
        _assert_outbound_provider_policy(body, suffix=suffix)
        last_error: Exception | None = None
        for attempt in range(TRANSPORT_RETRIES_MAX + 1):
            started = time.perf_counter()
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.post(
                        self.connection.base_url.rstrip("/") + suffix,
                        headers={
                            "Authorization": f"Bearer {self.connection.api_key}",
                            "Content-Type": "application/json",
                        },
                        data=encoded,
                        timeout=self.timeout_seconds,
                        allow_redirects=False,
                    )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < TRANSPORT_RETRIES_MAX:
                    continue
                raise Doc4ContractError("provider_transport_failed") from exc
            duration = time.perf_counter() - started
            if response.is_redirect:
                raise Doc4ContractError("provider_redirect_forbidden")
            if len(response.content) > MAX_PROVIDER_RESPONSE_BYTES:
                raise Doc4ContractError("provider_response_bytes_exceeded")
            if response.status_code in {429, 500, 502, 503, 504} and attempt < TRANSPORT_RETRIES_MAX:
                continue
            if not response.ok:
                raise ProviderHttpError(
                    http_status=response.status_code,
                    private_receipt={
                        "schema_version": "broker_reports_doc4_provider_http_failure_private_v1",
                        "endpoint": suffix,
                        "http_status": response.status_code,
                        "attempts_total": attempt + 1,
                        "transport_retries_total": attempt,
                        "request_sha256": request_sha256,
                        "response_sha256": sha256_bytes(response.content),
                        "response_bytes": len(response.content),
                        "response_body_base64": base64.b64encode(
                            response.content
                        ).decode("ascii"),
                        "duration_seconds": round(duration, 3),
                        "provider_calls_total": attempt + 1,
                        "integrity_sha256": "",
                    },
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise Doc4ContractError("provider_response_not_json") from exc
            if not isinstance(payload, dict):
                raise Doc4ContractError("provider_response_root_invalid")
            return payload, {
                "http_status": response.status_code,
                "attempts_total": attempt + 1,
                "transport_retries_total": attempt,
                "http_session_scope": "ONE_REQUEST_NO_REUSE",
                "request_sha256": request_sha256,
                "response_sha256": sha256_bytes(response.content),
                "response_bytes": len(response.content),
                "response_body_base64": base64.b64encode(
                    response.content
                ).decode("ascii"),
                "duration_seconds": round(duration, 3),
            }
        raise Doc4ContractError("provider_transport_failed") from last_error


class PdfViewSemanticExperimentFactory:
    """Canonical inactive DOC4 runner construction boundary."""

    @staticmethod
    def create() -> "PdfViewSemanticExperimentRunner":
        return PdfViewSemanticExperimentRunner()


class PdfViewSemanticExperimentRunner:
    """The sole DOC4 experiment coordinator; no product entrypoint imports it."""

    def __init__(self, candidate: ModelCandidate | None = None) -> None:
        self.candidate = candidate or ModelCandidate()

    def freeze_plan(
        self,
        *,
        sources: list[CorpusSource],
        system_prompt: bytes,
        task_prompt: bytes,
        pdf_wrapper: str,
        view_wrapper: str,
        response_schema: dict[str, Any],
        base_commit: str,
        implementation_commit: str,
        gold_checklist_sha256_by_safe_id: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if tuple(item.safe_id for item in sources) != CORPUS_IDS:
            raise Doc4ContractError("corpus_order_or_identity_invalid")
        bindings = [_source_binding(item) for item in sources]
        gold_hashes = gold_checklist_sha256_by_safe_id or {}
        if gold_hashes and set(gold_hashes) != set(CORPUS_IDS):
            raise Doc4ContractError("gold_checklist_binding_incomplete")
        plan = {
            "schema_version": EXPERIMENT_RUN_PLAN_SCHEMA_VERSION,
            "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
            "runner_version": EXPERIMENT_RUNNER_VERSION,
            "semantic_validator_owner": SEMANTIC_VALIDATOR_OWNER_VERSION,
            "base_commit": base_commit,
            "implementation_commit": implementation_commit,
            "candidate": asdict(self.candidate),
            "system_prompt_sha256": sha256_bytes(system_prompt),
            "task_prompt_sha256": sha256_bytes(task_prompt),
            "pdf_wrapper_sha256": sha256_bytes(pdf_wrapper.encode("utf-8")),
            "view_wrapper_sha256": sha256_bytes(view_wrapper.encode("utf-8")),
            "response_schema_sha256": sha256_bytes(canonical_json_bytes(response_schema)),
            "run_order": [
                {"safe_id": safe_id, "arms": list(RUN_ORDER[safe_id])}
                for safe_id in CORPUS_IDS
            ],
            "sources": bindings,
            "gold_checklist_sha256_by_safe_id": {
                safe_id: gold_hashes[safe_id] for safe_id in CORPUS_IDS
            } if gold_hashes else {},
            "gold_checklists_created_before_provider_calls": bool(gold_hashes),
            "provider_calls_started": False,
            "prompts_frozen": True,
            "candidate_frozen": True,
            "source_artifacts_frozen": True,
            "product_route_connected": False,
            "integrity_sha256": "",
        }
        plan["integrity_sha256"] = integrity_sha256(plan)
        return plan

    def context_preflight(
        self,
        *,
        transport: OpenAiDoc4Transport,
        source_mode: str,
        source: bytes | str,
        filename: str,
        system_prompt: str,
        task_prompt: str,
        source_wrapper: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        stages = _context_count_stages(
            candidate=self.candidate,
            source_mode=source_mode,
            source=source,
            filename=filename,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            source_wrapper=source_wrapper,
            response_schema=response_schema,
        )
        if len(stages) != 1:
            raise Doc4ContractError("provider_token_count_stage_count_invalid")
        body = stages[0]
        full_total, metadata = transport.count_input_tokens(body)
        expected_request_sha256 = sha256_bytes(
            canonical_json_bytes(_token_count_body(body))
        )
        if metadata.get("request_sha256") != expected_request_sha256:
            raise Doc4ContractError("provider_token_count_request_binding_invalid")
        raw_payload = metadata.get("raw_payload")
        if (
            not isinstance(raw_payload, dict)
            or metadata.get("raw_payload_sha256")
            != sha256_bytes(canonical_json_bytes(raw_payload))
            or raw_payload.get("input_tokens") != full_total
        ):
            raise Doc4ContractError(
                "provider_token_count_response_binding_invalid"
            )
        result = {
            "counting_mode": self.candidate.token_counting_mode,
            "total_input_tokens": full_total,
            "reserved_output_tokens": self.candidate.reserved_max_output_tokens,
            "safety_margin_tokens": self.candidate.safety_margin_tokens,
            "context_window": self.candidate.context_window,
            "eligible": (
                full_total
                + self.candidate.reserved_max_output_tokens
                + self.candidate.safety_margin_tokens
                <= self.candidate.context_window
            ),
            "reason": "FIT" if (
                full_total
                + self.candidate.reserved_max_output_tokens
                + self.candidate.safety_margin_tokens
                <= self.candidate.context_window
            ) else "NOT_ELIGIBLE_CONTEXT_LIMIT",
            "token_count_calls_total": 1,
            "token_count_call_receipts": [metadata],
        }
        return result

    def execute_arm(
        self,
        *,
        transport: OpenAiDoc4Transport,
        source_mode: str,
        source: bytes | str,
        filename: str,
        system_prompt: str,
        task_prompt: str,
        source_wrapper: str,
        response_schema: dict[str, Any],
        pdf_pages_total: int | None = None,
        view_registry: ViewPointerRegistry | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        request_body = build_arm_request(
            candidate=self.candidate,
            source_mode=source_mode,
            source=source,
            filename=filename,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            source_wrapper=source_wrapper,
            response_schema=response_schema,
        )
        attempts: list[dict[str, Any]] = []
        first_error: str | None = None
        page_texts = pdf_page_texts(source) if source_mode == "PDF" else None
        for schema_attempt in range(SCHEMA_RETRIES_MAX + 1):
            response, metadata = transport.submit(copy.deepcopy(request_body))
            raw_payload = metadata.pop("raw_payload")
            try:
                validate_semantic_response(
                    response,
                    response_schema,
                    expected_source_mode=source_mode,
                    pdf_pages_total=pdf_pages_total,
                    pdf_page_texts=page_texts,
                    view_registry=view_registry,
                )
            except Doc4ContractError as exc:
                first_error = first_error or str(exc)
                attempts.append({"metadata": metadata, "raw_payload": raw_payload, "validation_error": str(exc)})
                if schema_attempt < SCHEMA_RETRIES_MAX:
                    continue
                raise Doc4ContractError("invalid_structured_response") from exc
            attempts.append({"metadata": metadata, "raw_payload": raw_payload, "validation_error": None})
            return response, {
                "request": request_body,
                "attempts": attempts,
                "schema_retries_total": schema_attempt,
                "first_schema_error": first_error,
                "arm_status": "PASSED",
            }
        raise Doc4ContractError("invalid_structured_response")


def build_arm_request(
    *,
    candidate: ModelCandidate,
    source_mode: str,
    source: bytes | str,
    filename: str,
    system_prompt: str,
    task_prompt: str,
    source_wrapper: str,
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    task = source_wrapper.rstrip() + "\n\n" + task_prompt.rstrip() + "\n"
    if source_mode == "PDF":
        if not isinstance(source, bytes) or not source.startswith(b"%PDF-"):
            raise Doc4ContractError("pdf_arm_source_invalid")
        if len(source) > PDF_MAX_BYTES:
            raise Doc4ContractError("pdf_arm_source_too_large")
        content = [
            {"type": "input_text", "text": task},
            {
                "type": "input_file",
                "filename": filename,
                "file_data": "data:application/pdf;base64," + base64.b64encode(source).decode("ascii"),
                "detail": PDF_DETAIL,
            },
        ]
    elif source_mode == "LLM_VIEW":
        if not isinstance(source, str):
            raise Doc4ContractError("view_arm_source_invalid")
        encoded = source.encode("utf-8")
        if source.encode("utf-8").decode("utf-8") != source:
            raise Doc4ContractError("view_arm_source_not_utf8")
        if not source.startswith("BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1\n") or not source.endswith("END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1\n"):
            raise Doc4ContractError("view_arm_source_not_complete")
        if b"\r" in encoded:
            raise Doc4ContractError("view_arm_source_contains_cr")
        content = [{"type": "input_text", "text": task + "\n" + source}]
    else:
        raise Doc4ContractError("source_mode_invalid")
    request = {
        "model": candidate.request_model_id,
        "instructions": system_prompt.rstrip() + "\n",
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": candidate.reserved_max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "broker_reports_doc4_semantic_response_v1",
                "strict": True,
                "schema": response_schema,
            }
        },
    }
    _assert_request_isolation(request, source_mode=source_mode)
    return request


def authorized_request_keys(
    *,
    candidate: ModelCandidate,
    sources: list[CorpusSource],
    system_prompt: str,
    task_prompt: str,
    pdf_wrapper: str,
    view_wrapper: str,
    response_schema: dict[str, Any],
) -> frozenset[str]:
    """Freeze the only request bodies the private DOC4 transport may send."""

    keys: set[str] = set()
    for source in sources:
        for source_mode, payload, filename, wrapper in (
            ("PDF", source.pdf_path.read_bytes(), f"{source.safe_id}.pdf", pdf_wrapper),
            (
                "LLM_VIEW",
                source.llm_view_path.read_text(encoding="utf-8"),
                f"{source.safe_id}.txt",
                view_wrapper,
            ),
        ):
            request = build_arm_request(
                candidate=candidate,
                source_mode=source_mode,
                source=payload,
                filename=filename,
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                source_wrapper=wrapper,
                response_schema=response_schema,
            )
            keys.add(
                "/responses:" + sha256_bytes(canonical_json_bytes(request))
            )
            keys.update(
                "/responses/input_tokens:"
                + sha256_bytes(canonical_json_bytes(_token_count_body(item)))
                for item in _context_count_stages(
                    candidate=candidate,
                    source_mode=source_mode,
                    source=payload,
                    filename=filename,
                    system_prompt=system_prompt,
                    task_prompt=task_prompt,
                    source_wrapper=wrapper,
                    response_schema=response_schema,
                )
            )
    return frozenset(keys)


def context_preflight_request_sha256s(
    *,
    candidate: ModelCandidate,
    source_mode: str,
    source: bytes | str,
    filename: str,
    system_prompt: str,
    task_prompt: str,
    source_wrapper: str,
    response_schema: dict[str, Any],
) -> tuple[str, ...]:
    return tuple(
        sha256_bytes(canonical_json_bytes(_token_count_body(body)))
        for body in _context_count_stages(
            candidate=candidate,
            source_mode=source_mode,
            source=source,
            filename=filename,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            source_wrapper=source_wrapper,
            response_schema=response_schema,
        )
    )


def view_pointer_registry(view_text: str) -> ViewPointerRegistry:
    payload = ManagedDocumentLlmViewAuditor().audit(view_text).payload
    block_anchors: dict[str, frozenset[str]] = {}
    tables: dict[str, tuple[str, tuple[int, ...]]] = {}
    block_types: dict[str, str] = {}
    block_text_by_id: dict[str, str] = {}
    table_cells_by_block_id: dict[str, tuple[tuple[str, ...], ...]] = {}
    for block in payload["blocks"]:
        block_id = block["block_id"]
        block_types[block_id] = block["block_type"]
        block_text_by_id[block_id] = json.dumps(
            block.get("content"), ensure_ascii=False, sort_keys=True
        )
        block_anchors[block_id] = frozenset(
            item["anchor_id"] for item in block.get("source", [])
        )
        if block["block_type"] == "TABLE":
            content = block["content"]
            rows = content.get("rows", [])
            tables[block_id] = (
                content["table_id"],
                tuple(len(row) for row in rows),
            )
            table_cells_by_block_id[block_id] = tuple(
                tuple(str(cell) for cell in row) for row in rows
            )
    return ViewPointerRegistry(
        block_anchor_ids=block_anchors,
        tables=tables,
        block_types=block_types,
        block_text_by_id=block_text_by_id,
        table_cells_by_block_id=table_cells_by_block_id,
    )


def pdf_pages_total(pdf_path: Path) -> int:
    try:
        total = len(PdfReader(str(pdf_path), strict=True).pages)
    except Exception as exc:
        raise Doc4ContractError("pdf_page_count_failed") from exc
    if total < 1:
        raise Doc4ContractError("pdf_has_no_pages")
    return total


def pdf_page_texts(source: bytes) -> tuple[str, ...]:
    if not source.startswith(b"%PDF-"):
        raise Doc4ContractError("pdf_text_source_invalid")
    try:
        return tuple(
            page.extract_text() or "" for page in PdfReader(BytesIO(source), strict=True).pages
        )
    except Exception as exc:
        raise Doc4ContractError("pdf_text_extraction_failed") from exc


def write_immutable_json(path: Path, value: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Doc4ContractError(f"immutable_output_exists:{path.name}") from exc
    readback = path.read_bytes()
    if readback != payload:
        raise Doc4ContractError(f"immutable_output_readback_mismatch:{path.name}")
    return sha256_bytes(payload)


def hash_bound_private_payload(
    schema_version: str,
    **fields: Any,
) -> dict[str, Any]:
    value = {"schema_version": schema_version, **copy.deepcopy(fields), "integrity_sha256": ""}
    value["integrity_sha256"] = integrity_sha256(value)
    return value


def provider_usage_from_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = [attempt for trace in traces for attempt in trace["attempts"]]
    metadata = [attempt["metadata"] for attempt in attempts]
    input_values = [item.get("input_tokens") for item in metadata]
    output_values = [item.get("output_tokens") for item in metadata]
    cached_values = [item.get("cached_tokens") for item in metadata]
    usage_complete = all(
        isinstance(value, int) and not isinstance(value, bool)
        for values in (input_values, output_values, cached_values)
        for value in values
    )
    return hash_bound_private_payload(
        "broker_reports_doc4_provider_usage_private_v1",
        provider_calls_total=sum(item["attempts_total"] for item in metadata),
        successful_calls_total=len(metadata),
        transport_retries_total=sum(item["transport_retries_total"] for item in metadata),
        schema_retries_total=sum(trace["schema_retries_total"] for trace in traces),
        input_tokens_total=sum(input_values) if usage_complete else None,
        output_tokens_total=sum(output_values) if usage_complete else None,
        cached_tokens_total=sum(cached_values) if usage_complete else None,
        provider_reported_cost_total=None,
        cost_status="NOT_REPORTED_BY_PROVIDER",
        usage_complete=usage_complete,
    )


def connection_from_env_file(path: Path) -> ProviderConnection:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return ProviderConnection(
        base_url=values.get("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
        api_key=values.get("OPENAI_API_KEY", ""),
    )


def _source_binding(source: CorpusSource) -> dict[str, Any]:
    paths = (
        source.pdf_path,
        source.managed_document_path,
        source.llm_view_path,
        source.doc2_coverage_receipt_path,
        source.doc3_render_receipt_path,
    )
    if any(not path.is_file() for path in paths):
        raise Doc4ContractError(f"source_artifact_missing:{source.safe_id}")
    pdf_bytes = source.pdf_path.read_bytes()
    view_bytes = source.llm_view_path.read_bytes()
    pdf_sha = sha256_bytes(pdf_bytes)
    view_sha = sha256_bytes(view_bytes)
    managed = read_json(source.managed_document_path)
    managed_schema = read_json(MANAGED_DOCUMENT_SCHEMA_PATH)
    managed = ManagedDocumentContractValidator(managed_schema).validate(managed).payload
    managed_sha = sha256_bytes(_doc3_managed_input_bytes(managed))
    coverage = read_json(source.doc2_coverage_receipt_path)
    render = read_json(source.doc3_render_receipt_path)
    _validate_external_schema(
        coverage,
        MANAGED_DOCUMENT_COVERAGE_SCHEMA_PATH,
        label="doc2_coverage_receipt",
    )
    if coverage.get("integrity_sha256") != coverage_integrity_sha256(coverage):
        raise Doc4ContractError(f"doc2_coverage_integrity_invalid:{source.safe_id}")
    counters = coverage.get("counters", {})
    entries = coverage.get("entries", [])
    status_counts = {
        status: sum(item.get("coverage_status") == status for item in entries)
        for status in ("UNRESOLVED", "KNOWN_LOSS", "BLOCKED_AT_SOURCE")
    }
    if (
        coverage.get("accepted") is not True
        or coverage.get("document_id") != managed.get("document_id")
        or counters.get("source_observations_total") != len(entries)
        or counters.get("coverage_entries_total") != len(entries)
        or counters.get("unresolved_total") != status_counts["UNRESOLVED"]
        or counters.get("known_loss_total") != status_counts["KNOWN_LOSS"]
        or counters.get("blocked_at_source_total")
        != status_counts["BLOCKED_AT_SOURCE"]
        or counters.get("unresolved_total") != 0
        or counters.get("blocked_at_source_total") != 0
        or counters.get("unaccounted_context_loss_total") != 0
        or counters.get("invented_source_content_total") != 0
    ):
        raise Doc4ContractError(f"doc2_coverage_not_complete:{source.safe_id}")
    _validate_external_schema(
        render,
        LLM_VIEW_RECEIPT_SCHEMA_PATH,
        label="doc3_render_receipt",
    )
    if managed.get("source", {}).get("checksum_sha256") != pdf_sha:
        raise Doc4ContractError(f"pdf_managed_source_identity_mismatch:{source.safe_id}")
    if coverage.get("source_checksum_sha256") != pdf_sha:
        raise Doc4ContractError(f"doc2_coverage_source_identity_mismatch:{source.safe_id}")
    if coverage.get("managed_document_integrity_sha256") != managed.get("integrity_sha256"):
        raise Doc4ContractError(f"doc2_managed_integrity_mismatch:{source.safe_id}")
    if render.get("input_managed_document_sha256") != managed_sha:
        raise Doc4ContractError(f"doc3_managed_input_identity_mismatch:{source.safe_id}")
    if render.get("output_view_sha256") != view_sha:
        raise Doc4ContractError(f"doc3_view_output_identity_mismatch:{source.safe_id}")
    replay = ManagedDocumentLlmViewFactory().create(
        managed_schema,
        read_json(DOC1_TO_DOC3_FIELD_COVERAGE_PATH),
    ).render(managed)
    if replay.view_text.encode("utf-8") != view_bytes:
        raise Doc4ContractError(f"doc3_view_replay_mismatch:{source.safe_id}")
    if replay.receipt != render:
        raise Doc4ContractError(f"doc3_receipt_replay_mismatch:{source.safe_id}")
    ManagedDocumentLlmViewAuditor().audit(view_bytes)
    return {
        "safe_id": source.safe_id,
        "pdf_sha256": pdf_sha,
        "managed_document_sha256": managed_sha,
        "llm_view_sha256": view_sha,
        "doc2_coverage_receipt_sha256": sha256_bytes(source.doc2_coverage_receipt_path.read_bytes()),
        "doc3_render_receipt_sha256": sha256_bytes(source.doc3_render_receipt_path.read_bytes()),
        "pdf_bytes": len(pdf_bytes),
        "pdf_pages": pdf_pages_total(source.pdf_path),
        "llm_view_bytes": len(view_bytes),
        "identity_invariant": True,
    }


def _doc3_managed_input_bytes(payload: dict[str, Any]) -> bytes:
    """Reproduce DOC3's frozen input-identity serialization without importing DOC1."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_external_schema(value: dict[str, Any], path: Path, *, label: str) -> None:
    schema = read_json(path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise Doc4ContractError(f"{label}_schema_invalid") from exc
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "$"
        raise Doc4ContractError(
            f"{label}_invalid:{location}:{first.validator}"
        )


def _context_count_stages(
    *,
    candidate: ModelCandidate,
    source_mode: str,
    source: bytes | str,
    filename: str,
    system_prompt: str,
    task_prompt: str,
    source_wrapper: str,
    response_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    full = build_arm_request(
        candidate=candidate,
        source_mode=source_mode,
        source=source,
        filename=filename,
        system_prompt=system_prompt,
        task_prompt=task_prompt,
        source_wrapper=source_wrapper,
        response_schema=response_schema,
    )
    full.pop("max_output_tokens")
    return [full]


def _token_count_body(request_body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"model", "instructions", "input", "text"}
    return {key: copy.deepcopy(value) for key, value in request_body.items() if key in allowed}


def _assert_outbound_provider_policy(
    request: dict[str, Any], *, suffix: str
) -> None:
    if request.get("model") != REQUEST_MODEL_ID:
        raise Doc4ContractError("provider_outbound_model_not_authorized")
    if suffix == "/responses/input_tokens":
        if set(request) != {"model", "instructions", "input", "text"}:
            raise Doc4ContractError("provider_token_count_shape_invalid")
        return
    if suffix != "/responses":
        raise Doc4ContractError("provider_endpoint_not_authorized")
    if set(request) != {
        "model",
        "instructions",
        "input",
        "max_output_tokens",
        "text",
    }:
        raise Doc4ContractError("provider_response_request_shape_invalid")


def _assert_request_isolation(request: dict[str, Any], *, source_mode: str) -> None:
    forbidden = {
        "previous_response_id",
        "conversation",
        "include",
        "prompt",
        "background",
        "tools",
        "store",
        "temperature",
        "top_p",
        "reasoning",
    }
    if forbidden.intersection(request):
        raise Doc4ContractError("arm_state_or_external_context_present")
    content = request["input"][0]["content"]
    types = [item["type"] for item in content]
    if source_mode == "PDF" and types.count("input_file") != 1:
        raise Doc4ContractError("pdf_arm_file_isolation_invalid")
    if source_mode == "LLM_VIEW" and "input_file" in types:
        raise Doc4ContractError("view_arm_contains_pdf")


def _usage_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
    return {
        "input_tokens": _optional_nonnegative_int(usage.get("input_tokens")),
        "output_tokens": _optional_nonnegative_int(usage.get("output_tokens")),
        "total_tokens": _optional_nonnegative_int(usage.get("total_tokens")),
        "cached_tokens": _optional_nonnegative_int(details.get("cached_tokens")) or 0,
        "provider_reported_cost": None,
        "cost_status": "NOT_REPORTED_BY_PROVIDER",
    }


def _optional_nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _validate_openai_base_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "api.openai.com" or parsed.path.rstrip("/") != "/v1":
        raise Doc4ContractError("provider_base_url_not_canonical_openai")
