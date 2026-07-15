from __future__ import annotations

import copy
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from .pdf_hybrid_contracts import sha256_json


PDF_CONTINUATION_DISCOVERY_SCHEMA = (
    "broker_reports_pdf_continuation_discovery_v1"
)
PDF_CONTINUATION_DISCOVERY_POLICY_VERSION = (
    "pdf_continuation_discovery_policy_v1"
)

FACTORY_REQUIRED = (
    "PdfContinuationDiscoveryFactory.create is the only continuation-discovery "
    "entrypoint"
)
FORBIDDEN = (
    "Callers must not infer continuation from text or values, ask a VLM to guess "
    "a continuation, group ambiguous candidates, or construct discovery results "
    "outside the factory-owned runtime"
)

_FACTORY_TOKEN = object()
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_DESCRIPTOR_KEYS = {
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "table_ref",
    "page_width",
    "page_height",
    "table_bbox",
    "columns_total",
    "table_strategy_ref",
    "geometry_confidence",
}
_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "discovery_id",
    "status",
    "manual_review_required",
    "continuation_groups",
    "not_grouped",
    "input_descriptor_refs",
    "reason_codes",
    "deterministic_geometry_only",
    "text_or_values_used",
    "vlm_used",
    "authoritative",
    "result_checksum",
}
_GROUP_KEYS = {
    "continuation_group_id",
    "document_ref",
    "pdf_sha256",
    "fragment_count",
    "shared_column_count",
    "table_strategy_ref",
    "horizontal_normalized_iou",
    "fragments",
    "group_checksum",
}
_FRAGMENT_KEYS = {
    "descriptor_ref",
    "fragment_order",
    "page_ref",
    "page_number",
    "table_ref",
    "edge_role",
    "normalized_edge_position",
}
_DECISION_KEYS = {
    "descriptor_ref",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "table_ref",
    "status",
    "manual_review_required",
    "reason_codes",
    "decision_checksum",
}

_EDGE_SIGNAL_ABSENT = "pdf_continuation_edge_signal_absent"
_GROUPED_REASON = "pdf_continuation_exact_two_page_pair_grouped"
_MANUAL_REASON_CODES = {
    "pdf_continuation_column_model_invalid",
    "pdf_continuation_column_model_mismatch",
    "pdf_continuation_descriptor_identity_duplicate",
    "pdf_continuation_document_or_sha_mismatch",
    "pdf_continuation_edge_candidate_ambiguous",
    "pdf_continuation_edge_pair_incomplete",
    "pdf_continuation_geometry_confidence_below_threshold",
    "pdf_continuation_geometry_confidence_invalid",
    "pdf_continuation_horizontal_overlap_insufficient",
    "pdf_continuation_page_dimensions_missing",
    "pdf_continuation_pages_nonadjacent",
    "pdf_continuation_strategy_invalid",
    "pdf_continuation_strategy_mismatch",
    "pdf_continuation_table_bbox_invalid",
    "pdf_continuation_three_page_chain_forbidden",
}


class PdfContinuationDiscoveryError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfContinuationDiscoveryConfig:
    policy_version: str = PDF_CONTINUATION_DISCOVERY_POLICY_VERSION
    bottom_edge_minimum: float = 0.88
    top_edge_maximum: float = 0.15
    minimum_columns: int = 2
    minimum_geometry_confidence: float = 0.8
    minimum_horizontal_normalized_iou: float = 0.9
    fragment_count: int = 2


@dataclass(frozen=True)
class _Candidate:
    document_ref: str
    pdf_sha256: str
    page_ref: str
    page_number: int
    table_ref: str
    page_width: float | None
    page_height: float | None
    table_bbox: tuple[float, float, float, float] | None
    columns_total: int | None
    table_strategy_ref: str | None
    geometry_confidence: float | None
    descriptor_ref: str
    input_reason_codes: tuple[str, ...]

    @property
    def geometry_available(self) -> bool:
        return (
            self.page_width is not None
            and self.page_height is not None
            and self.table_bbox is not None
        )

    @property
    def top_ratio(self) -> float | None:
        if not self.geometry_available:
            return None
        assert self.page_height is not None
        assert self.table_bbox is not None
        return _rounded(self.table_bbox[1] / self.page_height)

    @property
    def bottom_ratio(self) -> float | None:
        if not self.geometry_available:
            return None
        assert self.page_height is not None
        assert self.table_bbox is not None
        return _rounded(self.table_bbox[3] / self.page_height)


