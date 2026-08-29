from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from broker_reports_gate1.contracts import sha256_json
from broker_reports_gate1.full_source import FullSourceArtifactFactory
from broker_reports_gate1.pdf_document_visual_adjudication import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfDocumentVisualAdjudicationError,
    PdfDocumentVisualAdjudicationFactory,
)
from broker_reports_gate1.pdf_table_locator_provider import (
    PDF_DOCUMENT_VISUAL_PROVIDER_ADAPTER_VERSION,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    PRIVATE_EVIDENCE_REF,
    _page_candidate_refs,
    _pdf_bytes,
    _scope_box,
    _source_bound_case,
    _source_bound_table_vectors,
)


PACKAGE = Path(__file__).resolve().parents[1] / "broker_reports_gate1"


class _ProviderFactory:
    def __init__(
        self,
        proposal: dict,
        critic: dict | None = None,
        receipt_mutator: Any | None = None,
    ) -> None:
        self.adapter = _Provider(
            proposal,
            critic or proposal,
            receipt_mutator=receipt_mutator,
        )

    def create_with_connection(self, connection: Any) -> "_Provider":
        assert connection is _CONNECTION
        return self.adapter


class _Provider:
    def __init__(
        self,
        proposal: dict,
        critic: dict,
        *,
        receipt_mutator: Any | None,
    ) -> None:
        self.outputs = {"PROPOSAL": proposal, "CRITIC": critic}
        self.calls: list[dict[str, Any]] = []
        self.receipt_mutator = receipt_mutator
        self.config = SimpleNamespace(model_id="models/gemini-3.5-flash")
        self.profile = SimpleNamespace(
            approved_model_ids=(
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash",
            )
        )

    def invoke_document_visual_geometry(self, **kwargs: Any) -> dict:
        pages = kwargs["page_images"]
        assert all(
            set(page) == {"png_bytes", "raster_manifest"} for page in pages
        )
        document_binding = {
            "document_ref": pages[0]["raster_manifest"]["document_ref"],
            "pdf_sha256": pages[0]["raster_manifest"]["pdf_sha256"],
            "pages": [
                {
                    "page_ordinal": ordinal,
                    "page_number": page["raster_manifest"]["page_number"],
                    "page_ref": page["raster_manifest"]["page_ref"],
                    "raster_manifest_hash": page["raster_manifest"][
                        "manifest_hash"
                    ],
                    "png_sha256": hashlib.sha256(page["png_bytes"]).hexdigest(),
                }
                for ordinal, page in enumerate(pages, start=1)
            ],
        }
        binding_sha256 = sha256_json(document_binding)
        call = {
            "phase": kwargs["phase"],
            "page_manifest_hashes": [
                page["raster_manifest"]["manifest_hash"] for page in pages
            ],
            "png_hashes": [
                hashlib.sha256(page["png_bytes"]).hexdigest() for page in pages
            ],
            "first_geometry_proposal": copy.deepcopy(
                kwargs["first_geometry_proposal"]
            ),
            "attempt_number": kwargs["attempt_number"],
            "attempt_lineage": copy.deepcopy(kwargs["attempt_lineage"]),
        }
        self.calls.append(call)
        attempt_id = f"{kwargs['task_id']}_a{kwargs['attempt_number']}"
        request_hash = sha256_json(
            {
                "phase": kwargs["phase"],
                "binding": document_binding,
                "first": kwargs["first_geometry_proposal"],
            }
        )
        attempt = {
            "task_id": kwargs["task_id"],
            "attempt_id": attempt_id,
            "attempt_number": kwargs["attempt_number"],
            "attempt_lineage": copy.deepcopy(kwargs["attempt_lineage"]),
            "phase": kwargs["phase"],
            "document_binding": document_binding,
            "document_binding_sha256": binding_sha256,
            "adapter_identity": PDF_DOCUMENT_VISUAL_PROVIDER_ADAPTER_VERSION,
            "transport_identity": (
                "gemini_generate_content_native_document_full_page_json_schema"
            ),
            "provider_calls": 2,
            "provider_http_calls": 2,
            "count_tokens_http_calls": 1,
            "model_generation_calls": 1,
            "http_status": 200,
            "finish_reason": "STOP",
            "parse_result": "parsed_object",
            "terminal_failure_class": None,
            "hidden_retry": False,
            "provider_failover": False,
            "model_values_used_as_source_literals": False,
            "table_identity_assigned": False,
            "continuation_decided": False,
            "product_reachability": False,
            "request_hash": request_hash,
            "generation_request_hash": request_hash,
            "counted_generation_body_hash": request_hash,
            "count_tokens_request_hash": hashlib.sha256(
                f"count:{request_hash}".encode()
            ).hexdigest(),
            "count_tokens_response_hash": hashlib.sha256(
                f"response:{request_hash}".encode()
            ).hexdigest(),
            "generation_request_bytes": 1000,
            "count_tokens_request_bytes": 1100,
            "counted_input_tokens": 100,
            "maximum_counted_input_tokens": 1000,
            "count_tokens_within_hard_guard": True,
            "canonical_schema_hash": hashlib.sha256(b"canonical-schema").hexdigest(),
            "adapted_schema_hash": hashlib.sha256(b"adapted-schema").hexdigest(),
            "model_requested": "models/gemini-3.5-flash",
            "model_resolved": "models/gemini-3.5-flash",
        }
        if self.receipt_mutator is not None:
            self.receipt_mutator(kwargs["phase"], attempt)
        return {
            "json_output": copy.deepcopy(self.outputs[kwargs["phase"]]),
            "attempt": attempt,
        }


