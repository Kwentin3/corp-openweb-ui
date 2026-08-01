from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Mapping

from .managed_document_contracts import (
    ManagedDocument,
    ManagedDocumentContractValidator,
)
from .managed_document_coverage import (
    MANAGED_DOCUMENT_COVERAGE_SCHEMA_VERSION,
    SOURCE_OBSERVATION_INVENTORY_SCHEMA_VERSION,
    canonical_sha256,
    require_private_contract,
    seal_private_contract,
    validate_managed_document_coverage,
    validate_source_observation_inventory,
)
from .pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserError,
    PdfTextLayerParserFactory,
)
from .table_projection import (
    NormalizedTableProjectionFactory,
)


MANAGED_PDF_BUILDER_VERSION = "broker_reports_managed_pdf_document_builder_v1"
MANAGED_PDF_BUILD_TRACE_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_document_build_trace_v1"
)
MANAGED_DOCUMENT_ARTIFACT_TYPE = "private_broker_reports_managed_document_v1"
SOURCE_OBSERVATION_ARTIFACT_TYPE = (
    "private_broker_reports_source_observation_inventory_v1"
)
MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE = (
    "private_broker_reports_managed_document_coverage_v1"
)
MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE = (
    "private_broker_reports_managed_document_build_trace_v1"
)
DOC2_PRIVATE_ARTIFACT_TYPES = frozenset(
    {
        MANAGED_DOCUMENT_ARTIFACT_TYPE,
        SOURCE_OBSERVATION_ARTIFACT_TYPE,
        MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE,
        MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE,
    }
)

FACTORY_REQUIRED = "ManagedPdfDocumentFactory.create is the only DOC2 PDF to Managed Document v1 entrypoint"
FORBIDDEN = "DOC2 callers must not use PdfLayoutUnitBuilder._build_page_units, product routes, provider calls, Gate 2, Semantic Pack, or Type-First as Managed Document reading-order authority"


@contextmanager
def inactive_doc2_artifact_type_scope():
    """Admit DOC2 private types only around the offline proof store operation."""

    from .artifact_models import ARTIFACT_TYPES

    preexisting = set(ARTIFACT_TYPES)
    ARTIFACT_TYPES.update(DOC2_PRIVATE_ARTIFACT_TYPES)
    try:
        yield
    finally:
        ARTIFACT_TYPES.intersection_update(preexisting)


@dataclass(frozen=True)
class ManagedPdfDocumentConfig:
    created_at: str = "2026-08-01T00:00:00Z"
    maximum_pages: int = 500
    maximum_observations: int = 250_000


@dataclass(frozen=True)
class ManagedPdfBuildResult:
    status: str
    reason_codes: tuple[str, ...]
    managed_document: ManagedDocument | None
    source_observation_inventory: dict[str, Any]
    coverage_receipt: dict[str, Any]
    build_trace: dict[str, Any]


class ManagedPdfDocumentFactory:
    def __init__(self, config: ManagedPdfDocumentConfig | None = None) -> None:
        self.config = config or ManagedPdfDocumentConfig()

    def create(self, schema: Mapping[str, Any]) -> "ManagedPdfDocumentBuilder":
        if self.config.maximum_pages <= 0:
            raise ValueError("managed_pdf_maximum_pages_invalid")
        if self.config.maximum_observations <= 0:
            raise ValueError("managed_pdf_maximum_observations_invalid")
        validator = ManagedDocumentContractValidator(schema)
        return ManagedPdfDocumentBuilder(
            config=self.config,
            validator=validator,
            observer=PdfSourceObservationAdapter(),
            assembler=PdfReadingOrderAssembler(),
            materializer=ManagedDocumentBlockMaterializer(),
            reconciler=ManagedDocumentCoverageReconciler(),
        )