class PdfContinuationDiscoveryFactory:
    def __init__(
        self, config: PdfContinuationDiscoveryConfig | None = None
    ) -> None:
        self.config = config or PdfContinuationDiscoveryConfig()

    def create(self) -> "PdfContinuationDiscoveryRuntime":
        if asdict(self.config) != asdict(PdfContinuationDiscoveryConfig()):
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_discovery_config_invalid"
            )
        return PdfContinuationDiscoveryRuntime(
            config=self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfContinuationDiscoveryRuntime:
    def __init__(
        self,
        *,
        config: PdfContinuationDiscoveryConfig,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_discovery_factory_required"
            )
        self.config = config
        self.policy_configuration_hash = sha256_json(asdict(config))

    def discover(self, *, descriptors: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(descriptors, list):
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_descriptor_set_invalid"
            )
        candidates = sorted(
            (
                self._candidate(value, input_ordinal=index)
                for index, value in enumerate(descriptors, start=1)
            ),
            key=_candidate_sort_key,
        )
        reason_codes: dict[int, set[str]] = {
            index: set(candidate.input_reason_codes)
            for index, candidate in enumerate(candidates)
        }
        self._mark_duplicate_identities(candidates, reason_codes)

        bottom_by_document_page: dict[
            tuple[str, int], list[int]
        ] = defaultdict(list)
        top_by_document_page: dict[tuple[str, int], list[int]] = defaultdict(list)
        for index, candidate in enumerate(candidates):
            if not candidate.geometry_available:
                continue
            if candidate.bottom_ratio is not None and (
                candidate.bottom_ratio >= self.config.bottom_edge_minimum
            ):
                bottom_by_document_page[
                    (candidate.document_ref, candidate.page_number)
                ].append(index)
            if candidate.top_ratio is not None and (
                candidate.top_ratio <= self.config.top_edge_maximum
            ):
                top_by_document_page[
                    (candidate.document_ref, candidate.page_number)
                ].append(index)

        tentative_links: list[tuple[int, int, float]] = []
        document_pages: dict[str, set[int]] = defaultdict(set)
        for candidate in candidates:
            document_pages[candidate.document_ref].add(candidate.page_number)
        for document_ref, pages in sorted(document_pages.items()):
            for page_number in sorted(pages):
                next_page = page_number + 1
                if next_page not in pages:
                    continue
                bottom = bottom_by_document_page.get(
                    (document_ref, page_number), []
                )
                top = top_by_document_page.get((document_ref, next_page), [])
                if len(bottom) > 1 or len(top) > 1:
                    for index in {*bottom, *top}:
                        reason_codes[index].add(
                            "pdf_continuation_edge_candidate_ambiguous"
                        )
                    continue
                if len(bottom) != 1 or len(top) != 1:
                    for index in {*bottom, *top}:
                        reason_codes[index].add(
                            "pdf_continuation_edge_pair_incomplete"
                        )
                    continue
                left_index = bottom[0]
                right_index = top[0]
                overlap, mismatch = self._pair_evidence(
                    candidates[left_index], candidates[right_index]
                )
                if mismatch:
                    reason_codes[left_index].update(mismatch)
                    reason_codes[right_index].update(mismatch)
                else:
                    assert overlap is not None
                    tentative_links.append(
                        (left_index, right_index, overlap)
                    )

        self._mark_unpaired_edge_signals(
            candidates=candidates,
            bottom_by_document_page=bottom_by_document_page,
            top_by_document_page=top_by_document_page,
            reason_codes=reason_codes,
        )

        eligible_links = [
            link
            for link in tentative_links
            if not reason_codes[link[0]] and not reason_codes[link[1]]
        ]
        links_by_page: dict[tuple[str, str, int], list[int]] = defaultdict(list)
        for link_ordinal, (left_index, right_index, _overlap) in enumerate(
            eligible_links
        ):
            left = candidates[left_index]
            right = candidates[right_index]
            links_by_page[
                (left.document_ref, left.pdf_sha256, left.page_number)
            ].append(link_ordinal)
            links_by_page[
                (right.document_ref, right.pdf_sha256, right.page_number)
            ].append(link_ordinal)
        forbidden_links = {
            link_ordinal
            for link_ordinals in links_by_page.values()
            if len(link_ordinals) > 1
            for link_ordinal in link_ordinals
        }
        for link_ordinal in forbidden_links:
            left_index, right_index, _overlap = eligible_links[link_ordinal]
            reason_codes[left_index].add(
                "pdf_continuation_three_page_chain_forbidden"
            )
            reason_codes[right_index].add(
                "pdf_continuation_three_page_chain_forbidden"
            )

        accepted_links = [
            link
            for link_ordinal, link in enumerate(eligible_links)
            if link_ordinal not in forbidden_links
            and not reason_codes[link[0]]
            and not reason_codes[link[1]]
        ]
        groups = [
            self._group(candidates[left], candidates[right], overlap)
            for left, right, overlap in accepted_links
        ]
        groups.sort(
            key=lambda item: (
                item["document_ref"],
                item["pdf_sha256"],
                item["fragments"][0]["page_number"],
                item["fragments"][0]["table_ref"],
            )
        )
        grouped_refs = {
            fragment["descriptor_ref"]
            for group in groups
            for fragment in group["fragments"]
        }

        decisions: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            if candidate.descriptor_ref in grouped_refs:
                continue
            reasons = reason_codes[index]
            if not reasons:
                reasons.add(_EDGE_SIGNAL_ABSENT)
            decision = {
                "descriptor_ref": candidate.descriptor_ref,
                "document_ref": candidate.document_ref,
                "pdf_sha256": candidate.pdf_sha256,
                "page_ref": candidate.page_ref,
                "page_number": candidate.page_number,
                "table_ref": candidate.table_ref,
                "status": "not_grouped",
                "manual_review_required": bool(
                    reasons & _MANUAL_REASON_CODES
                ),
                "reason_codes": sorted(reasons),
            }
            decision["decision_checksum"] = sha256_json(decision)
            decisions.append(decision)
        decisions.sort(
            key=lambda item: (
                item["document_ref"],
                item["pdf_sha256"],
                item["page_number"],
                item["page_ref"],
                item["table_ref"],
                item["descriptor_ref"],
            )
        )

        input_refs = sorted(candidate.descriptor_ref for candidate in candidates)
        aggregate_reasons = {
            reason
            for decision in decisions
            for reason in decision["reason_codes"]
        }
        if groups:
            aggregate_reasons.add(_GROUPED_REASON)
        result = {
            "schema_version": PDF_CONTINUATION_DISCOVERY_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": self.policy_configuration_hash,
            "discovery_id": "pdfcontinuation_"
            + sha256_json(
                {
                    "policy_configuration_hash": self.policy_configuration_hash,
                    "input_descriptor_refs": input_refs,
                }
            )[:24],
            "status": "grouped" if groups else "not_grouped",
            "manual_review_required": any(
                decision["manual_review_required"] for decision in decisions
            ),
            "continuation_groups": groups,
            "not_grouped": decisions,
            "input_descriptor_refs": input_refs,
            "reason_codes": sorted(aggregate_reasons),
            "deterministic_geometry_only": True,
            "text_or_values_used": False,
            "vlm_used": False,
            "authoritative": False,
        }
        result["result_checksum"] = sha256_json(result)
        errors = self.validate(result)
        if errors:
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_discovery_result_invalid",
                ",".join(errors),
            )
        return result

    def validate(self, value: Any) -> list[str]:
        if not isinstance(value, dict):
            return ["pdf_continuation_discovery_not_object"]
        errors: list[str] = []
        if set(value) != _RESULT_KEYS:
            errors.append("pdf_continuation_discovery_contract_invalid")
        if (
            value.get("schema_version") != PDF_CONTINUATION_DISCOVERY_SCHEMA
            or value.get("policy_version") != self.config.policy_version
            or value.get("policy_configuration_hash")
            != self.policy_configuration_hash
        ):
            errors.append("pdf_continuation_discovery_policy_invalid")
        groups = value.get("continuation_groups")
        decisions = value.get("not_grouped")
        input_refs = value.get("input_descriptor_refs")
        if not isinstance(groups, list):
            groups = []
            errors.append("pdf_continuation_discovery_groups_invalid")
        if not isinstance(decisions, list):
            decisions = []
            errors.append("pdf_continuation_discovery_decisions_invalid")
        if (
            not isinstance(input_refs, list)
            or not all(isinstance(item, str) and item for item in input_refs)
            or input_refs != sorted(input_refs)
        ):
            input_refs = []
            errors.append("pdf_continuation_discovery_input_refs_invalid")
        accounted_refs: list[str] = []
        for group in groups:
            group_errors, fragment_refs = self._validate_group(group)
            errors.extend(group_errors)
            accounted_refs.extend(fragment_refs)
        for decision in decisions:
            decision_errors, descriptor_ref = _validate_decision(decision)
            errors.extend(decision_errors)
            if descriptor_ref:
                accounted_refs.append(descriptor_ref)
        if Counter(accounted_refs) != Counter(input_refs):
            errors.append("pdf_continuation_discovery_input_coverage_invalid")
        expected_status = "grouped" if groups else "not_grouped"
        if value.get("status") != expected_status:
            errors.append("pdf_continuation_discovery_status_invalid")
        expected_manual = any(
            isinstance(item, dict)
            and item.get("manual_review_required") is True
            for item in decisions
        )
        if value.get("manual_review_required") is not expected_manual:
            errors.append("pdf_continuation_discovery_manual_state_invalid")
        expected_reasons = {
            reason
            for decision in decisions
            if isinstance(decision, dict)
            for reason in decision.get("reason_codes") or []
            if isinstance(reason, str)
        }
        if groups:
            expected_reasons.add(_GROUPED_REASON)
        if value.get("reason_codes") != sorted(expected_reasons):
            errors.append("pdf_continuation_discovery_reasons_invalid")
        if (
            value.get("deterministic_geometry_only") is not True
            or value.get("text_or_values_used") is not False
            or value.get("vlm_used") is not False
            or value.get("authoritative") is not False
        ):
            errors.append("pdf_continuation_discovery_authority_invalid")
        expected_id = "pdfcontinuation_" + sha256_json(
            {
                "policy_configuration_hash": self.policy_configuration_hash,
                "input_descriptor_refs": input_refs,
            }
        )[:24]
        if value.get("discovery_id") != expected_id:
            errors.append("pdf_continuation_discovery_identity_invalid")
        unsigned = copy.deepcopy(value)
        stored_checksum = unsigned.pop("result_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_continuation_discovery_checksum_invalid")
        return sorted(set(errors))

    def _candidate(
        self, value: Any, *, input_ordinal: int
    ) -> _Candidate:
        if not isinstance(value, dict) or set(value) != _DESCRIPTOR_KEYS:
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_descriptor_contract_invalid",
                str(input_ordinal),
            )
        document_ref = _identity(value.get("document_ref"))
        pdf_sha256 = str(value.get("pdf_sha256") or "")
        page_ref = _identity(value.get("page_ref"))
        page_number = _positive_integer(value.get("page_number"))
        table_ref = _identity(value.get("table_ref"))
        if (
            document_ref is None
            or _SHA256.fullmatch(pdf_sha256) is None
            or page_ref is None
            or page_number is None
            or table_ref is None
        ):
            raise PdfContinuationDiscoveryError(
                "pdf_continuation_descriptor_identity_invalid",
                str(input_ordinal),
            )
        reasons: set[str] = set()
        page_width = _positive_number(value.get("page_width"))
        page_height = _positive_number(value.get("page_height"))
        if page_width is None or page_height is None:
            reasons.add("pdf_continuation_page_dimensions_missing")
        table_bbox = _bbox(
            value.get("table_bbox"),
            page_width=page_width,
            page_height=page_height,
        )
        if table_bbox is None:
            reasons.add("pdf_continuation_table_bbox_invalid")
        columns_total = _positive_integer(value.get("columns_total"))
        if columns_total is None:
            reasons.add("pdf_continuation_column_model_invalid")
        strategy = _identity(value.get("table_strategy_ref"))
        if strategy is None:
            reasons.add("pdf_continuation_strategy_invalid")
        confidence = _unit_interval(value.get("geometry_confidence"))
        if confidence is None:
            reasons.add("pdf_continuation_geometry_confidence_invalid")
        normalized = {
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "table_ref": table_ref,
            "page_width": page_width,
            "page_height": page_height,
            "table_bbox": list(table_bbox) if table_bbox is not None else None,
            "columns_total": columns_total,
            "table_strategy_ref": strategy,
            "geometry_confidence": confidence,
        }
        descriptor_ref = "pdfcontdesc_" + sha256_json(normalized)[:24]
        return _Candidate(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            page_width=page_width,
            page_height=page_height,
            table_bbox=table_bbox,
            columns_total=columns_total,
            table_strategy_ref=strategy,
            geometry_confidence=confidence,
            descriptor_ref=descriptor_ref,
            input_reason_codes=tuple(sorted(reasons)),
        )

    def _mark_duplicate_identities(
        self,
        candidates: list[_Candidate],
        reason_codes: dict[int, set[str]],
    ) -> None:
        identities: dict[tuple[str, str, int, str, str], list[int]] = defaultdict(
            list
        )
        for index, candidate in enumerate(candidates):
            identities[
                (
                    candidate.document_ref,
                    candidate.pdf_sha256,
                    candidate.page_number,
                    candidate.page_ref,
                    candidate.table_ref,
                )
            ].append(index)
        for indexes in identities.values():
            if len(indexes) > 1:
                for index in indexes:
                    reason_codes[index].add(
                        "pdf_continuation_descriptor_identity_duplicate"
                    )

    def _pair_evidence(
        self, left: _Candidate, right: _Candidate
    ) -> tuple[float | None, set[str]]:
        reasons: set[str] = set()
        if (
            left.document_ref != right.document_ref
            or left.pdf_sha256 != right.pdf_sha256
        ):
            reasons.add("pdf_continuation_document_or_sha_mismatch")
        if right.page_number != left.page_number + 1:
            reasons.add("pdf_continuation_pages_nonadjacent")
        if (
            left.columns_total is None
            or right.columns_total is None
            or left.columns_total < self.config.minimum_columns
            or right.columns_total < self.config.minimum_columns
            or left.columns_total != right.columns_total
        ):
            reasons.add("pdf_continuation_column_model_mismatch")
        if (
            left.table_strategy_ref is None
            or right.table_strategy_ref is None
            or left.table_strategy_ref != right.table_strategy_ref
        ):
            reasons.add("pdf_continuation_strategy_mismatch")
        if (
            left.geometry_confidence is None
            or right.geometry_confidence is None
            or left.geometry_confidence
            < self.config.minimum_geometry_confidence
            or right.geometry_confidence
            < self.config.minimum_geometry_confidence
        ):
            reasons.add(
                "pdf_continuation_geometry_confidence_below_threshold"
            )
        overlap = _horizontal_normalized_iou(left, right)
        if (
            overlap is None
            or overlap < self.config.minimum_horizontal_normalized_iou
        ):
            reasons.add("pdf_continuation_horizontal_overlap_insufficient")
        return overlap, reasons

    def _mark_unpaired_edge_signals(
        self,
        *,
        candidates: list[_Candidate],
        bottom_by_document_page: dict[tuple[str, int], list[int]],
        top_by_document_page: dict[tuple[str, int], list[int]],
        reason_codes: dict[int, set[str]],
    ) -> None:
        all_bottom = {
            index
            for indexes in bottom_by_document_page.values()
            for index in indexes
        }
        all_top = {
            index for indexes in top_by_document_page.values() for index in indexes
        }
        for index in sorted(all_bottom):
            candidate = candidates[index]
            adjacent = top_by_document_page.get(
                (candidate.document_ref, candidate.page_number + 1), []
            )
            if adjacent:
                continue
            later = [
                other
                for other in sorted(all_top)
                if candidates[other].document_ref == candidate.document_ref
                and candidates[other].page_number > candidate.page_number + 1
            ]
            reason = (
                "pdf_continuation_pages_nonadjacent"
                if later
                else "pdf_continuation_edge_pair_incomplete"
            )
            reason_codes[index].add(reason)
            for other in later:
                reason_codes[other].add(
                    "pdf_continuation_pages_nonadjacent"
                )
        for index in sorted(all_top):
            candidate = candidates[index]
            adjacent = bottom_by_document_page.get(
                (candidate.document_ref, candidate.page_number - 1), []
            )
            if adjacent:
                continue
            earlier = [
                other
                for other in sorted(all_bottom)
                if candidates[other].document_ref == candidate.document_ref
                and candidates[other].page_number < candidate.page_number - 1
            ]
            reason = (
                "pdf_continuation_pages_nonadjacent"
                if earlier
                else "pdf_continuation_edge_pair_incomplete"
            )
            reason_codes[index].add(reason)
            for other in earlier:
                reason_codes[other].add(
                    "pdf_continuation_pages_nonadjacent"
                )

    def _group(
        self, left: _Candidate, right: _Candidate, overlap: float
    ) -> dict[str, Any]:
        fragments = [
            {
                "descriptor_ref": left.descriptor_ref,
                "fragment_order": 1,
                "page_ref": left.page_ref,
                "page_number": left.page_number,
                "table_ref": left.table_ref,
                "edge_role": "bottom_page_fragment",
                "normalized_edge_position": left.bottom_ratio,
            },
            {
                "descriptor_ref": right.descriptor_ref,
                "fragment_order": 2,
                "page_ref": right.page_ref,
                "page_number": right.page_number,
                "table_ref": right.table_ref,
                "edge_role": "top_page_fragment",
                "normalized_edge_position": right.top_ratio,
            },
        ]
        group = {
            "continuation_group_id": "pdfcontgroup_"
            + sha256_json(
                {
                    "policy_configuration_hash": self.policy_configuration_hash,
                    "document_ref": left.document_ref,
                    "pdf_sha256": left.pdf_sha256,
                    "descriptor_refs": [
                        left.descriptor_ref,
                        right.descriptor_ref,
                    ],
                }
            )[:24],
            "document_ref": left.document_ref,
            "pdf_sha256": left.pdf_sha256,
            "fragment_count": self.config.fragment_count,
            "shared_column_count": left.columns_total,
            "table_strategy_ref": left.table_strategy_ref,
            "horizontal_normalized_iou": overlap,
            "fragments": fragments,
        }
        group["group_checksum"] = sha256_json(group)
        return group

    def _validate_group(
        self, value: Any
    ) -> tuple[list[str], list[str]]:
        if not isinstance(value, dict):
            return ["pdf_continuation_group_not_object"], []
        errors: list[str] = []
        if set(value) != _GROUP_KEYS:
            errors.append("pdf_continuation_group_contract_invalid")
        fragments = value.get("fragments")
        fragment_refs: list[str] = []
        if not isinstance(fragments, list) or len(fragments) != 2:
            errors.append("pdf_continuation_group_fragments_invalid")
            fragments = []
        for expected_order, fragment in enumerate(fragments, start=1):
            if not isinstance(fragment, dict) or set(fragment) != _FRAGMENT_KEYS:
                errors.append("pdf_continuation_fragment_contract_invalid")
                continue
            descriptor_ref = fragment.get("descriptor_ref")
            if isinstance(descriptor_ref, str) and descriptor_ref:
                fragment_refs.append(descriptor_ref)
            else:
                errors.append("pdf_continuation_fragment_identity_invalid")
            expected_role = (
                "bottom_page_fragment"
                if expected_order == 1
                else "top_page_fragment"
            )
            edge = fragment.get("normalized_edge_position")
            if (
                fragment.get("fragment_order") != expected_order
                or fragment.get("edge_role") != expected_role
                or not _is_number(edge)
                or not 0.0 <= float(edge) <= 1.0
            ):
                errors.append("pdf_continuation_fragment_geometry_invalid")
        if len(fragments) == 2:
            left_page = _positive_integer(fragments[0].get("page_number"))
            right_page = _positive_integer(fragments[1].get("page_number"))
            left_edge = fragments[0].get("normalized_edge_position")
            right_edge = fragments[1].get("normalized_edge_position")
            if (
                left_page is None
                or right_page != left_page + 1
                or not _is_number(left_edge)
                or float(left_edge) < self.config.bottom_edge_minimum
                or not _is_number(right_edge)
                or float(right_edge) > self.config.top_edge_maximum
            ):
                errors.append("pdf_continuation_fragment_pair_invalid")
        if (
            value.get("fragment_count") != self.config.fragment_count
            or _positive_integer(value.get("shared_column_count")) is None
            or int(value.get("shared_column_count") or 0)
            < self.config.minimum_columns
            or not isinstance(value.get("table_strategy_ref"), str)
            or not value.get("table_strategy_ref")
            or not _is_number(value.get("horizontal_normalized_iou"))
            or float(value.get("horizontal_normalized_iou") or 0.0)
            < self.config.minimum_horizontal_normalized_iou
        ):
            errors.append("pdf_continuation_group_evidence_invalid")
        unsigned = copy.deepcopy(value)
        stored_checksum = unsigned.pop("group_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_continuation_group_checksum_invalid")
        return sorted(set(errors)), fragment_refs