_CONNECTION = object()


def _visual_table(
    payload: dict,
    *,
    page_number: int,
    title_refs: list[str],
    header_groups: list[list[str]],
    body_refs: list[str],
    body_status: str = "HAS_DATA",
) -> dict:
    projection = payload["pdf_text_layer_projection"]
    all_refs = [*title_refs, *(ref for group in header_groups for ref in group), *body_refs]
    return {
        "table_box_2d": _scope_box(projection, all_refs),
        "title_status": "PRESENT" if title_refs else "ABSENT",
        "title_boxes_2d": [_scope_box(projection, title_refs)] if title_refs else [],
        "header_status": "PRESENT" if header_groups else "ABSENT",
        "header_boxes_2d": [
            _scope_box(projection, group) for group in header_groups
        ],
        "body_status": body_status,
        "body_anchor_boxes_2d": (
            []
            if body_status == "EMPTY_TEMPLATE"
            else [_scope_box(projection, body_refs)]
        ),
    }


def _run(
    *,
    pdf_bytes: bytes,
    source_sha256: str,
    payload: dict,
    proposal: dict,
    critic: dict | None = None,
    receipt_mutator: Any | None = None,
):
    provider_factory = _ProviderFactory(
        proposal,
        critic,
        receipt_mutator=receipt_mutator,
    )
    runtime = PdfDocumentVisualAdjudicationFactory(
        provider_factory=provider_factory
    ).create_with_connection(_CONNECTION)
    result = runtime.adjudicate(
        task_id="document_visual_test",
        pdf_bytes=pdf_bytes,
        full_source_payload=payload,
        source_checksum_sha256=source_sha256,
        private_evidence_ref=PRIVATE_EVIDENCE_REF,
    )
    return result, provider_factory.adapter


def _two_page_observations(
    payload: dict,
    *,
    second_title: bool = False,
    repeated_header: bool = False,
) -> dict:
    projection = payload["pdf_text_layer_projection"]
    first = _page_candidate_refs(payload, 1)
    second = _page_candidate_refs(payload, 2)
    second_title_refs = [
        item["word_ref"]
        for item in projection["word_inventory"]
        if item["page_ref"]
        == next(
            page["page_ref"]
            for page in projection["page_inventory"]
            if page["page_number"] == 2
        )
        and item["word_ref"] not in second
    ]
    tables = [
        [
            _visual_table(
                payload,
                page_number=1,
                title_refs=[],
                header_groups=[first[:2]],
                body_refs=first[2:],
            )
        ],
        [
            _visual_table(
                payload,
                page_number=2,
                title_refs=second_title_refs if second_title else [],
                header_groups=[second[:2]] if repeated_header or second_title else [],
                body_refs=second[2:] if repeated_header or second_title else second,
            )
        ],
    ]
    return {"pages": [{"tables": value} for value in tables]}


def _numeric_headerless_case() -> tuple[bytes, str, dict]:
    pages = [
        {
            "texts": [
                (25, 55, "Item"),
                (200, 55, "Amount"),
                (25, 38, "Cash"),
                (200, 38, "10"),
                (25, 22, "Bonds"),
                (200, 22, "20"),
            ],
            "vectors": _source_bound_table_vectors(
                y0=15, y1=65, horizontal_ys=(15, 30, 46, 65)
            ),
        },
        {
            "texts": [
                (25, 305, "Funds"),
                (200, 305, "30"),
                (25, 288, "Shares"),
                (200, 288, "40"),
                (25, 271, "Options"),
                (200, 271, "50"),
            ],
            "vectors": _source_bound_table_vectors(
                y0=260, y1=315, horizontal_ys=(260, 279, 296, 315)
            ),
        },
    ]
    pdf_bytes = _pdf_bytes(pages)
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    built = FullSourceArtifactFactory().create().build(
        normalization_run_id="normrun_document_visual_adjudication",
        document_id="brdoc_document_visual_adjudication",
        profile_id="techprof_document_visual_adjudication",
        container_format="pdf",
        content_bytes=pdf_bytes,
        source_checksum_sha256=source_sha256,
    )
    assert built.summary["parser_completeness_status"] == "complete"
    return pdf_bytes, source_sha256, built.payloads[0]