class ManagedPdfDocumentBuilder:
    def __init__(
        self,
        *,
        config: ManagedPdfDocumentConfig,
        validator: ManagedDocumentContractValidator,
        observer: "PdfSourceObservationAdapter",
        assembler: "PdfReadingOrderAssembler",
        materializer: "ManagedDocumentBlockMaterializer",
        reconciler: "ManagedDocumentCoverageReconciler",
    ) -> None:
        self.config = config
        self.validator = validator
        self.observer = observer
        self.assembler = assembler
        self.materializer = materializer
        self.reconciler = reconciler

    def build(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
    ) -> ManagedPdfBuildResult:
        if not isinstance(content_bytes, bytes) or not content_bytes:
            raise ValueError("managed_pdf_source_bytes_invalid")
        source_sha256 = hashlib.sha256(content_bytes).hexdigest()
        document_id = _identifier("document_pdf", source_sha256)
        private_ref = source_artifact_ref or _identifier("private_pdf", source_sha256)
        observation = self.observer.observe(
            content_bytes,
            document_id=document_id,
            source_checksum_sha256=source_sha256,
            private_source_ref=private_ref,
        )
        if observation["status"] == "BLOCKED":
            return self._blocked_result(
                observation=observation,
                content_bytes=content_bytes,
                private_source_ref=private_ref,
            )
        if len(observation["pages"]) > self.config.maximum_pages:
            observation = _blocked_observation(
                document_id=document_id,
                source_checksum_sha256=source_sha256,
                reason_code="managed_pdf_page_budget_exceeded",
            )
            return self._blocked_result(
                observation=observation,
                content_bytes=content_bytes,
                private_source_ref=private_ref,
            )

        assembled = self.assembler.assemble(observation)
        if assembled["status"] == "BLOCKED":
            observation["reason_codes"] = sorted(
                {*observation.get("reason_codes", []), *assembled["reason_codes"]}
            )
            observation["blocking_observations"] = assembled["blocking_observations"]
            return self._blocked_result(
                observation=observation,
                content_bytes=content_bytes,
                private_source_ref=private_ref,
            )

        materialized = self.materializer.materialize(
            assembled,
            content_bytes=content_bytes,
            private_source_ref=private_ref,
            created_at=self.config.created_at,
        )
        inventory = self.reconciler.build_inventory(
            observation=observation,
            materialized=materialized,
        )
        if inventory["observations_total"] > self.config.maximum_observations:
            raise ValueError("managed_pdf_observation_budget_exceeded")
        receipt = self.reconciler.reconcile(
            inventory=inventory,
            materialized=materialized,
            accepted=True,
        )
        require_private_contract(validate_source_observation_inventory(inventory))
        require_private_contract(validate_managed_document_coverage(receipt, inventory))

        candidate = materialized["document"]
        quality = candidate["quality"]
        if receipt["counters"]["unresolved_total"]:
            quality["status"] = "BLOCKED"
            quality["blocking_losses_total"] += 1
        if receipt["counters"]["unaccounted_context_loss_total"]:
            raise ValueError("managed_pdf_unaccounted_context_loss")
        if receipt["counters"]["invented_source_content_total"]:
            raise ValueError("managed_pdf_invented_source_content")
        managed_document = self.validator.seal(candidate)
        receipt["managed_document_integrity_sha256"] = managed_document.integrity_sha256
        receipt = seal_private_contract(receipt)
        require_private_contract(validate_managed_document_coverage(receipt, inventory))
        build_trace = self._build_trace(
            status=managed_document.payload["quality"]["status"],
            reason_codes=observation.get("reason_codes", []),
            inventory=inventory,
            receipt=receipt,
            managed_document=managed_document,
            parser_provenance={
                "page_parser": assembled["page_parser"],
                "page_parser_version": assembled["page_parser_version"],
                "page_parser_config_ref": assembled["page_parser_config_ref"],
                "layout_parser": assembled["layout_parser"],
                "layout_parser_version": assembled["layout_parser_version"],
                "layout_parser_config_ref": assembled["layout_parser_config_ref"],
            },
        )
        return ManagedPdfBuildResult(
            status=managed_document.payload["quality"]["status"],
            reason_codes=tuple(sorted(set(observation.get("reason_codes", [])))),
            managed_document=managed_document,
            source_observation_inventory=inventory,
            coverage_receipt=receipt,
            build_trace=build_trace,
        )

    def _blocked_result(
        self,
        *,
        observation: dict[str, Any],
        content_bytes: bytes,
        private_source_ref: str,
    ) -> ManagedPdfBuildResult:
        source_sha256 = observation["source_checksum_sha256"]
        document_id = observation["document_id"]
        raw_observations = list(observation.get("blocking_observations") or [])
        if not raw_observations:
            raw_observations = [
                {
                    "observation_id": _identifier(
                        "observation_parser_failure", source_sha256
                    ),
                    "observation_type": "PARSER_FAILURE",
                    "page": None,
                    "bbox": None,
                    "parent_observation_ids": [],
                    "source_refs": [private_source_ref],
                    "observation_checksum_sha256": hashlib.sha256(
                        "|".join(observation.get("reason_codes") or []).encode("utf-8")
                    ).hexdigest(),
                }
            ]
        inventory = seal_private_contract(
            {
                "schema_version": SOURCE_OBSERVATION_INVENTORY_SCHEMA_VERSION,
                "document_id": document_id,
                "source_checksum_sha256": source_sha256,
                "observations_total": len(raw_observations),
                "observations": raw_observations,
            }
        )
        entries = [
            {
                "observation_id": item["observation_id"],
                "coverage_status": "BLOCKED_AT_SOURCE",
                "block_ids": [],
                "anchor_ids": [],
                "loss_ids": [],
                "reason_code": next(
                    iter(observation.get("reason_codes") or []),
                    "managed_pdf_source_blocked",
                ),
            }
            for item in raw_observations
        ]
        receipt = seal_private_contract(
            {
                "schema_version": MANAGED_DOCUMENT_COVERAGE_SCHEMA_VERSION,
                "document_id": document_id,
                "source_checksum_sha256": source_sha256,
                "accepted": False,
                "managed_document_integrity_sha256": None,
                "entries": entries,
                "counters": {
                    "source_observations_total": len(raw_observations),
                    "coverage_entries_total": len(entries),
                    "unresolved_total": 0,
                    "known_loss_total": 0,
                    "blocked_at_source_total": len(entries),
                    "unaccounted_context_loss_total": 0,
                    "invented_source_content_total": 0,
                },
            }
        )
        require_private_contract(validate_source_observation_inventory(inventory))
        require_private_contract(validate_managed_document_coverage(receipt, inventory))
        trace = self._build_trace(
            status="BLOCKED",
            reason_codes=observation.get("reason_codes", []),
            inventory=inventory,
            receipt=receipt,
            managed_document=None,
            parser_provenance=None,
        )
        return ManagedPdfBuildResult(
            status="BLOCKED",
            reason_codes=tuple(sorted(set(observation.get("reason_codes", [])))),
            managed_document=None,
            source_observation_inventory=inventory,
            coverage_receipt=receipt,
            build_trace=trace,
        )

    def _build_trace(
        self,
        *,
        status: str,
        reason_codes: list[str],
        inventory: dict[str, Any],
        receipt: dict[str, Any],
        managed_document: ManagedDocument | None,
        parser_provenance: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return seal_private_contract(
            {
                "schema_version": MANAGED_PDF_BUILD_TRACE_SCHEMA_VERSION,
                "builder_version": MANAGED_PDF_BUILDER_VERSION,
                "document_id": inventory["document_id"],
                "source_checksum_sha256": inventory["source_checksum_sha256"],
                "status": status,
                "reason_codes": sorted(set(reason_codes)),
                "reading_order_policy": (
                    "page_then_parser_block_order_then_parser_word_order_with_"
                    "validated_tables_at_first_owned_word"
                ),
                "factory_route": [
                    "ManagedPdfDocumentFactory.create",
                    "PdfTextLayerParserFactory.create(page_text)",
                    "PdfTextLayerParserFactory.create(table_candidates)",
                    "NormalizedTableProjectionFactory.create",
                ],
                "parser_provenance": copy.deepcopy(parser_provenance),
                "forbidden_route_used": False,
                "pdf_layout_unit_builder_used": False,
                "product_route_connected": False,
                "provider_calls_total": 0,
                "knowledge_rag_used": False,
                "embeddings_used": False,
                "vectorization_performed": False,
                "managed_document_integrity_sha256": (
                    managed_document.integrity_sha256 if managed_document else None
                ),
                "observation_inventory_integrity_sha256": inventory["integrity_sha256"],
                "coverage_receipt_integrity_sha256": receipt["integrity_sha256"],
                "created_at_policy": "fixed_contract_epoch_for_deterministic_replay",
            }
        )


class PdfSourceObservationAdapter:
    def __init__(self) -> None:
        self.parser_factory = PdfTextLayerParserFactory()

    def observe(
        self,
        content_bytes: bytes,
        *,
        document_id: str,
        source_checksum_sha256: str,
        private_source_ref: str,
    ) -> dict[str, Any]:
        try:
            page_parser = self.parser_factory.create(
                PdfParserCapabilityRequest(capability="page_text")
            )
            page_result = page_parser.parse(content_bytes)
        except PdfTextLayerParserError as exc:
            return _blocked_observation(
                document_id=document_id,
                source_checksum_sha256=source_checksum_sha256,
                reason_code=exc.code,
            )
        if page_result.parser_completeness_status == "blocked" or not page_result.pages:
            reasons = list(page_result.parser_completeness_reason_codes)
            return _blocked_observation(
                document_id=document_id,
                source_checksum_sha256=source_checksum_sha256,
                reason_code=(
                    "pdf_encrypted_without_key"
                    if "pdf_encrypted_without_key" in reasons
                    else next(iter(reasons), "managed_pdf_page_parser_blocked")
                ),
            )
        try:
            layout_parser = self.parser_factory.create(
                PdfParserCapabilityRequest(capability="table_candidates")
            )
            layout_result = layout_parser.parse(content_bytes)
        except PdfTextLayerParserError as exc:
            return _blocked_observation(
                document_id=document_id,
                source_checksum_sha256=source_checksum_sha256,
                reason_code=exc.code,
            )
        if len(page_result.pages) != len(layout_result.pages):
            return _blocked_observation(
                document_id=document_id,
                source_checksum_sha256=source_checksum_sha256,
                reason_code="managed_pdf_page_reconciliation_failed",
            )

        page_text_by_number = {
            int(item.get("page_number") or 0): item for item in page_result.pages
        }
        pages = []
        reason_codes = [
            *list(page_result.parser_completeness_reason_codes),
            *list(layout_result.layout_reason_codes),
        ]
        for raw_page in layout_result.pages:
            page_number = int(raw_page.get("page_number") or 0)
            text_page = page_text_by_number.get(page_number)
            if text_page is None:
                return _blocked_observation(
                    document_id=document_id,
                    source_checksum_sha256=source_checksum_sha256,
                    reason_code="managed_pdf_page_text_missing",
                )
            pages.append(
                _materialize_observed_page(
                    raw_page=raw_page,
                    text_page=text_page,
                    source_checksum_sha256=source_checksum_sha256,
                    document_id=document_id,
                    layout_parser_version=layout_result.parser_engine_version,
                    layout_parser_config_ref=layout_result.parser_config_ref,
                )
            )
        return {
            "status": "READY",
            "document_id": document_id,
            "source_checksum_sha256": source_checksum_sha256,
            "private_source_ref": private_source_ref,
            "page_parser": page_result.parser_engine,
            "page_parser_version": page_result.parser_engine_version,
            "page_parser_config_ref": page_result.parser_config_ref,
            "layout_parser": layout_result.parser_engine,
            "layout_parser_version": layout_result.parser_engine_version,
            "layout_parser_config_ref": layout_result.parser_config_ref,
            "reason_codes": sorted(set(reason_codes)),
            "pages": pages,
        }


class PdfReadingOrderAssembler:
    def assemble(self, observation: dict[str, Any]) -> dict[str, Any]:
        blocking: list[dict[str, Any]] = []
        pages = copy.deepcopy(observation["pages"])
        for page in pages:
            words_to_candidates: dict[str, list[str]] = {}
            for candidate in page["table_candidates"]:
                for word_ref in candidate["contributing_word_refs"]:
                    words_to_candidates.setdefault(word_ref, []).append(
                        candidate["table_candidate_ref"]
                    )
            overlaps = {
                word_ref: refs
                for word_ref, refs in words_to_candidates.items()
                if len(set(refs)) > 1
            }
            block_line_refs = [
                line_ref
                for block in page["text_blocks"]
                for line_ref in block["line_refs"]
            ]
            known_line_refs = [item["line_ref"] for item in page["text_lines"]]
            duplicate_lines = [
                ref for ref, count in Counter(block_line_refs).items() if count > 1
            ]
            if (
                overlaps
                or duplicate_lines
                or set(block_line_refs) != set(known_line_refs)
            ):
                checksum = hashlib.sha256(
                    json.dumps(
                        {
                            "overlap_count": len(overlaps),
                            "duplicate_line_count": len(duplicate_lines),
                            "line_scope_matches": set(block_line_refs)
                            == set(known_line_refs),
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                blocking.append(
                    {
                        "observation_id": _identifier(
                            "observation_order_ambiguity",
                            observation["source_checksum_sha256"],
                            page["page_number"],
                        ),
                        "observation_type": "UNKNOWN_OBSERVATION",
                        "page": page["page_number"],
                        "bbox": None,
                        "parent_observation_ids": [],
                        "source_refs": [],
                        "observation_checksum_sha256": checksum,
                    }
                )
        if blocking:
            return {
                "status": "BLOCKED",
                "reason_codes": ["managed_pdf_reading_order_ambiguity"],
                "blocking_observations": blocking,
            }
        return {
            "status": "READY",
            **copy.deepcopy(observation),
        }


class ManagedDocumentBlockMaterializer:
    def __init__(self) -> None:
        self.table_service = NormalizedTableProjectionFactory().create()

    def materialize(
        self,
        assembled: dict[str, Any],
        *,
        content_bytes: bytes,
        private_source_ref: str,
        created_at: str,
    ) -> dict[str, Any]:
        source_sha256 = assembled["source_checksum_sha256"]
        document_id = assembled["document_id"]
        anchors: list[dict[str, Any]] = []
        blocks: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        losses: list[dict[str, Any]] = []
        coverage_bindings: dict[str, dict[str, list[str] | str]] = {}

        for page in assembled["pages"]:
            page_number = page["page_number"]
            boundary_anchor = _anchor(
                source_sha256=source_sha256,
                private_source_ref=private_source_ref,
                page=page_number,
                source_block_ref=page["page_ref"],
                bbox=None,
            )
            anchors.append(boundary_anchor)
            boundary_block = _block(
                block_id=_identifier("block_page", source_sha256, page_number),
                ordinal=len(blocks),
                block_type="BOUNDARY",
                content={
                    "information_class": "CONTENT",
                    "boundary_type": "PAGE",
                    "source_part_index": page_number,
                    "label": _metadata_field(
                        status="PRESENT",
                        origin="DETERMINISTIC_DERIVED",
                        value=f"Page {page_number}",
                        anchor_ids=[boundary_anchor["anchor_id"]],
                    ),
                },
                anchor_ids=[boundary_anchor["anchor_id"]],
            )
            blocks.append(boundary_block)
            coverage_bindings[page["page_observation_id"]] = _binding(
                "REPRESENTED_BY_BLOCK", boundary_block, boundary_anchor
            )

            table_states = self._table_states(
                page=page,
                document_id=document_id,
                source_sha256=source_sha256,
            )
            candidate_by_word: dict[str, dict[str, Any]] = {}
            for state in table_states.values():
                for word_ref in state["candidate"]["contributing_word_refs"]:
                    candidate_by_word[word_ref] = state
            emitted_candidates: set[str] = set()
            line_by_ref = {item["line_ref"]: item for item in page["text_lines"]}
            word_by_ref = {item["word_ref"]: item for item in page["words"]}

            for source_block in page["text_blocks"]:
                paragraph_lines: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
                block_output_ids: list[str] = []

                def flush_paragraph() -> None:
                    if not paragraph_lines:
                        return
                    text_lines = [
                        " ".join(str(word["text"]) for word in words).strip()
                        for _, words in paragraph_lines
                    ]
                    raw_text = "\n".join(value for value in text_lines if value)
                    if not raw_text:
                        paragraph_lines.clear()
                        return
                    bbox = _bbox_union(
                        [line.get("bbox") for line, _ in paragraph_lines]
                    )
                    anchor = _anchor(
                        source_sha256=source_sha256,
                        private_source_ref=private_source_ref,
                        page=page_number,
                        source_block_ref=_identifier(
                            "pdf_paragraph_source",
                            *[line["line_ref"] for line, _ in paragraph_lines],
                        ),
                        bbox=bbox,
                    )
                    anchors.append(anchor)
                    block = _block(
                        block_id=_identifier(
                            "block_paragraph",
                            source_sha256,
                            page_number,
                            *[line["line_ref"] for line, _ in paragraph_lines],
                        ),
                        ordinal=len(blocks),
                        block_type="PARAGRAPH",
                        content={
                            "information_class": "CONTENT",
                            "raw_text": raw_text,
                            "join_events": [],
                        },
                        anchor_ids=[anchor["anchor_id"]],
                    )
                    blocks.append(block)
                    block_output_ids.append(block["block_id"])
                    for line, _ in paragraph_lines:
                        coverage_bindings[line["line_observation_id"]] = _binding(
                            "REPRESENTED_BY_BLOCK", block, anchor
                        )
                    paragraph_lines.clear()

                for line_ref in source_block["line_refs"]:
                    line = line_by_ref[line_ref]
                    current_words: list[dict[str, Any]] = []
                    for word_ref in line["word_refs"]:
                        state = candidate_by_word.get(word_ref)
                        if state is None:
                            current_words.append(word_by_ref[word_ref])
                            continue
                        if current_words:
                            paragraph_lines.append((line, current_words))
                            current_words = []
                        if paragraph_lines:
                            flush_paragraph()
                        candidate_ref = state["candidate"]["table_candidate_ref"]
                        if candidate_ref not in emitted_candidates:
                            block, anchor, issue, loss = self._table_or_unknown_block(
                                state=state,
                                source_sha256=source_sha256,
                                private_source_ref=private_source_ref,
                                page=page_number,
                                ordinal=len(blocks),
                            )
                            anchors.append(anchor)
                            blocks.append(block)
                            block_output_ids.append(block["block_id"])
                            emitted_candidates.add(candidate_ref)
                            coverage_bindings[
                                state["candidate"]["table_observation_id"]
                            ] = _binding(
                                (
                                    "REPRESENTED_BY_TABLE"
                                    if state["accepted"]
                                    else "KNOWN_LOSS"
                                ),
                                block,
                                anchor,
                                loss,
                            )
                            if state.get("validated_observation_id"):
                                coverage_bindings[state["validated_observation_id"]] = (
                                    _binding("REPRESENTED_BY_TABLE", block, anchor)
                                )
                            if issue:
                                issues.append(issue)
                            if loss:
                                losses.append(loss)
                    if current_words:
                        paragraph_lines.append((line, current_words))
                    elif line["line_observation_id"] not in coverage_bindings:
                        table_state = next(
                            (
                                state
                                for word_ref in line["word_refs"]
                                if (state := candidate_by_word.get(word_ref))
                                is not None
                            ),
                            None,
                        )
                        if table_state:
                            candidate_binding = coverage_bindings.get(
                                table_state["candidate"]["table_observation_id"]
                            )
                            if candidate_binding:
                                coverage_bindings[line["line_observation_id"]] = {
                                    **copy.deepcopy(candidate_binding),
                                    "coverage_status": (
                                        "REPRESENTED_BY_TABLE"
                                        if table_state["accepted"]
                                        else "KNOWN_LOSS"
                                    ),
                                }
                flush_paragraph()
                source_block_anchor_ids = [
                    anchor_id
                    for block in blocks
                    if block["block_id"] in block_output_ids
                    for anchor_id in block["source_anchor_ids"]
                ]
                coverage_bindings[source_block["block_observation_id"]] = {
                    "coverage_status": "REPRESENTED_BY_BLOCK",
                    "block_ids": block_output_ids,
                    "anchor_ids": list(dict.fromkeys(source_block_anchor_ids)),
                    "loss_ids": [],
                }

            for state in table_states.values():
                candidate = state["candidate"]
                if candidate["table_candidate_ref"] in emitted_candidates:
                    continue
                block, anchor, issue, loss = self._table_or_unknown_block(
                    state=state,
                    source_sha256=source_sha256,
                    private_source_ref=private_source_ref,
                    page=page_number,
                    ordinal=len(blocks),
                )
                anchors.append(anchor)
                blocks.append(block)
                emitted_candidates.add(candidate["table_candidate_ref"])
                coverage_bindings[candidate["table_observation_id"]] = _binding(
                    "REPRESENTED_BY_TABLE" if state["accepted"] else "KNOWN_LOSS",
                    block,
                    anchor,
                    loss,
                )
                if state.get("validated_observation_id"):
                    coverage_bindings[state["validated_observation_id"]] = _binding(
                        "REPRESENTED_BY_TABLE", block, anchor
                    )
                if issue:
                    issues.append(issue)
                if loss:
                    losses.append(loss)

            if page["image_objects_total"]:
                visual_anchor = _anchor(
                    source_sha256=source_sha256,
                    private_source_ref=private_source_ref,
                    page=page_number,
                    source_block_ref=_identifier(
                        "full_page_visual", source_sha256, page_number
                    ),
                    bbox=None,
                )
                visual_block_id = _identifier(
                    "block_visual", source_sha256, page_number
                )
                issue_id = _identifier("issue_visual", source_sha256, page_number)
                content_loss_id = _identifier(
                    "loss_visual_content", source_sha256, page_number
                )
                order_loss_id = _identifier(
                    "loss_visual_order", source_sha256, page_number
                )
                visual_block = _block(
                    block_id=visual_block_id,
                    ordinal=len(blocks),
                    block_type="VISUAL",
                    content={
                        "information_class": "CONTENT",
                        "visual_type": "UNKNOWN",
                        "caption": _metadata_field(),
                        "safe_description": _metadata_field(),
                        "private_artifact": _private_ref(
                            private_source_ref, source_sha256
                        ),
                        "processing_status": "UNPROCESSED",
                    },
                    anchor_ids=[visual_anchor["anchor_id"]],
                    restoration_status="PARTIAL",
                    issue_ids=[issue_id],
                )
                anchors.append(visual_anchor)
                blocks.append(visual_block)
                issue = {
                    "issue_id": issue_id,
                    "code": "pdf_visual_content_unprocessed",
                    "severity": "WARNING",
                    "message": (
                        "The source-visible image objects remain bound to the private PDF; "
                        "no visual interpretation was attempted."
                    ),
                    "anchor_ids": [visual_anchor["anchor_id"]],
                    "block_ids": [visual_block_id],
                    "relation_ids": [],
                    "recoverability": "RECOVERABLE",
                    "requires_source_reread": True,
                }
                content_loss = {
                    "loss_id": content_loss_id,
                    "context_class": "CONTENT",
                    "what_lost": "Normalized interpretation of source-visible image objects.",
                    "where": f"PDF page {page_number}.",
                    "reason": "DOC2 performs no OCR, VLM, provider, or visual semantic inference.",
                    "recoverability": "RECOVERABLE",
                    "requires_source_reread": True,
                    "blocks_semantic_analysis": False,
                    "accounted": True,
                    "anchor_ids": [visual_anchor["anchor_id"]],
                    "block_ids": [visual_block_id],
                }
                order_loss = {
                    "loss_id": order_loss_id,
                    "context_class": "ORDER",
                    "what_lost": (
                        "Exact placement of image objects relative to text and table blocks."
                    ),
                    "where": f"PDF page {page_number}.",
                    "reason": (
                        "The current source observation exposes only a page-level image count, "
                        "so the page-tail VISUAL block is a container and not a source-order claim."
                    ),
                    "recoverability": "RECOVERABLE",
                    "requires_source_reread": True,
                    "blocks_semantic_analysis": False,
                    "accounted": True,
                    "anchor_ids": [visual_anchor["anchor_id"]],
                    "block_ids": [visual_block_id],
                }
                issues.append(issue)
                losses.extend([content_loss, order_loss])
                coverage_bindings[page["visual_observation_id"]] = _binding(
                    "KNOWN_LOSS",
                    visual_block,
                    visual_anchor,
                    [content_loss, order_loss],
                )

        unknown_blocks = sum(item["block_type"] == "UNKNOWN" for item in blocks)
        visual_blocks = sum(item["block_type"] == "VISUAL" for item in blocks)
        quality_status = "PARTIAL" if issues or losses else "COMPLETE"
        document = {
            "schema_version": "broker_reports_managed_document_v1",
            "document_id": document_id,
            "information_partition": {
                "CONTENT": ["/metadata", "/blocks/*/content"],
                "PROVENANCE": ["/source", "/anchors", "/relations"],
                "CONTROL": [
                    "/information_partition",
                    "/blocks/*/restoration",
                    "/quality",
                ],
                "PRIVATE_SOURCE": [
                    "/source/artifact",
                    "/anchors/*/locator/private_locator",
                    "/blocks/*/content/private_artifact",
                ],
            },
            "source": {
                "information_class": "PROVENANCE",
                "format": "PDF",
                "artifact": _private_ref(private_source_ref, source_sha256),
                "checksum_sha256": source_sha256,
                "mime_type": "application/pdf",
                "size_bytes": len(content_bytes),
                "source_part_count": len(assembled["pages"]),
                "normalizer": {
                    "name": "ManagedPdfDocumentFactory",
                    "version": MANAGED_PDF_BUILDER_VERSION,
                },
                "created_at": created_at,
                "source_details": {
                    "kind": "PDF",
                    "encrypted_status": "NOT_ENCRYPTED",
                },
            },
            "metadata": _unknown_metadata(),
            "anchors": anchors,
            "blocks": blocks,
            "relations": [],
            "quality": {
                "information_class": "CONTROL",
                "status": quality_status,
                "source_elements_total": 0,
                "preserved_blocks_total": len(blocks),
                "unknown_blocks_total": unknown_blocks,
                "unsupported_elements_total": unknown_blocks + visual_blocks,
                "known_losses_total": len(losses),
                "conflicts_total": 0,
                "unaccounted_context_loss_total": 0,
                "blocking_losses_total": 0,
                "issue_ledger": issues,
                "loss_ledger": losses,
            },
        }
        return {
            "document": document,
            "coverage_bindings": coverage_bindings,
            "validated_table_observations": [
                state["validated_observation"]
                for page in assembled["pages"]
                for state in self._table_states(
                    page=page,
                    document_id=document_id,
                    source_sha256=source_sha256,
                ).values()
                if state.get("validated_observation")
            ],
        }

    def _table_states(
        self,
        *,
        page: dict[str, Any],
        document_id: str,
        source_sha256: str,
    ) -> dict[str, dict[str, Any]]:
        if "_doc2_table_states" in page:
            return page["_doc2_table_states"]
        payload_ref = _identifier("doc2_payload", source_sha256)
        parent_payload = {
            "source_payload_ref": payload_ref,
            "pdf_text_layer_projection": {
                "word_inventory": page["words"],
                "bbox_inventory": page["bboxes"],
                "table_candidate_inventory": page["table_candidates"],
            },
        }
        units = []
        for candidate in page["table_candidates"]:
            unit_ref = _identifier("doc2_table_unit", candidate["table_candidate_ref"])
            units.append(
                {
                    "document_id": document_id,
                    "unit_ref": unit_ref,
                    "pdf_unit_type": "pdf_table_candidate_unit",
                    "parent_payload_ref": payload_ref,
                    "normalization_run_id": _identifier("doc2_run", source_sha256),
                    "parser_ref": page["layout_parser_ref"],
                    "parser": "pdfplumber",
                    "parser_version": page["layout_parser_version"],
                    "layout_parser_config_ref": page["layout_parser_config_ref"],
                    "source_checksum_ref": "srcsum_" + source_sha256[:24],
                    "payload_checksum_ref": None,
                    "source_unit_checksum_ref": None,
                    "pdf_layout_unit_checksum_ref": _identifier(
                        "doc2_layout_checksum", candidate["table_candidate_ref"]
                    ),
                    "table_candidate_ref": candidate["table_candidate_ref"],
                    "table_strategy_ref": candidate["table_strategy_ref"],
                    "geometry_confidence": candidate["geometry_confidence"],
                    "table_bbox_ref": candidate["bbox_ref"],
                    "table_contributing_word_refs": candidate["contributing_word_refs"],
                    "table_fallback_text_refs": candidate["fallback_text_refs"],
                    "table_fallback_source_value_refs": [],
                    "layout_line_refs": candidate["fallback_text_refs"],
                    "page_refs": [page["page_ref"]],
                    "pdf_layout_coverage": {
                        "selected_source_refs": [
                            *candidate["contributing_word_refs"],
                            *candidate["fallback_text_refs"],
                        ]
                    },
                }
            )
        result = self.table_service.build_for_document(
            source_format="pdf",
            payloads=[parent_payload],
            source_units=units,
        )
        projection_by_candidate = {
            projection["table_ref"]: projection for projection in result.projections
        }
        states = {}
        for candidate in page["table_candidates"]:
            projection = projection_by_candidate.get(candidate["table_candidate_ref"])
            accepted = bool(
                projection
                and projection.get("validator_status") == "passed"
                and projection.get("projection_status") == "ready"
                and projection.get("table_candidate_status") == "validated_geometry"
                and projection.get("reconstruction_quality") in {"high", "medium"}
            )
            validated_observation_id = (
                _identifier(
                    "observation_validated_table",
                    candidate["table_candidate_ref"],
                )
                if accepted
                else None
            )
            validated_observation = (
                {
                    "observation_id": validated_observation_id,
                    "observation_type": "VALIDATED_LOGICAL_TABLE",
                    "page": page["page_number"],
                    "bbox": candidate["bbox"],
                    "parent_observation_ids": [candidate["table_observation_id"]],
                    "source_refs": candidate["contributing_word_refs"],
                    "observation_checksum_sha256": (
                        projection["table_projection_checksum_ref"].split("_")[-1]
                        if projection
                        and len(
                            projection["table_projection_checksum_ref"].split("_")[-1]
                        )
                        == 64
                        else hashlib.sha256(
                            str(
                                projection.get("table_projection_checksum_ref")
                                if projection
                                else ""
                            ).encode("utf-8")
                        ).hexdigest()
                    ),
                }
                if accepted
                else None
            )
            states[candidate["table_candidate_ref"]] = {
                "candidate": candidate,
                "projection": projection,
                "accepted": accepted,
                "validated_observation_id": validated_observation_id,
                "validated_observation": validated_observation,
            }
        page["_doc2_table_states"] = states
        return states

    def _table_or_unknown_block(
        self,
        *,
        state: dict[str, Any],
        source_sha256: str,
        private_source_ref: str,
        page: int,
        ordinal: int,
    ) -> tuple[
        dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None
    ]:
        candidate = state["candidate"]
        anchor = _anchor(
            source_sha256=source_sha256,
            private_source_ref=private_source_ref,
            page=page,
            source_block_ref=candidate["table_candidate_ref"],
            bbox=candidate["bbox"],
        )
        suffix = candidate["table_candidate_ref"]
        if state["accepted"]:
            projection = state["projection"]
            private_values = {
                item["value_path_ref"]: item.get("normalized_value")
                for item in projection["private_values"]
            }
            cells_by_row: dict[str, list[dict[str, Any]]] = {}
            for cell in projection["cells"]:
                cells_by_row.setdefault(cell["row_ref"], []).append(cell)
            rows: list[list[str | None]] = []
            annotations = []
            for row_index, row_ref in enumerate(projection["row_refs"]):
                row_cells = sorted(
                    cells_by_row.get(row_ref, []),
                    key=lambda item: int(item["column_ordinal"]),
                )
                values: list[str | None] = []
                for column_index, cell in enumerate(row_cells):
                    value = private_values.get(cell["normalized_private_value_path"])
                    normalized = (
                        str(value) if value is not None and str(value) != "" else None
                    )
                    values.append(normalized)
                    annotations.append(
                        {
                            "row_index": row_index,
                            "column_index": column_index,
                            "state": ("PRESENT" if normalized is not None else "EMPTY"),
                            "origin": "SOURCE_EXPLICIT",
                            "evidence_anchor_ids": [anchor["anchor_id"]],
                            "issue_ids": [],
                        }
                    )
                if values:
                    rows.append(values)
            block = _block(
                block_id=_identifier("block_table", suffix),
                ordinal=ordinal,
                block_type="TABLE",
                content={
                    "information_class": "CONTENT",
                    "table_id": _identifier("table_pdf", suffix),
                    "title": _metadata_field(),
                    "description": (
                        "Mechanically validated PDF grid with source-bound cell values; "
                        "semantic table meaning is not claimed."
                    ),
                    "rows": rows,
                    "completeness_status": "COMPLETE",
                    "header_hierarchy": {"status": "UNKNOWN", "entries": []},
                    "row_groups": {"status": "UNKNOWN", "groups": []},
                    "row_markers": [],
                    "units": [],
                    "cell_annotations": annotations,
                    "related_relation_ids": [],
                    "continuation_relation_ids": [],
                    "known_gap_ids": [],
                },
                anchor_ids=[anchor["anchor_id"]],
            )
            return block, anchor, None, None

        issue_id = _identifier("issue_table_unknown", suffix)
        loss_id = _identifier("loss_table_structure", suffix)
        raw_text = " ".join(candidate["contributing_text"]).strip() or None
        block = _block(
            block_id=_identifier("block_unknown_table", suffix),
            ordinal=ordinal,
            block_type="UNKNOWN",
            content={
                "information_class": "CONTENT",
                "raw_text": raw_text,
                "private_artifact": _private_ref(private_source_ref, source_sha256),
                "reason": (
                    "The parser marked a table region, but its logical grid did not pass "
                    "the deterministic source-binding validator."
                ),
            },
            anchor_ids=[anchor["anchor_id"]],
            restoration_status="PARTIAL",
            issue_ids=[issue_id],
        )
        issue = {
            "issue_id": issue_id,
            "code": "pdf_table_grid_not_validated",
            "severity": "WARNING",
            "message": (
                "Source text and private location are preserved without minting TABLE truth."
            ),
            "anchor_ids": [anchor["anchor_id"]],
            "block_ids": [block["block_id"]],
            "relation_ids": [],
            "recoverability": "RECOVERABLE",
            "requires_source_reread": True,
        }
        loss = {
            "loss_id": loss_id,
            "context_class": "STRUCTURE",
            "what_lost": "Validated logical row and column structure for the table region.",
            "where": f"PDF page {page}, source region {candidate['table_candidate_ref']}.",
            "reason": "The deterministic table projection acceptance gate did not pass.",
            "recoverability": "RECOVERABLE",
            "requires_source_reread": True,
            "blocks_semantic_analysis": False,
            "accounted": True,
            "anchor_ids": [anchor["anchor_id"]],
            "block_ids": [block["block_id"]],
        }
        return block, anchor, issue, loss


class ManagedDocumentCoverageReconciler:
    def build_inventory(
        self,
        *,
        observation: dict[str, Any],
        materialized: dict[str, Any],
    ) -> dict[str, Any]:
        observations = []
        for page in observation["pages"]:
            observations.append(
                {
                    "observation_id": page["page_observation_id"],
                    "observation_type": "PAGE_BOUNDARY",
                    "page": page["page_number"],
                    "bbox": None,
                    "parent_observation_ids": [],
                    "source_refs": [page["page_ref"]],
                    "observation_checksum_sha256": page["page_checksum_sha256"],
                }
            )
            for block in page["text_blocks"]:
                observations.append(
                    {
                        "observation_id": block["block_observation_id"],
                        "observation_type": "TEXT_BLOCK",
                        "page": page["page_number"],
                        "bbox": block["bbox"],
                        "parent_observation_ids": [page["page_observation_id"]],
                        "source_refs": block["line_refs"],
                        "observation_checksum_sha256": block["checksum_sha256"],
                    }
                )
            for line in page["text_lines"]:
                observations.append(
                    {
                        "observation_id": line["line_observation_id"],
                        "observation_type": "TEXT_LINE",
                        "page": page["page_number"],
                        "bbox": line["bbox"],
                        "parent_observation_ids": [page["page_observation_id"]],
                        "source_refs": line["word_refs"],
                        "observation_checksum_sha256": line["text_checksum_sha256"],
                    }
                )
            for candidate in page["table_candidates"]:
                observations.append(
                    {
                        "observation_id": candidate["table_observation_id"],
                        "observation_type": "TABLE_REGION",
                        "page": page["page_number"],
                        "bbox": candidate["bbox"],
                        "parent_observation_ids": [page["page_observation_id"]],
                        "source_refs": candidate["contributing_word_refs"],
                        "observation_checksum_sha256": candidate["checksum_sha256"],
                    }
                )
            if page["image_objects_total"]:
                observations.append(
                    {
                        "observation_id": page["visual_observation_id"],
                        "observation_type": "FULL_PAGE_VISUAL",
                        "page": page["page_number"],
                        "bbox": None,
                        "parent_observation_ids": [page["page_observation_id"]],
                        "source_refs": [page["page_ref"]],
                        "observation_checksum_sha256": hashlib.sha256(
                            f"{page['page_ref']}|{page['image_objects_total']}".encode(
                                "utf-8"
                            )
                        ).hexdigest(),
                    }
                )
        observations.extend(materialized["validated_table_observations"])
        inventory = seal_private_contract(
            {
                "schema_version": SOURCE_OBSERVATION_INVENTORY_SCHEMA_VERSION,
                "document_id": observation["document_id"],
                "source_checksum_sha256": observation["source_checksum_sha256"],
                "observations_total": len(observations),
                "observations": observations,
            }
        )
        materialized["document"]["quality"]["source_elements_total"] = len(observations)
        return inventory

    def reconcile(
        self,
        *,
        inventory: dict[str, Any],
        materialized: dict[str, Any],
        accepted: bool,
    ) -> dict[str, Any]:
        bindings = materialized["coverage_bindings"]
        entries = []
        for observation in inventory["observations"]:
            binding = bindings.get(observation["observation_id"])
            if binding is None:
                binding = {
                    "coverage_status": "UNRESOLVED",
                    "block_ids": [],
                    "anchor_ids": [],
                    "loss_ids": [],
                }
            entries.append(
                {
                    "observation_id": observation["observation_id"],
                    **copy.deepcopy(binding),
                    "reason_code": _coverage_reason(binding["coverage_status"]),
                }
            )
        unresolved = sum(item["coverage_status"] == "UNRESOLVED" for item in entries)
        known_loss = sum(item["coverage_status"] == "KNOWN_LOSS" for item in entries)
        blocked = sum(
            item["coverage_status"] == "BLOCKED_AT_SOURCE" for item in entries
        )
        return seal_private_contract(
            {
                "schema_version": MANAGED_DOCUMENT_COVERAGE_SCHEMA_VERSION,
                "document_id": inventory["document_id"],
                "source_checksum_sha256": inventory["source_checksum_sha256"],
                "accepted": bool(accepted and not unresolved and not blocked),
                "managed_document_integrity_sha256": None,
                "entries": entries,
                "counters": {
                    "source_observations_total": len(inventory["observations"]),
                    "coverage_entries_total": len(entries),
                    "unresolved_total": unresolved,
                    "known_loss_total": known_loss,
                    "blocked_at_source_total": blocked,
                    "unaccounted_context_loss_total": 0,
                    "invented_source_content_total": 0,
                },
            }
        )


def _materialize_observed_page(
    *,
    raw_page: dict[str, Any],
    text_page: dict[str, Any],
    source_checksum_sha256: str,
    document_id: str,
    layout_parser_version: str,
    layout_parser_config_ref: str,
) -> dict[str, Any]:
    page_number = int(raw_page.get("page_number") or 0)
    page_ref = _identifier("pdf_page", source_checksum_sha256, page_number)
    words = []
    word_by_ordinal = {}
    bboxes = []
    bbox_by_value: dict[str, str] = {}

    def bbox_ref(value: Any) -> str:
        normalized = _bbox(value)
        key = json.dumps(normalized, separators=(",", ":"))
        if key not in bbox_by_value:
            ref = _identifier("pdf_bbox", source_checksum_sha256, page_number, key)
            bbox_by_value[key] = ref
            bboxes.append({"bbox_ref": ref, "bbox": normalized})
        return bbox_by_value[key]

    for raw in raw_page.get("word_inventory") or []:
        ordinal = int(raw.get("parser_ordinal") or 0)
        text = str(raw.get("text") or "")
        word_ref = _identifier(
            "pdf_word", source_checksum_sha256, page_number, ordinal, text
        )
        item = {
            "word_ref": word_ref,
            "page_ref": page_ref,
            "parser_ordinal": ordinal,
            "text": text,
            "bbox": _bbox(raw.get("bbox")),
            "bbox_ref": bbox_ref(raw.get("bbox")),
            "source_value_ref": _identifier("srcval", word_ref, text),
        }
        words.append(item)
        word_by_ordinal[ordinal] = item

    lines = []
    line_by_ordinal = {}
    for raw in raw_page.get("line_inventory") or []:
        ordinal = int(raw.get("parser_ordinal") or 0)
        text = str(raw.get("text") or "")
        line_ref = _identifier(
            "pdf_line", source_checksum_sha256, page_number, ordinal, text
        )
        item = {
            "line_ref": line_ref,
            "line_observation_id": _identifier("observation_line", line_ref),
            "parser_ordinal": ordinal,
            "text": text,
            "text_checksum_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bbox": _bbox(raw.get("bbox")),
            "bbox_ref": bbox_ref(raw.get("bbox")),
            "word_refs": [
                word_by_ordinal[int(value)]["word_ref"]
                for value in raw.get("word_parser_ordinals") or []
                if int(value) in word_by_ordinal
            ],
        }
        lines.append(item)
        line_by_ordinal[ordinal] = item

    text_blocks = []
    for raw in raw_page.get("block_inventory") or []:
        ordinal = int(raw.get("parser_ordinal") or 0)
        line_refs = [
            line_by_ordinal[int(value)]["line_ref"]
            for value in raw.get("line_parser_ordinals") or []
            if int(value) in line_by_ordinal
        ]
        block_ref = _identifier(
            "pdf_source_block",
            source_checksum_sha256,
            page_number,
            ordinal,
            *line_refs,
        )
        text_blocks.append(
            {
                "source_block_ref": block_ref,
                "block_observation_id": _identifier(
                    "observation_text_block", block_ref
                ),
                "parser_ordinal": ordinal,
                "bbox": _bbox(raw.get("bbox")),
                "line_refs": line_refs,
                "checksum_sha256": hashlib.sha256(
                    "|".join(line_refs).encode("utf-8")
                ).hexdigest(),
            }
        )

    table_candidates = []
    for candidate_ordinal, raw in enumerate(
        raw_page.get("table_candidate_inventory") or [], 1
    ):
        contributing_words = [
            word_by_ordinal[int(value)]
            for value in raw.get("contributing_word_parser_ordinals") or []
            if int(value) in word_by_ordinal
        ]
        contributing_word_refs = [item["word_ref"] for item in contributing_words]
        candidate_word_set = set(contributing_word_refs)
        overlapping_lines = [
            line for line in lines if _bbox_overlap(line["bbox"], raw.get("bbox"))
        ]
        if any(
            set(line["word_refs"]) - candidate_word_set
            and set(line["word_refs"]) & candidate_word_set
            for line in overlapping_lines
        ):
            reconstruction_reasons = sorted(
                {
                    *list(raw.get("reconstruction_reason_codes") or []),
                    "pdf_table_candidate_cross_line_partial_rejected",
                }
            )
        else:
            reconstruction_reasons = sorted(
                set(raw.get("reconstruction_reason_codes") or [])
            )
        table_ref = _identifier(
            "pdf_table_candidate",
            source_checksum_sha256,
            page_number,
            candidate_ordinal,
            *contributing_word_refs,
        )
        rows, cells = _materialize_candidate_cells(
            table_ref=table_ref,
            page_ref=page_ref,
            raw_cells=list(raw.get("cell_inventory") or []),
            word_by_ordinal=word_by_ordinal,
            bbox_ref=bbox_ref,
        )
        if "pdf_table_candidate_cross_line_partial_rejected" in reconstruction_reasons:
            rows = []
            cells = []
        candidate = {
            "table_candidate_ref": table_ref,
            "table_observation_id": _identifier("observation_table_region", table_ref),
            "parser_ordinal": candidate_ordinal,
            "bbox": _bbox(raw.get("bbox")),
            "bbox_ref": bbox_ref(raw.get("bbox")),
            "page_ref": page_ref,
            "table_strategy_ref": raw.get("table_strategy_ref"),
            "geometry_confidence": float(raw.get("geometry_confidence") or 0.0),
            "row_inventory": rows,
            "cell_inventory": cells,
            "contributing_word_refs": contributing_word_refs,
            "contributing_text": [str(item["text"]) for item in contributing_words],
            "fallback_text_refs": [item["line_ref"] for item in overlapping_lines],
            "reconstruction_reason_codes": reconstruction_reasons,
        }
        candidate["checksum_sha256"] = canonical_sha256(candidate)
        table_candidates.append(candidate)

    page_text = str(text_page.get("text") or "")
    return {
        "page_number": page_number,
        "page_ref": page_ref,
        "page_observation_id": _identifier("observation_page", page_ref),
        "page_checksum_sha256": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
        "image_objects_total": int(text_page.get("image_objects_total") or 0),
        "visual_observation_id": _identifier("observation_visual", page_ref),
        "words": words,
        "text_lines": lines,
        "text_blocks": text_blocks,
        "table_candidates": table_candidates,
        "bboxes": bboxes,
        "layout_parser_ref": _identifier(
            "parser_pdfplumber",
            layout_parser_version,
            layout_parser_config_ref,
            document_id,
        ),
        "layout_parser_version": layout_parser_version,
        "layout_parser_config_ref": layout_parser_config_ref,
    }


def _materialize_candidate_cells(
    *,
    table_ref: str,
    page_ref: str,
    raw_cells: list[dict[str, Any]],
    word_by_ordinal: dict[int, dict[str, Any]],
    bbox_ref,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(
        raw_cells,
        key=lambda item: (_bbox(item.get("bbox"))[1], _bbox(item.get("bbox"))[0]),
    )
    row_groups: list[list[dict[str, Any]]] = []
    for cell in ordered:
        top = _bbox(cell.get("bbox"))[1]
        target = next(
            (
                group
                for group in reversed(row_groups)
                if abs(top - _bbox(group[0].get("bbox"))[1]) <= 2.0
            ),
            None,
        )
        if target is None:
            row_groups.append([cell])
        else:
            target.append(cell)
    rows = []
    cells = []
    for row_ordinal, group in enumerate(row_groups, 1):
        row_ref = _identifier("pdf_table_row", table_ref, row_ordinal)
        cell_refs = []
        for column_ordinal, raw in enumerate(
            sorted(group, key=lambda item: _bbox(item.get("bbox"))[0]), 1
        ):
            cell_ref = _identifier(
                "pdf_table_cell",
                table_ref,
                row_ordinal,
                column_ordinal,
                raw.get("bbox"),
            )
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": row_ref,
                    "page_ref": page_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "bbox_ref": bbox_ref(raw.get("bbox")),
                    "word_refs": [
                        word_by_ordinal[int(value)]["word_ref"]
                        for value in raw.get("word_parser_ordinals") or []
                        if int(value) in word_by_ordinal
                    ],
                    "semantic_role": "not_claimed",
                }
            )
            cell_refs.append(cell_ref)
        rows.append(
            {
                "row_ref": row_ref,
                "page_ref": page_ref,
                "row_ordinal": row_ordinal,
                "cell_refs": cell_refs,
                "semantic_role": "not_claimed",
            }
        )
    return rows, cells


def _blocked_observation(
    *, document_id: str, source_checksum_sha256: str, reason_code: str
) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "document_id": document_id,
        "source_checksum_sha256": source_checksum_sha256,
        "reason_codes": [reason_code],
        "pages": [],
    }


def _identifier(prefix: str, *parts: Any) -> str:
    material = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _bbox(value: Any) -> list[float]:
    values = list(value or [0.0, 0.0, 0.0, 0.0])[:4]
    return [round(float(item), 6) for item in values]


def _bbox_union(values: list[Any]) -> list[float] | None:
    bboxes = [_bbox(value) for value in values if value is not None]
    if not bboxes:
        return None
    return [
        min(item[0] for item in bboxes),
        min(item[1] for item in bboxes),
        max(item[2] for item in bboxes),
        max(item[3] for item in bboxes),
    ]


def _bbox_overlap(left: Any, right: Any) -> bool:
    a = _bbox(left)
    b = _bbox(right)
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _metadata_field(
    *,
    status: str = "UNKNOWN",
    origin: str = "UNKNOWN_ORIGIN",
    value: str | None = None,
    anchor_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "information_class": "CONTENT",
        "status": status,
        "origin": origin,
        "value": value,
        "candidates": [],
        "evidence_anchor_ids": list(anchor_ids or []),
    }


def _unknown_metadata() -> dict[str, Any]:
    return {
        "document_type": _metadata_field(),
        "title": _metadata_field(),
        "issuer": _metadata_field(),
        "document_date": _metadata_field(),
        "reporting_period": _metadata_field(),
        "owner_or_account": _metadata_field(),
        "language": _metadata_field(),
        "primary_currency": _metadata_field(),
        "additional": [],
    }


def _private_ref(ref: str, checksum: str) -> dict[str, Any]:
    return {
        "information_class": "PRIVATE_SOURCE",
        "status": "PRESENT",
        "ref": ref,
        "checksum_sha256": checksum,
    }


def _anchor(
    *,
    source_sha256: str,
    private_source_ref: str,
    page: int,
    source_block_ref: str,
    bbox: list[float] | None,
) -> dict[str, Any]:
    anchor_id = _identifier("anchor_pdf", source_sha256, page, source_block_ref, bbox)
    return {
        "information_class": "PROVENANCE",
        "anchor_id": anchor_id,
        "source_format": "PDF",
        "checksum_sha256": source_sha256,
        "locator": {
            "kind": "PDF",
            "source_part_index": page,
            "page": page,
            "source_block_ref": source_block_ref,
            "bbox": bbox,
            "private_locator": _private_ref(private_source_ref, source_sha256),
        },
    }


def _block(
    *,
    block_id: str,
    ordinal: int,
    block_type: str,
    content: dict[str, Any],
    anchor_ids: list[str],
    restoration_status: str = "RESTORED",
    issue_ids: list[str] | None = None,
) -> dict[str, Any]:
    ids = list(issue_ids or [])
    return {
        "block_id": block_id,
        "ordinal": ordinal,
        "block_type": block_type,
        "content": content,
        "source_anchor_ids": anchor_ids,
        "restoration": {
            "information_class": "CONTROL",
            "status": restoration_status,
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": ids,
        },
        "issue_ids": ids,
    }


def _binding(
    coverage_status: str,
    block: dict[str, Any],
    anchor: dict[str, Any],
    loss: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    losses = loss if isinstance(loss, list) else ([loss] if loss else [])
    return {
        "coverage_status": coverage_status,
        "block_ids": [block["block_id"]],
        "anchor_ids": [anchor["anchor_id"]],
        "loss_ids": [item["loss_id"] for item in losses],
    }


def _coverage_reason(status: str) -> str:
    return {
        "REPRESENTED_BY_BLOCK": "source_observation_materialized",
        "REPRESENTED_BY_ANCHOR": "source_observation_anchored",
        "REPRESENTED_BY_TABLE": "source_observation_table_owned",
        "DUPLICATE_SUPPRESSED": "source_observation_duplicate_suppressed",
        "KNOWN_LOSS": "source_observation_loss_accounted",
        "BLOCKED_AT_SOURCE": "source_observation_blocked_at_source",
        "UNRESOLVED": "source_observation_unresolved",
    }[status]