def _validate_decision(value: Any) -> tuple[list[str], str | None]:
    if not isinstance(value, dict):
        return ["pdf_continuation_decision_not_object"], None
    errors: list[str] = []
    if set(value) != _DECISION_KEYS:
        errors.append("pdf_continuation_decision_contract_invalid")
    descriptor_ref = value.get("descriptor_ref")
    if not isinstance(descriptor_ref, str) or not descriptor_ref:
        descriptor_ref = None
        errors.append("pdf_continuation_decision_identity_invalid")
    reasons = value.get("reason_codes")
    if (
        value.get("status") != "not_grouped"
        or not isinstance(reasons, list)
        or not reasons
        or not all(isinstance(item, str) and item for item in reasons)
        or reasons != sorted(set(reasons))
    ):
        errors.append("pdf_continuation_decision_reasons_invalid")
        reasons = []
    expected_manual = bool(set(reasons) & _MANUAL_REASON_CODES)
    if value.get("manual_review_required") is not expected_manual:
        errors.append("pdf_continuation_decision_manual_state_invalid")
    unsigned = copy.deepcopy(value)
    stored_checksum = unsigned.pop("decision_checksum", None)
    if stored_checksum != sha256_json(unsigned):
        errors.append("pdf_continuation_decision_checksum_invalid")
    return sorted(set(errors)), descriptor_ref