def test_two_passes_use_same_rasters_and_numeric_headerless_is_legacy_proven() -> None:
    pdf_bytes, source_sha256, payload = _numeric_headerless_case()
    observations = _two_page_observations(payload)

    result, provider = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=observations,
    )

    assert [call["phase"] for call in provider.calls] == ["PROPOSAL", "CRITIC"]
    assert provider.calls[0]["page_manifest_hashes"] == provider.calls[1][
        "page_manifest_hashes"
    ]
    assert provider.calls[0]["png_hashes"] == provider.calls[1]["png_hashes"]
    assert provider.calls[1]["first_geometry_proposal"] == observations
    assert result.provider_accounting["provider_http_calls"] == 4
    assert result.provider_accounting["model_generation_calls"] == 2
    assert result.status == "COVERAGE_COMPLETE"
    assert result.as_dict()["document_complete"] is False
    assert len(result.page_coverage) == 2
    assert all(item["status"] == "ACCOUNTED" for item in result.page_coverage)
    assert len(result.recovery.tables) == 1
    assert result.recovery.diagnostics["continued_tables_total"] == 1
    assert result.recovery.unowned_word_refs == []
    assert "facts" not in result.as_dict()


@pytest.mark.parametrize(
    "mutation",
    ["same_forged_binding", "critic_binding_changed", "zero_calls"],
)
def test_provider_receipt_must_prove_exact_rendered_binding_and_real_calls(
    mutation: str,
) -> None:
    pdf_bytes, source_sha256, payload = _numeric_headerless_case()
    observations = _two_page_observations(payload)

    def mutate(phase: str, attempt: dict) -> None:
        if mutation == "same_forged_binding":
            attempt["document_binding"] = {
                "document_ref": "forged",
                "pdf_sha256": "0" * 64,
                "pages": [],
            }
            attempt["document_binding_sha256"] = sha256_json(
                attempt["document_binding"]
            )
        elif mutation == "critic_binding_changed" and phase == "CRITIC":
            attempt["document_binding"]["pages"][0]["page_ref"] = "mutated"
            attempt["document_binding_sha256"] = sha256_json(
                attempt["document_binding"]
            )
        elif mutation == "zero_calls":
            attempt["provider_calls"] = 0
            attempt["provider_http_calls"] = 0
            attempt["count_tokens_http_calls"] = 0
            attempt["model_generation_calls"] = 0

    with pytest.raises(PdfDocumentVisualAdjudicationError) as raised:
        _run(
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            payload=payload,
            proposal=observations,
            receipt_mutator=mutate,
        )

    assert raised.value.code == "document_visual_provider_accounting_invalid"


@pytest.mark.parametrize(
    "mutation",
    ["missing", "empty", "same_unapproved", "critic_different"],
)
def test_attempt_model_identity_must_equal_created_provider_config(
    mutation: str,
) -> None:
    pdf_bytes, source_sha256, payload = _numeric_headerless_case()
    observations = _two_page_observations(payload)

    def mutate(phase: str, attempt: dict) -> None:
        if mutation == "missing":
            attempt.pop("model_requested")
            attempt.pop("model_resolved")
        elif mutation == "empty":
            attempt["model_requested"] = ""
            attempt["model_resolved"] = ""
        elif mutation == "same_unapproved":
            attempt["model_requested"] = "models/forged"
            attempt["model_resolved"] = "models/forged"
        elif mutation == "critic_different" and phase == "CRITIC":
            attempt["model_requested"] = "models/gemini-3.1-flash-lite"
            attempt["model_resolved"] = "models/gemini-3.1-flash-lite"

    with pytest.raises(PdfDocumentVisualAdjudicationError) as raised:
        _run(
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            payload=payload,
            proposal=observations,
            receipt_mutator=mutate,
        )

    assert raised.value.code == "document_visual_provider_accounting_invalid"


def test_created_provider_model_must_be_approved_and_models_shaped() -> None:
    observations = {"pages": [{"tables": []}]}
    provider_factory = _ProviderFactory(observations)
    provider_factory.adapter.config.model_id = "gemini-3.5-flash"

    with pytest.raises(PdfDocumentVisualAdjudicationError) as raised:
        PdfDocumentVisualAdjudicationFactory(
            provider_factory=provider_factory
        ).create_with_connection(_CONNECTION)

    assert raised.value.code == "document_visual_provider_model_invalid"