def _candidate_sort_key(candidate: _Candidate) -> tuple[Any, ...]:
    bbox = candidate.table_bbox or (math.inf, math.inf, math.inf, math.inf)
    return (
        candidate.document_ref,
        candidate.pdf_sha256,
        candidate.page_number,
        candidate.page_ref,
        bbox[1],
        bbox[0],
        candidate.table_ref,
        candidate.descriptor_ref,
    )


def _horizontal_normalized_iou(
    left: _Candidate, right: _Candidate
) -> float | None:
    if not left.geometry_available or not right.geometry_available:
        return None
    assert left.page_width is not None
    assert right.page_width is not None
    assert left.table_bbox is not None
    assert right.table_bbox is not None
    left_interval = (
        left.table_bbox[0] / left.page_width,
        left.table_bbox[2] / left.page_width,
    )
    right_interval = (
        right.table_bbox[0] / right.page_width,
        right.table_bbox[2] / right.page_width,
    )
    intersection = max(
        0.0,
        min(left_interval[1], right_interval[1])
        - max(left_interval[0], right_interval[0]),
    )
    union = (
        max(left_interval[1], right_interval[1])
        - min(left_interval[0], right_interval[0])
    )
    if union <= 0.0:
        return None
    return _rounded(intersection / union)


def _bbox(
    value: Any,
    *,
    page_width: float | None,
    page_height: float | None,
) -> tuple[float, float, float, float] | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or not all(_is_number(item) for item in value)
    ):
        return None
    result = tuple(_rounded(float(item)) for item in value)
    if (
        page_width is None
        or page_height is None
        or result[0] < 0.0
        or result[1] < 0.0
        or result[2] <= result[0]
        or result[3] <= result[1]
        or result[2] > page_width
        or result[3] > page_height
    ):
        return None
    return result


def _identity(value: Any) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 256:
        return None
    return value


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _positive_number(value: Any) -> float | None:
    if not _is_number(value) or float(value) <= 0.0:
        return None
    return _rounded(float(value))


def _unit_interval(value: Any) -> float | None:
    if not _is_number(value) or not 0.0 <= float(value) <= 1.0:
        return None
    return _rounded(float(value))


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _rounded(value: float) -> float:
    return round(value, 6)