@pytest.mark.parametrize("distinct_title", [True, False])
def test_present_title_is_boundary_and_repeated_header_stays_logicalrow_owned(
    distinct_title: bool,
) -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case(
        distinct_second_title=distinct_title,
        second_header_labels=None if distinct_title else ("Instrument", "Currency"),
    )
    observations = _two_page_observations(
        payload,
        second_title=distinct_title,
        repeated_header=True,
    )

    result, _ = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=observations,
    )

    assert len(result.recovery.tables) == (2 if distinct_title else 1)
    assert result.recovery.unowned_word_refs == []
    assert result.as_dict()["continuation_decided_by_coordinator"] is False


def test_missed_parser_candidate_and_critic_only_region_are_partial() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    proposal = {"pages": [{"tables": []}, {"tables": []}]}
    second = _page_candidate_refs(payload, 2)
    critic_only = _visual_table(
        payload,
        page_number=2,
        title_refs=[],
        header_groups=[],
        body_refs=second,
    )
    critic = {"pages": [{"tables": []}, {"tables": [critic_only]}]}

    result, _ = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=proposal,
        critic=critic,
    )

    assert result.status == "PARTIAL"
    codes = {issue["code"] for issue in result.issues}
    assert "document_visual_critic_only_region" in codes
    assert "document_visual_parser_candidate_missed" in codes
    assert result.recovery.unowned_word_refs == []


@pytest.mark.parametrize("body_status", ["EMPTY_TEMPLATE", "EXPLAINER"])
def test_empty_and_explainer_never_exclude_source_words(body_status: str) -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first = _page_candidate_refs(payload, 1)
    table = _visual_table(
        payload,
        page_number=1,
        title_refs=[],
        header_groups=[first[:2]],
        body_refs=first[2:],
        body_status=body_status,
    )
    observations = {"pages": [{"tables": [table]}, {"tables": []}]}

    result, _ = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=observations,
    )

    assert result.status == "PARTIAL"
    assert not any(
        item["status"] == "REVIEWED_SOURCE_BOUND"
        for item in result.parser_candidate_coverage
    )
    assert result.recovery.unowned_word_refs == []


def test_duplicate_or_disagreeing_visual_geometry_is_inspectable_partial() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first = _page_candidate_refs(payload, 1)
    table = _visual_table(
        payload,
        page_number=1,
        title_refs=[],
        header_groups=[first[:2]],
        body_refs=first[2:],
    )
    proposal = {"pages": [{"tables": [table, copy.deepcopy(table)]}, {"tables": []}]}
    critic = {"pages": [{"tables": [table]}, {"tables": []}]}

    result, _ = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=proposal,
        critic=critic,
    )

    assert result.status == "PARTIAL"
    assert any(
        issue["code"] == "document_visual_region_nonunique_or_overlapping"
        for issue in result.issues
    )
    assert len(
        [
            item
            for item in result.observation_coverage
            if item["page_ref"]
            == payload["pdf_text_layer_projection"]["page_inventory"][0]["page_ref"]
        ]
    ) == 3
    assert result.recovery.unowned_word_refs == []


def test_two_nonoverlapping_regions_bound_to_one_candidate_are_ambiguous() -> None:
    pdf_bytes, source_sha256, payload = _source_bound_case()
    first = _page_candidate_refs(payload, 1)
    upper = _visual_table(
        payload,
        page_number=1,
        title_refs=[],
        header_groups=[first[:2]],
        body_refs=first[2:4],
    )
    lower = _visual_table(
        payload,
        page_number=1,
        title_refs=[],
        header_groups=[],
        body_refs=first[4:],
    )
    observations = {
        "pages": [{"tables": [upper, lower]}, {"tables": []}]
    }

    result, _ = _run(
        pdf_bytes=pdf_bytes,
        source_sha256=source_sha256,
        payload=payload,
        proposal=observations,
    )

    assert result.status == "PARTIAL"
    assert any(
        issue["code"] == "document_visual_parser_candidate_nonunique"
        for issue in result.issues
    )
    assert result.recovery.unowned_word_refs == []


def test_coordinator_is_inactive_closed_world_and_has_no_ready_receipt_input() -> None:
    source = (PACKAGE / "pdf_document_visual_adjudication.py").read_text(
        encoding="utf-8"
    )
    assert "PdfDocumentVisualAdjudicationFactory.create_with_connection" in FACTORY_REQUIRED
    assert "no ready receipt input" in FORBIDDEN
    assert "SourceBoundTableScopeReceipt" not in source
    assert "openwebui_actions" not in source
    assert "canonical_normalizer" not in source
    assert "facts" not in source
    assert "pdf_document_visual_adjudication" not in (
        PACKAGE / "__init__.py"
    ).read_text(encoding="utf-8")
