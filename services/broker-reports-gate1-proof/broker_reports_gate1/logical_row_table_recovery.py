from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import statistics
import unicodedata
from dataclasses import dataclass, field as dataclass_field, replace
from typing import Any, Mapping, Sequence

from .source_bound_table_scope import (
    SourceBoundTableScopeFactory,
    SourceBoundTableScopeReceipt,
)


FACTORY_REQUIRED = (
    "LogicalRowTableFactory.create is the sole construction route for the "
    "inactive managed-document-v2 logical-row recovery runtime"
)
FORBIDDEN = (
    "Recovery must not select behavior by filename, path, document id, source "
    "hash, customer value, page number, prior grid owner, provider output, or "
    "visual-gold content"
)

RECOVERY_SCHEMA_VERSION = "broker_reports_logical_row_table_recovery_v1"
RECOVERY_POLICY_VERSION = "logical_row_geometry_recovery_policy_v1"
PDF_PROJECTION_SCHEMA_VERSION = "pdf_text_layer_projection_v0"

_TOTAL_PREFIXES = (
    "grand total",
    "total",
    "overall total",
    "общий итог",
    "итого",
    "всего",
)
_SUBTOTAL_PREFIXES = (
    "subtotal",
    "sub total",
    "итого по",
    "подытог",
    "промежуточный итог",
)
_NOTE_PREFIXES = (
    "note",
    "notes",
    "footnote",
    "примечание",
    "примечания",
)
_CONTINUATION_MARKERS = (
    "continued",
    "continuation",
    "продолжение",
)
_UNIT_PATTERN = re.compile(
    r"^(?:%|[$€£¥]|usd|eur|gbp|rub|rur|cny|jpy|chf|cad|aud|шт\.?|pcs\.?)$",
    flags=re.IGNORECASE,
)
_CURRENCY_MARKER_PATTERN = re.compile(
    r"^(?:[$€£¥]|usd|eur|gbp|rub|rur|cny|jpy|chf|cad|aud)$",
    flags=re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(
    r"^[\(\[]?[+\-−]?(?:\d{1,3}(?:[\s,.'’]\d{3})+|\d+)(?:[.,]\d+)?"
    r"(?:\s*%)?[\)\]]?$"
)
_MARKER_PATTERN = re.compile(r"^(?:[-–—•·▪◦]|\(?[a-zа-я]\)|\d+[.)])$", re.I)

_SCOPE_SEPARATOR_NONE = "NONE"
_SCOPE_SEPARATOR_LOCAL = "LOCAL"
_SCOPE_SEPARATOR_AMBIGUOUS = "AMBIGUOUS"
_SCOPE_SEPARATOR_FULL = "FULL"


class LogicalRowTableRecoveryError(ValueError):
    """Raised when the normalized PDF projection cannot be recovered safely."""


def logical_table_block_id(table_id: str) -> str:
    """Return the v2 builder's deterministic block id for a recovered table."""

    if not re.fullmatch(r"table_[a-z0-9][a-z0-9_-]{2,127}", table_id):
        raise LogicalRowTableRecoveryError("logical_row_table_id_invalid")
    return f"block_logical_table_{table_id.removeprefix('table_')}"


@dataclass(frozen=True)
class LogicalRowTableRecoveryConfig:
    max_words: int = 100_000
    max_candidates: int = 5_000
    row_y_tolerance_ratio: float = 0.55
    entry_gap_height_ratio: float = 1.15
    boundary_gap_height_ratio: float = 2.6
    indentation_height_ratio: float = 0.8
    column_tolerance_width_ratio: float = 0.035
    minimum_column_observations: int = 3
    continuation_top_ratio: float = 0.24
    continuation_bottom_ratio: float = 0.76


@dataclass(frozen=True)
class LogicalRowTableRecoveryResult:
    schema_version: str
    recovery_policy_version: str
    tables: list[dict[str, Any]]
    anchors: list[dict[str, Any]]
    geometry_evidence: list[dict[str, Any]]
    source_word_ownership: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    # Exact complement of table-owned words. The document builder may emit
    # these through its paragraph/other-block owner; this recovery owner does
    # not itself assign non-table block semantics.
    paragraph_owned_word_refs: list[str]
    unowned_word_refs: list[str]
    diagnostics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "schema_version": self.schema_version,
                "recovery_policy_version": self.recovery_policy_version,
                "tables": self.tables,
                "anchors": self.anchors,
                "geometry_evidence": self.geometry_evidence,
                "source_word_ownership": self.source_word_ownership,
                "issues": self.issues,
                "paragraph_owned_word_refs": self.paragraph_owned_word_refs,
                "unowned_word_refs": self.unowned_word_refs,
                "diagnostics": self.diagnostics,
            }
        )


@dataclass(frozen=True)
class _Page:
    page_ref: str
    page_number: int
    width: float
    height: float


@dataclass(frozen=True)
class _Word:
    word_ref: str
    page_ref: str
    text: str
    bbox: tuple[float, float, float, float]
    order: int


@dataclass(frozen=True)
class _ObjectGeometry:
    object_ref: str
    page_ref: str
    bbox: tuple[float, float, float, float]
    object_kind: str


@dataclass
class _EntryBand:
    words: list[_Word]
    bbox: tuple[float, float, float, float]
    text: str
    anchor_ids: list[str]
    geometry_evidence_id: str | None = None
    entry_id: str | None = None
    logical_column_id: str | None = None
    covers_logical_column_ids: list[str] = dataclass_field(default_factory=list)
    column_binding_status: str = "NOT_APPLICABLE"
    geometry_column_ordinals: list[int] | None = None
    # A source rule may prove a wider logical header scope than the glyph box.
    # This remains internal evidence: public bindings are still materialized
    # only after logical tracks have been proven independently.
    proven_header_coverage_bbox: tuple[float, float, float, float] | None = None


@dataclass
class _RowBand:
    page_ref: str
    bbox: tuple[float, float, float, float]
    words: list[_Word]
    entries: list[_EntryBand]
    role: str = "UNKNOWN"
    nesting_level: int = 0
    parent_row_id: str | None = None
    row_id: str | None = None
    anchor_ids: list[str] | None = None
    geometry_evidence_id: str | None = None
    issue_ids: list[str] | None = None
    external_title: bool = False
    external_note: bool = False
    # Immutable structural input for logical-column discovery when a later
    # word-exact microtrack pass decomposes one physical entry.  These entries
    # are never materialized and never own source words; emitted entry evidence
    # always comes from ``entries`` above.
    column_evidence_entries: tuple[_EntryBand, ...] | None = None
    # Physical pre-coalescence rows used only to recover optional column
    # tracks.  Canonical row and entry evidence is always materialized from
    # this row itself; these snapshots never receive ids or own source words.
    column_evidence_rows: tuple[_RowBand, ...] | None = None
    row_coalescence_kind: str | None = None
    # Set only by the strict leading ruled-header proof.  Plain numeric values
    # remain values; this bit lets the post-binding kind pass distinguish a
    # source column-number band from an ordinary numeric body row.
    sequential_marker_header: bool = False
    # Set only by the immutable unruled leading-suffix proof prepared while
    # page-object geometry is still available.
    proven_leading_suffix_header: bool = False
    # Semantic uncertainty decided by the table-wide immutable row plan.  The
    # public issue ledger is materialized only after the complete plan passes.
    semantic_issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _LeadingHeaderRolePlan:
    source_fingerprint_sha256: str
    marker_row_index: int | None
    promoted_header_row_indexes: tuple[int, ...]


@dataclass(frozen=True)
class _StableHeaderEvidence:
    signatures: tuple[tuple[str, ...], ...]
    body_supported: bool
    source_proven: bool


@dataclass(frozen=True)
class _UnruledSuffixHeaderEntryDecision:
    row_index: int
    entry_index: int
    coverage_bbox: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class _UnruledSuffixHeaderDecision:
    region_index: int
    root_row_word_refs: tuple[str, ...]
    proof_kind: str
    entry_decisions: tuple[_UnruledSuffixHeaderEntryDecision, ...]


@dataclass(frozen=True)
class _UnruledSuffixHeaderPlan:
    source_fingerprint_sha256: str
    decisions: tuple[_UnruledSuffixHeaderDecision, ...]


@dataclass(frozen=True)
class _OrderedRowSemanticDecision:
    ordinal: int
    role: str
    nesting_level: int
    parent_ordinal: int | None
    group_scope_end_ordinal: int | None
    issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _OrderedRowSemanticPlan:
    source_fingerprint_sha256: str
    decisions: tuple[_OrderedRowSemanticDecision, ...]


@dataclass(frozen=True)
class _RuledBaselineOutputRowPlan:
    word_refs: tuple[str, ...]
    entry_word_ref_groups: tuple[tuple[str, ...], ...]
    geometry_column_ordinals: tuple[tuple[int, ...] | None, ...]
    row_coalescence_kind: str | None = None
    evidence_entry_word_ref_groups: (
        tuple[tuple[tuple[str, ...], ...], ...] | None
    ) = None
    external_title: bool = False
    external_note: bool = False


@dataclass(frozen=True)
class _RuledBaselineRecoveryPlan:
    plan_id: str
    page_ref: str
    core_word_refs: tuple[str, ...]
    source_fingerprint_sha256: str
    output_rows: tuple[_RuledBaselineOutputRowPlan, ...]
    original_ruled_column_bands: tuple[tuple[float, float], ...]
    title_pseudorule_ref_groups: tuple[tuple[str, ...], ...]
    wrapped_label_ref_groups: tuple[tuple[str, ...], ...]
    released_non_table_word_refs: tuple[str, ...] = ()
    requires_boundary_bracket: bool = True
    boundary_bracket_proven: bool = False
    attached_leading_row_ref_groups: tuple[tuple[str, ...], ...] = ()
    attached_trailing_row_ref_groups: tuple[tuple[str, ...], ...] = ()


@dataclass
class _Region:
    source_ref: str
    page: _Page
    bbox: tuple[float, float, float, float]
    words: list[_Word]
    rows: list[_RowBand]
    confidence: float
    origin: str
    object_refs: list[str]
    ruled_column_bands: list[tuple[float, float]] | None = None
    # Internal-only proof that a parser candidate was physically shaped as a
    # short singleton followed by one mirrored four-entry seed band.  It is
    # deliberately not part of the managed-document contract.  A later
    # same-page reconciliation may consume it only when two independently
    # discovered continuation lanes match the two seeds uniquely.
    mirrored_lane_seed: bool = False
    ruled_baseline_recovery_plan: _RuledBaselineRecoveryPlan | None = None
    released_non_table_word_refs: tuple[str, ...] = ()
    continuation_issue_codes: tuple[str, ...] = ()
    source_bound_scope_ref: str | None = None
    source_bound_binding_status: str | None = None
    source_bound_structural_authority: bool = False
    source_bound_proposal_sha256: str | None = None
    source_bound_raster_manifest_hash: str | None = None
    source_bound_receipt_title_word_refs: tuple[str, ...] = ()
    source_bound_receipt_header_word_ref_groups: tuple[tuple[str, ...], ...] = ()
    source_bound_receipt_body_word_refs: tuple[str, ...] = ()
    source_bound_title_word_refs: tuple[str, ...] = ()
    source_bound_header_status: str | None = None
    source_bound_header_word_ref_groups: tuple[tuple[str, ...], ...] = ()
    source_bound_header_signatures: tuple[tuple[str, ...], ...] = ()
    source_bound_body_word_refs: tuple[str, ...] = ()
    source_bound_issue_codes: tuple[str, ...] = ()


@dataclass
class _ColumnTrack:
    edge: str
    coordinate: float
    tolerance: float
    entries: list[_EntryBand]
    row_indexes: set[int]


@dataclass(frozen=True)
class _ColumnEvidenceLineage:
    """Word-exact physical observations mapped to canonical row entries."""

    rows: tuple[_RowBand, ...]
    canonical_children_by_parent: Mapping[int, tuple[_EntryBand, ...]]
    parents_by_canonical_child: Mapping[int, tuple[_EntryBand, ...]]
    canonical_row_by_evidence_row: Mapping[int, _RowBand]
    snapshot_backed_canonical_rows: frozenset[int]


@dataclass(frozen=True)
class _EntryColumnBindingPlan:
    """One immutable entry binding prepared before public state is changed."""

    entry: _EntryBand
    logical_column_ordinal: int | None = None
    covered_column_ordinals: tuple[int, ...] = ()


@dataclass(frozen=True)
class _LogicalColumnMaterializationPlan:
    """One proven logical column inside a fail-closed scope plan."""

    track: _ColumnTrack
    key: tuple[Any, ...]
    alignment_source: str
    material: Mapping[str, Any]


@dataclass(frozen=True)
class _ColumnMaterializationScopePlan:
    """All columns and bindings committed together or not at all."""

    source_fingerprint_sha256: str
    plan_fingerprint_sha256: str
    columns: tuple[_LogicalColumnMaterializationPlan, ...]
    bindings: tuple[_EntryColumnBindingPlan, ...]


@dataclass(frozen=True)
class _LegacyPostTrackBindingDecision:
    """One canonical entry assignment after legacy tracks are immutable."""

    row_index: int
    entry_index: int
    track_ordinal: int
    proof_kind: str


@dataclass(frozen=True)
class _LegacyPostTrackBindingPlan:
    """Fingerprint-bound legacy bindings committed together or not at all."""

    source_fingerprint_sha256: str
    minimum_column_observations: int
    decisions: tuple[_LegacyPostTrackBindingDecision, ...]


@dataclass(frozen=True)
class _LegacyActiveTrackBindingPlan:
    """Bindings proven only after the logical track subset is immutable."""

    source_fingerprint_sha256: str
    minimum_column_observations: int
    active_track_ordinals: tuple[int, ...]
    decisions: tuple[_LegacyPostTrackBindingDecision, ...]


class LogicalRowTableFactory:
    """Sole factory for deterministic row-first table recovery."""

    def __init__(
        self,
        config: LogicalRowTableRecoveryConfig | None = None,
    ) -> None:
        self.config = config or LogicalRowTableRecoveryConfig()

    def create(self) -> "LogicalRowTableRecoveryRuntime":
        _validate_config(self.config)
        return LogicalRowTableRecoveryRuntime(self.config)


class LogicalRowTableRecoveryRuntime:
    """Consumes only the public normalized PDF text-layer projection."""

    def __init__(self, config: LogicalRowTableRecoveryConfig) -> None:
        self.config = config

    def recover(
        self,
        pdf_text_layer_projection: Mapping[str, Any],
        *,
        source_checksum_sha256: str,
        private_evidence_ref: str,
    ) -> LogicalRowTableRecoveryResult:
        return self._recover(
            pdf_text_layer_projection,
            source_checksum_sha256=source_checksum_sha256,
            private_evidence_ref=private_evidence_ref,
            source_bound_scope_receipts=(),
        )

    def recover_with_source_bound_scopes(
        self,
        *,
        full_source_payload: Mapping[str, Any],
        source_checksum_sha256: str,
        private_evidence_ref: str,
        source_bound_scope_requests: tuple[Mapping[str, Any], ...],
    ) -> LogicalRowTableRecoveryResult:
        """Bind original geometry and recover inside one factory-routed call."""

        if not isinstance(full_source_payload, dict) or not isinstance(
            source_bound_scope_requests, tuple
        ) or not source_bound_scope_requests:
            raise LogicalRowTableRecoveryError(
                "logical_row_source_bound_scope_requests_invalid"
            )
        payload = copy.deepcopy(full_source_payload)
        receipts: list[SourceBoundTableScopeReceipt] = []
        for request in source_bound_scope_requests:
            if not isinstance(request, Mapping) or set(request) != {
                "proposal",
                "page_ref",
                "page_number",
                "raster_manifest",
            }:
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_scope_requests_invalid"
                )
            bound = (
                SourceBoundTableScopeFactory()
                .create()
                .bind(
                    proposal=request["proposal"],
                    full_source_payload=payload,
                    source_checksum_sha256=source_checksum_sha256,
                    page_ref=request["page_ref"],
                    page_number=request["page_number"],
                    raster_manifest=request["raster_manifest"],
                )
            )
            receipts.extend(bound.scopes)
        projection = payload.get("pdf_text_layer_projection")
        if not isinstance(projection, Mapping):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_bound_scope_requests_invalid"
            )
        return self._recover(
            projection,
            source_checksum_sha256=source_checksum_sha256,
            private_evidence_ref=private_evidence_ref,
            source_bound_scope_receipts=tuple(receipts),
        )

    def _recover(
        self,
        pdf_text_layer_projection: Mapping[str, Any],
        *,
        source_checksum_sha256: str,
        private_evidence_ref: str,
        source_bound_scope_receipts: tuple[SourceBoundTableScopeReceipt, ...],
    ) -> LogicalRowTableRecoveryResult:
        projection = _projection_copy(pdf_text_layer_projection)
        _validate_recovery_inputs(
            projection,
            source_checksum_sha256=source_checksum_sha256,
            private_evidence_ref=private_evidence_ref,
            config=self.config,
        )
        pages = _materialize_pages(projection)
        bbox_by_ref = _materialize_bboxes(projection)
        words = _materialize_words(projection, bbox_by_ref=bbox_by_ref)
        source_word_refs = frozenset(word.word_ref for word in words)
        page_by_ref = {page.page_ref: page for page in pages}
        words_by_page: dict[str, list[_Word]] = {}
        for word in words:
            words_by_page.setdefault(word.page_ref, []).append(word)

        object_bboxes = _materialize_object_bboxes(
            projection,
            bbox_by_ref=bbox_by_ref,
        )
        regions = _candidate_regions(
            projection,
            bbox_by_ref=bbox_by_ref,
            words=words,
            page_by_ref=page_by_ref,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        regions.extend(
            _discover_aligned_regions(
                words_by_page=words_by_page,
                pages=pages,
                occupied=regions,
                object_bboxes=object_bboxes,
                config=self.config,
            )
        )
        regions = _reconcile_adjacent_mirrored_lanes(
            regions,
            config=self.config,
        )
        regions = _plan_unique_ruled_baseline_recovery(
            regions,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        regions = _attach_unique_boundary_brackets(
            regions,
            words_by_page=words_by_page,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        regions = _attach_unique_leading_header_stacks(
            regions,
            words_by_page=words_by_page,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        regions = _apply_planned_ruled_baseline_recovery(regions)
        regions = _split_repeated_microtrack_entries(
            regions,
            config=self.config,
        )
        regions = _coalesce_logical_row_fragments(
            regions,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        suffix_header_plan = _plan_unruled_leading_suffix_headers(
            regions,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        _apply_unruled_leading_suffix_header_plan(
            regions,
            plan=suffix_header_plan,
            object_bboxes=object_bboxes,
        )
        regions = _partition_region_words(regions, config=self.config)
        regions = _reconcile_same_page_table_scopes(
            regions,
            words_by_page=words_by_page,
            object_bboxes=object_bboxes,
            config=self.config,
        )
        detached_scope_issue_codes: tuple[str, ...] = ()
        if source_bound_scope_receipts:
            regions, detached_scope_issue_codes = _apply_source_bound_table_scopes(
                regions,
                scopes=source_bound_scope_receipts,
                projection=projection,
                source_checksum_sha256=source_checksum_sha256,
                pages=pages,
                words=words,
                config=self.config,
            )
        accepted_retained_refs, accepted_released_refs = (
            _source_accounting_scope(regions)
        )
        accepted_scope_refs = frozenset(
            {*accepted_retained_refs, *accepted_released_refs}
        )
        if not accepted_scope_refs.issubset(source_word_refs):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_scope_invalid"
            )
        groups = _group_continuations(regions, config=self.config)
        grouped_regions = [region for group in groups for region in group]
        grouped_retained_refs, released_non_table_word_refs = (
            _source_accounting_scope(grouped_regions)
        )
        if (
            accepted_scope_refs
            != {*grouped_retained_refs, *released_non_table_word_refs}
            or grouped_retained_refs.intersection(
                released_non_table_word_refs
            )
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_scope_invalid"
            )

        state = _RecoveryState(
            source_checksum_sha256=source_checksum_sha256.lower(),
            private_evidence_ref=private_evidence_ref,
            bbox_by_ref=bbox_by_ref,
        )
        for code in detached_scope_issue_codes:
            state.add_issue(
                code=code,
                message=_source_bound_scope_issue_message(code),
                anchor_ids=[],
                block_ids=[],
            )
        tables = [
            _materialize_logical_table(group, state=state, config=self.config)
            for group in groups
        ]
        owner_source_word_ids = [
            str(item["source_word_id"])
            for item in state.source_word_ownership
        ]
        owner_word_refs = [
            state.word_ref_by_source_word_id.get(source_word_id, "")
            for source_word_id in owner_source_word_ids
        ]
        multiple_word_owners_total = len(owner_word_refs) - len(
            set(owner_word_refs)
        )
        if (
            any(not word_ref for word_ref in owner_word_refs)
            or len(owner_source_word_ids) != len(set(owner_source_word_ids))
            or multiple_word_owners_total
            or len(owner_word_refs) != len(grouped_retained_refs)
            or set(owner_word_refs) != grouped_retained_refs
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_materialization_invalid"
            )
        paragraph_word_ref_set = frozenset(
            {
                *(source_word_refs - accepted_scope_refs),
                *released_non_table_word_refs,
            }
        )
        paragraph_owned_word_refs = sorted(paragraph_word_ref_set)
        owner_word_ref_set = frozenset(owner_word_refs)
        all_accounted_refs = {
            *paragraph_word_ref_set,
            *owner_word_ref_set,
        }
        unowned_word_refs = sorted(
            word.word_ref for word in words if word.word_ref not in all_accounted_refs
        )
        if (
            owner_word_ref_set.intersection(paragraph_word_ref_set)
            or all_accounted_refs != source_word_refs
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_materialization_invalid"
            )

        return LogicalRowTableRecoveryResult(
            schema_version=RECOVERY_SCHEMA_VERSION,
            recovery_policy_version=RECOVERY_POLICY_VERSION,
            tables=tables,
            anchors=state.anchors,
            geometry_evidence=state.geometry_evidence,
            source_word_ownership=state.source_word_ownership,
            issues=state.issues,
            paragraph_owned_word_refs=paragraph_owned_word_refs,
            unowned_word_refs=unowned_word_refs,
            diagnostics={
                "projection_schema_version": projection["schema_version"],
                "pages_total": len(pages),
                "words_total": len(words),
                "candidate_regions_total": sum(
                    region.origin == "PARSER_CANDIDATE" for region in regions
                ),
                "aligned_regions_total": sum(
                    region.origin == "ALIGNED_DISCOVERY" for region in regions
                ),
                "logical_tables_total": len(tables),
                "continued_tables_total": sum(len(group) > 1 for group in groups),
                "logical_rows_total": sum(
                    len(table["ordered_rows"]) for table in tables
                ),
                "entries_total": sum(
                    len(row["entries"])
                    for table in tables
                    for row in table["ordered_rows"]
                ),
                "table_words_total": len(owner_word_ref_set),
                "paragraph_words_total": len(paragraph_owned_word_refs),
                "unowned_words_total": len(unowned_word_refs),
                "multiple_word_owners_total": multiple_word_owners_total,
                "provider_calls": 0,
                "visual_gold_reads": 0,
                "pdf_layout_units_consumed": 0,
                "grid_owner_calls": 0,
                **(
                    {
                        "source_bound_scope_receipts_total": len(
                            source_bound_scope_receipts
                        ),
                        "source_bound_scope_receipts_partial": sum(
                            scope.binding_status == "PARTIAL"
                            for scope in source_bound_scope_receipts
                        )
                        + len(detached_scope_issue_codes),
                    }
                    if source_bound_scope_receipts
                    else {}
                ),
            },
        )


class _RecoveryState:
    def __init__(
        self,
        *,
        source_checksum_sha256: str,
        private_evidence_ref: str,
        bbox_by_ref: dict[str, tuple[float, float, float, float]],
    ) -> None:
        self.source_checksum_sha256 = source_checksum_sha256
        self.private_evidence_ref = private_evidence_ref.rstrip("#/")
        self.bbox_by_ref = bbox_by_ref
        self.anchors: list[dict[str, Any]] = []
        self.geometry_evidence: list[dict[str, Any]] = []
        self.source_word_ownership: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = []
        self.anchor_ids: set[str] = set()
        self.word_ref_by_source_word_id: dict[str, str] = {}

    def anchor_for_word(self, word: _Word, *, page_number: int) -> str:
        anchor_id = _identifier("anchor", ["word", word.word_ref])
        if anchor_id in self.anchor_ids:
            return anchor_id
        private_checksum = _sha256_json(
            [word.page_ref, word.word_ref, list(word.bbox)]
        )
        self.anchors.append(
            {
                "information_class": "PROVENANCE",
                "anchor_id": anchor_id,
                "source_format": "PDF",
                "checksum_sha256": _sha256_json(
                    [self.source_checksum_sha256, word.word_ref, word.text]
                ),
                "locator": {
                    "kind": "PDF",
                    "source_part_index": page_number,
                    "page": page_number,
                    "source_block_ref": word.word_ref,
                    "bbox": list(word.bbox),
                    "private_locator": {
                        "information_class": "PRIVATE_SOURCE",
                        "status": "PRESENT",
                        "ref": f"{self.private_evidence_ref}#{anchor_id}",
                        "checksum_sha256": private_checksum,
                    },
                },
            }
        )
        self.anchor_ids.add(anchor_id)
        return anchor_id

    def anchor_for_region(
        self,
        *,
        page: _Page,
        bbox: tuple[float, float, float, float],
        source_ref: str,
    ) -> str:
        anchor_id = _identifier(
            "anchor", ["region", page.page_ref, source_ref, list(bbox)]
        )
        if anchor_id in self.anchor_ids:
            return anchor_id
        checksum = _sha256_json([page.page_ref, source_ref, list(bbox)])
        self.anchors.append(
            {
                "information_class": "PROVENANCE",
                "anchor_id": anchor_id,
                "source_format": "PDF",
                "checksum_sha256": _sha256_json(
                    [self.source_checksum_sha256, checksum]
                ),
                "locator": {
                    "kind": "PDF",
                    "source_part_index": page.page_number,
                    "page": page.page_number,
                    "source_block_ref": source_ref,
                    "bbox": list(bbox),
                    "private_locator": {
                        "information_class": "PRIVATE_SOURCE",
                        "status": "PRESENT",
                        "ref": f"{self.private_evidence_ref}#{anchor_id}",
                        "checksum_sha256": checksum,
                    },
                },
            }
        )
        self.anchor_ids.add(anchor_id)
        return anchor_id

    def add_geometry(
        self,
        *,
        kind: str,
        key: Sequence[Any],
        anchor_ids: list[str],
        material: Mapping[str, Any],
        issue_ids: list[str] | None = None,
    ) -> str:
        evidence_id = _identifier("geometry", [kind, *key])
        checksum = _sha256_json(material)
        self.geometry_evidence.append(
            {
                "information_class": "PRIVATE_SOURCE",
                "geometry_evidence_id": evidence_id,
                "kind": kind,
                "origin": "DETERMINISTIC_DERIVED",
                "source_anchor_ids": _unique(anchor_ids),
                "private_artifact": {
                    "information_class": "PRIVATE_SOURCE",
                    "status": "PRESENT",
                    "ref": f"{self.private_evidence_ref}#{evidence_id}",
                    "checksum_sha256": checksum,
                },
                "evidence_checksum_sha256": checksum,
                "issue_ids": list(issue_ids or []),
            }
        )
        return evidence_id

    def add_issue(
        self,
        *,
        code: str,
        message: str,
        anchor_ids: list[str],
        block_ids: list[str],
    ) -> str:
        issue_id = _identifier("issue", [code, *anchor_ids])
        self.issues.append(
            {
                "issue_id": issue_id,
                "code": code,
                "severity": "WARNING",
                "message": message,
                "anchor_ids": _unique(anchor_ids),
                "block_ids": _unique(block_ids),
                "relation_ids": [],
                "recoverability": "RECOVERABLE",
                "requires_source_reread": False,
            }
        )
        return issue_id


def _validate_config(config: LogicalRowTableRecoveryConfig) -> None:
    if config.max_words < 1 or config.max_candidates < 1:
        raise LogicalRowTableRecoveryError("logical_row_recovery_budget_invalid")
    ratios = (
        config.row_y_tolerance_ratio,
        config.entry_gap_height_ratio,
        config.boundary_gap_height_ratio,
        config.indentation_height_ratio,
        config.column_tolerance_width_ratio,
        config.continuation_top_ratio,
        config.continuation_bottom_ratio,
    )
    if any(not math.isfinite(item) or item <= 0.0 for item in ratios):
        raise LogicalRowTableRecoveryError("logical_row_recovery_ratio_invalid")
    if not 0.0 < config.continuation_top_ratio < config.continuation_bottom_ratio < 1.0:
        raise LogicalRowTableRecoveryError(
            "logical_row_recovery_continuation_ratio_invalid"
        )
    if config.minimum_column_observations < 2:
        raise LogicalRowTableRecoveryError(
            "logical_row_recovery_column_observations_invalid"
        )


def _projection_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise LogicalRowTableRecoveryError("logical_row_projection_invalid")
    return copy.deepcopy(dict(value))


def _validate_recovery_inputs(
    projection: dict[str, Any],
    *,
    source_checksum_sha256: str,
    private_evidence_ref: str,
    config: LogicalRowTableRecoveryConfig,
) -> None:
    if projection.get("schema_version") != PDF_PROJECTION_SCHEMA_VERSION:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_schema_version_invalid"
        )
    required_lists = (
        "page_inventory",
        "bbox_inventory",
        "word_inventory",
        "line_inventory",
        "block_inventory",
        "vector_line_inventory",
        "rect_inventory",
        "table_candidate_inventory",
    )
    if any(not isinstance(projection.get(key), list) for key in required_lists):
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_public_shape_invalid"
        )
    if len(projection["word_inventory"]) > config.max_words:
        raise LogicalRowTableRecoveryError("logical_row_projection_word_budget_exceeded")
    if len(projection["table_candidate_inventory"]) > config.max_candidates:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_candidate_budget_exceeded"
        )
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_checksum_sha256):
        raise LogicalRowTableRecoveryError("logical_row_source_checksum_invalid")
    if not isinstance(private_evidence_ref, str) or not private_evidence_ref.strip():
        raise LogicalRowTableRecoveryError(
            "logical_row_private_evidence_ref_invalid"
        )
    if len(private_evidence_ref) > 180:
        raise LogicalRowTableRecoveryError(
            "logical_row_private_evidence_ref_too_long"
        )
    for key, field in (
        ("page_inventory", "page_ref"),
        ("bbox_inventory", "bbox_ref"),
        ("word_inventory", "word_ref"),
        ("line_inventory", "line_ref"),
        ("block_inventory", "block_ref"),
        ("table_candidate_inventory", "table_candidate_ref"),
    ):
        values = [
            str(item.get(field) or "")
            for item in _dicts(projection[key])
        ]
        if any(not item for item in values) or len(values) != len(set(values)):
            raise LogicalRowTableRecoveryError(
                f"logical_row_projection_{field}_invalid"
            )


def _materialize_pages(projection: dict[str, Any]) -> list[_Page]:
    pages = []
    for raw in _dicts(projection["page_inventory"]):
        page_number = _positive_int(raw.get("page_number"))
        page_ref = str(raw.get("page_ref") or "")
        width = _positive_number(
            raw.get("layout_page_width") or raw.get("width") or 1.0
        )
        height = _positive_number(
            raw.get("layout_page_height") or raw.get("height") or 1.0
        )
        pages.append(
            _Page(
                page_ref=page_ref,
                page_number=page_number,
                width=width,
                height=height,
            )
        )
    if not pages:
        return []
    if len({page.page_number for page in pages}) != len(pages):
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_page_number_invalid"
        )
    return sorted(pages, key=lambda item: item.page_number)


def _materialize_bboxes(
    projection: dict[str, Any],
) -> dict[str, tuple[float, float, float, float]]:
    result = {}
    for raw in _dicts(projection["bbox_inventory"]):
        bbox_ref = str(raw.get("bbox_ref") or "")
        result[bbox_ref] = _valid_bbox(raw.get("bbox"))
    return result


def _materialize_words(
    projection: dict[str, Any],
    *,
    bbox_by_ref: dict[str, tuple[float, float, float, float]],
) -> list[_Word]:
    page_refs = {
        str(item.get("page_ref") or "")
        for item in _dicts(projection["page_inventory"])
    }
    result = []
    for raw in _dicts(projection["word_inventory"]):
        page_ref = str(raw.get("page_ref") or "")
        bbox_ref = str(raw.get("bbox_ref") or "")
        if page_ref not in page_refs or bbox_ref not in bbox_by_ref:
            raise LogicalRowTableRecoveryError(
                "logical_row_projection_word_geometry_unresolved"
            )
        if (
            _bbox_width(bbox_by_ref[bbox_ref]) <= 0.0
            or _bbox_height(bbox_by_ref[bbox_ref]) <= 0.0
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_projection_word_bbox_invalid"
            )
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        result.append(
            _Word(
                word_ref=str(raw.get("word_ref") or ""),
                page_ref=page_ref,
                text=text,
                bbox=bbox_by_ref[bbox_ref],
                order=int(
                    raw.get("geometry_reading_order")
                    or raw.get("parser_ordinal")
                    or 0
                ),
            )
        )
    return sorted(
        result,
        key=lambda item: (item.page_ref, item.bbox[1], item.bbox[0], item.order),
    )


def _materialize_object_bboxes(
    projection: dict[str, Any],
    *,
    bbox_by_ref: dict[str, tuple[float, float, float, float]],
) -> list[_ObjectGeometry]:
    surfaces = (
        ("line_inventory", "line_ref"),
        ("block_inventory", "block_ref"),
        ("vector_line_inventory", "object_ref"),
        ("rect_inventory", "object_ref"),
    )
    result = []
    for key, ref_field in surfaces:
        for raw in _dicts(projection[key]):
            bbox = bbox_by_ref.get(str(raw.get("bbox_ref") or ""))
            page_ref = str(raw.get("page_ref") or "")
            object_ref = str(
                raw.get(ref_field)
                or raw.get("pdfvectorline_ref")
                or raw.get("pdfrect_ref")
                or ""
            )
            if bbox is not None and page_ref and object_ref:
                result.append(
                    _ObjectGeometry(
                        object_ref=object_ref,
                        page_ref=page_ref,
                        bbox=bbox,
                        object_kind=key,
                    )
                )
    return result


def _ruled_candidate_rows(
    candidate: dict[str, Any],
    *,
    selected_words: list[_Word],
    bbox_by_ref: dict[str, tuple[float, float, float, float]],
    table_bbox: tuple[float, float, float, float],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_RowBand] | None, list[tuple[float, float]] | None]:
    """Project occupied ruled geometry into logical rows, never grid cells."""

    raw_rows = sorted(
        _dicts(candidate.get("row_inventory")),
        key=lambda item: int(item.get("row_ordinal") or 0),
    )
    raw_cells = _dicts(candidate.get("cell_inventory"))
    columns_total = int(candidate.get("columns_total") or 0)
    if len(raw_rows) < 2 or columns_total < 2 or not raw_cells:
        return None, None
    if not _has_dual_axis_grid_topology(
        page_ref=str(candidate.get("page_ref") or ""),
        table_bbox=table_bbox,
        columns_total=columns_total,
        object_bboxes=object_bboxes,
    ):
        return None, None
    column_bands = _ruled_column_bands(
        raw_cells,
        columns_total=columns_total,
        bbox_by_ref=bbox_by_ref,
    )
    if len(column_bands) != columns_total:
        return None, None
    word_by_ref = {word.word_ref: word for word in selected_words}
    selected_refs = set(word_by_ref)
    owned_refs: list[str] = []
    result: list[_RowBand] = []
    for raw_row in raw_rows:
        row_ref = str(raw_row.get("row_ref") or "")
        row_ordinal = int(raw_row.get("row_ordinal") or 0)
        cells = sorted(
            (
                cell
                for cell in raw_cells
                if str(cell.get("row_ref") or "") == row_ref
                or int(cell.get("row_ordinal") or 0) == row_ordinal
            ),
            key=lambda item: (
                bbox_by_ref.get(str(item.get("bbox_ref") or ""), (0, 0, 0, 0))[0],
                int(item.get("column_ordinal") or 0),
            ),
        )
        entries: list[_EntryBand] = []
        row_words: list[_Word] = []
        occupied_bboxes: list[tuple[float, float, float, float]] = []
        for cell in cells:
            cell_bbox = bbox_by_ref.get(str(cell.get("bbox_ref") or ""))
            if cell_bbox is None:
                return None, None
            cell_words = [
                word_by_ref[ref]
                for ref in _strings(cell.get("word_refs"))
                if ref in word_by_ref
            ]
            if not cell_words:
                continue
            if len(cell_words) != len(_strings(cell.get("word_refs"))):
                return None, None
            cell_words = sorted(
                cell_words,
                key=lambda word: (word.bbox[1], word.bbox[0], word.order),
            )
            owned_refs.extend(word.word_ref for word in cell_words)
            row_words.extend(cell_words)
            occupied_bboxes.append(cell_bbox)
            typical_height = statistics.median(
                _bbox_height(word.bbox) for word in cell_words
            )
            word_groups = _entry_word_groups(
                sorted(cell_words, key=lambda word: (word.bbox[0], word.order)),
                typical_height=typical_height,
                config=config,
            )
            group_columns = [
                _word_group_columns(group, column_bands=column_bands)
                for group in word_groups
            ]
            split_proven = (
                len(word_groups) >= 2
                and all(len(columns) == 1 for columns in group_columns)
                and len({columns[0] for columns in group_columns})
                == len(group_columns)
                and [columns[0] for columns in group_columns]
                == sorted(columns[0] for columns in group_columns)
            )
            if split_proven:
                for group, columns in zip(word_groups, group_columns):
                    entries.append(
                        _entry_from_words(
                            group,
                            bbox=_merge_bboxes([word.bbox for word in group]),
                            geometry_column_ordinals=columns,
                        )
                    )
            else:
                entries.append(
                    _entry_from_words(
                        cell_words,
                        bbox=cell_bbox,
                        geometry_column_ordinals=_bbox_covered_columns(
                            cell_bbox,
                            column_bands=column_bands,
                        ),
                    )
                )
        if not entries:
            continue
        row_words = sorted(
            row_words,
            key=lambda word: (word.bbox[1], word.bbox[0], word.order),
        )
        entries.sort(key=lambda entry: (entry.bbox[0], entry.bbox[1]))
        result.append(
            _RowBand(
                page_ref=row_words[0].page_ref,
                bbox=_merge_bboxes(occupied_bboxes),
                words=row_words,
                entries=entries,
            )
        )
    if (
        len(owned_refs) != len(set(owned_refs))
        or set(owned_refs) != selected_refs
        or len(result) < 2
    ):
        return None, None
    return result, column_bands


def _has_dual_axis_grid_topology(
    *,
    page_ref: str,
    table_bbox: tuple[float, float, float, float],
    columns_total: int,
    object_bboxes: list[_ObjectGeometry],
) -> bool:
    """Require a physical 2D grid before using parser cell inventories.

    Horizontal rules alone are common in financial statements and do not make
    a row/cell grid.  Internal vertical tracks must persist through a material
    part of the candidate, and horizontal rules must establish row bands.
    """

    table_width = _bbox_width(table_bbox)
    table_height = _bbox_height(table_bbox)
    if table_width <= 0.0 or table_height <= 0.0:
        return False
    coordinate_tolerance = max(1.0, min(3.0, table_width * 0.004))
    vertical_segments: list[tuple[float, float, float]] = []
    horizontal_segments: list[tuple[float, float, float]] = []
    for item in object_bboxes:
        if (
            item.page_ref != page_ref
            or item.object_kind
            not in {"vector_line_inventory", "rect_inventory"}
            or not _bbox_overlap(item.bbox, table_bbox)
        ):
            continue
        clipped = (
            max(item.bbox[0], table_bbox[0]),
            max(item.bbox[1], table_bbox[1]),
            min(item.bbox[2], table_bbox[2]),
            min(item.bbox[3], table_bbox[3]),
        )
        width = _bbox_width(clipped)
        height = _bbox_height(clipped)
        if item.object_kind == "vector_line_inventory":
            if height >= max(3.0, width * 4.0):
                vertical_segments.append(
                    ((_bbox_center_x(clipped)), clipped[1], clipped[3])
                )
            if width >= max(3.0, height * 4.0):
                horizontal_segments.append(
                    (((clipped[1] + clipped[3]) / 2.0), clipped[0], clipped[2])
                )
            continue

        # Rectangles contribute their four physical edges.  A lone outer box
        # has no internal X track, so it cannot satisfy this gate by itself.
        vertical_segments.extend(
            [
                (clipped[0], clipped[1], clipped[3]),
                (clipped[2], clipped[1], clipped[3]),
            ]
        )
        horizontal_segments.extend(
            [
                (clipped[1], clipped[0], clipped[2]),
                (clipped[3], clipped[0], clipped[2]),
            ]
        )

    vertical_tracks = _persistent_rule_tracks(
        vertical_segments,
        coordinate_tolerance=coordinate_tolerance,
        minimum_coverage=table_height * 0.3,
    )
    internal_vertical_tracks = [
        coordinate
        for coordinate in vertical_tracks
        if table_bbox[0] + coordinate_tolerance
        < coordinate
        < table_bbox[2] - coordinate_tolerance
    ]
    horizontal_tracks = _persistent_rule_tracks(
        horizontal_segments,
        coordinate_tolerance=coordinate_tolerance,
        minimum_coverage=table_width * 0.45,
    )
    return (
        len(internal_vertical_tracks) >= columns_total - 1
        and len(horizontal_tracks) >= 2
    )


def _persistent_rule_tracks(
    segments: list[tuple[float, float, float]],
    *,
    coordinate_tolerance: float,
    minimum_coverage: float,
) -> list[float]:
    clusters: list[list[tuple[float, float, float]]] = []
    for segment in sorted(segments):
        target = next(
            (
                cluster
                for cluster in clusters
                if abs(
                    segment[0]
                    - statistics.median(item[0] for item in cluster)
                )
                <= coordinate_tolerance
            ),
            None,
        )
        if target is None:
            clusters.append([segment])
        else:
            target.append(segment)
    result = []
    for cluster in clusters:
        intervals = sorted((item[1], item[2]) for item in cluster)
        coverage = 0.0
        if intervals:
            start, end = intervals[0]
            for interval_start, interval_end in intervals[1:]:
                if interval_start <= end + coordinate_tolerance:
                    end = max(end, interval_end)
                else:
                    coverage += max(0.0, end - start)
                    start, end = interval_start, interval_end
            coverage += max(0.0, end - start)
        if coverage >= minimum_coverage:
            result.append(statistics.median(item[0] for item in cluster))
    return sorted(result)


def _ruled_column_bands(
    cells: list[dict[str, Any]],
    *,
    columns_total: int,
    bbox_by_ref: dict[str, tuple[float, float, float, float]],
) -> list[tuple[float, float]]:
    rows: dict[int, list[tuple[float, float, float, float]]] = {}
    for cell in cells:
        bbox = bbox_by_ref.get(str(cell.get("bbox_ref") or ""))
        if bbox is None:
            return []
        rows.setdefault(int(cell.get("row_ordinal") or 0), []).append(bbox)
    leaf_rows = [
        sorted(values, key=lambda bbox: bbox[0])
        for values in rows.values()
        if len(values) == columns_total
    ]
    for leaf in leaf_rows:
        boundaries = [leaf[0][0], *[bbox[2] for bbox in leaf]]
        if all(
            boundaries[index] < boundaries[index + 1]
            for index in range(len(boundaries) - 1)
        ):
            return [
                (boundaries[index], boundaries[index + 1])
                for index in range(columns_total)
            ]
    edges = sorted(
        [coordinate for values in rows.values() for bbox in values for coordinate in (bbox[0], bbox[2])]
    )
    clusters: list[list[float]] = []
    for edge in edges:
        target = next(
            (
                cluster
                for cluster in clusters
                if abs(edge - statistics.median(cluster)) <= 2.0
            ),
            None,
        )
        if target is None:
            clusters.append([edge])
        else:
            target.append(edge)
    boundaries = sorted(statistics.median(cluster) for cluster in clusters)
    if len(boundaries) != columns_total + 1:
        return []
    return list(zip(boundaries, boundaries[1:]))


def _entry_from_words(
    words: list[_Word],
    *,
    bbox: tuple[float, float, float, float],
    geometry_column_ordinals: list[int],
) -> _EntryBand:
    reading_order = sorted(
        words,
        key=lambda word: (word.bbox[1], word.bbox[0], word.order),
    )
    return _EntryBand(
        words=reading_order,
        bbox=bbox,
        text=_render_source_word_sequence(reading_order),
        anchor_ids=[],
        geometry_column_ordinals=geometry_column_ordinals,
    )


def _word_group_columns(
    words: list[_Word],
    *,
    column_bands: list[tuple[float, float]],
) -> list[int]:
    return sorted(
        {
            index
            for word in words
            for index, band in enumerate(column_bands)
            if band[0] <= _bbox_center_x(word.bbox) <= band[1]
        }
    )


def _bbox_covered_columns(
    bbox: tuple[float, float, float, float],
    *,
    column_bands: list[tuple[float, float]],
) -> list[int]:
    return [
        index
        for index, band in enumerate(column_bands)
        if bbox[0] <= (band[0] + band[1]) / 2.0 <= bbox[2]
    ]


def _first_row_is_title_like(
    rows: list[_RowBand],
    *,
    table_bbox: tuple[float, float, float, float],
    column_bands: list[tuple[float, float]],
) -> bool:
    if not rows or len(rows[0].entries) != 1:
        return False
    entry = rows[0].entries[0]
    covered = entry.geometry_column_ordinals or []
    return (
        len(covered) >= max(2, math.ceil(len(column_bands) * 0.6))
        or _bbox_width(entry.bbox) >= _bbox_width(table_bbox) * 0.6
    )


def _nearby_external_title_rows(
    *,
    page_words: list[_Word],
    table_words: list[_Word],
    table_bbox: tuple[float, float, float, float],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowBand]:
    table_refs = {word.word_ref for word in table_words}
    outside = [word for word in page_words if word.word_ref not in table_refs]
    rows = _row_bands(outside, config=config)
    typical_height = statistics.median(
        (_bbox_height(word.bbox) for word in table_words),
    )
    base_gap_limit = max(18.0, typical_height * 2.6)
    extended_gap_limit = max(base_gap_limit, typical_height * 3.5)
    title_like_rows = [
        row
        for row in rows
        if len(row.entries) == 1
        and row.bbox[3] <= table_bbox[1] + 2.0
        and table_bbox[0] <= _bbox_center_x(row.bbox) <= table_bbox[2]
        and _bbox_width(row.bbox) <= _bbox_width(table_bbox) * 1.15
    ]
    candidates = [
        row
        for row in title_like_rows
        if 0.0 <= table_bbox[1] - row.bbox[3] <= base_gap_limit
    ]
    title = max(candidates, key=lambda row: row.bbox[3]) if candidates else None
    if title is None:
        extended_candidates = sorted(
            (
                row
                for row in title_like_rows
                if 0.0
                <= table_bbox[1] - row.bbox[3]
                <= extended_gap_limit
            ),
            key=lambda row: row.bbox[3],
            reverse=True,
        )
        for extended in extended_candidates:
            preceding = [row for row in rows if row.bbox[3] <= extended.bbox[1]]
            if not preceding:
                continue
            previous = max(preceding, key=lambda row: row.bbox[3])
            if previous in title_like_rows and _can_merge_external_title_rows(
                previous,
                extended,
                page_ref=extended.page_ref,
                table_bbox=table_bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            ):
                title = extended
                break
    if title is None:
        return []
    title_rows = [title]
    preceding = [row for row in rows if row.bbox[3] <= title.bbox[1]]
    if preceding:
        previous = max(preceding, key=lambda row: row.bbox[3])
        if (
            previous in title_like_rows
            and _can_merge_external_title_rows(
                previous,
                title,
                page_ref=title.page_ref,
                table_bbox=table_bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ):
            title_rows.insert(0, previous)
    if len(title_rows) == 2 and _external_second_line_is_metadata(
        title_rows[0],
        title_rows[1],
        table_bbox=table_bbox,
        typical_height=typical_height,
    ):
        title_rows[0].external_title = True
        title_rows[1].external_note = True
        return title_rows
    title_words = [word for row in title_rows for word in row.words]
    title_bbox = _merge_bboxes([row.bbox for row in title_rows])
    return [
        _RowBand(
            page_ref=title.page_ref,
            bbox=title_bbox,
            words=title_words,
            entries=[
                _entry_from_words(
                    title_words,
                    bbox=title_bbox,
                    geometry_column_ordinals=[],
                )
            ],
            external_title=True,
        )
    ]


def _can_merge_external_title_rows(
    upper: _RowBand,
    lower: _RowBand,
    *,
    page_ref: str,
    table_bbox: tuple[float, float, float, float],
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> bool:
    return (
        lower.bbox[1] - upper.bbox[3]
        <= max(4.0, typical_height * 1.4)
        and _external_title_rows_horizontally_compatible(
            upper,
            lower,
            table_bbox=table_bbox,
            typical_height=typical_height,
        )
        and not _horizontal_separator_between(
            upper,
            lower,
            page_ref=page_ref,
            table_bbox=table_bbox,
            object_bboxes=object_bboxes,
        )
    )


def _external_title_rows_horizontally_compatible(
    upper: _RowBand,
    lower: _RowBand,
    *,
    table_bbox: tuple[float, float, float, float],
    typical_height: float,
) -> bool:
    table_width = _bbox_width(table_bbox)
    envelope = table_width * 0.1
    if any(
        row.bbox[0] < table_bbox[0] - envelope
        or row.bbox[2] > table_bbox[2] + envelope
        for row in (upper, lower)
    ):
        return False
    left_alignment = abs(upper.bbox[0] - lower.bbox[0]) <= max(
        typical_height * 1.5,
        table_width * 0.08,
    )
    center_alignment = abs(
        _bbox_center_x(upper.bbox) - _bbox_center_x(lower.bbox)
    ) <= table_width * 0.15
    overlap = max(
        0.0,
        min(upper.bbox[2], lower.bbox[2])
        - max(upper.bbox[0], lower.bbox[0]),
    )
    minimum_width = min(_bbox_width(upper.bbox), _bbox_width(lower.bbox))
    overlap_compatible = minimum_width > 0.0 and overlap >= minimum_width * 0.5
    return left_alignment or center_alignment or overlap_compatible


def _external_second_line_is_metadata(
    upper: _RowBand,
    lower: _RowBand,
    *,
    table_bbox: tuple[float, float, float, float],
    typical_height: float,
) -> bool:
    text = " ".join(entry.text for entry in lower.entries).strip()
    normalized = _normalize_text(text)
    if _starts_with(normalized, _NOTE_PREFIXES):
        return True
    if re.search(r"\S\s*[:=：]\s*\S", text):
        return True
    tokens = [word.text.strip() for word in lower.words if word.text.strip()]
    if (
        2 <= len(tokens) <= 8
        and any(_looks_value_like(token) for token in tokens)
        and any(not _looks_value_like(token) for token in tokens)
    ):
        return True
    table_width = _bbox_width(table_bbox)
    alignment_delta = abs(upper.bbox[0] - lower.bbox[0])
    return alignment_delta > max(typical_height * 1.5, table_width * 0.08)


def _horizontal_separator_between(
    upper: _RowBand,
    lower: _RowBand,
    *,
    page_ref: str,
    table_bbox: tuple[float, float, float, float],
    object_bboxes: list[_ObjectGeometry],
) -> bool:
    gap_top = upper.bbox[3]
    gap_bottom = lower.bbox[1]
    if gap_bottom <= gap_top:
        return False
    table_width = _bbox_width(table_bbox)
    for item in object_bboxes:
        if (
            item.page_ref != page_ref
            or item.object_kind
            not in {"vector_line_inventory", "rect_inventory"}
        ):
            continue
        y_coordinates = (
            ((item.bbox[1] + item.bbox[3]) / 2.0,)
            if item.object_kind == "vector_line_inventory"
            else (item.bbox[1], item.bbox[3])
        )
        if (
            _bbox_width(item.bbox) >= table_width * 0.4
            and any(gap_top < y < gap_bottom for y in y_coordinates)
        ):
            return True
    return False


def _candidate_regions(
    projection: dict[str, Any],
    *,
    bbox_by_ref: dict[str, tuple[float, float, float, float]],
    words: list[_Word],
    page_by_ref: dict[str, _Page],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    words_by_ref = {word.word_ref: word for word in words}
    raw_regions: list[_Region] = []
    candidates = sorted(
        _dicts(projection["table_candidate_inventory"]),
        key=lambda item: (
            -float(item.get("geometry_confidence") or 0.0),
            str(item.get("page_ref") or ""),
            str(item.get("table_candidate_ref") or ""),
        ),
    )
    for raw in candidates:
        page_ref = str(raw.get("page_ref") or "")
        page = page_by_ref.get(page_ref)
        bbox = bbox_by_ref.get(str(raw.get("bbox_ref") or ""))
        if page is None or bbox is None:
            continue
        if _bbox_width(bbox) <= 0.0 or _bbox_height(bbox) <= 0.0:
            continue
        selected = [
            words_by_ref[ref]
            for ref in _strings(raw.get("contributing_word_refs"))
            if ref in words_by_ref and words_by_ref[ref].page_ref == page_ref
        ]
        if not selected:
            selected = [
                word
                for word in words
                if word.page_ref == page_ref and _center_inside(word.bbox, bbox)
            ]
        ruled_bands: list[tuple[float, float]] | None = None
        ruled_rows = None
        if raw.get("table_strategy_ref") == "ruled_lines_v0":
            ruled_rows, ruled_bands = _ruled_candidate_rows(
                raw,
                selected_words=selected,
                bbox_by_ref=bbox_by_ref,
                table_bbox=bbox,
                object_bboxes=object_bboxes,
                config=config,
            )
        rows = ruled_rows or _row_bands(selected, config=config)
        first_row_is_title_like = _first_row_is_title_like(
            rows,
            table_bbox=bbox,
            column_bands=ruled_bands or [],
        )
        if ruled_rows is not None and (
            len(rows) >= 3 or not first_row_is_title_like
        ):
            external_title_rows = _nearby_external_title_rows(
                page_words=[word for word in words if word.page_ref == page_ref],
                table_words=selected,
                table_bbox=bbox,
                object_bboxes=object_bboxes,
                config=config,
            )
            if external_title_rows and (
                not rows
                or _row_signature(external_title_rows[0])
                != _row_signature(rows[0])
            ):
                rows = [*external_title_rows, *rows]
                selected = [
                    *[
                        word
                        for external_row in external_title_rows
                        for word in external_row.words
                    ],
                    *selected,
                ]
        if (
            ruled_rows is not None
            and len(rows) >= 2
        ):
            # A closed ruled region is already strong physical-boundary
            # evidence, including an all-text body. Preserve its ordered rows
            # as one source part; do not require financial/value-like text or
            # manufacture multiple logical tables from sparse interior bands.
            segments = [rows]
        else:
            segments = _segment_table_rows(
                rows,
                config=config,
                minimum_core_rows=2,
            )
        for segment_ordinal, segment in enumerate(segments, 1):
            mirrored_lane_seed = _is_mirrored_lane_seed_segment(segment)
            linearized, lane_linearized = _linearize_mirrored_lane_pairs(
                segment,
                config=config,
            )
            lane_segments = (
                [linearized]
                if ruled_rows is not None or lane_linearized
                else _split_side_by_side_lanes(linearized, config=config)
            )
            for lane_ordinal, lane_segment in enumerate(lane_segments, 1):
                segment_words = [
                    word for row in lane_segment for word in row.words
                ]
                segment_bbox = _merge_bboxes(
                    [row.bbox for row in lane_segment]
                )
                raw_regions.append(
                    _Region(
                        source_ref=_identifier(
                            "candidate_region",
                            [
                                raw.get("table_candidate_ref"),
                                segment_ordinal,
                                lane_ordinal,
                                *[word.word_ref for word in segment_words],
                            ],
                        ),
                        page=page,
                        bbox=segment_bbox,
                        words=segment_words,
                        rows=lane_segment,
                        confidence=float(raw.get("geometry_confidence") or 0.0),
                        origin="PARSER_CANDIDATE",
                        object_refs=_overlapping_object_refs(
                            page_ref=page_ref,
                            bbox=segment_bbox,
                            object_bboxes=object_bboxes,
                        ),
                        ruled_column_bands=(
                            None if lane_linearized else ruled_bands
                        ),
                        mirrored_lane_seed=(
                            mirrored_lane_seed and lane_linearized
                        ),
                    )
                )

    result: list[_Region] = []
    for region in sorted(
        raw_regions,
        key=lambda item: (-item.confidence, -len(item.words), *_region_key(item)),
    ):
        duplicate_index = next(
            (
                index
                for index, accepted in enumerate(result)
                if accepted.page.page_ref == region.page.page_ref
                and _bbox_iou(accepted.bbox, region.bbox) >= 0.78
            ),
            None,
        )
        if duplicate_index is None:
            result.append(region)
        elif len(region.words) > len(result[duplicate_index].words):
            result[duplicate_index] = region
    return sorted(result, key=_region_key)


def _discover_aligned_regions(
    *,
    words_by_page: dict[str, list[_Word]],
    pages: list[_Page],
    occupied: list[_Region],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    result = []
    occupied_by_page: dict[str, list[tuple[float, float, float, float]]] = {}
    for region in occupied:
        occupied_by_page.setdefault(region.page.page_ref, []).append(region.bbox)
    for page in pages:
        available = [
            word
            for word in words_by_page.get(page.page_ref, [])
            if not any(
                _center_inside(word.bbox, bbox)
                for bbox in occupied_by_page.get(page.page_ref, [])
            )
        ]
        rows = _row_bands(available, config=config)
        if len(rows) < config.minimum_column_observations:
            continue
        runs = _segment_table_rows(
            rows,
            config=config,
            minimum_core_rows=config.minimum_column_observations,
        )
        for ordinal, run in enumerate(runs, 1):
            linearized, lane_linearized = _linearize_mirrored_lane_pairs(
                run,
                config=config,
            )
            lane_runs = (
                [linearized]
                if lane_linearized
                else _split_side_by_side_lanes(linearized, config=config)
            )
            for lane_ordinal, lane_run in enumerate(lane_runs, 1):
                dense_rows = [row for row in lane_run if len(row.entries) >= 2]
                if len(dense_rows) < config.minimum_column_observations:
                    continue
                column_centers = _repeated_entry_centers(
                    dense_rows,
                    width=max(1.0, page.width),
                    config=config,
                )
                has_value = any(
                    _looks_value_like(entry.text)
                    for row in dense_rows
                    for entry in row.entries
                )
                if len(column_centers) < 2 or not has_value:
                    continue
                selected_words = [
                    word for row in lane_run for word in row.words
                ]
                bbox = _merge_bboxes([row.bbox for row in lane_run])
                source_ref = _identifier(
                    "aligned_region",
                    [
                        page.page_ref,
                        ordinal,
                        lane_ordinal,
                        *[word.word_ref for word in selected_words],
                    ],
                )
                result.append(
                    _Region(
                        source_ref=source_ref,
                        page=page,
                        bbox=bbox,
                        words=selected_words,
                        rows=lane_run,
                        confidence=0.7,
                        origin="ALIGNED_DISCOVERY",
                        object_refs=_overlapping_object_refs(
                            page_ref=page.page_ref,
                            bbox=bbox,
                            object_bboxes=object_bboxes,
                        ),
                    )
                )
    return sorted(result, key=_region_key)


def _is_mirrored_lane_seed_segment(rows: list[_RowBand]) -> bool:
    """Recognize only the physical seed shape used by lane reconciliation.

    This does not itself assert that there are two logical tables.  It merely
    records the observable parser shape so a later, independent aligned region
    can prove (or fail to prove) the two continuations.
    """

    if (
        len(rows) != 2
        or len(rows[0].entries) != 1
        or len(rows[1].entries) != 4
        or not 2 <= len(rows[0].words) <= 4
    ):
        return False
    return not any(_looks_value_like(word.text) for word in rows[0].words)


def _linearize_mirrored_lane_pairs(
    rows: list[_RowBand],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_RowBand], bool]:
    if (
        len(rows) < 2
        or len(rows[0].entries) != 1
        or len(rows[0].entries[0].words) < 2
        or any(len(row.entries) != 4 for row in rows[1:])
    ):
        return rows, False
    lane_rows = rows[1:]
    typical_height = statistics.median(_bbox_height(row.bbox) for row in rows)
    full_bbox = _merge_bboxes([row.bbox for row in lane_rows])
    full_width = max(1.0, _bbox_width(full_bbox))
    tolerance = max(
        typical_height * 2.0,
        full_width * config.column_tolerance_width_ratio,
    )
    separator_gaps = [
        row.entries[2].bbox[0] - row.entries[1].bbox[2]
        for row in lane_rows
    ]
    internal_gaps = [
        gap
        for row in lane_rows
        for gap in (
            row.entries[1].bbox[0] - row.entries[0].bbox[2],
            row.entries[3].bbox[0] - row.entries[2].bbox[2],
        )
        if gap > 0.0
    ]
    if any(gap <= 0.0 for gap in separator_gaps):
        return rows, False
    separator_gap = statistics.median(separator_gaps)
    if internal_gaps:
        if separator_gap < max(
            typical_height * 3.0,
            statistics.median(internal_gaps) * 2.0,
        ):
            return rows, False
    elif separator_gap < max(1.0, typical_height * 0.5):
        return rows, False

    shifts = []
    left_boxes = []
    normalized_right_boxes = []
    for row in lane_rows:
        pair_shifts = [
            _bbox_center_x(row.entries[index + 2].bbox)
            - _bbox_center_x(row.entries[index].bbox)
            for index in (0, 1)
        ]
        if abs(pair_shifts[0] - pair_shifts[1]) > tolerance * 1.5:
            return rows, False
        shift = statistics.median(pair_shifts)
        shifts.append(shift)
        for index in (0, 1):
            left_boxes.append((index, row.entries[index].bbox))
            right_bbox = row.entries[index + 2].bbox
            normalized_right_boxes.append(
                (
                    index,
                    (
                        right_bbox[0] - shift,
                        right_bbox[1],
                        right_bbox[2] - shift,
                        right_bbox[3],
                    ),
                )
            )
    if max(shifts) - min(shifts) > tolerance * 1.5:
        return rows, False

    tracks = []
    for ordinal in (0, 1):
        boxes = [
            bbox
            for index, bbox in [*left_boxes, *normalized_right_boxes]
            if index == ordinal
        ]
        tracks.append(
            (
                statistics.median(bbox[0] for bbox in boxes),
                statistics.median(_bbox_center_x(bbox) for bbox in boxes),
                statistics.median(bbox[2] for bbox in boxes),
            )
        )
    header_words = sorted(
        rows[0].entries[0].words,
        key=lambda word: (word.bbox[0], word.order),
    )
    header_tolerance = max(
        typical_height * 2.5,
        _bbox_width(_merge_bboxes([bbox for _, bbox in left_boxes])) * 0.28,
    )
    split_candidates = []
    for split_index in range(1, len(header_words)):
        groups = [header_words[:split_index], header_words[split_index:]]
        boxes = [_merge_bboxes([word.bbox for word in group]) for group in groups]
        distances = [
            min(
                abs(box[0] - track[0]),
                abs(_bbox_center_x(box) - track[1]),
                abs(box[2] - track[2]),
            )
            for box, track in zip(boxes, tracks)
        ]
        if all(distance <= header_tolerance for distance in distances):
            split_candidates.append((sum(distances), groups, boxes))
    if not split_candidates:
        return rows, False
    _, header_groups, header_boxes = min(
        split_candidates,
        key=lambda item: item[0],
    )
    header_entries = [
        _entry_from_words(
            group,
            bbox=bbox,
            geometry_column_ordinals=[ordinal],
        )
        for ordinal, (group, bbox) in enumerate(
            zip(header_groups, header_boxes)
        )
    ]
    header_row = _row_from_entries(rows[0], header_entries)
    left_rows = []
    right_rows = []
    for row in lane_rows:
        for ordinal, entry in enumerate(row.entries[:2]):
            entry.geometry_column_ordinals = [ordinal]
        for ordinal, entry in enumerate(row.entries[2:]):
            entry.geometry_column_ordinals = [ordinal]
        left_rows.append(_row_from_entries(row, row.entries[:2]))
        right_rows.append(_row_from_entries(row, row.entries[2:]))
    return [header_row, *left_rows, *right_rows], True


def _split_side_by_side_lanes(
    rows: list[_RowBand],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[list[_RowBand]]:
    dense = [row for row in rows if len(row.entries) >= 4]
    if len(dense) < config.minimum_column_observations:
        return [rows]
    counts: dict[int, int] = {}
    for row in dense:
        counts[len(row.entries)] = counts.get(len(row.entries), 0) + 1
    modal_count = max(counts, key=lambda count: (counts[count], count))
    if modal_count < 4 or modal_count % 2:
        return [rows]
    modal_rows = [row for row in dense if len(row.entries) == modal_count]
    if len(modal_rows) < config.minimum_column_observations:
        return [rows]
    split_index = modal_count // 2
    separator_gaps = [
        row.entries[split_index].bbox[0]
        - row.entries[split_index - 1].bbox[2]
        for row in modal_rows
    ]
    if any(gap <= 0.0 for gap in separator_gaps):
        return [rows]
    internal_gaps = [
        row.entries[index + 1].bbox[0] - row.entries[index].bbox[2]
        for row in modal_rows
        for index in range(modal_count - 1)
        if index != split_index - 1
    ]
    positive_internal = [gap for gap in internal_gaps if gap > 0.0]
    typical_height = statistics.median(_bbox_height(row.bbox) for row in rows)
    internal_reference = (
        statistics.median(positive_internal) if positive_internal else 0.0
    )
    separator_gap = statistics.median(separator_gaps)
    if separator_gap < max(
        typical_height * 4.0,
        internal_reference * 2.2,
    ):
        return [rows]

    left_bbox = _merge_bboxes(
        [entry.bbox for row in modal_rows for entry in row.entries[:split_index]]
    )
    right_bbox = _merge_bboxes(
        [entry.bbox for row in modal_rows for entry in row.entries[split_index:]]
    )
    width_ratio = _bbox_width(left_bbox) / max(1.0, _bbox_width(right_bbox))
    if not 0.7 <= width_ratio <= 1.4:
        return [rows]
    left_signature = _lane_relative_signature(
        modal_rows,
        start=0,
        end=split_index,
        lane_bbox=left_bbox,
    )
    right_signature = _lane_relative_signature(
        modal_rows,
        start=split_index,
        end=modal_count,
        lane_bbox=right_bbox,
    )
    if len(left_signature) != len(right_signature) or any(
        abs(left - right) > 0.12
        for left, right in zip(left_signature, right_signature)
    ):
        return [rows]
    if not all(
        _lane_has_label_value_evidence(
            modal_rows,
            start=start,
            end=end,
        )
        for start, end in ((0, split_index), (split_index, modal_count))
    ):
        return [rows]

    separator_x = statistics.median(
        (
            row.entries[split_index - 1].bbox[2]
            + row.entries[split_index].bbox[0]
        )
        / 2.0
        for row in modal_rows
    )
    lanes: list[list[_RowBand]] = [[], []]
    for row in rows:
        if any(entry.bbox[0] < separator_x < entry.bbox[2] for entry in row.entries):
            return [rows]
        row_entries = [
            [
                entry
                for entry in row.entries
                if _bbox_center_x(entry.bbox) < separator_x
            ],
            [
                entry
                for entry in row.entries
                if _bbox_center_x(entry.bbox) >= separator_x
            ],
        ]
        for lane_index, entries in enumerate(row_entries):
            if entries:
                lanes[lane_index].append(_row_from_entries(row, entries))
    if any(
        len(lane) < 2
        or sum(_is_table_core_row(row) for row in lane) < 2
        for lane in lanes
    ):
        return [rows]
    return lanes


def _lane_relative_signature(
    rows: list[_RowBand],
    *,
    start: int,
    end: int,
    lane_bbox: tuple[float, float, float, float],
) -> list[float]:
    width = max(1.0, _bbox_width(lane_bbox))
    return [
        statistics.median(
            (_bbox_center_x(row.entries[index].bbox) - lane_bbox[0]) / width
            for row in rows
        )
        for index in range(start, end)
    ]


def _lane_has_label_value_evidence(
    rows: list[_RowBand],
    *,
    start: int,
    end: int,
) -> bool:
    supported = sum(
        not _looks_value_like(row.entries[start].text)
        and any(
            _looks_value_like(row.entries[index].text)
            for index in range(start + 1, end)
        )
        for row in rows
    )
    return supported >= 2


def _row_from_entries(
    source: _RowBand,
    entries: list[_EntryBand],
) -> _RowBand:
    words = [word for entry in entries for word in entry.words]
    return _RowBand(
        page_ref=source.page_ref,
        bbox=_merge_bboxes([entry.bbox for entry in entries]),
        words=words,
        entries=entries,
        external_title=source.external_title,
        external_note=source.external_note,
    )


@dataclass(frozen=True)
class _MirroredLaneReconciliation:
    seed_index: int
    continuation_index: int
    lane_rows: tuple[list[_RowBand], list[_RowBand]]


def _reconcile_adjacent_mirrored_lanes(
    regions: list[_Region],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Repartition a proven same-page two-lane continuation.

    The ordinary lane splitter intentionally keeps its global minimum and
    separator-strength rules.  This narrower path is allowed only when a
    parser candidate supplies one independently proven seed per lane and an
    adjacent candidate-free region supplies the asymmetric continuations.
    """

    ordered = sorted(regions, key=_region_key)
    plans: list[_MirroredLaneReconciliation] = []
    for seed_index, seed in enumerate(ordered):
        if seed.origin != "PARSER_CANDIDATE" or not seed.mirrored_lane_seed:
            continue
        for continuation_index, continuation in enumerate(ordered):
            if (
                continuation_index == seed_index
                or continuation.origin != "ALIGNED_DISCOVERY"
            ):
                continue
            lane_rows = _adjacent_mirrored_lane_plan(
                seed,
                continuation,
                config=config,
            )
            if lane_rows is not None:
                plans.append(
                    _MirroredLaneReconciliation(
                        seed_index=seed_index,
                        continuation_index=continuation_index,
                        lane_rows=lane_rows,
                    )
                )

    seed_degrees: dict[int, int] = {}
    continuation_degrees: dict[int, int] = {}
    for plan in plans:
        seed_degrees[plan.seed_index] = seed_degrees.get(plan.seed_index, 0) + 1
        continuation_degrees[plan.continuation_index] = (
            continuation_degrees.get(plan.continuation_index, 0) + 1
        )
    accepted = [
        plan
        for plan in plans
        if seed_degrees[plan.seed_index] == 1
        and continuation_degrees[plan.continuation_index] == 1
    ]
    if not accepted:
        return ordered

    consumed: set[int] = set()
    replacements: list[_Region] = []
    for plan in accepted:
        if plan.seed_index in consumed or plan.continuation_index in consumed:
            continue
        seed = ordered[plan.seed_index]
        continuation = ordered[plan.continuation_index]
        rebuilt = _rebuild_mirrored_lane_regions(
            seed,
            continuation,
            lane_rows=plan.lane_rows,
        )
        if rebuilt is None:
            continue
        consumed.update({plan.seed_index, plan.continuation_index})
        replacements.extend(rebuilt)

    if not replacements:
        return ordered
    return sorted(
        [
            *[
                region
                for index, region in enumerate(ordered)
                if index not in consumed
            ],
            *replacements,
        ],
        key=_region_key,
    )


def _adjacent_mirrored_lane_plan(
    seed: _Region,
    continuation: _Region,
    *,
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_RowBand], list[_RowBand]] | None:
    if (
        seed.page.page_ref != continuation.page.page_ref
        or len(seed.rows) != 3
        or any(len(row.entries) != 2 for row in seed.rows)
        or any(_looks_value_like(word.text) for word in seed.rows[0].words)
        or not _region_has_exact_row_word_partition(seed)
        or not _region_has_exact_row_word_partition(continuation)
    ):
        return None
    residual, first_seed, second_seed = seed.rows
    if not 2 <= len(residual.words) <= 4:
        return None
    if not _rows_share_vertical_band(first_seed, second_seed):
        return None

    continuation_lanes = _strict_asymmetric_continuation_lanes(
        continuation.rows,
        config=config,
    )
    if continuation_lanes is None:
        return None
    left_lane, right_lane = continuation_lanes

    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in [*seed.rows, *continuation.rows]
    )
    vertical_gap = continuation.rows[0].bbox[1] - max(
        first_seed.bbox[3], second_seed.bbox[3]
    )
    if vertical_gap < 0.0 or vertical_gap > max(1.0, typical_height):
        return None
    seed_span = _merge_bboxes([first_seed.bbox, second_seed.bbox])
    continuation_span = _merge_bboxes(
        [continuation.rows[0].bbox, continuation.rows[1].bbox]
    )
    if _horizontal_interval_overlap_ratio(seed_span, continuation_span) < (
        1.0 - config.column_tolerance_width_ratio
    ):
        return None

    lane_tracks = (
        _entry_interval_signature(left_lane[:2]),
        _entry_interval_signature(right_lane[:2]),
    )
    seed_rows = (first_seed, second_seed)
    seed_matches = [
        [
            lane_index
            for lane_index, tracks in enumerate(lane_tracks)
            if _entries_strongly_match_tracks(
                seed_row.entries,
                tracks,
                config=config,
            )
        ]
        for seed_row in seed_rows
    ]
    if (
        any(len(matches) != 1 for matches in seed_matches)
        or seed_matches[0][0] == seed_matches[1][0]
    ):
        return None

    seed_by_lane = {
        matches[0]: seed_row
        for seed_row, matches in zip(seed_rows, seed_matches)
    }
    result = (
        [seed_by_lane[0], *left_lane],
        [seed_by_lane[1], *right_lane],
    )
    if any(
        any(
            upper.bbox[1] > lower.bbox[1]
            for upper, lower in zip(lane, lane[1:])
        )
        for lane in result
    ):
        return None
    return result


def _strict_asymmetric_continuation_lanes(
    rows: list[_RowBand],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_RowBand], list[_RowBand]] | None:
    prefix_total = 2
    if (
        len(rows) < prefix_total + config.minimum_column_observations
        or any(len(row.entries) != 4 for row in rows[:prefix_total])
        or any(len(row.entries) != 2 for row in rows[prefix_total:])
    ):
        return None
    prefix = rows[:prefix_total]
    tail = rows[prefix_total:]
    if not all(
        _lane_has_label_value_evidence(prefix, start=start, end=end)
        for start, end in ((0, 2), (2, 4))
    ):
        return None
    if any(
        row.entries[index].bbox[2] >= row.entries[index + 1].bbox[0]
        for row in prefix
        for index in range(3)
    ):
        return None

    separator_x = statistics.median(
        (
            row.entries[1].bbox[2] + row.entries[2].bbox[0]
        )
        / 2.0
        for row in prefix
    )
    if any(
        entry.bbox[0] < separator_x < entry.bbox[2]
        for row in rows
        for entry in row.entries
    ):
        return None

    left_prefix = [_row_from_entries(row, row.entries[:2]) for row in prefix]
    right_prefix = [_row_from_entries(row, row.entries[2:]) for row in prefix]
    lane_tracks = (
        _entry_interval_signature(left_prefix),
        _entry_interval_signature(right_prefix),
    )
    tail_matches = [
        [
            lane_index
            for lane_index, tracks in enumerate(lane_tracks)
            if _entries_strongly_match_tracks(
                row.entries,
                tracks,
                config=config,
            )
        ]
        for row in tail
    ]
    if any(len(matches) != 1 for matches in tail_matches):
        return None
    tail_lane_indexes = {matches[0] for matches in tail_matches}
    if len(tail_lane_indexes) != 1:
        return None
    tail_lane_index = next(iter(tail_lane_indexes))

    left = list(left_prefix)
    right = list(right_prefix)
    target = left if tail_lane_index == 0 else right
    target.extend(tail)
    return left, right


def _entry_interval_signature(
    rows: list[_RowBand],
) -> tuple[tuple[float, float], ...]:
    if not rows or len({len(row.entries) for row in rows}) != 1:
        return ()
    return tuple(
        (
            statistics.median(row.entries[index].bbox[0] for row in rows),
            statistics.median(row.entries[index].bbox[2] for row in rows),
        )
        for index in range(len(rows[0].entries))
    )


def _entries_strongly_match_tracks(
    entries: list[_EntryBand],
    tracks: tuple[tuple[float, float], ...],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if len(entries) != len(tracks) or not tracks:
        return False
    minimum_overlap = 1.0 - config.column_tolerance_width_ratio
    return all(
        _interval_overlap_ratio(
            (entry.bbox[0], entry.bbox[2]),
            track,
        )
        >= minimum_overlap
        for entry, track in zip(entries, tracks)
    )


def _rows_share_vertical_band(left: _RowBand, right: _RowBand) -> bool:
    intersection = min(left.bbox[3], right.bbox[3]) - max(
        left.bbox[1], right.bbox[1]
    )
    minimum_height = min(_bbox_height(left.bbox), _bbox_height(right.bbox))
    return minimum_height > 0.0 and intersection / minimum_height >= 0.8


def _horizontal_interval_overlap_ratio(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    return _interval_overlap_ratio(
        (left[0], left[2]),
        (right[0], right[2]),
    )


def _interval_overlap_ratio(
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    intersection = max(0.0, min(left[1], right[1]) - max(left[0], right[0]))
    minimum_width = min(left[1] - left[0], right[1] - right[0])
    if minimum_width <= 0.0:
        return 0.0
    return intersection / minimum_width


def _region_has_exact_row_word_partition(region: _Region) -> bool:
    region_refs = [word.word_ref for word in region.words]
    row_refs = [word.word_ref for row in region.rows for word in row.words]
    return (
        len(region_refs) == len(set(region_refs))
        and len(row_refs) == len(set(row_refs))
        and set(region_refs) == set(row_refs)
    )


def _rebuild_mirrored_lane_regions(
    seed: _Region,
    continuation: _Region,
    *,
    lane_rows: tuple[list[_RowBand], list[_RowBand]],
) -> tuple[_Region, _Region] | None:
    residual_refs = {word.word_ref for word in seed.rows[0].words}
    input_refs = {word.word_ref for word in [*seed.words, *continuation.words]}
    if len(input_refs) != len(seed.words) + len(continuation.words):
        return None

    lane_ref_sets = [
        {word.word_ref for row in rows for word in row.words}
        for rows in lane_rows
    ]
    lane_ref_totals = [
        sum(len(row.words) for row in rows)
        for rows in lane_rows
    ]
    if (
        any(len(refs) != total for refs, total in zip(lane_ref_sets, lane_ref_totals))
        or lane_ref_sets[0].intersection(lane_ref_sets[1])
        or residual_refs.intersection(lane_ref_sets[0] | lane_ref_sets[1])
        or residual_refs | lane_ref_sets[0] | lane_ref_sets[1] != input_refs
    ):
        return None

    input_word_by_ref = {
        word.word_ref: word for word in [*seed.words, *continuation.words]
    }
    regions = []
    for lane_ordinal, (rows, word_refs) in enumerate(
        zip(lane_rows, lane_ref_sets),
        1,
    ):
        if any(len(row.entries) != 2 for row in rows):
            return None
        for row in rows:
            for column_ordinal, entry in enumerate(row.entries):
                entry.geometry_column_ordinals = [column_ordinal]
        words = sorted(
            [input_word_by_ref[word_ref] for word_ref in word_refs],
            key=lambda word: (word.bbox[1], word.bbox[0], word.order),
        )
        bbox = _merge_bboxes([row.bbox for row in rows])
        regions.append(
            _Region(
                source_ref=_identifier(
                    "reconciled_lane_region",
                    [
                        seed.source_ref,
                        continuation.source_ref,
                        lane_ordinal,
                        *[word.word_ref for word in words],
                    ],
                ),
                page=seed.page,
                bbox=bbox,
                words=words,
                rows=rows,
                confidence=min(seed.confidence, continuation.confidence),
                origin="PARSER_CANDIDATE+ALIGNED_DISCOVERY",
                object_refs=sorted(
                    {*seed.object_refs, *continuation.object_refs}
                ),
            )
        )
    return regions[0], regions[1]


def _plan_unique_ruled_baseline_recovery(
    regions: list[_Region],
    *,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Mark one uniquely proven ruled span defect without changing its rows."""

    ordered = sorted(regions, key=_region_key)
    ref_degrees: dict[str, int] = {}
    for region in ordered:
        for word in region.words:
            ref_degrees[word.word_ref] = ref_degrees.get(word.word_ref, 0) + 1
    candidates: list[tuple[int, _RuledBaselineRecoveryPlan]] = []
    for region_index, region in enumerate(ordered):
        plan = _ruled_baseline_recovery_plan_for_region(
            region,
            object_bboxes=object_bboxes,
            config=config,
        )
        if plan is None or any(
            ref_degrees.get(word_ref) != 1
            for word_ref in plan.core_word_refs
        ):
            continue
        candidates.append((region_index, plan))
    if len(candidates) != 1:
        return ordered
    region_index, plan = candidates[0]
    planned_region = copy.copy(ordered[region_index])
    planned_region.ruled_baseline_recovery_plan = plan
    rebuilt = list(ordered)
    rebuilt[region_index] = planned_region
    return rebuilt


def _ruled_baseline_recovery_plan_for_region(
    region: _Region,
    *,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> _RuledBaselineRecoveryPlan | None:
    bands = tuple(region.ruled_column_bands or ())
    if (
        region.origin != "PARSER_CANDIDATE"
        or region.mirrored_lane_seed
        or region.ruled_baseline_recovery_plan is not None
        or region.released_non_table_word_refs
        or len(bands) != 2
        or any(left[0] >= left[1] for left in bands)
        or bands[0][1] > bands[1][0]
        or not region.rows
        or not _region_has_exact_row_word_partition(region)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in region.rows
        )
    ):
        return None
    ruled_rows = [
        row
        for row in region.rows
        if any(
            entry.geometry_column_ordinals is not None
            for entry in row.entries
        )
    ]
    if not ruled_rows:
        return None
    ruled_bbox = _merge_bboxes([row.bbox for row in ruled_rows])
    if not _has_dual_axis_grid_topology(
        page_ref=region.page.page_ref,
        table_bbox=ruled_bbox,
        columns_total=len(bands),
        object_bboxes=object_bboxes,
    ):
        return None

    baseline_rows = _row_bands(list(region.words), config=config)
    if (
        len(baseline_rows) <= len(region.rows)
        or not _rows_have_strict_source_order(baseline_rows)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in baseline_rows
        )
    ):
        return None
    baseline_refs = [
        word.word_ref for row in baseline_rows for word in row.words
    ]
    core_word_refs = tuple(
        word.word_ref for word in sorted(region.words, key=lambda word: word.order)
    )
    if (
        len(baseline_refs) != len(set(baseline_refs))
        or set(baseline_refs) != set(core_word_refs)
    ):
        return None

    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in baseline_rows
    )
    if typical_height <= 0.0:
        return None
    title_candidates = _title_pseudorule_macro_candidates(
        baseline_rows,
        region=region,
        typical_height=typical_height,
    )
    wrapped_candidates = _ruled_wrapped_label_macro_candidates(
        baseline_rows,
        region=region,
        typical_height=typical_height,
        object_bboxes=object_bboxes,
    )
    if len(title_candidates) != 1 or len(wrapped_candidates) != 1:
        return None
    title_pair = title_candidates[0]
    wrapped_pair = wrapped_candidates[0]
    if set(title_pair).intersection(wrapped_pair):
        return None
    title_refs = {
        word.word_ref for word in baseline_rows[title_pair[0]].words
    }
    title_owners = [
        row
        for row in region.rows
        if title_refs
        and title_refs <= {word.word_ref for word in row.words}
    ]
    if len(title_owners) != 1:
        return None
    released_refs = tuple(
        word.word_ref for word in baseline_rows[title_pair[1]].words
    )
    if not released_refs:
        return None

    stable_rows = [
        row
        for index, row in enumerate(baseline_rows)
        if index not in set(title_pair)
    ]
    stable_height = statistics.median(
        _bbox_height(row.bbox) for row in stable_rows
    )
    if stable_height <= 0.0 or any(
        not stable_height * 0.75
        <= _bbox_height(row.bbox)
        <= stable_height * 1.25
        for row in stable_rows
    ):
        return None
    if not _ruled_region_has_span_defect(
        region,
        baseline_rows=baseline_rows,
    ):
        return None

    row_entry_ordinals: list[tuple[tuple[int, ...], ...]] = []
    for row_index, row in enumerate(baseline_rows):
        if row_index in set(title_pair):
            row_entry_ordinals.append(tuple(() for _ in row.entries))
            continue
        ordinals = tuple(
            tuple(
                _word_group_columns(
                    entry.words,
                    column_bands=list(bands),
                )
            )
            for entry in row.entries
        )
        if any(len(value) != 1 for value in ordinals):
            return None
        row_entry_ordinals.append(ordinals)
    observed_ordinals = [
        ordinal
        for row_index, row in enumerate(baseline_rows)
        if row_index not in set(title_pair)
        for entry_index, _ in enumerate(row.entries)
        for ordinal in row_entry_ordinals[row_index][entry_index]
    ]
    if any(observed_ordinals.count(ordinal) < 3 for ordinal in (0, 1)):
        return None
    right_value_entries = [
        row.entries[-1]
        for row_index, row in enumerate(baseline_rows)
        if row_index not in set(title_pair)
        and row.entries
        and row_entry_ordinals[row_index][-1] == (1,)
        and _looks_value_like(row.entries[-1].text)
    ]
    if len(right_value_entries) < 3 or (
        max(entry.bbox[2] for entry in right_value_entries)
        - min(entry.bbox[2] for entry in right_value_entries)
        > region.page.width * config.column_tolerance_width_ratio
    ):
        return None

    output_rows = _ruled_baseline_output_plans(
        baseline_rows,
        row_entry_ordinals=row_entry_ordinals,
        title_pair=title_pair,
        wrapped_pair=wrapped_pair,
        title_external_title=title_owners[0].external_title,
        title_external_note=title_owners[0].external_note,
    )
    if output_rows is None:
        return None
    output_refs = [
        word_ref
        for row_plan in output_rows
        for word_ref in row_plan.word_refs
    ]
    if (
        len(output_refs) != len(set(output_refs))
        or len(released_refs) != len(set(released_refs))
        or set(output_refs).intersection(released_refs)
        or output_refs
        != [
            word_ref
            for word_ref in core_word_refs
            if word_ref not in set(released_refs)
        ]
    ):
        return None
    fingerprint = _ruled_baseline_source_fingerprint(
        region,
        core_word_refs=core_word_refs,
    )
    if not fingerprint:
        return None
    title_ref_groups = tuple(
        tuple(word.word_ref for word in baseline_rows[index].words)
        for index in title_pair
    )
    wrapped_ref_groups = tuple(
        tuple(word.word_ref for word in baseline_rows[index].words)
        for index in wrapped_pair
    )
    plan_id = _identifier(
        "ruled_baseline_plan",
        [
            region.page.page_ref,
            fingerprint,
            *core_word_refs,
            *[
                [list(group) for group in row.entry_word_ref_groups]
                for row in output_rows
            ],
            *released_refs,
        ],
    )
    return _RuledBaselineRecoveryPlan(
        plan_id=plan_id,
        page_ref=region.page.page_ref,
        core_word_refs=core_word_refs,
        source_fingerprint_sha256=fingerprint,
        output_rows=tuple(output_rows),
        original_ruled_column_bands=bands,
        title_pseudorule_ref_groups=title_ref_groups,
        wrapped_label_ref_groups=wrapped_ref_groups,
        released_non_table_word_refs=released_refs,
    )


def _title_pseudorule_macro_candidates(
    rows: list[_RowBand],
    *,
    region: _Region,
    typical_height: float,
) -> list[tuple[int, int]]:
    result = []
    for index, (title, pseudorule) in enumerate(zip(rows, rows[1:])):
        text = "".join(entry.text for entry in pseudorule.entries)
        visible = [character for character in text if not character.isspace()]
        gap = pseudorule.bbox[1] - title.bbox[3]
        if (
            len(title.entries) != 1
            or not any(character.isalnum() for character in title.entries[0].text)
            or _looks_value_like(title.entries[0].text)
            or len(pseudorule.entries) != 1
            or not visible
            or any(character.isalnum() for character in visible)
            or _looks_value_like(pseudorule.entries[0].text)
            or _bbox_width(pseudorule.bbox) < _bbox_width(region.bbox) * 0.9
            or _bbox_height(pseudorule.bbox) > typical_height * 0.75
            or gap < 0.0
            or gap > typical_height
        ):
            continue
        result.append((index, index + 1))
    return result


def _ruled_wrapped_label_macro_candidates(
    rows: list[_RowBand],
    *,
    region: _Region,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> list[tuple[int, int]]:
    source_ref_sets = [
        {word.word_ref for word in source_row.words}
        for source_row in region.rows
    ]
    baseline_ref_sets = [
        {word.word_ref for word in row.words} for row in rows
    ]
    result = []
    for index, (upper, lower) in enumerate(zip(rows, rows[1:])):
        upper_refs = baseline_ref_sets[index]
        lower_refs = baseline_ref_sets[index + 1]
        single_owners = [
            source_index
            for source_index, source_refs in enumerate(source_ref_sets)
            if upper_refs | lower_refs == source_refs
        ]
        adjacent_owners = [
            source_index
            for source_index in range(len(source_ref_sets) - 1)
            if upper_refs == source_ref_sets[source_index]
            and lower_refs == source_ref_sets[source_index + 1]
        ]
        if single_owners or len(adjacent_owners) != 1:
            continue
        source_refs = (
            source_ref_sets[adjacent_owners[0]]
            | source_ref_sets[adjacent_owners[0] + 1]
        )
        participant_indexes = [
            candidate_index
            for candidate_index, candidate_refs in enumerate(baseline_ref_sets)
            if candidate_refs and candidate_refs <= source_refs
        ]
        upper_text = upper.entries[0].text.strip() if upper.entries else ""
        lower_text = lower.entries[0].text.strip() if lower.entries else ""
        lower_first_alpha = next(
            (character for character in lower_text if character.isalpha()),
            "",
        )
        bands = list(region.ruled_column_bands or [])
        gap = lower.bbox[1] - upper.bbox[3]
        if (
            participant_indexes != [index, index + 1]
            or len(upper.entries) != 1
            or any(_looks_value_like(entry.text) for entry in upper.entries)
            or len(lower.entries) != 2
            or _looks_numeric(lower.entries[0].text)
            or not lower_first_alpha
            or not lower_first_alpha.islower()
            or _normalize_text(upper_text) == _normalize_text(lower_text)
            or _starts_with(_normalize_text(upper_text), _NOTE_PREFIXES)
            or _starts_with(_normalize_text(upper_text), _SUBTOTAL_PREFIXES)
            or _starts_with(_normalize_text(upper_text), _TOTAL_PREFIXES)
            or _word_group_columns(upper.entries[0].words, column_bands=bands)
            != [0]
            or _word_group_columns(lower.entries[0].words, column_bands=bands)
            != [0]
            or any(
                not _looks_value_like(entry.text)
                or _word_group_columns(entry.words, column_bands=bands) != [1]
                for entry in lower.entries[1:]
            )
            or abs(upper.bbox[0] - lower.bbox[0]) > typical_height * 0.75
            or gap < 0.0
            or gap > typical_height
        ):
            continue
        result.append((index, index + 1))
    return result


def _ruled_region_has_span_defect(
    region: _Region,
    *,
    baseline_rows: list[_RowBand],
) -> bool:
    overlapping_disjoint = any(
        upper.bbox[1] < lower.bbox[3]
        and lower.bbox[1] < upper.bbox[3]
        and {
            word.word_ref for word in upper.words
        }.isdisjoint(word.word_ref for word in lower.words)
        for index, upper in enumerate(region.rows)
        for lower in region.rows[index + 1 :]
    )
    baseline_ref_sets = [
        {word.word_ref for word in row.words} for row in baseline_rows
    ]
    multibaseline = any(
        sum(bool(refs and refs <= source_refs) for refs in baseline_ref_sets) >= 2
        for source_row in region.rows
        for source_refs in [
            {word.word_ref for word in source_row.words}
        ]
    )
    return overlapping_disjoint or multibaseline


def _ruled_baseline_output_plans(
    rows: list[_RowBand],
    *,
    row_entry_ordinals: list[tuple[tuple[int, ...], ...]],
    title_pair: tuple[int, int],
    wrapped_pair: tuple[int, int],
    title_external_title: bool,
    title_external_note: bool,
) -> list[_RuledBaselineOutputRowPlan] | None:
    result = []
    macro_by_start = {
        title_pair[0]: (title_pair, "TITLE_PSEUDO_RULE"),
        wrapped_pair[0]: (wrapped_pair, "RULED_WRAPPED_LABEL"),
    }
    consumed: set[int] = set()
    for index, row in enumerate(rows):
        if index in consumed:
            continue
        macro = macro_by_start.get(index)
        if macro is None:
            result.append(
                _RuledBaselineOutputRowPlan(
                    word_refs=tuple(word.word_ref for word in row.words),
                    entry_word_ref_groups=tuple(
                        tuple(word.word_ref for word in entry.words)
                        for entry in row.entries
                    ),
                    geometry_column_ordinals=tuple(
                        tuple(value) for value in row_entry_ordinals[index]
                    ),
                    external_title=row.external_title,
                )
            )
            continue
        indexes, kind = macro
        participants = [rows[item] for item in indexes]
        if kind == "TITLE_PSEUDO_RULE":
            title = participants[0]
            entry_groups = tuple(
                tuple(word.word_ref for word in entry.words)
                for entry in title.entries
            )
            ordinals = tuple(None for _ in title.entries)
            canonical_participants = [title]
            evidence_participants = [title]
        else:
            upper, lower = participants
            upper_ordinal = row_entry_ordinals[indexes[0]][0]
            lower_label_ordinal = row_entry_ordinals[indexes[1]][0]
            if upper_ordinal != lower_label_ordinal or len(upper_ordinal) != 1:
                return None
            entry_groups = (
                tuple(
                    word.word_ref
                    for word in [
                        *upper.entries[0].words,
                        *lower.entries[0].words,
                    ]
                ),
                *tuple(
                    tuple(word.word_ref for word in entry.words)
                    for entry in lower.entries[1:]
                ),
            )
            ordinals = (
                tuple(upper_ordinal),
                *tuple(
                    tuple(value)
                    for value in row_entry_ordinals[indexes[1]][1:]
                ),
            )
            canonical_participants = participants
            evidence_participants = participants
        if len(entry_groups) != len(ordinals):
            return None
        result.append(
            _RuledBaselineOutputRowPlan(
                word_refs=tuple(
                    word.word_ref
                    for participant in canonical_participants
                    for word in participant.words
                ),
                entry_word_ref_groups=entry_groups,
                geometry_column_ordinals=ordinals,
                row_coalescence_kind=kind,
                evidence_entry_word_ref_groups=tuple(
                    tuple(
                        tuple(word.word_ref for word in entry.words)
                        for entry in participant.entries
                    )
                    for participant in evidence_participants
                ),
                external_title=(
                    title_external_title if kind == "TITLE_PSEUDO_RULE" else False
                ),
                external_note=(
                    title_external_note if kind == "TITLE_PSEUDO_RULE" else False
                ),
            )
        )
        consumed.update(indexes)
    return result


def _ruled_baseline_source_fingerprint(
    region: _Region,
    *,
    core_word_refs: tuple[str, ...],
) -> str:
    core_ref_set = set(core_word_refs)
    if len(core_ref_set) != len(core_word_refs):
        return ""
    core_rows = []
    covered_refs: list[str] = []
    for row in region.rows:
        row_refs = [word.word_ref for word in row.words]
        intersection = set(row_refs).intersection(core_ref_set)
        if not intersection:
            continue
        if intersection != set(row_refs):
            return ""
        covered_refs.extend(row_refs)
        core_rows.append(
            {
                "bbox": list(row.bbox),
                "word_refs": row_refs,
                "entries": [
                    {
                        "bbox": list(entry.bbox),
                        "word_refs": [word.word_ref for word in entry.words],
                        "ordinals": entry.geometry_column_ordinals,
                    }
                    for entry in row.entries
                ],
                "external_title": row.external_title,
                "external_note": row.external_note,
            }
        )
    if (
        len(covered_refs) != len(set(covered_refs))
        or set(covered_refs) != core_ref_set
    ):
        return ""
    word_by_ref = {word.word_ref: word for word in region.words}
    if any(word_ref not in word_by_ref for word_ref in core_word_refs):
        return ""
    return _sha256_json(
        {
            "page_ref": region.page.page_ref,
            "bands": region.ruled_column_bands,
            "rows": core_rows,
            "words": [
                {
                    "word_ref": word_ref,
                    "order": word_by_ref[word_ref].order,
                    "bbox": list(word_by_ref[word_ref].bbox),
                    "text": word_by_ref[word_ref].text,
                }
                for word_ref in core_word_refs
            ],
        }
    )


def _region_has_valid_ruled_baseline_plan(region: _Region) -> bool:
    plan = region.ruled_baseline_recovery_plan
    if (
        plan is None
        or plan.page_ref != region.page.page_ref
        or tuple(region.ruled_column_bands or ())
        != plan.original_ruled_column_bands
        or not _region_has_exact_row_word_partition(region)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in region.rows
        )
    ):
        return False
    core_refs = list(plan.core_word_refs)
    released_refs = list(plan.released_non_table_word_refs)
    released_ref_set = set(released_refs)
    expected_output_refs = [
        word_ref for word_ref in core_refs if word_ref not in released_ref_set
    ]
    output_refs = [
        word_ref
        for row_plan in plan.output_rows
        for word_ref in row_plan.word_refs
    ]
    entry_refs = [
        word_ref
        for row_plan in plan.output_rows
        for group in row_plan.entry_word_ref_groups
        for word_ref in group
    ]
    if (
        not core_refs
        or len(core_refs) != len(set(core_refs))
        or not released_refs
        or len(released_refs) != len(released_ref_set)
        or not released_ref_set < set(core_refs)
        or len(output_refs) != len(set(output_refs))
        or len(entry_refs) != len(set(entry_refs))
        or output_refs != expected_output_refs
        or entry_refs != expected_output_refs
        or set(output_refs).intersection(released_ref_set)
    ):
        return False
    for row_plan in plan.output_rows:
        flattened = [
            word_ref
            for group in row_plan.entry_word_ref_groups
            for word_ref in group
        ]
        if (
            not row_plan.word_refs
            or flattened != list(row_plan.word_refs)
            or len(row_plan.entry_word_ref_groups)
            != len(row_plan.geometry_column_ordinals)
            or any(
                ordinals is not None
                and (
                    len(ordinals) != 1
                    or ordinals[0] < 0
                    or ordinals[0]
                    >= len(plan.original_ruled_column_bands)
                )
                for ordinals in row_plan.geometry_column_ordinals
            )
        ):
            return False
        evidence = row_plan.evidence_entry_word_ref_groups
        if evidence is not None:
            evidence_refs = [
                word_ref
                for physical_row in evidence
                for group in physical_row
                for word_ref in group
            ]
            if evidence_refs != list(row_plan.word_refs):
                return False
    macro_ref_groups = [
        *plan.title_pseudorule_ref_groups,
        *plan.wrapped_label_ref_groups,
    ]
    macro_refs = [word_ref for group in macro_ref_groups for word_ref in group]
    if (
        len(plan.title_pseudorule_ref_groups) != 2
        or len(plan.wrapped_label_ref_groups) != 2
        or len(macro_refs) != len(set(macro_refs))
        or not set(macro_refs) <= set(core_refs)
        or tuple(released_refs) != plan.title_pseudorule_ref_groups[1]
        or sum(
            row_plan.row_coalescence_kind == "TITLE_PSEUDO_RULE"
            for row_plan in plan.output_rows
        )
        != 1
        or sum(
            row_plan.row_coalescence_kind == "RULED_WRAPPED_LABEL"
            for row_plan in plan.output_rows
        )
        != 1
    ):
        return False
    region_refs = [word.word_ref for word in region.words]
    if any(region_refs.count(word_ref) != 1 for word_ref in core_refs):
        return False
    attached_groups = [
        *plan.attached_leading_row_ref_groups,
        *plan.attached_trailing_row_ref_groups,
    ]
    attached_refs = [word_ref for group in attached_groups for word_ref in group]
    if (
        len(attached_refs) != len(set(attached_refs))
        or set(attached_refs).intersection(core_refs)
        or set(attached_refs).intersection(released_ref_set)
        or not set(attached_refs) <= set(region_refs)
    ):
        return False
    core_ref_set = set(core_refs)
    noncore_row_groups = [
        tuple(word.word_ref for word in row.words)
        for row in region.rows
        if not {word.word_ref for word in row.words}.intersection(core_ref_set)
    ]
    if noncore_row_groups != attached_groups:
        return False
    return bool(
        _ruled_baseline_source_fingerprint(
            region,
            core_word_refs=plan.core_word_refs,
        )
        == plan.source_fingerprint_sha256
    )


def _forward_ruled_baseline_plan_for_boundary(
    region: _Region,
    *,
    leading_rows: list[_RowBand],
    trailing_row: _RowBand,
) -> _RuledBaselineRecoveryPlan | None:
    if not _region_has_valid_ruled_baseline_plan(region):
        return None
    plan = region.ruled_baseline_recovery_plan
    if plan is None or plan.boundary_bracket_proven:
        return None
    return replace(
        plan,
        boundary_bracket_proven=True,
        attached_leading_row_ref_groups=(
            *tuple(
                tuple(word.word_ref for word in row.words)
                for row in leading_rows
            ),
            *plan.attached_leading_row_ref_groups,
        ),
        attached_trailing_row_ref_groups=(
            *plan.attached_trailing_row_ref_groups,
            tuple(word.word_ref for word in trailing_row.words),
        ),
    )


def _forward_ruled_baseline_plan_for_leading_header(
    region: _Region,
    *,
    leading_rows: list[_RowBand],
) -> _RuledBaselineRecoveryPlan | None:
    if not _region_has_valid_ruled_baseline_plan(region):
        return None
    plan = region.ruled_baseline_recovery_plan
    if plan is None:
        return None
    return replace(
        plan,
        attached_leading_row_ref_groups=(
            *tuple(
                tuple(word.word_ref for word in row.words)
                for row in leading_rows
            ),
            *plan.attached_leading_row_ref_groups,
        ),
    )


def _apply_planned_ruled_baseline_recovery(
    regions: list[_Region],
) -> list[_Region]:
    """Commit valid marked plans atomically and consume every marker."""

    ordered = sorted(regions, key=_region_key)
    marked = [
        (index, region)
        for index, region in enumerate(ordered)
        if region.ruled_baseline_recovery_plan is not None
    ]
    if not marked:
        return ordered
    cleared = [_region_without_ruled_baseline_plan(region) for region in ordered]
    global_ref_degrees: dict[str, int] = {}
    for region in ordered:
        for word in region.words:
            global_ref_degrees[word.word_ref] = (
                global_ref_degrees.get(word.word_ref, 0) + 1
            )
    replacements: dict[int, _Region] = {}
    released_refs: list[str] = []
    for region_index, region in marked:
        plan = region.ruled_baseline_recovery_plan
        if (
            plan is None
            or not _region_has_valid_ruled_baseline_plan(region)
            or (plan.requires_boundary_bracket and not plan.boundary_bracket_proven)
            or any(
                global_ref_degrees.get(word_ref) != 1
                for word_ref in plan.core_word_refs
            )
        ):
            return sorted(cleared, key=_region_key)
        rebuilt = _materialize_ruled_baseline_plan(region, plan=plan)
        if rebuilt is None:
            return sorted(cleared, key=_region_key)
        replacements[region_index] = rebuilt
        released_refs.extend(plan.released_non_table_word_refs)
    result = [
        replacements.get(index, cleared[index])
        for index in range(len(ordered))
    ]
    input_refs = [word.word_ref for region in ordered for word in region.words]
    output_refs = [word.word_ref for region in result for word in region.words]
    if (
        len(input_refs) != len(set(input_refs))
        or len(output_refs) != len(set(output_refs))
        or len(released_refs) != len(set(released_refs))
        or set(output_refs).intersection(released_refs)
        or set(input_refs) != {*output_refs, *released_refs}
        or output_refs
        != [
            word_ref
            for word_ref in input_refs
            if word_ref not in set(released_refs)
        ]
    ):
        return sorted(cleared, key=_region_key)
    return sorted(result, key=_region_key)


def _region_without_ruled_baseline_plan(region: _Region) -> _Region:
    if region.ruled_baseline_recovery_plan is None:
        return region
    cleared = copy.copy(region)
    cleared.ruled_baseline_recovery_plan = None
    return cleared


def _materialize_ruled_baseline_plan(
    region: _Region,
    *,
    plan: _RuledBaselineRecoveryPlan,
) -> _Region | None:
    core_ref_set = set(plan.core_word_refs)
    core_indexes = [
        index
        for index, row in enumerate(region.rows)
        if {word.word_ref for word in row.words}.intersection(core_ref_set)
    ]
    if not core_indexes or core_indexes != list(
        range(core_indexes[0], core_indexes[-1] + 1)
    ):
        return None
    leading_rows = copy.deepcopy(region.rows[: core_indexes[0]])
    trailing_rows = copy.deepcopy(region.rows[core_indexes[-1] + 1 :])
    if [
        tuple(word.word_ref for word in row.words) for row in leading_rows
    ] != list(plan.attached_leading_row_ref_groups):
        return None
    if [
        tuple(word.word_ref for word in row.words) for row in trailing_rows
    ] != list(plan.attached_trailing_row_ref_groups):
        return None
    word_by_ref = {word.word_ref: word for word in region.words}
    if len(word_by_ref) != len(region.words):
        return None
    core_rows = []
    for row_plan in plan.output_rows:
        row = _row_from_ruled_baseline_output_plan(
            row_plan,
            word_by_ref=word_by_ref,
            column_bands=list(plan.original_ruled_column_bands),
        )
        if row is None:
            return None
        core_rows.append(row)
    rows = [*leading_rows, *core_rows, *trailing_rows]
    released_ref_set = set(plan.released_non_table_word_refs)
    words = sorted(
        [
            word
            for word in region.words
            if word.word_ref not in released_ref_set
        ],
        key=lambda word: word.order,
    )
    rebuilt = _Region(
        source_ref=_identifier(
            "ruled_baseline_region",
            [region.source_ref, plan.plan_id, *[word.word_ref for word in words]],
        ),
        page=region.page,
        bbox=region.bbox,
        words=words,
        rows=rows,
        confidence=region.confidence,
        origin=f"{region.origin}+RULED_BASELINE_RECOVERY",
        object_refs=list(region.object_refs),
        ruled_column_bands=list(plan.original_ruled_column_bands),
        mirrored_lane_seed=False,
        ruled_baseline_recovery_plan=None,
        released_non_table_word_refs=tuple(
            [
                *region.released_non_table_word_refs,
                *plan.released_non_table_word_refs,
            ]
        ),
    )
    if (
        not _region_has_exact_row_word_partition(rebuilt)
        or not _rows_have_strict_source_order(rebuilt.rows)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in rebuilt.rows
        )
        or any(
            word.word_ref in released_ref_set
            for row in rebuilt.rows
            for word in row.words
        )
    ):
        return None
    return rebuilt


def _row_from_ruled_baseline_output_plan(
    plan: _RuledBaselineOutputRowPlan,
    *,
    word_by_ref: dict[str, _Word],
    column_bands: list[tuple[float, float]],
) -> _RowBand | None:
    if any(word_ref not in word_by_ref for word_ref in plan.word_refs):
        return None
    words = [word_by_ref[word_ref] for word_ref in plan.word_refs]
    entries = []
    for group, ordinals in zip(
        plan.entry_word_ref_groups,
        plan.geometry_column_ordinals,
    ):
        if not group or any(word_ref not in word_by_ref for word_ref in group):
            return None
        entry_words = [word_by_ref[word_ref] for word_ref in group]
        entries.append(
            _EntryBand(
                words=entry_words,
                bbox=_merge_bboxes([word.bbox for word in entry_words]),
                text=_render_source_word_sequence(entry_words),
                anchor_ids=[],
                geometry_column_ordinals=(
                    None if ordinals is None else list(ordinals)
                ),
            )
        )
    row = _RowBand(
        page_ref=words[0].page_ref,
        bbox=_merge_bboxes([word.bbox for word in words]),
        words=words,
        entries=entries,
        external_title=plan.external_title,
        external_note=plan.external_note,
        row_coalescence_kind=plan.row_coalescence_kind,
    )
    evidence = plan.evidence_entry_word_ref_groups
    if evidence is not None:
        evidence_rows = []
        for physical_index, physical_groups in enumerate(evidence):
            physical_entries = []
            physical_words = []
            for group in physical_groups:
                group_words = [word_by_ref[word_ref] for word_ref in group]
                physical_words.extend(group_words)
                physical_entries.append(
                    _EntryBand(
                        words=group_words,
                        bbox=_merge_bboxes(
                            [word.bbox for word in group_words]
                        ),
                        text=_render_source_word_sequence(group_words),
                        anchor_ids=[],
                        geometry_column_ordinals=(
                            None
                            if plan.external_title
                            else _word_group_columns(
                                group_words,
                                column_bands=column_bands,
                            )
                        ),
                    )
                )
            evidence_rows.append(
                _RowBand(
                    page_ref=physical_words[0].page_ref,
                    bbox=_merge_bboxes(
                        [word.bbox for word in physical_words]
                    ),
                    words=physical_words,
                    entries=physical_entries,
                    external_title=(
                        plan.external_title and physical_index == 0
                    ),
                )
            )
        row.column_evidence_rows = tuple(evidence_rows)
    return row if _row_has_exact_entry_word_partition(row) else None


@dataclass(frozen=True)
class _BoundaryBracketPlan:
    region_index: int
    leading_rows: list[_RowBand]
    trailing_row: _RowBand


def _attach_unique_boundary_brackets(
    regions: list[_Region],
    *,
    words_by_page: dict[str, list[_Word]],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Attach a complete leading-and-terminal bracket to one table only."""

    ordered = sorted(regions, key=_region_key)
    claimed_refs = {
        word.word_ref for region in ordered for word in region.words
    }
    unclaimed_rows_by_page = {
        page_ref: _row_bands(
            [word for word in page_words if word.word_ref not in claimed_refs],
            config=config,
        )
        for page_ref, page_words in words_by_page.items()
    }
    plans = []
    for region_index, region in enumerate(ordered):
        bracket = _boundary_bracket_for_region(
            region,
            unclaimed_rows=unclaimed_rows_by_page.get(
                region.page.page_ref,
                [],
            ),
            object_bboxes=object_bboxes,
            config=config,
        )
        if bracket is not None:
            leading_rows, trailing_row = bracket
            plans.append(
                _BoundaryBracketPlan(
                    region_index=region_index,
                    leading_rows=leading_rows,
                    trailing_row=trailing_row,
                )
            )

    bracket_ref_degrees: dict[str, int] = {}
    for plan in plans:
        refs = {
            word.word_ref
            for row in [*plan.leading_rows, plan.trailing_row]
            for word in row.words
        }
        for word_ref in refs:
            bracket_ref_degrees[word_ref] = (
                bracket_ref_degrees.get(word_ref, 0) + 1
            )
    accepted = [
        plan
        for plan in plans
        if all(
            bracket_ref_degrees[word.word_ref] == 1
            for row in [*plan.leading_rows, plan.trailing_row]
            for word in row.words
        )
    ]
    if not accepted:
        return ordered

    consumed: set[int] = set()
    replacements: list[_Region] = []
    for plan in accepted:
        region = ordered[plan.region_index]
        rebuilt = _rebuild_with_boundary_bracket(
            region,
            leading_rows=plan.leading_rows,
            trailing_row=plan.trailing_row,
            object_bboxes=object_bboxes,
        )
        if rebuilt is None:
            continue
        consumed.add(plan.region_index)
        replacements.append(rebuilt)
    return sorted(
        [
            *[
                region
                for index, region in enumerate(ordered)
                if index not in consumed
            ],
            *replacements,
        ],
        key=_region_key,
    )


def _boundary_bracket_for_region(
    region: _Region,
    *,
    unclaimed_rows: list[_RowBand],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_RowBand], _RowBand] | None:
    if not region.rows or not _region_has_exact_row_word_partition(region):
        return None
    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in region.rows
    )
    maximum_gap = max(1.0, typical_height)
    before = [
        row for row in unclaimed_rows if row.bbox[3] <= region.bbox[1]
    ]
    leading_rows: list[_RowBand] = []
    lower = region.rows[0]
    for row in reversed(before):
        gap = lower.bbox[1] - row.bbox[3]
        if gap < 0.0 or gap > maximum_gap:
            break
        if not _row_belongs_to_core_envelope(
            row,
            core_rows=region.rows,
            direction="LEADING",
            config=config,
        ):
            break
        if _horizontal_separator_between(
            row,
            lower,
            page_ref=region.page.page_ref,
            table_bbox=_merge_bboxes([row.bbox, region.bbox]),
            object_bboxes=object_bboxes,
        ):
            break
        leading_rows.insert(0, row)
        lower = row
    if not leading_rows:
        return None

    after = [
        row for row in unclaimed_rows if row.bbox[1] >= region.bbox[3]
    ]
    if not after:
        return None
    trailing_row = after[0]
    trailing_gap = trailing_row.bbox[1] - region.bbox[3]
    if trailing_gap < 0.0 or trailing_gap > maximum_gap:
        return None
    if (
        len(trailing_row.entries) < 2
        or not _row_is_terminal_total(trailing_row)
        or not _rightmost_value_track_matches(
            trailing_row,
            region=region,
            config=config,
        )
        or _horizontal_separator_between(
            region.rows[-1],
            trailing_row,
            page_ref=region.page.page_ref,
            table_bbox=_merge_bboxes([region.bbox, trailing_row.bbox]),
            object_bboxes=object_bboxes,
        )
    ):
        return None

    leading_words = [word for row in leading_rows for word in row.words]
    trailing_words = list(trailing_row.words)
    bracket_refs = [
        word.word_ref for word in [*leading_words, *trailing_words]
    ]
    region_refs = [word.word_ref for word in region.words]
    if (
        len(bracket_refs) != len(set(bracket_refs))
        or set(bracket_refs).intersection(region_refs)
        or max(word.order for word in leading_words)
        >= min(word.order for word in region.words)
        or max(word.order for word in region.words)
        >= min(word.order for word in trailing_words)
    ):
        return None
    return leading_rows, trailing_row


def _rightmost_value_track_matches(
    row: _RowBand,
    *,
    region: _Region,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    rightmost = row.entries[-1]
    if not _looks_value_like(rightmost.text) or region.page.width <= 0.0:
        return False
    stable = [
        candidate.entries[-1]
        for candidate in region.rows
        if len(candidate.entries) >= 2
        and _looks_value_like(candidate.entries[-1].text)
    ]
    if len(stable) < config.minimum_column_observations:
        return False
    expected_left = statistics.median(entry.bbox[0] for entry in stable)
    expected_right = statistics.median(entry.bbox[2] for entry in stable)
    return (
        abs(rightmost.bbox[0] - expected_left) / region.page.width
        <= config.column_tolerance_width_ratio
        and abs(rightmost.bbox[2] - expected_right) / region.page.width
        <= config.column_tolerance_width_ratio
    )


def _rebuild_with_boundary_bracket(
    region: _Region,
    *,
    leading_rows: list[_RowBand],
    trailing_row: _RowBand,
    object_bboxes: list[_ObjectGeometry],
) -> _Region | None:
    rows = [*leading_rows, *region.rows, trailing_row]
    refs = [word.word_ref for row in rows for word in row.words]
    expected_refs = {
        word.word_ref
        for word in [
            *[word for row in leading_rows for word in row.words],
            *region.words,
            *trailing_row.words,
        ]
    }
    if len(refs) != len(set(refs)) or set(refs) != expected_refs:
        return None
    words = sorted(
        [word for row in rows for word in row.words],
        key=lambda word: word.order,
    )
    bbox = _merge_bboxes([row.bbox for row in rows])
    forwarded_plan = _forward_ruled_baseline_plan_for_boundary(
        region,
        leading_rows=leading_rows,
        trailing_row=trailing_row,
    )
    return _Region(
        source_ref=_identifier(
            "boundary_bracket_region",
            [region.source_ref, *[word.word_ref for word in words]],
        ),
        page=region.page,
        bbox=bbox,
        words=words,
        rows=rows,
        confidence=region.confidence,
        origin=f"{region.origin}+BOUNDARY_BRACKET",
        object_refs=_overlapping_object_refs(
            page_ref=region.page.page_ref,
            bbox=bbox,
            object_bboxes=object_bboxes,
        ),
        ruled_column_bands=region.ruled_column_bands,
        ruled_baseline_recovery_plan=forwarded_plan,
    )


@dataclass(frozen=True)
class _LeadingHeaderStackPlan:
    region_index: int
    rows: list[_RowBand]


def _attach_unique_leading_header_stacks(
    regions: list[_Region],
    *,
    words_by_page: dict[str, list[_Word]],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Attach a compact, track-backed leading header stack to one table."""

    ordered = sorted(regions, key=_region_key)
    claimed_refs = {
        word.word_ref for region in ordered for word in region.words
    }
    unclaimed_rows_by_page = {
        page_ref: _row_bands(
            [word for word in page_words if word.word_ref not in claimed_refs],
            config=config,
        )
        for page_ref, page_words in words_by_page.items()
    }
    plans = []
    for region_index, region in enumerate(ordered):
        rows = _leading_header_stack_for_region(
            region,
            unclaimed_rows=unclaimed_rows_by_page.get(
                region.page.page_ref,
                [],
            ),
            object_bboxes=object_bboxes,
            config=config,
        )
        if rows is not None:
            plans.append(
                _LeadingHeaderStackPlan(
                    region_index=region_index,
                    rows=rows,
                )
            )

    header_ref_degrees: dict[str, int] = {}
    for plan in plans:
        for word_ref in {
            word.word_ref for row in plan.rows for word in row.words
        }:
            header_ref_degrees[word_ref] = (
                header_ref_degrees.get(word_ref, 0) + 1
            )
    accepted = [
        plan
        for plan in plans
        if all(
            header_ref_degrees[word.word_ref] == 1
            for row in plan.rows
            for word in row.words
        )
    ]
    if not accepted:
        return ordered

    consumed: set[int] = set()
    replacements: list[_Region] = []
    for plan in accepted:
        region = ordered[plan.region_index]
        rebuilt = _rebuild_with_leading_header_stack(
            region,
            leading_rows=plan.rows,
            object_bboxes=object_bboxes,
        )
        if rebuilt is None:
            continue
        consumed.add(plan.region_index)
        replacements.append(rebuilt)
    return sorted(
        [
            *[
                region
                for index, region in enumerate(ordered)
                if index not in consumed
            ],
            *replacements,
        ],
        key=_region_key,
    )


def _leading_header_stack_for_region(
    region: _Region,
    *,
    unclaimed_rows: list[_RowBand],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowBand] | None:
    if (
        not region.rows
        or region.page.width <= 0.0
        or not _region_has_exact_row_word_partition(region)
    ):
        return None
    dense_rows = [row for row in region.rows if len(row.entries) >= 2]
    tracks = _repeated_entry_tracks(
        dense_rows,
        width=max(1.0, _bbox_width(region.bbox)),
        config=config,
    )
    if len(tracks) < 2:
        return None

    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in region.rows
    )
    before = [
        row for row in unclaimed_rows if row.bbox[3] <= region.bbox[1]
    ]
    if not before:
        return None
    nearest = before[-1]
    outer_gap = region.rows[0].bbox[1] - nearest.bbox[3]
    if (
        outer_gap < 0.0
        or outer_gap > max(1.0, typical_height)
        or _horizontal_separator_between(
            nearest,
            region.rows[0],
            page_ref=region.page.page_ref,
            table_bbox=_merge_bboxes([nearest.bbox, region.bbox]),
            object_bboxes=object_bboxes,
        )
    ):
        return None

    leading_rows: list[_RowBand] = []
    supported_track_indexes: set[int] = set()
    lower = region.rows[0]
    maximum_internal_gap = max(
        1.0,
        typical_height * config.boundary_gap_height_ratio,
    )
    for row in reversed(before):
        gap = lower.bbox[1] - row.bbox[3]
        if gap < 0.0 or gap > (
            max(1.0, typical_height)
            if not leading_rows
            else maximum_internal_gap
        ):
            break
        row_tracks = _compact_header_row_track_support(
            row,
            tracks=tracks,
            page_width=region.page.width,
            config=config,
        )
        if row_tracks is None:
            break
        leading_rows.insert(0, row)
        supported_track_indexes.update(row_tracks)
        lower = row

    if (
        not 2 <= len(leading_rows) <= 4
        or len(supported_track_indexes) < 2
    ):
        return None

    header_words = [
        word for row in leading_rows for word in row.words
    ]
    header_refs = [word.word_ref for word in header_words]
    region_refs = [word.word_ref for word in region.words]
    ordered_rows = [*leading_rows, region.rows[0]]
    if (
        len(header_refs) != len(set(header_refs))
        or set(header_refs).intersection(region_refs)
        or any(
            max(word.order for word in upper.words)
            >= min(word.order for word in lower_row.words)
            for upper, lower_row in zip(ordered_rows, ordered_rows[1:])
        )
    ):
        return None
    return leading_rows


def _compact_header_row_track_support(
    row: _RowBand,
    *,
    tracks: list[_ColumnTrack],
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> set[int] | None:
    if (
        not 1 <= len(row.entries) <= 4
        or len(row.words) > 4
        or _is_table_core_row(row)
        or any(_looks_value_like(entry.text) for entry in row.entries)
    ):
        return None
    supported: set[int] = set()
    for entry in row.entries:
        entry_tracks = {
            index
            for index, track in enumerate(tracks)
            if entry.bbox[0] <= track.coordinate <= entry.bbox[2]
            or abs(_entry_edge(entry, track.edge) - track.coordinate)
            / page_width
            <= config.column_tolerance_width_ratio
        }
        if not entry_tracks:
            return None
        supported.update(entry_tracks)
    return supported


def _rebuild_with_leading_header_stack(
    region: _Region,
    *,
    leading_rows: list[_RowBand],
    object_bboxes: list[_ObjectGeometry],
) -> _Region | None:
    rows = [*leading_rows, *region.rows]
    refs = [word.word_ref for row in rows for word in row.words]
    expected_refs = {
        word.word_ref
        for word in [
            *[word for row in leading_rows for word in row.words],
            *region.words,
        ]
    }
    if len(refs) != len(set(refs)) or set(refs) != expected_refs:
        return None
    words = sorted(
        [word for row in rows for word in row.words],
        key=lambda word: word.order,
    )
    bbox = _merge_bboxes([row.bbox for row in rows])
    forwarded_plan = _forward_ruled_baseline_plan_for_leading_header(
        region,
        leading_rows=leading_rows,
    )
    return _Region(
        source_ref=_identifier(
            "leading_header_stack_region",
            [region.source_ref, *[word.word_ref for word in words]],
        ),
        page=region.page,
        bbox=bbox,
        words=words,
        rows=rows,
        confidence=region.confidence,
        origin=f"{region.origin}+LEADING_HEADER_STACK",
        object_refs=_overlapping_object_refs(
            page_ref=region.page.page_ref,
            bbox=bbox,
            object_bboxes=object_bboxes,
        ),
        ruled_column_bands=region.ruled_column_bands,
        ruled_baseline_recovery_plan=forwarded_plan,
    )


@dataclass(frozen=True)
class _MicrotrackCutPlan:
    region_index: int
    row_index: int
    entry_index: int
    cut_index: int
    marker_side: str
    value_bbox: tuple[float, float, float, float]
    marker_bbox: tuple[float, float, float, float]
    word_refs: tuple[str, ...]


def _split_repeated_microtrack_entries(
    regions: list[_Region],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Split only unique value/marker microtracks repeated across rows.

    Planning is global and read-only.  Any ambiguity in a repeated pattern
    returns the original regions, so one safe-looking entry can never leave a
    partially mutated table behind.
    """

    ordered = sorted(regions, key=_region_key)
    candidates: list[_MicrotrackCutPlan] = []
    for region_index, region in enumerate(ordered):
        if _region_has_valid_ruled_baseline_plan(region):
            continue
        classified_rows = copy.deepcopy(region.rows)
        _classify_rows(classified_rows)
        for row_index, (row, classified) in enumerate(
            zip(region.rows, classified_rows)
        ):
            if classified.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
                continue
            if not _row_has_atomic_word_geometry(row):
                continue
            for entry_index, entry in enumerate(row.entries):
                if entry_index == 0:
                    continue
                candidates.extend(
                    _microtrack_cut_candidates(
                        entry,
                        region_index=region_index,
                        row_index=row_index,
                        entry_index=entry_index,
                    )
                )

    adjacency = {
        index: {
            other
            for other in range(len(candidates))
            if index != other
            and _microtrack_plans_compatible(
                candidates[index],
                candidates[other],
                regions=ordered,
                config=config,
            )
        }
        for index in range(len(candidates))
    }
    supported_indexes: set[int] = set()
    visited: set[int] = set()
    for start in range(len(candidates)):
        if start in visited:
            continue
        component: set[int] = set()
        pending = [start]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        visited.update(component)
        row_keys = {
            (
                candidates[index].region_index,
                candidates[index].row_index,
            )
            for index in component
        }
        if len(row_keys) < 2:
            continue
        if len(row_keys) != len(component) or any(
            not _microtrack_plans_compatible(
                candidates[left],
                candidates[right],
                regions=ordered,
                config=config,
            )
            for left in component
            for right in component
            if left < right
        ):
            return ordered
        supported_indexes.update(component)

    supported = [candidates[index] for index in sorted(supported_indexes)]
    if not supported:
        return ordered
    plans_by_entry: dict[tuple[int, int, int], list[_MicrotrackCutPlan]] = {}
    owned_refs: set[str] = set()
    for plan in supported:
        key = (plan.region_index, plan.row_index, plan.entry_index)
        plans_by_entry.setdefault(key, []).append(plan)
        if owned_refs.intersection(plan.word_refs):
            return ordered
        owned_refs.update(plan.word_refs)
    if any(len(plans) != 1 for plans in plans_by_entry.values()):
        return ordered

    rebuilt = copy.deepcopy(ordered)
    plans_by_row: dict[tuple[int, int], dict[int, _MicrotrackCutPlan]] = {}
    for (region_index, row_index, entry_index), plans in plans_by_entry.items():
        plans_by_row.setdefault((region_index, row_index), {})[
            entry_index
        ] = plans[0]
    affected_regions: set[int] = set()
    for (region_index, row_index), entry_plans in sorted(plans_by_row.items()):
        region = rebuilt[region_index]
        row = region.rows[row_index]
        original_entries = list(row.entries)
        if row.column_evidence_entries is None:
            row.column_evidence_entries = tuple(copy.deepcopy(original_entries))
        rebuilt_entries = []
        for entry_index, entry in enumerate(original_entries):
            plan = entry_plans.get(entry_index)
            if plan is None:
                rebuilt_entries.append(entry)
                continue
            words = sorted(
                entry.words,
                key=lambda word: (word.bbox[0], word.order),
            )
            if tuple(word.word_ref for word in words) != plan.word_refs:
                return ordered
            groups = [words[: plan.cut_index], words[plan.cut_index :]]
            if any(not group for group in groups):
                return ordered
            rebuilt_entries.extend(
                _EntryBand(
                    words=list(group),
                    bbox=_merge_bboxes([word.bbox for word in group]),
                    text=_render_source_word_sequence(group),
                    anchor_ids=[],
                )
                for group in groups
            )
        row.entries = rebuilt_entries
        affected_regions.add(region_index)

    for region_index in affected_regions:
        region = rebuilt[region_index]
        region.origin = f"{region.origin}+REPEATED_MICROTRACK"
        if not _region_has_exact_row_word_partition(region):
            return ordered
        for row in region.rows:
            entry_refs = [
                word.word_ref for entry in row.entries for word in entry.words
            ]
            row_refs = [word.word_ref for word in row.words]
            if (
                len(entry_refs) != len(set(entry_refs))
                or set(entry_refs) != set(row_refs)
            ):
                return ordered
    return sorted(rebuilt, key=_region_key)


def _microtrack_cut_candidates(
    entry: _EntryBand,
    *,
    region_index: int,
    row_index: int,
    entry_index: int,
) -> list[_MicrotrackCutPlan]:
    words = sorted(entry.words, key=lambda word: (word.bbox[0], word.order))
    if len(words) < 2 or any(
        words[index].order >= words[index + 1].order
        or words[index].bbox[2] > words[index + 1].bbox[0]
        for index in range(len(words) - 1)
    ):
        return []
    typical_height = statistics.median(_bbox_height(word.bbox) for word in words)
    result = []
    for cut_index in range(1, len(words)):
        left = words[:cut_index]
        right = words[cut_index:]
        left_value = _microtrack_value_or_placeholder(left)
        right_value = _microtrack_value_or_placeholder(right)
        left_marker = _compact_microtrack_marker(
            left,
            typical_height=typical_height,
        )
        right_marker = _compact_microtrack_marker(
            right,
            typical_height=typical_height,
        )
        if left_value and right_marker and not right_value:
            marker_side = "RIGHT"
            value_words = left
            marker_words = right
        elif left_marker and right_value and not left_value:
            marker_side = "LEFT"
            value_words = right
            marker_words = left
        else:
            continue
        result.append(
            _MicrotrackCutPlan(
                region_index=region_index,
                row_index=row_index,
                entry_index=entry_index,
                cut_index=cut_index,
                marker_side=marker_side,
                value_bbox=_merge_bboxes([word.bbox for word in value_words]),
                marker_bbox=_merge_bboxes([word.bbox for word in marker_words]),
                word_refs=tuple(word.word_ref for word in words),
            )
        )
    return result


def _microtrack_value_or_placeholder(words: list[_Word]) -> bool:
    separated = " ".join(word.text.strip() for word in words).strip()
    joined = "".join(word.text.strip() for word in words).strip()
    return bool(
        _looks_value_like(separated)
        or _looks_value_like(joined)
        or (
            len(words) == 1
            and _MARKER_PATTERN.fullmatch(words[0].text.strip())
        )
    )


def _compact_microtrack_marker(
    words: list[_Word],
    *,
    typical_height: float,
) -> bool:
    if not words or len(words) > 2:
        return False
    separated = " ".join(word.text.strip() for word in words).strip()
    if _UNIT_PATTERN.fullmatch(unicodedata.normalize("NFKC", separated)):
        return True
    return bool(
        all(word.text.strip().isalpha() for word in words)
        and _bbox_width(_merge_bboxes([word.bbox for word in words]))
        <= max(1.0, typical_height * 4.0)
        and not re.search(r"[.!?;]\s*$", separated)
    )


def _row_has_atomic_word_geometry(row: _RowBand) -> bool:
    if not row.words:
        return False
    word_bbox = _merge_bboxes([word.bbox for word in row.words])
    return _bbox_height(row.bbox) <= max(1.0, _bbox_height(word_bbox)) * 1.25


def _microtrack_plans_compatible(
    left: _MicrotrackCutPlan,
    right: _MicrotrackCutPlan,
    *,
    regions: list[_Region],
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if (
        left.region_index != right.region_index
        or left.row_index == right.row_index
        or left.marker_side != right.marker_side
    ):
        return False
    page_width = regions[left.region_index].page.width
    if page_width <= 0.0:
        return False
    return all(
        abs(left_bbox[edge] - right_bbox[edge]) / page_width
        <= config.column_tolerance_width_ratio
        for left_bbox, right_bbox in (
            (left.value_bbox, right.value_bbox),
            (left.marker_bbox, right.marker_bbox),
        )
        for edge in (0, 2)
    )


@dataclass(frozen=True)
class _RowCoalescencePlan:
    region_index: int
    start_index: int
    end_index: int
    kind: str
    entry_word_ref_groups: tuple[tuple[str, ...], ...]


def _coalesce_logical_row_fragments(
    regions: list[_Region],
    *,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Coalesce only uniquely proven physical fragments into logical rows."""

    ordered = sorted(regions, key=_region_key)
    region_ref_counts: dict[str, int] = {}
    for region in ordered:
        for word in region.words:
            region_ref_counts[word.word_ref] = (
                region_ref_counts.get(word.word_ref, 0) + 1
            )

    plans: list[_RowCoalescencePlan] = []
    for region_index, region in enumerate(ordered):
        if (
            _region_has_valid_ruled_baseline_plan(region)
            or region.ruled_column_bands is not None
            or not region.rows
            or not _region_has_exact_row_word_partition(region)
        ):
            continue
        typical_height = statistics.median(
            _bbox_height(row.bbox) for row in region.rows
        )
        if typical_height <= 0.0:
            continue
        plans.extend(
            _wrapped_label_coalescence_plans(
                region,
                region_index=region_index,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
                config=config,
            )
        )
        plans.extend(
            _leaf_header_coalescence_plans(
                region,
                region_index=region_index,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
                config=config,
            )
        )
        plans.extend(
            _group_label_coalescence_plans(
                region,
                region_index=region_index,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        )
        plans.extend(
            _narrow_header_coalescence_plans(
                region,
                region_index=region_index,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
                config=config,
            )
        )
    if not plans:
        return ordered

    occupied_rows: set[tuple[int, int]] = set()
    planned_refs: set[str] = set()
    for plan in sorted(
        plans,
        key=lambda item: (
            item.region_index,
            item.start_index,
            item.end_index,
            item.kind,
        ),
    ):
        row_keys = {
            (plan.region_index, index)
            for index in range(plan.start_index, plan.end_index)
        }
        refs = {
            word_ref
            for group in plan.entry_word_ref_groups
            for word_ref in group
        }
        if (
            not refs
            or occupied_rows.intersection(row_keys)
            or planned_refs.intersection(refs)
            or any(region_ref_counts.get(word_ref) != 1 for word_ref in refs)
        ):
            return ordered
        occupied_rows.update(row_keys)
        planned_refs.update(refs)

    rebuilt = copy.deepcopy(ordered)
    plans_by_region: dict[int, list[_RowCoalescencePlan]] = {}
    for plan in plans:
        plans_by_region.setdefault(plan.region_index, []).append(plan)
    for region_index, region_plans in sorted(plans_by_region.items()):
        source_region = ordered[region_index]
        target_region = rebuilt[region_index]
        next_plan_by_start = {
            plan.start_index: plan
            for plan in sorted(
                region_plans,
                key=lambda item: (item.start_index, item.end_index),
            )
        }
        rebuilt_rows: list[_RowBand] = []
        index = 0
        while index < len(source_region.rows):
            plan = next_plan_by_start.get(index)
            if plan is None:
                rebuilt_rows.append(copy.deepcopy(source_region.rows[index]))
                index += 1
                continue
            participants = source_region.rows[
                plan.start_index : plan.end_index
            ]
            replacement = _row_from_coalescence_plan(
                participants,
                plan=plan,
            )
            if replacement is None:
                return ordered
            rebuilt_rows.append(replacement)
            index = plan.end_index
        target_region.rows = rebuilt_rows
        target_region.origin = (
            f"{target_region.origin}+LOGICAL_ROW_COALESCENCE"
        )
        if (
            not _region_has_exact_row_word_partition(target_region)
            or any(
                not _row_has_exact_entry_word_partition(row)
                for row in target_region.rows
            )
        ):
            return ordered
    return sorted(rebuilt, key=_region_key)


def _wrapped_label_coalescence_plans(
    region: _Region,
    *,
    region_index: int,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowCoalescencePlan]:
    result = []
    for upper_index, (upper, lower) in enumerate(
        zip(region.rows, region.rows[1:])
    ):
        if not all(_row_is_grouping_eligible(row) for row in (upper, lower)):
            continue
        if (
            len(upper.entries) != 1
            or len(upper.words) < 2
            or _looks_value_like(upper.entries[0].text)
            or _text_is_terminal(upper.entries[0].text)
            or len(lower.entries) < 3
            or len(lower.entries[0].words) < 2
            or _looks_value_like(lower.entries[0].text)
            or not _leading_alpha_is_lower(lower.entries[0].text)
            or not _rows_share_zero_gap_boundary(
                upper,
                lower,
                typical_height=typical_height,
            )
            or abs(upper.bbox[0] - lower.entries[0].bbox[0])
            > typical_height * 0.25
            or lower.entries[0].bbox[0] < upper.bbox[0] - typical_height * 0.1
            or lower.entries[0].bbox[2] > upper.bbox[2] + typical_height * 0.1
            or _bbox_width(lower.entries[0].bbox)
            > _bbox_width(upper.bbox) - typical_height * 0.5
            or not _looks_value_like(lower.entries[-1].text)
            or _horizontal_separator_at_row_boundary(
                upper,
                lower,
                page_ref=region.page.page_ref,
                table_bbox=region.bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ):
            continue
        downstream = _bounded_downstream_rows(
            region,
            after_index=upper_index + 1,
            typical_height=typical_height,
            object_bboxes=object_bboxes,
        )
        if not _suffix_tracks_repeat_later(
            lower.entries[1:],
            downstream,
            page_width=region.page.width,
            config=config,
        ):
            continue
        combined_refs = tuple(
            word.word_ref
            for word in [*upper.entries[0].words, *lower.entries[0].words]
        )
        result.append(
            _RowCoalescencePlan(
                region_index=region_index,
                start_index=upper_index,
                end_index=upper_index + 2,
                kind="WRAPPED_LABEL",
                entry_word_ref_groups=(
                    combined_refs,
                    *[
                        tuple(word.word_ref for word in entry.words)
                        for entry in lower.entries[1:]
                    ],
                ),
            )
        )
    return result


def _leaf_header_coalescence_plans(
    region: _Region,
    *,
    region_index: int,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowCoalescencePlan]:
    result = []
    components = _maximal_row_components(
        region,
        row_predicate=lambda row: (
            _row_is_grouping_eligible(row)
            and all(not _looks_value_like(entry.text) for entry in row.entries)
        ),
        adjacency_predicate=lambda upper, lower: (
            _rows_share_zero_gap_boundary(
                upper,
                lower,
                typical_height=typical_height,
            )
            and not _horizontal_separator_at_row_boundary(
                upper,
                lower,
                page_ref=region.page.page_ref,
                table_bbox=region.bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ),
    )
    for start_index, end_index in components:
        if not 2 <= end_index - start_index <= 4:
            continue
        rows = region.rows[start_index:end_index]
        terminal_words = sorted(
            rows[-1].words,
            key=lambda word: (word.bbox[0], word.order),
        )
        if not 3 <= len(terminal_words) <= 12:
            continue
        centers = [_bbox_center_x(word.bbox) for word in terminal_words]
        if any(
            centers[index + 1] - centers[index] < typical_height * 0.5
            for index in range(len(centers) - 1)
        ):
            continue
        buckets: list[list[str]] = [[] for _ in centers]
        valid = True
        for row in rows:
            assignments = []
            for word in row.words:
                distances = [
                    abs(_bbox_center_x(word.bbox) - center)
                    for center in centers
                ]
                ranked = sorted(range(len(distances)), key=distances.__getitem__)
                if (
                    len(ranked) < 2
                    or distances[ranked[1]] - distances[ranked[0]]
                    < typical_height * 0.5
                ):
                    valid = False
                    break
                assignments.append(ranked[0])
                buckets[ranked[0]].append(word.word_ref)
            if not valid or assignments != sorted(assignments):
                valid = False
                break
        if not valid or any(not bucket for bucket in buckets):
            continue
        downstream = _bounded_downstream_rows(
            region,
            after_index=end_index - 1,
            typical_height=typical_height,
            object_bboxes=object_bboxes,
        )
        if (
            sum(
                _row_matches_leaf_body_tracks(
                    row,
                    header_bboxes=[word.bbox for word in terminal_words],
                    page_width=region.page.width,
                    config=config,
                )
                for row in downstream
            )
            < config.minimum_column_observations
        ):
            continue
        result.append(
            _RowCoalescencePlan(
                region_index=region_index,
                start_index=start_index,
                end_index=end_index,
                kind="LEAF_HEADER",
                entry_word_ref_groups=tuple(tuple(bucket) for bucket in buckets),
            )
        )
    return result


def _group_label_coalescence_plans(
    region: _Region,
    *,
    region_index: int,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> list[_RowCoalescencePlan]:
    components = _maximal_row_components(
        region,
        row_predicate=lambda row: (
            _row_is_grouping_eligible(row)
            and len(row.entries) == 1
            and not _looks_value_like(row.entries[0].text)
        ),
        adjacency_predicate=lambda upper, lower: (
            _rows_share_zero_gap_boundary(
                upper,
                lower,
                typical_height=typical_height,
            )
            and abs(upper.bbox[0] - lower.bbox[0])
            <= typical_height * 0.25
            and not _horizontal_separator_at_row_boundary(
                upper,
                lower,
                page_ref=region.page.page_ref,
                table_bbox=region.bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ),
    )
    result = []
    region_width = _bbox_width(region.bbox)
    for start_index, end_index in components:
        if not 2 <= end_index - start_index <= 4 or end_index >= len(region.rows):
            continue
        rows = region.rows[start_index:end_index]
        body = region.rows[end_index]
        widths = [_bbox_width(row.bbox) for row in rows]
        body_gap = body.bbox[1] - rows[-1].bbox[3]
        if (
            any(not _leading_alpha_is_lower(row.entries[0].text) for row in rows[1:])
            or any(_text_is_terminal(row.entries[0].text) for row in rows[:-1])
            or any(
                widths[index + 1] > widths[index] + typical_height * 0.1
                for index in range(len(widths) - 1)
            )
            or sum(len(row.words) for row in rows) > 12
            or any(len(row.words) > 5 for row in rows)
            or _bbox_width(_merge_bboxes([row.bbox for row in rows]))
            > region_width * 0.3
            or rows[0].bbox[0] > region.bbox[0] + region_width * 0.3
            or not _row_is_grouping_eligible(body)
            or len(body.entries) < 2
            or not any(_looks_value_like(entry.text) for entry in body.entries)
            or not -typical_height * 0.05 <= body_gap <= typical_height
            or _horizontal_separator_at_row_boundary(
                rows[-1],
                body,
                page_ref=region.page.page_ref,
                table_bbox=region.bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ):
            continue
        result.append(
            _RowCoalescencePlan(
                region_index=region_index,
                start_index=start_index,
                end_index=end_index,
                kind="GROUP_LABEL_STACK",
                entry_word_ref_groups=(
                    tuple(word.word_ref for row in rows for word in row.words),
                ),
            )
        )
    return result


def _narrow_header_coalescence_plans(
    region: _Region,
    *,
    region_index: int,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowCoalescencePlan]:
    components = _maximal_row_components(
        region,
        row_predicate=lambda row: (
            _row_is_grouping_eligible(row)
            and len(row.entries) == 1
            and not _looks_value_like(row.entries[0].text)
        ),
        adjacency_predicate=lambda upper, lower: (
            _rows_share_zero_gap_boundary(
                upper,
                lower,
                typical_height=typical_height,
            )
            and not _horizontal_separator_at_row_boundary(
                upper,
                lower,
                page_ref=region.page.page_ref,
                table_bbox=region.bbox,
                typical_height=typical_height,
                object_bboxes=object_bboxes,
            )
        ),
    )
    result = []
    region_width = _bbox_width(region.bbox)
    for start_index, end_index in components:
        if end_index - start_index != 2:
            continue
        upper, lower = region.rows[start_index:end_index]
        envelope = _merge_bboxes([upper.bbox, lower.bbox])
        if (
            any(
                row.bbox[0] < region.bbox[0] + region_width * 0.7
                or _bbox_width(row.bbox) > region_width * 0.3
                for row in (upper, lower)
            )
            or _horizontal_interval_overlap_ratio(upper.bbox, lower.bbox) < 0.75
            or abs(_bbox_center_x(upper.bbox) - _bbox_center_x(lower.bbox))
            > typical_height * 0.25
            or len(upper.words) + len(lower.words) > 4
        ):
            continue
        downstream = _bounded_downstream_rows(
            region,
            after_index=end_index - 1,
            typical_height=typical_height,
            object_bboxes=object_bboxes,
        )
        suffix_rows = [
            row
            for row in downstream
            if _row_is_narrow_suffix_body(
                row,
                header_envelope=envelope,
                typical_height=typical_height,
            )
        ]
        if not _has_two_stable_suffix_rows(
            suffix_rows,
            page_width=region.page.width,
            config=config,
        ):
            continue
        result.append(
            _RowCoalescencePlan(
                region_index=region_index,
                start_index=start_index,
                end_index=end_index,
                kind="NARROW_HEADER",
                entry_word_ref_groups=(
                    tuple(
                        word.word_ref
                        for row in (upper, lower)
                        for word in row.words
                    ),
                ),
            )
        )
    return result


def _maximal_row_components(
    region: _Region,
    *,
    row_predicate: Any,
    adjacency_predicate: Any,
) -> list[tuple[int, int]]:
    result = []
    index = 0
    while index < len(region.rows):
        if not row_predicate(region.rows[index]):
            index += 1
            continue
        end = index + 1
        while (
            end < len(region.rows)
            and row_predicate(region.rows[end])
            and adjacency_predicate(region.rows[end - 1], region.rows[end])
        ):
            end += 1
        result.append((index, end))
        index = end
    return result


def _row_from_coalescence_plan(
    rows: list[_RowBand],
    *,
    plan: _RowCoalescencePlan,
) -> _RowBand | None:
    if len(rows) < 2 or not _rows_have_strict_source_order(rows):
        return None
    words = [word for row in rows for word in row.words]
    word_by_ref = {word.word_ref: word for word in words}
    if len(word_by_ref) != len(words):
        return None
    planned_refs = [
        word_ref
        for group in plan.entry_word_ref_groups
        for word_ref in group
    ]
    if (
        len(planned_refs) != len(set(planned_refs))
        or set(planned_refs) != set(word_by_ref)
    ):
        return None
    entries = []
    for group in plan.entry_word_ref_groups:
        entry_words = [word_by_ref[word_ref] for word_ref in group]
        if not entry_words or any(
            entry_words[index].order >= entry_words[index + 1].order
            for index in range(len(entry_words) - 1)
        ):
            return None
        entries.append(
            _EntryBand(
                words=entry_words,
                bbox=_merge_bboxes([word.bbox for word in entry_words]),
                text=_render_source_word_sequence(entry_words),
                anchor_ids=[],
            )
        )
    return _RowBand(
        page_ref=rows[0].page_ref,
        bbox=_merge_bboxes([row.bbox for row in rows]),
        words=words,
        entries=entries,
        column_evidence_rows=tuple(copy.deepcopy(rows)),
        row_coalescence_kind=plan.kind,
    )


def _row_is_grouping_eligible(row: _RowBand) -> bool:
    return bool(
        not row.external_title
        and not row.external_note
        and row.column_evidence_rows is None
        and row.entries
        and row.words
        and all(entry.geometry_column_ordinals is None for entry in row.entries)
        and _row_has_exact_entry_word_partition(row)
    )


def _row_has_exact_entry_word_partition(row: _RowBand) -> bool:
    row_refs = [word.word_ref for word in row.words]
    entry_refs = [
        word.word_ref for entry in row.entries for word in entry.words
    ]
    return bool(
        len(row_refs) == len(set(row_refs))
        and len(entry_refs) == len(set(entry_refs))
        and set(row_refs) == set(entry_refs)
        and all(
            row.words[index].order < row.words[index + 1].order
            for index in range(len(row.words) - 1)
        )
    )


def _rows_have_strict_source_order(rows: list[_RowBand]) -> bool:
    if any(not _row_has_exact_entry_word_partition(row) for row in rows):
        return False
    return all(
        max(word.order for word in upper.words)
        < min(word.order for word in lower.words)
        for upper, lower in zip(rows, rows[1:])
    )


def _rows_share_zero_gap_boundary(
    upper: _RowBand,
    lower: _RowBand,
    *,
    typical_height: float,
) -> bool:
    gap = lower.bbox[1] - upper.bbox[3]
    return -typical_height * 0.05 <= gap <= typical_height * 0.1


def _horizontal_separator_at_row_boundary(
    upper: _RowBand,
    lower: _RowBand,
    *,
    page_ref: str,
    table_bbox: tuple[float, float, float, float],
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> bool:
    lower_bound = upper.bbox[3] - typical_height * 0.1
    upper_bound = lower.bbox[1] + typical_height * 0.1
    table_width = _bbox_width(table_bbox)
    for item in object_bboxes:
        if (
            item.page_ref != page_ref
            or item.object_kind
            not in {"vector_line_inventory", "rect_inventory"}
            or _bbox_width(item.bbox) < table_width * 0.4
        ):
            continue
        y_coordinates = (
            ((item.bbox[1] + item.bbox[3]) / 2.0,)
            if item.object_kind == "vector_line_inventory"
            else (item.bbox[1], item.bbox[3])
        )
        if any(lower_bound <= value <= upper_bound for value in y_coordinates):
            return True
    return False


def _bounded_downstream_rows(
    region: _Region,
    *,
    after_index: int,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> list[_RowBand]:
    result = []
    previous = region.rows[after_index]
    for row in region.rows[after_index + 1 : after_index + 13]:
        gap = row.bbox[1] - previous.bbox[3]
        if gap < -typical_height * 0.05 or gap > typical_height * 2.0:
            break
        if _horizontal_separator_at_row_boundary(
            previous,
            row,
            page_ref=region.page.page_ref,
            table_bbox=region.bbox,
            typical_height=typical_height,
            object_bboxes=object_bboxes,
        ):
            break
        result.append(row)
        previous = row
    return result


def _suffix_tracks_repeat_later(
    expected: list[_EntryBand],
    rows: list[_RowBand],
    *,
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if not expected or page_width <= 0.0:
        return False
    observed = [False] * len(expected)
    for row in rows:
        for candidate in row.entries[1:]:
            matches = [
                index
                for index, entry in enumerate(expected)
                if _looks_value_like(candidate.text) == _looks_value_like(entry.text)
                and _entries_share_track(
                    candidate,
                    entry,
                    page_width=page_width,
                    config=config,
                )
            ]
            if len(matches) == 1:
                observed[matches[0]] = True
    return all(observed)


def _entries_share_track(
    left: _EntryBand,
    right: _EntryBand,
    *,
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    tolerance = page_width * config.column_tolerance_width_ratio
    return min(
        abs(left.bbox[0] - right.bbox[0]),
        abs(left.bbox[2] - right.bbox[2]),
        abs(_bbox_center_x(left.bbox) - _bbox_center_x(right.bbox)),
    ) <= tolerance


def _row_matches_leaf_body_tracks(
    row: _RowBand,
    *,
    header_bboxes: list[tuple[float, float, float, float]],
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if (
        not _row_is_grouping_eligible(row)
        or len(row.entries) != len(header_bboxes) + 1
    ):
        return False
    tolerance = page_width * config.column_tolerance_width_ratio
    return all(
        min(
            abs(entry.bbox[0] - header_bbox[0]),
            abs(entry.bbox[2] - header_bbox[2]),
            abs(_bbox_center_x(entry.bbox) - _bbox_center_x(header_bbox)),
        )
        <= tolerance
        for entry, header_bbox in zip(row.entries[1:], header_bboxes)
    )


def _row_is_narrow_suffix_body(
    row: _RowBand,
    *,
    header_envelope: tuple[float, float, float, float],
    typical_height: float,
) -> bool:
    suffix = row.entries[1:]
    return bool(
        _row_is_grouping_eligible(row)
        and len(suffix) >= 2
        and _looks_value_like(suffix[-1].text)
        and all(
            header_envelope[0] - typical_height * 0.25
            <= _bbox_center_x(entry.bbox)
            <= header_envelope[2] + typical_height * 0.25
            for entry in suffix
        )
    )


def _has_two_stable_suffix_rows(
    rows: list[_RowBand],
    *,
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if len(left.entries) != len(right.entries):
                continue
            if all(
                _entries_share_track(
                    left_entry,
                    right_entry,
                    page_width=page_width,
                    config=config,
                )
                for left_entry, right_entry in zip(
                    left.entries[1:],
                    right.entries[1:],
                )
            ):
                return True
    return False


def _leading_alpha_is_lower(value: str) -> bool:
    leading = next((character for character in value if character.isalpha()), "")
    return bool(leading and leading.islower())


def _text_is_terminal(value: str) -> bool:
    return bool(re.search(r"[.!?;:][\s\]\)]*$", value.strip()))


def _segment_table_rows(
    rows: list[_RowBand],
    *,
    config: LogicalRowTableRecoveryConfig,
    minimum_core_rows: int,
) -> list[list[_RowBand]]:
    """Find dense aligned row runs without assigning rectangular cells."""

    if not rows:
        return []
    typical_height = statistics.median(_bbox_height(row.bbox) for row in rows)
    gap_limit = max(10.0, typical_height * config.boundary_gap_height_ratio)
    components: list[list[_RowBand]] = []
    current = [rows[0]]
    for row in rows[1:]:
        if row.bbox[1] - current[-1].bbox[3] > gap_limit:
            components.append(current)
            current = [row]
        else:
            current.append(row)
    components.append(current)
    components = _merge_sparse_aligned_components(
        components,
        minimum_core_rows=minimum_core_rows,
        config=config,
    )
    components = [
        bounded
        for component in components
        for bounded in _split_component_on_terminal_reset(component)
    ]

    segments: list[list[_RowBand]] = []
    for component in components:
        core_indexes = [
            index
            for index, row in enumerate(component)
            if _is_table_core_row(row)
        ]
        if not core_indexes:
            continue
        clusters: list[list[int]] = [[core_indexes[0]]]
        for index in core_indexes[1:]:
            if index - clusters[-1][-1] <= 4:
                clusters[-1].append(index)
            else:
                clusters.append([index])
        for cluster_index, cluster in enumerate(clusters):
            if len(cluster) < minimum_core_rows:
                continue
            core_rows = [component[index] for index in cluster]
            start = cluster[0]
            lower_bound = (
                clusters[cluster_index - 1][-1] + 1 if cluster_index > 0 else 0
            )
            while start > lower_bound:
                previous = component[start - 1]
                if _row_belongs_to_core_envelope(
                    previous,
                    core_rows=core_rows,
                    direction="LEADING",
                    config=config,
                ):
                    start -= 1
                    continue
                break
            end = cluster[-1] + 1
            while end < len(component):
                next_row = component[end]
                if _is_table_core_row(next_row):
                    break
                if not _row_belongs_to_core_envelope(
                    next_row,
                    core_rows=core_rows,
                    direction="TRAILING",
                    config=config,
                ):
                    break
                end += 1
            candidate = component[start:end]
            if len(candidate) >= 2:
                segments.append(candidate)

    accepted: list[list[_RowBand]] = []
    for segment in sorted(
        segments,
        key=lambda item: (item[0].bbox[1], item[0].bbox[0], -len(item)),
    ):
        if any(
            set(id(row) for row in segment)
            <= set(id(row) for row in existing)
            for existing in accepted
        ):
            continue
        accepted.append(segment)
    return accepted


def _merge_sparse_aligned_components(
    components: list[list[_RowBand]],
    *,
    minimum_core_rows: int,
    config: LogicalRowTableRecoveryConfig,
) -> list[list[_RowBand]]:
    merged: list[list[_RowBand]] = []
    for component in components:
        if not merged or not _sparse_components_share_alignment(
            merged[-1],
            component,
            minimum_core_rows=minimum_core_rows,
            config=config,
        ):
            merged.append(component)
            continue
        merged[-1] = [*merged[-1], *component]
    return merged


def _sparse_components_share_alignment(
    left: list[_RowBand],
    right: list[_RowBand],
    *,
    minimum_core_rows: int,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    left_core_total = sum(_is_table_core_row(row) for row in left)
    right_core_total = sum(_is_table_core_row(row) for row in right)
    if (
        left_core_total >= minimum_core_rows
        and right_core_total >= minimum_core_rows
    ):
        return False
    combined = [*left, *right]
    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in combined
    )
    gap = right[0].bbox[1] - left[-1].bbox[3]
    if gap > max(12.0, typical_height * 8.0):
        return False
    left_signature = _component_alignment_signature(left)
    right_signature = _component_alignment_signature(right)
    if left_signature is None or right_signature is None:
        return False
    if len(left_signature) != len(right_signature):
        return False
    combined_bbox = _merge_bboxes([row.bbox for row in combined])
    tolerance = max(
        5.0,
        _bbox_width(combined_bbox) * config.column_tolerance_width_ratio,
    )
    return all(
        min(abs(a - b) for a, b in zip(left_edges, right_edges)) <= tolerance
        for left_edges, right_edges in zip(left_signature, right_signature)
    )


def _component_alignment_signature(
    component: list[_RowBand],
) -> list[tuple[float, float, float]] | None:
    aligned = [row for row in component if len(row.entries) >= 2]
    if not aligned:
        return None
    counts: dict[int, int] = {}
    for row in aligned:
        counts[len(row.entries)] = counts.get(len(row.entries), 0) + 1
    modal_count = max(counts, key=lambda count: (counts[count], count))
    modal_rows = [row for row in aligned if len(row.entries) == modal_count]
    return [
        (
            statistics.median(row.entries[index].bbox[0] for row in modal_rows),
            statistics.median(
                _bbox_center_x(row.entries[index].bbox) for row in modal_rows
            ),
            statistics.median(row.entries[index].bbox[2] for row in modal_rows),
        )
        for index in range(modal_count)
    ]


def _split_component_on_terminal_reset(
    component: list[_RowBand],
) -> list[list[_RowBand]]:
    if len(component) < 5:
        return [component]
    split_indexes: list[int] = []
    lower_bound = 0
    for index, row in enumerate(component[:-2]):
        if index < lower_bound or not _row_is_terminal_total(row):
            continue
        tail = component[index + 1 :]
        first_core_offset = next(
            (
                offset
                for offset, candidate in enumerate(tail)
                if _is_table_core_row(candidate)
            ),
            None,
        )
        if first_core_offset is None or first_core_offset > 3:
            continue
        reset_context = tail[:first_core_offset]
        first_core = tail[first_core_offset]
        header_reset = any(_row_is_header_reset(item) for item in reset_context)
        if not header_reset and _row_is_header_reset(first_core):
            header_reset = True
        if not header_reset:
            continue
        following_core = any(
            _is_table_core_row(candidate)
            for candidate in tail[first_core_offset + 1 : first_core_offset + 4]
        )
        if not following_core:
            continue
        split_index = index + 1
        split_indexes.append(split_index)
        lower_bound = split_index
    if not split_indexes:
        return [component]
    boundaries = [0, *split_indexes, len(component)]
    return [
        component[start:end]
        for start, end in zip(boundaries, boundaries[1:])
        if end > start
    ]


def _row_is_terminal_total(row: _RowBand) -> bool:
    normalized = _normalize_text(" ".join(entry.text for entry in row.entries))
    return (
        _starts_with(normalized, _TOTAL_PREFIXES)
        and not _starts_with(normalized, _SUBTOTAL_PREFIXES)
        and any(_looks_value_like(entry.text) for entry in row.entries)
    )


def _row_is_header_reset(row: _RowBand) -> bool:
    return (
        len(row.entries) >= 2
        and not any(_looks_value_like(entry.text) for entry in row.entries)
    )


def _row_belongs_to_core_envelope(
    row: _RowBand,
    *,
    core_rows: list[_RowBand],
    direction: str,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if not row.entries or not core_rows:
        return False
    core_bbox = _merge_bboxes([candidate.bbox for candidate in core_rows])
    core_width = max(1.0, _bbox_width(core_bbox))
    typical_height = statistics.median(
        _bbox_height(candidate.bbox) for candidate in core_rows
    )
    horizontal_margin = max(typical_height * 2.0, core_width * 0.12)
    if (
        row.bbox[0] < core_bbox[0] - horizontal_margin
        or row.bbox[2] > core_bbox[2] + horizontal_margin
    ):
        return False

    if len(row.entries) >= 2:
        return _row_matches_core_alignment(
            row,
            core_rows=core_rows,
            core_bbox=core_bbox,
            config=config,
        )

    normalized = _normalize_text(row.entries[0].text)
    words_total = len(
        re.findall(r"\w+", row.entries[0].text, flags=re.UNICODE)
    )
    sentence_terminated = bool(
        re.search(r"[.!?;]\s*$", row.entries[0].text.strip())
    )
    if words_total > 16 or (words_total > 5 and sentence_terminated):
        return False
    if direction == "TRAILING" and not (
        _starts_with(normalized, _NOTE_PREFIXES)
        or _starts_with(normalized, _SUBTOTAL_PREFIXES)
        or _starts_with(normalized, _TOTAL_PREFIXES)
        or normalized.startswith("*")
    ):
        return False

    first_entry_left = statistics.median(
        candidate.entries[0].bbox[0]
        for candidate in core_rows
        if candidate.entries
    )
    left_aligned = abs(row.bbox[0] - first_entry_left) <= horizontal_margin
    centered = abs(_bbox_center_x(row.bbox) - _bbox_center_x(core_bbox)) <= max(
        horizontal_margin,
        core_width * 0.16,
    )
    modal_entry_count = _modal_entry_count(core_rows)
    covered_ordinals = set(row.entries[0].geometry_column_ordinals or [])
    explicit_multi_track_span = (
        modal_entry_count >= 2
        and len(covered_ordinals) >= 2
        and all(0 <= ordinal < modal_entry_count for ordinal in covered_ordinals)
    )
    if direction == "LEADING":
        return bool(
            centered
            or explicit_multi_track_span
            or (
                left_aligned
                and words_total <= 8
                and not sentence_terminated
            )
        )
    return centered or left_aligned


def _modal_entry_count(rows: list[_RowBand]) -> int:
    counts: dict[int, int] = {}
    for row in rows:
        counts[len(row.entries)] = counts.get(len(row.entries), 0) + 1
    return max(counts, key=lambda count: (counts[count], count)) if counts else 0


def _row_matches_core_alignment(
    row: _RowBand,
    *,
    core_rows: list[_RowBand],
    core_bbox: tuple[float, float, float, float],
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    core_width = max(1.0, _bbox_width(core_bbox))
    tolerance = max(6.0, core_width * config.column_tolerance_width_ratio)
    entry_counts: dict[int, int] = {}
    for candidate in core_rows:
        entry_counts[len(candidate.entries)] = (
            entry_counts.get(len(candidate.entries), 0) + 1
        )
    modal_count = max(entry_counts, key=lambda count: (entry_counts[count], count))
    modal_rows = [
        candidate for candidate in core_rows if len(candidate.entries) == modal_count
    ]
    expected_centers = [
        statistics.median(
            _bbox_center_x(candidate.entries[index].bbox)
            for candidate in modal_rows
        )
        for index in range(modal_count)
    ]
    expected_left_edges = [
        statistics.median(
            candidate.entries[index].bbox[0] for candidate in modal_rows
        )
        for index in range(modal_count)
    ]
    expected_right_edges = [
        statistics.median(
            candidate.entries[index].bbox[2] for candidate in modal_rows
        )
        for index in range(modal_count)
    ]
    center_matched: set[int] = set()
    edge_matched: set[int] = set()
    edge_tolerance = max(3.0, tolerance * 0.75)
    for entry in row.entries:
        center = _bbox_center_x(entry.bbox)
        center_matches = [
            index
            for index, expected in enumerate(expected_centers)
            if index not in center_matched
            and abs(center - expected) <= tolerance * 1.8
        ]
        if center_matches:
            center_matched.add(
                min(
                    center_matches,
                    key=lambda index: abs(center - expected_centers[index]),
                )
            )
        edge_matches = [
            index
            for index in range(modal_count)
            if index not in edge_matched
            and (
                abs(entry.bbox[0] - expected_left_edges[index])
                <= edge_tolerance
                or abs(entry.bbox[2] - expected_right_edges[index])
                <= edge_tolerance
            )
        ]
        if edge_matches:
            edge_matched.add(
                min(
                    edge_matches,
                    key=lambda index: min(
                        abs(entry.bbox[0] - expected_left_edges[index]),
                        abs(entry.bbox[2] - expected_right_edges[index]),
                    ),
                )
            )
    required = min(2, len(row.entries), len(expected_centers))
    return max(len(center_matched), len(edge_matched)) >= required


def _is_table_core_row(row: _RowBand) -> bool:
    return len(row.entries) >= 2 and (
        len(row.entries) >= 3
        or any(_looks_value_like(entry.text) for entry in row.entries)
    )


def _plan_unruled_leading_suffix_headers(
    regions: list[_Region],
    *,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> _UnruledSuffixHeaderPlan:
    """Prepare geometry-backed row-zero header decisions before classification.

    The two accepted owners are intentionally narrow: an already-proven
    ``NARROW_HEADER`` coalescence lineage, or one unique partial-rule hierarchy
    above a proven leaf band.  Object geometry is fingerprinted with the row
    structure so the later commit cannot apply a stale proposal.
    """

    fingerprint = _unruled_suffix_header_source_fingerprint(
        regions,
        object_bboxes=object_bboxes,
    )
    word_ref_degree: dict[str, int] = {}
    for region in regions:
        for word in region.words:
            word_ref_degree[word.word_ref] = (
                word_ref_degree.get(word.word_ref, 0) + 1
            )
    decisions: list[_UnruledSuffixHeaderDecision] = []
    for region_index, region in enumerate(regions):
        if region.ruled_column_bands or any(
            word_ref_degree.get(word.word_ref) != 1 for word in region.words
        ):
            continue
        candidates = [
            candidate
            for candidate in (
                _narrow_suffix_header_decision(
                    region,
                    region_index=region_index,
                    object_bboxes=object_bboxes,
                    config=config,
                ),
                _partial_rule_root_header_decision(
                    region,
                    region_index=region_index,
                    object_bboxes=object_bboxes,
                    config=config,
                ),
            )
            if candidate is not None
        ]
        if len(candidates) == 1:
            decisions.append(candidates[0])
    return _UnruledSuffixHeaderPlan(
        source_fingerprint_sha256=fingerprint,
        decisions=tuple(decisions),
    )


def _narrow_suffix_header_decision(
    region: _Region,
    *,
    region_index: int,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> _UnruledSuffixHeaderDecision | None:
    if len(region.rows) < 3:
        return None
    root = region.rows[0]
    physical_rows = root.column_evidence_rows
    if (
        root.external_title
        or root.external_note
        or root.role not in {"UNKNOWN", "TABLE_TITLE"}
        or root.row_coalescence_kind != "NARROW_HEADER"
        or len(root.entries) != 1
        or any(_looks_value_like(entry.text) for entry in root.entries)
        or not _row_has_exact_entry_word_partition(root)
        or physical_rows is None
        or len(physical_rows) != 2
        or not _coalesced_row_lineage_is_word_exact(root)
        or not _rows_have_strict_source_order(list(physical_rows))
        or any(
            row.external_title
            or row.external_note
            or len(row.entries) != 1
            or _looks_value_like(row.entries[0].text)
            for row in physical_rows
        )
    ):
        return None
    heights = [
        _bbox_height(row.bbox)
        for row in (*physical_rows, *tuple(region.rows[1:]))
        if row.entries and _bbox_height(row.bbox) > 0.0
    ]
    if not heights:
        return None
    typical_height = statistics.median(heights)
    region_width = _bbox_width(region.bbox)
    envelope = _merge_bboxes([row.bbox for row in physical_rows])
    upper, lower = physical_rows
    if (
        region_width <= 0.0
        or any(
            row.bbox[0] < region.bbox[0] + region_width * 0.7
            or _bbox_width(row.bbox) > region_width * 0.3
            for row in physical_rows
        )
        or _horizontal_interval_overlap_ratio(upper.bbox, lower.bbox) < 0.75
        or abs(_bbox_center_x(upper.bbox) - _bbox_center_x(lower.bbox))
        > typical_height * 0.25
        or len(upper.words) + len(lower.words) > 4
    ):
        return None
    downstream = _bounded_downstream_rows(
        region,
        after_index=0,
        typical_height=typical_height,
        object_bboxes=object_bboxes,
    )
    suffix_rows = [
        row
        for row in downstream
        if _row_is_narrow_suffix_body(
            row,
            header_envelope=envelope,
            typical_height=typical_height,
        )
    ]
    if not _has_two_stable_suffix_rows(
        suffix_rows,
        page_width=region.page.width,
        config=config,
    ):
        return None
    return _UnruledSuffixHeaderDecision(
        region_index=region_index,
        root_row_word_refs=tuple(word.word_ref for word in root.words),
        proof_kind="NARROW_HEADER",
        entry_decisions=(
            _UnruledSuffixHeaderEntryDecision(
                row_index=0,
                entry_index=0,
                coverage_bbox=None,
            ),
        ),
    )


def _partial_rule_root_header_decision(
    region: _Region,
    *,
    region_index: int,
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> _UnruledSuffixHeaderDecision | None:
    if len(region.rows) < 6 or "LEADING_HEADER_STACK" not in region.origin:
        return None
    root, branches, leaves = region.rows[:3]
    if (
        root.external_title
        or root.external_note
        or root.role not in {"UNKNOWN", "TABLE_TITLE"}
        or root.row_coalescence_kind is not None
        or len(root.entries) != 1
        or any(_looks_value_like(entry.text) for entry in root.entries)
        or branches.external_title
        or branches.external_note
        or branches.row_coalescence_kind is not None
        or len(branches.entries) != 2
        or any(_looks_value_like(entry.text) for entry in branches.entries)
        or leaves.external_title
        or leaves.external_note
        or leaves.row_coalescence_kind != "LEAF_HEADER"
        or not 4 <= len(leaves.entries) <= 12
        or any(_looks_value_like(entry.text) for entry in leaves.entries)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in (root, branches, leaves)
        )
        or not _rows_have_strict_source_order([root, branches, leaves])
        or not _coalesced_row_lineage_is_word_exact(leaves)
    ):
        return None
    leaf_centers = [_bbox_center_x(entry.bbox) for entry in leaves.entries]
    branch_centers = [_bbox_center_x(entry.bbox) for entry in branches.entries]
    if leaf_centers != sorted(leaf_centers) or branch_centers != sorted(
        branch_centers
    ):
        return None
    heights = [
        _bbox_height(row.bbox)
        for row in region.rows
        if row.entries and _bbox_height(row.bbox) > 0.0
    ]
    if not heights:
        return None
    typical_height = statistics.median(heights)
    supporting_body = [
        row
        for row in region.rows[3:15]
        if _row_matches_leaf_body_tracks(
            row,
            header_bboxes=[entry.bbox for entry in leaves.entries],
            page_width=region.page.width,
            config=config,
        )
        and any(_looks_value_like(entry.text) for entry in row.entries[1:])
    ]
    if len(supporting_body) < config.minimum_column_observations:
        return None
    label_centers = [_bbox_center_x(row.entries[0].bbox) for row in supporting_body]
    root_rules = _horizontal_rule_bboxes_between(
        root,
        branches,
        page_ref=region.page.page_ref,
        typical_height=typical_height,
        object_bboxes=object_bboxes,
    )
    suffix_right = max(entry.bbox[2] for entry in leaves.entries)
    edge_tolerance = max(
        2.0,
        typical_height * 0.75,
        _bbox_width(region.bbox) * 0.015,
    )
    root_entry_center = _bbox_center_x(root.entries[0].bbox)
    root_candidates = [
        rule
        for rule in root_rules
        if _rule_covered_center_indexes(rule, leaf_centers)
        == tuple(range(len(leaf_centers)))
        and not _rule_covered_center_indexes(rule, label_centers)
        and rule[0] > region.bbox[0] + _bbox_width(region.bbox) * 0.1
        and rule[0] > max(label_centers) + typical_height * 0.1
        and abs(rule[2] - suffix_right) <= edge_tolerance
        and rule[0] < min(leaf_centers) - typical_height * 0.1
        and rule[2] > max(leaf_centers) + typical_height * 0.1
        and rule[0] < root_entry_center < rule[2]
        and abs(_bbox_center_x(rule) - root_entry_center)
        <= max(typical_height, _bbox_width(rule) * 0.08)
    ]
    if len(root_candidates) != 1:
        return None
    root_rule = root_candidates[0]
    child_rules = [
        rule
        for rule in _horizontal_rule_bboxes_between(
            branches,
            leaves,
            page_ref=region.page.page_ref,
            typical_height=typical_height,
            object_bboxes=object_bboxes,
        )
        if rule[0] >= root_rule[0] - edge_tolerance
        and rule[2] <= root_rule[2] + edge_tolerance
    ]
    qualified_children: list[
        tuple[tuple[float, float, float, float], tuple[int, ...]]
    ] = []
    for rule in child_rules:
        covered = _rule_covered_center_indexes(rule, leaf_centers)
        if (
            len(covered) < 2
            or len(covered) >= len(leaf_centers)
            or covered != tuple(range(covered[0], covered[-1] + 1))
        ):
            continue
        qualified_children.append((rule, covered))
    qualified_children.sort(key=lambda item: item[0][0])
    if len(qualified_children) != len(branches.entries):
        return None
    covered_union: list[int] = []
    for branch_index, ((rule, covered), branch_center) in enumerate(
        zip(qualified_children, branch_centers)
    ):
        if (
            not rule[0] < branch_center < rule[2]
            or abs(_bbox_center_x(rule) - branch_center)
            > max(typical_height, _bbox_width(rule) * 0.08)
            or branch_index
            and qualified_children[branch_index - 1][0][2] >= rule[0]
        ):
            return None
        covered_union.extend(covered)
    if covered_union != list(range(len(leaf_centers))):
        return None
    return _UnruledSuffixHeaderDecision(
        region_index=region_index,
        root_row_word_refs=tuple(word.word_ref for word in root.words),
        proof_kind="PARTIAL_RULE_ROOT",
        entry_decisions=(
            _UnruledSuffixHeaderEntryDecision(0, 0, root_rule),
            *tuple(
                _UnruledSuffixHeaderEntryDecision(1, index, rule)
                for index, (rule, _) in enumerate(qualified_children)
            ),
        ),
    )


def _horizontal_rule_bboxes_between(
    upper: _RowBand,
    lower: _RowBand,
    *,
    page_ref: str,
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> list[tuple[float, float, float, float]]:
    lower_y = upper.bbox[3] - typical_height * 0.1
    upper_y = lower.bbox[1] + typical_height * 0.1
    result = []
    for item in object_bboxes:
        center_y = (item.bbox[1] + item.bbox[3]) / 2.0
        if (
            item.page_ref != page_ref
            or item.object_kind
            not in {"vector_line_inventory", "rect_inventory"}
            or not lower_y <= center_y <= upper_y
            or _bbox_width(item.bbox) < typical_height * 2.0
            or _bbox_height(item.bbox) > max(1.0, typical_height * 0.25)
        ):
            continue
        result.append(item.bbox)
    return sorted(result, key=lambda bbox: (bbox[0], bbox[1], bbox[2], bbox[3]))


def _rule_covered_center_indexes(
    rule: tuple[float, float, float, float],
    centers: Sequence[float],
) -> tuple[int, ...]:
    inset = min(0.25, _bbox_width(rule) * 0.001)
    return tuple(
        index
        for index, center in enumerate(centers)
        if rule[0] + inset < center < rule[2] - inset
    )


def _coalesced_row_lineage_is_word_exact(row: _RowBand) -> bool:
    physical_rows = row.column_evidence_rows
    if physical_rows is None or any(
        not _row_has_exact_entry_word_partition(item) for item in physical_rows
    ):
        return False
    physical_refs = [
        word.word_ref for item in physical_rows for word in item.words
    ]
    canonical_refs = [word.word_ref for word in row.words]
    return bool(
        len(physical_refs) == len(set(physical_refs))
        and len(canonical_refs) == len(set(canonical_refs))
        and physical_refs == canonical_refs
    )


def _apply_unruled_leading_suffix_header_plan(
    regions: list[_Region],
    *,
    plan: _UnruledSuffixHeaderPlan,
    object_bboxes: list[_ObjectGeometry],
) -> None:
    if plan.source_fingerprint_sha256 != _unruled_suffix_header_source_fingerprint(
        regions,
        object_bboxes=object_bboxes,
    ):
        raise LogicalRowTableRecoveryError(
            "unruled_leading_suffix_header_plan_invalid"
        )
    if len({decision.region_index for decision in plan.decisions}) != len(
        plan.decisions
    ):
        raise LogicalRowTableRecoveryError(
            "unruled_leading_suffix_header_plan_invalid"
        )
    commits: list[tuple[_RowBand, list[tuple[_EntryBand, Any]]]] = []
    for decision in plan.decisions:
        if not 0 <= decision.region_index < len(regions):
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        region = regions[decision.region_index]
        if not region.rows or region.ruled_column_bands:
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        root = region.rows[0]
        if (
            tuple(word.word_ref for word in root.words)
            != decision.root_row_word_refs
            or root.proven_leading_suffix_header
            or decision.proof_kind not in {"NARROW_HEADER", "PARTIAL_RULE_ROOT"}
        ):
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        indexes = [
            (item.row_index, item.entry_index)
            for item in decision.entry_decisions
        ]
        expected_indexes = (
            [(0, 0)]
            if decision.proof_kind == "NARROW_HEADER"
            else [(0, 0), (1, 0), (1, 1)]
        )
        if indexes != expected_indexes:
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        entry_commits: list[tuple[_EntryBand, Any]] = []
        for item in decision.entry_decisions:
            if (
                not 0 <= item.row_index < len(region.rows)
                or not 0 <= item.entry_index < len(region.rows[item.row_index].entries)
            ):
                raise LogicalRowTableRecoveryError(
                    "unruled_leading_suffix_header_plan_invalid"
                )
            entry = region.rows[item.row_index].entries[item.entry_index]
            bbox = item.coverage_bbox
            if entry.proven_header_coverage_bbox is not None or (
                bbox is not None
                and (
                    len(bbox) != 4
                    or not all(math.isfinite(value) for value in bbox)
                    or bbox[0] >= bbox[2]
                    or bbox[1] > bbox[3]
                    or not bbox[0] < _bbox_center_x(entry.bbox) < bbox[2]
                )
            ):
                raise LogicalRowTableRecoveryError(
                    "unruled_leading_suffix_header_plan_invalid"
                )
            entry_commits.append((entry, bbox))
        if decision.proof_kind == "NARROW_HEADER" and any(
            bbox is not None for _, bbox in entry_commits
        ):
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        if decision.proof_kind == "PARTIAL_RULE_ROOT" and any(
            bbox is None for _, bbox in entry_commits
        ):
            raise LogicalRowTableRecoveryError(
                "unruled_leading_suffix_header_plan_invalid"
            )
        commits.append((root, entry_commits))
    for root, entry_commits in commits:
        root.proven_leading_suffix_header = True
        for entry, bbox in entry_commits:
            entry.proven_header_coverage_bbox = bbox


def _unruled_suffix_header_source_fingerprint(
    regions: list[_Region],
    *,
    object_bboxes: list[_ObjectGeometry],
) -> str:
    page_refs = {region.page.page_ref for region in regions}
    return _sha256_json(
        {
            "regions": [
                {
                    "source_ref": region.source_ref,
                    "page_ref": region.page.page_ref,
                    "bbox": list(region.bbox),
                    "origin": region.origin,
                    "ruled_column_bands": region.ruled_column_bands,
                    "word_refs": [word.word_ref for word in region.words],
                    "rows": [
                        _unruled_suffix_header_row_material(row)
                        for row in region.rows
                    ],
                }
                for region in regions
            ],
            "objects": [
                {
                    "object_ref": item.object_ref,
                    "page_ref": item.page_ref,
                    "kind": item.object_kind,
                    "bbox": list(item.bbox),
                }
                for item in sorted(
                    (
                        candidate
                        for candidate in object_bboxes
                        if candidate.page_ref in page_refs
                    ),
                    key=lambda candidate: (
                        candidate.page_ref,
                        candidate.object_ref,
                        candidate.object_kind,
                        candidate.bbox,
                    ),
                )
            ],
        }
    )


def _unruled_suffix_header_row_material(row: _RowBand) -> dict[str, Any]:
    return {
        "page_ref": row.page_ref,
        "bbox": list(row.bbox),
        "role": row.role,
        "external_title": row.external_title,
        "external_note": row.external_note,
        "row_coalescence_kind": row.row_coalescence_kind,
        "words": [
            [word.word_ref, word.text, word.order, list(word.bbox)]
            for word in row.words
        ],
        "entries": [
            {
                "text": entry.text,
                "bbox": list(entry.bbox),
                "word_refs": [word.word_ref for word in entry.words],
                "geometry_column_ordinals": entry.geometry_column_ordinals,
            }
            for entry in row.entries
        ],
        "column_evidence_rows": [
            {
                "bbox": list(item.bbox),
                "word_refs": [word.word_ref for word in item.words],
                "entries": [
                    {
                        "bbox": list(entry.bbox),
                        "text": entry.text,
                        "word_refs": [word.word_ref for word in entry.words],
                    }
                    for entry in item.entries
                ],
            }
            for item in row.column_evidence_rows or ()
        ],
    }


def _partition_region_words(
    regions: list[_Region],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    result: list[_Region] = []
    claimed: set[str] = set()
    for region in sorted(regions, key=_region_key):
        selected = [word for word in region.words if word.word_ref not in claimed]
        rows = (
            region.rows
            if len(selected) == len(region.words)
            else _row_bands(selected, config=config)
        )
        if len(rows) < 2 or sum(len(row.entries) for row in rows) < 3:
            continue
        claimed.update(word.word_ref for word in selected)
        region.words = selected
        region.rows = rows
        result.append(region)
    return result


def _source_accounting_scope(
    regions: Sequence[_Region],
) -> tuple[frozenset[str], frozenset[str]]:
    """Validate one immutable retained/released source-word partition."""

    retained_refs: list[str] = []
    released_refs: list[str] = []
    for region in regions:
        if not _region_has_exact_row_word_partition(region) or any(
            not _row_has_exact_entry_word_partition(row)
            for row in region.rows
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_partition_invalid"
            )
        region_retained_refs = [word.word_ref for word in region.words]
        region_released_refs = list(region.released_non_table_word_refs)
        if (
            any(not word_ref for word_ref in region_released_refs)
            or len(region_released_refs) != len(set(region_released_refs))
            or set(region_retained_refs).intersection(region_released_refs)
        ):
            raise LogicalRowTableRecoveryError(
                "logical_row_source_accounting_scope_invalid"
            )
        retained_refs.extend(region_retained_refs)
        released_refs.extend(region_released_refs)
    if (
        len(retained_refs) != len(set(retained_refs))
        or len(released_refs) != len(set(released_refs))
        or set(retained_refs).intersection(released_refs)
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_accounting_scope_invalid"
        )
    return frozenset(retained_refs), frozenset(released_refs)


@dataclass(frozen=True)
class _ScopeBoundaryPlan:
    action: str
    participant_indexes: tuple[int, ...]
    split_index: int | None = None


def _reconcile_same_page_table_scopes(
    regions: list[_Region],
    *,
    words_by_page: Mapping[str, list[_Word]],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> list[_Region]:
    """Apply only uniquely proven same-page scope splits and merges.

    Proposal discovery is read-only.  Overlapping proposals form one conflict
    component and are left unchanged; independent unique components may still
    commit.  This keeps boundary repair atomic without changing generic row or
    cross-page continuation semantics.
    """

    ordered = sorted(regions, key=_region_key)
    if not ordered:
        return ordered
    proposals: list[_ScopeBoundaryPlan] = []
    for region_index, region in enumerate(ordered):
        proposals.extend(
            _ScopeBoundaryPlan(
                action="SPLIT",
                participant_indexes=(region_index,),
                split_index=split_index,
            )
            for split_index in _same_page_scope_split_indexes(
                region,
                object_bboxes=object_bboxes,
                config=config,
            )
        )

    owned_refs = {
        word.word_ref for region in ordered for word in region.words
    }
    for left_index in range(len(ordered) - 1):
        right_index = left_index + 1
        left = ordered[left_index]
        right = ordered[right_index]
        if _same_page_scope_merge_candidate(
            left,
            right,
            page_words=words_by_page.get(left.page.page_ref, []),
            owned_refs=owned_refs,
            object_bboxes=object_bboxes,
            config=config,
        ):
            proposals.append(
                _ScopeBoundaryPlan(
                    action="MERGE",
                    participant_indexes=(left_index, right_index),
                )
            )

    if not proposals:
        return ordered

    proposal_adjacency = {
        index: {
            other
            for other, candidate in enumerate(proposals)
            if index != other
            and set(proposals[index].participant_indexes).intersection(
                candidate.participant_indexes
            )
        }
        for index in range(len(proposals))
    }
    accepted: list[_ScopeBoundaryPlan] = []
    visited: set[int] = set()
    for start in range(len(proposals)):
        if start in visited:
            continue
        component: set[int] = set()
        pending = [start]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(proposal_adjacency[current] - component)
        visited.update(component)
        if len(component) == 1:
            accepted.append(proposals[next(iter(component))])

    if not accepted:
        return ordered
    plan_by_first_index = {
        plan.participant_indexes[0]: plan for plan in accepted
    }
    rebuilt: list[_Region] = []
    index = 0
    while index < len(ordered):
        plan = plan_by_first_index.get(index)
        if plan is None:
            rebuilt.append(ordered[index])
            index += 1
            continue
        if plan.action == "SPLIT" and plan.split_index is not None:
            source = ordered[index]
            split_regions = _materialize_scope_split(
                source,
                split_index=plan.split_index,
                object_bboxes=object_bboxes,
            )
            if split_regions is None:
                return ordered
            rebuilt.extend(split_regions)
            index += 1
            continue
        if plan.action == "MERGE" and len(plan.participant_indexes) == 2:
            right_index = plan.participant_indexes[1]
            if right_index != index + 1:
                return ordered
            merged = _materialize_scope_merge(
                ordered[index],
                ordered[right_index],
                object_bboxes=object_bboxes,
            )
            if merged is None:
                return ordered
            rebuilt.append(merged)
            index += 2
            continue
        return ordered

    try:
        input_retained_refs, input_released_refs = _source_accounting_scope(
            ordered
        )
        output_retained_refs, output_released_refs = _source_accounting_scope(
            rebuilt
        )
    except LogicalRowTableRecoveryError:
        return ordered
    if (
        input_retained_refs != output_retained_refs
        or input_released_refs != output_released_refs
    ):
        return ordered
    return sorted(rebuilt, key=_region_key)


def _same_page_scope_split_indexes(
    region: _Region,
    *,
    object_bboxes: list[_ObjectGeometry] | None = None,
    config: LogicalRowTableRecoveryConfig,
) -> list[int]:
    if (
        len(region.rows) < 6
        or not _region_has_exact_row_word_partition(region)
        or region.ruled_column_bands
    ):
        return []
    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in region.rows
    )
    if typical_height <= 0.0:
        return []
    result = []
    for terminal_index in range(1, len(region.rows) - 3):
        if not _row_is_terminal_total(region.rows[terminal_index]):
            continue
        prefix_gaps = [
            region.rows[index].bbox[1] - region.rows[index - 1].bbox[3]
            for index in range(1, terminal_index + 1)
        ]
        positive_prefix_gaps = [gap for gap in prefix_gaps if gap > 0.0]
        if not positive_prefix_gaps:
            continue
        split_index = terminal_index + 1
        boundary_gap = (
            region.rows[split_index].bbox[1]
            - region.rows[terminal_index].bbox[3]
        )
        gap_threshold = max(
            typical_height * 1.25,
            statistics.median(positive_prefix_gaps) * 2.0,
        )
        if boundary_gap < gap_threshold:
            continue
        title = region.rows[split_index]
        if not _row_is_independent_scope_title(
            title,
            region_bbox=region.bbox,
            typical_height=typical_height,
        ):
            continue
        following = region.rows[split_index + 1 :]
        core_rows = [row for row in following if _is_table_core_row(row)]
        if (
            len(core_rows) < 2
            or any(not _is_table_core_row(row) for row in following[:2])
            or _component_alignment_signature(core_rows) is None
            or not any(_row_is_terminal_total(row) for row in core_rows[1:])
        ):
            continue
        if _scope_has_active_compatible_column_header(
            region.rows[:split_index],
            core_rows,
            page_width=region.page.width,
            config=config,
        ):
            continue
        separator_class = _classify_scope_boundary_separator(
            page_ref=region.page.page_ref,
            upper_bbox=region.rows[terminal_index].bbox,
            lower_bbox=title.bbox,
            envelope_bbox=region.bbox,
            typical_height=typical_height,
            object_bboxes=list(object_bboxes or []),
        )
        if separator_class == _SCOPE_SEPARATOR_AMBIGUOUS:
            continue
        left_rows = region.rows[:split_index]
        right_rows = region.rows[split_index:]
        if (
            len(left_rows) < 2
            or len(right_rows) < 3
            or not _rows_have_strict_source_order(left_rows)
            or not _rows_have_strict_source_order(right_rows)
        ):
            continue
        result.append(split_index)
    return result


def _row_is_independent_scope_title(
    row: _RowBand,
    *,
    region_bbox: tuple[float, float, float, float],
    typical_height: float,
) -> bool:
    if (
        not _row_is_grouping_eligible(row)
        or len(row.entries) != 1
        or _looks_value_like(row.entries[0].text)
        or not _text_is_terminal(row.entries[0].text)
    ):
        return False
    word_total = len(
        re.findall(r"\w+", row.entries[0].text, flags=re.UNICODE)
    )
    return bool(
        word_total >= 4
        and _bbox_width(row.bbox) >= _bbox_width(region_bbox) * 0.55
        and abs(row.bbox[0] - region_bbox[0]) <= typical_height * 0.25
    )


def _scope_has_active_compatible_column_header(
    prefix: list[_RowBand],
    following_core: list[_RowBand],
    *,
    page_width: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    for header in prefix:
        if (
            not _row_is_grouping_eligible(header)
            or not _row_is_header_reset(header)
        ):
            continue
        compatible = 0
        for body in following_core:
            if len(header.entries) != len(body.entries):
                continue
            if all(
                _entries_share_track(
                    header_entry,
                    body_entry,
                    page_width=page_width,
                    config=config,
                )
                for header_entry, body_entry in zip(
                    header.entries,
                    body.entries,
                )
            ):
                compatible += 1
        if compatible >= 2:
            return True
    return False


def _same_page_scope_merge_candidate(
    left: _Region,
    right: _Region,
    *,
    page_words: list[_Word],
    owned_refs: set[str],
    object_bboxes: list[_ObjectGeometry],
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    if (
        left.page.page_ref != right.page.page_ref
        or not left.rows
        or not right.rows
        or not _region_has_exact_row_word_partition(left)
        or not _region_has_exact_row_word_partition(right)
        or left.ruled_column_bands
        or right.ruled_column_bands
    ):
        return False
    left_orders = [word.order for word in left.words]
    right_orders = [word.order for word in right.words]
    if not left_orders or not right_orders or max(left_orders) >= min(right_orders):
        return False
    if any(
        max(left_orders) < word.order < min(right_orders)
        and word.word_ref not in owned_refs
        for word in page_words
    ):
        return False
    width_ratio = _bbox_width(left.bbox) / max(1.0, _bbox_width(right.bbox))
    if not 0.9 <= width_ratio <= 1.1:
        return False
    left_signature = _region_alignment_signature(left)
    right_signature = _region_alignment_signature(right)
    if (
        len(left_signature) < 2
        or len(left_signature) != len(right_signature)
        or any(
            abs(left_value - right_value) > 0.035
            for left_value, right_value in zip(
                left_signature,
                right_signature,
            )
        )
    ):
        return False
    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in [*left.rows, *right.rows]
    )
    if typical_height <= 0.0:
        return False
    gap = right.bbox[1] - left.bbox[3]
    if gap < 0.0 or gap > typical_height * 3.0:
        return False
    if not _region_has_active_geometry_column_header(
        left,
        typical_height=typical_height,
        config=config,
    ):
        return False
    if _region_has_independent_title_or_header(
        right,
        typical_height=typical_height,
    ):
        return False
    if not _region_begins_compact_group_reset(
        right,
        typical_height=typical_height,
    ):
        return False
    separator_class = _classify_scope_boundary_separator(
        page_ref=left.page.page_ref,
        upper_bbox=left.bbox,
        lower_bbox=right.bbox,
        envelope_bbox=_merge_bboxes([left.bbox, right.bbox]),
        typical_height=typical_height,
        object_bboxes=object_bboxes,
    )
    if separator_class in {
        _SCOPE_SEPARATOR_AMBIGUOUS,
        _SCOPE_SEPARATOR_FULL,
    }:
        return False
    return True


def _region_has_active_geometry_column_header(
    region: _Region,
    *,
    typical_height: float,
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    for header_index, header in enumerate(region.rows):
        if header.row_coalescence_kind not in {"LEAF_HEADER", "NARROW_HEADER"}:
            continue
        physical_rows = list(header.column_evidence_rows or ())
        physical_refs = [
            word.word_ref for row in physical_rows for word in row.words
        ]
        header_refs = [word.word_ref for word in header.words]
        if (
            len(physical_rows) < 2
            or len(physical_refs) != len(set(physical_refs))
            or set(physical_refs) != set(header_refs)
            or not _rows_have_strict_source_order(physical_rows)
        ):
            continue
        downstream = region.rows[header_index + 1 :]
        if header.row_coalescence_kind == "NARROW_HEADER":
            suffix_rows = [
                row
                for row in downstream
                if _row_is_narrow_suffix_body(
                    row,
                    header_envelope=header.bbox,
                    typical_height=typical_height,
                )
            ]
            if len(suffix_rows) >= 2 and _has_two_stable_suffix_rows(
                suffix_rows,
                page_width=region.page.width,
                config=config,
            ):
                return True
            continue
        header_bboxes = [entry.bbox for entry in header.entries]
        matching_rows = [
            row
            for row in downstream
            if _row_matches_leaf_body_tracks(
                row,
                header_bboxes=header_bboxes,
                page_width=region.page.width,
                config=config,
            )
        ]
        if len(matching_rows) >= 2:
            return True
    return False


def _region_has_independent_title_or_header(
    region: _Region,
    *,
    typical_height: float,
) -> bool:
    if any(row.external_title or row.external_note for row in region.rows):
        return True
    if any(
        row.row_coalescence_kind in {"LEAF_HEADER", "NARROW_HEADER"}
        or _row_is_header_reset(row)
        for row in region.rows
    ):
        return True
    return _row_is_independent_scope_title(
        region.rows[0],
        region_bbox=region.bbox,
        typical_height=typical_height,
    )


def _region_begins_compact_group_reset(
    region: _Region,
    *,
    typical_height: float,
) -> bool:
    reset = region.rows[0]
    if (
        not _row_is_grouping_eligible(reset)
        or len(reset.entries) != 1
        or _looks_value_like(reset.entries[0].text)
        or _text_is_terminal(reset.entries[0].text)
    ):
        return False
    word_total = len(
        re.findall(r"\w+", reset.entries[0].text, flags=re.UNICODE)
    )
    following = region.rows[1:]
    return bool(
        2 <= word_total <= 8
        and _bbox_width(reset.bbox) <= _bbox_width(region.bbox) * 0.8
        and abs(reset.bbox[0] - region.bbox[0]) <= typical_height * 0.25
        and len(following) >= 2
        and _is_table_core_row(following[0])
        and _is_table_core_row(following[1])
    )


def _classify_scope_boundary_separator(
    *,
    page_ref: str,
    upper_bbox: tuple[float, float, float, float],
    lower_bbox: tuple[float, float, float, float],
    envelope_bbox: tuple[float, float, float, float],
    typical_height: float,
    object_bboxes: list[_ObjectGeometry],
) -> str:
    lower_bound = upper_bbox[3] - typical_height * 0.1
    upper_bound = lower_bbox[1] + typical_height * 0.1
    candidates: list[tuple[float, float, float]] = []
    for item in object_bboxes:
        if (
            item.page_ref != page_ref
            or item.object_kind
            not in {"vector_line_inventory", "rect_inventory"}
            or _bbox_width(item.bbox) <= 0.0
        ):
            continue
        if item.object_kind == "rect_inventory" and (
            _bbox_height(item.bbox) > typical_height * 0.25
        ):
            continue
        if _bbox_width(item.bbox) < _bbox_height(item.bbox) * 4.0:
            continue
        y_coordinate = _bbox_center_y(item.bbox)
        if lower_bound <= y_coordinate <= upper_bound:
            candidates.append((item.bbox[0], item.bbox[2], y_coordinate))
    if not candidates:
        return _SCOPE_SEPARATOR_NONE

    clusters: list[list[tuple[float, float, float]]] = []
    for candidate in sorted(candidates, key=lambda item: (item[2], item[0])):
        match = next(
            (
                cluster
                for cluster in clusters
                if abs(
                    candidate[2]
                    - statistics.median(item[2] for item in cluster)
                )
                <= typical_height * 0.1
                and _interval_overlap_ratio(
                    (candidate[0], candidate[1]),
                    (
                        min(item[0] for item in cluster),
                        max(item[1] for item in cluster),
                    ),
                )
                >= 0.8
                and min(
                    candidate[1] - candidate[0],
                    statistics.median(item[1] - item[0] for item in cluster),
                )
                / max(
                    candidate[1] - candidate[0],
                    statistics.median(item[1] - item[0] for item in cluster),
                )
                >= 0.9
            ),
            None,
        )
        if match is None:
            clusters.append([candidate])
        else:
            match.append(candidate)

    envelope_width = max(1.0, _bbox_width(envelope_bbox))
    classifications = []
    for cluster in clusters:
        cluster_width = statistics.median(
            item[1] - item[0] for item in cluster
        )
        width_ratio = cluster_width / envelope_width
        if width_ratio >= 0.4:
            classifications.append(_SCOPE_SEPARATOR_FULL)
        elif width_ratio >= 0.3:
            classifications.append(_SCOPE_SEPARATOR_AMBIGUOUS)
        else:
            classifications.append(_SCOPE_SEPARATOR_LOCAL)
    if _SCOPE_SEPARATOR_FULL in classifications:
        return _SCOPE_SEPARATOR_FULL
    if _SCOPE_SEPARATOR_AMBIGUOUS in classifications:
        return _SCOPE_SEPARATOR_AMBIGUOUS
    return _SCOPE_SEPARATOR_LOCAL


def _materialize_scope_split(
    source: _Region,
    *,
    split_index: int,
    object_bboxes: list[_ObjectGeometry],
) -> tuple[_Region, _Region] | None:
    if (
        source.released_non_table_word_refs
        or split_index <= 0
        or split_index >= len(source.rows)
    ):
        return None
    result = []
    for ordinal, rows in enumerate(
        (source.rows[:split_index], source.rows[split_index:]),
        1,
    ):
        cloned_rows = copy.deepcopy(rows)
        words = [word for row in cloned_rows for word in row.words]
        if not words or not _rows_have_strict_source_order(cloned_rows):
            return None
        bbox = _merge_bboxes([row.bbox for row in cloned_rows])
        result.append(
            _Region(
                source_ref=_identifier(
                    "scope_split_region",
                    [
                        source.source_ref,
                        ordinal,
                        *[word.word_ref for word in words],
                    ],
                ),
                page=source.page,
                bbox=bbox,
                words=words,
                rows=cloned_rows,
                confidence=source.confidence,
                origin=f"{source.origin}+SCOPE_SPLIT",
                object_refs=_overlapping_object_refs(
                    page_ref=source.page.page_ref,
                    bbox=bbox,
                    object_bboxes=object_bboxes,
                ),
                ruled_column_bands=copy.deepcopy(source.ruled_column_bands),
            )
        )
    return result[0], result[1]


def _materialize_scope_merge(
    left: _Region,
    right: _Region,
    *,
    object_bboxes: list[_ObjectGeometry],
) -> _Region | None:
    try:
        input_retained_refs, input_released_refs = _source_accounting_scope(
            [left, right]
        )
    except LogicalRowTableRecoveryError:
        return None
    rows = copy.deepcopy([*left.rows, *right.rows])
    if not rows or not _rows_have_strict_source_order(rows):
        return None
    words = [word for row in rows for word in row.words]
    if len(words) != len({word.word_ref for word in words}):
        return None
    bbox = _merge_bboxes([row.bbox for row in rows])
    merged = _Region(
        source_ref=_identifier(
            "scope_merge_region",
            [
                left.source_ref,
                right.source_ref,
                *[word.word_ref for word in words],
                *sorted(input_released_refs),
            ],
        ),
        page=left.page,
        bbox=bbox,
        words=words,
        rows=rows,
        confidence=min(left.confidence, right.confidence),
        origin=f"{left.origin}+SCOPE_MERGE",
        object_refs=_overlapping_object_refs(
            page_ref=left.page.page_ref,
            bbox=bbox,
            object_bboxes=object_bboxes,
        ),
        ruled_column_bands=None,
        released_non_table_word_refs=tuple(sorted(input_released_refs)),
    )
    try:
        output_retained_refs, output_released_refs = _source_accounting_scope(
            [merged]
        )
    except LogicalRowTableRecoveryError:
        return None
    if (
        input_retained_refs != output_retained_refs
        or input_released_refs != output_released_refs
    ):
        return None
    return merged


def _apply_source_bound_table_scopes(
    regions: list[_Region],
    *,
    scopes: tuple[SourceBoundTableScopeReceipt, ...],
    projection: dict[str, Any],
    source_checksum_sha256: str,
    pages: list[_Page],
    words: list[_Word],
    config: LogicalRowTableRecoveryConfig,
) -> tuple[list[_Region], tuple[str, ...]]:
    """Attach exact reviewed structure without deciding logical table identity."""

    if not isinstance(scopes, tuple):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )
    page_by_ref = {page.page_ref: page for page in pages}
    word_by_ref = {word.word_ref: word for word in words}
    ordered_word_refs = tuple(
        word.word_ref
        for word in sorted(words, key=lambda item: (item.page_ref, item.order))
    )
    bbox_by_ref = _materialize_bboxes(projection)
    candidate_by_ref = {
        str(item.get("table_candidate_ref") or ""): item
        for item in _dicts(projection["table_candidate_inventory"])
    }
    claimed_scope_refs: set[str] = set()
    detached_issues: list[str] = []
    result = copy.deepcopy(regions)

    for scope in scopes:
        _validate_source_bound_table_scope(
            scope,
            source_checksum_sha256=source_checksum_sha256,
            page_by_ref=page_by_ref,
            word_by_ref=word_by_ref,
        )
        if set(scope.scope_word_refs).intersection(claimed_scope_refs):
            detached_issues.append("source_bound_table_scope_overlap")
            overlap_refs = set(scope.scope_word_refs).intersection(claimed_scope_refs)
            for region in result:
                if overlap_refs.intersection(word.word_ref for word in region.words):
                    region.source_bound_issue_codes = tuple(
                        _unique(
                            [
                                *region.source_bound_issue_codes,
                                "source_bound_table_scope_overlap",
                            ]
                        )
                    )
            continue
        claimed_scope_refs.update(scope.scope_word_refs)

        candidate_refs: set[str] = set()
        if scope.locator_candidate_ref is not None:
            raw_candidate = candidate_by_ref.get(scope.locator_candidate_ref)
            if raw_candidate is None:
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_locator_stale"
                )
            candidate_refs = set(_strings(raw_candidate.get("contributing_word_refs")))
            if (
                raw_candidate.get("page_ref") != scope.page_ref
                or raw_candidate.get("bbox_ref") != scope.locator_bbox_ref
                or scope.locator_bbox_ref not in bbox_by_ref
                or tuple(bbox_by_ref[scope.locator_bbox_ref])
                != scope.locator_bbox_pdf_points
                or not candidate_refs
                or not candidate_refs.issubset(word_by_ref)
            ):
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_locator_stale"
                )
            header_refs = {
                ref for group in scope.header_word_ref_groups for ref in group
            }
            expected_body_refs = tuple(
                ref
                for ref in ordered_word_refs
                if ref in candidate_refs
                and ref not in set(scope.title_word_refs)
                and ref not in header_refs
            )
            expected_scope_refs = tuple(
                ref
                for ref in ordered_word_refs
                if ref in candidate_refs or ref in set(scope.title_word_refs)
            )
            if (
                expected_body_refs != scope.body_word_refs
                or expected_scope_refs != scope.scope_word_refs
            ):
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_scope_partition_stale"
                )

        match_refs = set(scope.body_word_refs or scope.body_anchor_word_refs)
        if not match_refs:
            match_refs = {
                *scope.title_word_refs,
                *(
                    ref
                    for group in scope.header_word_ref_groups
                    for ref in group
                ),
            }
        matches = [
            region
            for region in result
            if region.page.page_ref == scope.page_ref
            and match_refs
            and match_refs.issubset(
                {word.word_ref for word in region.words}
            )
        ]
        if scope.binding_status == "PARTIAL":
            if len(matches) == 1:
                _attach_source_bound_receipt(matches[0], scope)
                matches[0].source_bound_issue_codes = tuple(
                    _unique(
                        [
                            *matches[0].source_bound_issue_codes,
                            *scope.issue_codes,
                        ]
                    )
                )
            else:
                detached_issues.extend(scope.issue_codes)
            continue

        required_refs = {
            *scope.body_word_refs,
            *(
                ref
                for group in scope.header_word_ref_groups
                for ref in group
            ),
        }
        matches = [
            region
            for region in result
            if region.page.page_ref == scope.page_ref
            and required_refs.issubset(
                {word.word_ref for word in region.words}
            )
        ]
        if len(matches) != 1:
            detached_issues.append("source_bound_table_scope_region_ambiguous")
            continue
        region = matches[0]
        existing_header = _stable_header_evidence(region, config=config)
        if (
            scope.header_status == "ABSENT"
            and existing_header.signatures
            and existing_header.source_proven
            and existing_header.body_supported
        ):
            _attach_source_bound_receipt(region, scope)
            region.source_bound_issue_codes = tuple(
                _unique(
                    [
                        *region.source_bound_issue_codes,
                        "source_bound_table_scope_header_presence_conflict",
                    ]
                )
            )
            continue
        title_refs = set(scope.title_word_refs)
        conflicting_title_owners = [
            other
            for other in result
            if other is not region
            and title_refs.intersection(word.word_ref for word in other.words)
        ]
        if conflicting_title_owners:
            region.source_bound_issue_codes = tuple(
                _unique(
                    [
                        *region.source_bound_issue_codes,
                        "source_bound_table_scope_title_owner_conflict",
                    ]
                )
            )
            continue

        if title_refs:
            title_words = [word_by_ref[ref] for ref in scope.title_word_refs]
            existing_title_rows = [
                row
                for row in region.rows
                if {word.word_ref for word in row.words}.issubset(title_refs)
                and row.words
            ]
            existing_title_refs = {
                word.word_ref for row in existing_title_rows for word in row.words
            }
            if existing_title_refs and existing_title_refs != title_refs:
                region.source_bound_issue_codes = tuple(
                    _unique(
                        [
                            *region.source_bound_issue_codes,
                            "source_bound_table_scope_title_partition_conflict",
                        ]
                    )
                )
                continue
            if not existing_title_rows:
                existing_title_rows = _row_bands(title_words, config=config)
                if not existing_title_rows:
                    region.source_bound_issue_codes = tuple(
                        _unique(
                            [
                                *region.source_bound_issue_codes,
                                "source_bound_table_scope_title_partition_conflict",
                            ]
                        )
                    )
                    continue
                region.rows = [*existing_title_rows, *region.rows]
                region.words = sorted(
                    [*title_words, *region.words],
                    key=lambda item: (item.bbox[1], item.bbox[0], item.order),
                )
                region.bbox = _merge_bboxes([row.bbox for row in region.rows])
                region.source_ref = _identifier(
                    "source_bound_region",
                    [region.source_ref, scope.scope_ref, *scope.scope_word_refs],
                )
                region.origin += "+SOURCE_BOUND_SCOPE"
            for row in existing_title_rows:
                row.external_title = True

        if scope.header_status == "ABSENT":
            _attach_source_bound_receipt(region, scope)
            region.source_bound_title_word_refs = scope.title_word_refs
            region.source_bound_body_word_refs = scope.body_word_refs
            region.source_bound_issue_codes = tuple(
                _unique(
                    [
                        *region.source_bound_issue_codes,
                        "logical_table_continuation_header_ambiguous",
                    ]
                )
            )
            continue

        if scope.header_status == "PRESENT" and not _source_bound_header_is_leading(
            region,
            header_word_ref_groups=scope.header_word_ref_groups,
            body_word_refs=scope.body_word_refs,
            title_word_refs=scope.title_word_refs,
        ):
            _attach_source_bound_receipt(region, scope)
            region.source_bound_issue_codes = tuple(
                _unique(
                    [
                        *region.source_bound_issue_codes,
                        "source_bound_table_scope_header_presence_conflict",
                    ]
                )
            )
            continue

        signatures: list[tuple[str, ...]] = []
        for group in scope.header_word_ref_groups:
            group_rows = _row_bands([word_by_ref[ref] for ref in group], config=config)
            if not group_rows:
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_header_partition_invalid"
                )
            signatures.extend(_row_literal_signature(row) for row in group_rows)
            group_refs = set(group)
            matching_rows = [
                row
                for row in region.rows
                if row.words
                and {word.word_ref for word in row.words}.issubset(group_refs)
            ]
            if {
                word.word_ref for row in matching_rows for word in row.words
            } != group_refs:
                raise LogicalRowTableRecoveryError(
                    "logical_row_source_bound_header_partition_invalid"
                )
            for row in matching_rows:
                row.proven_leading_suffix_header = True

        _attach_source_bound_receipt(region, scope)
        region.source_bound_title_word_refs = scope.title_word_refs
        region.source_bound_header_status = scope.header_status
        region.source_bound_header_word_ref_groups = scope.header_word_ref_groups
        region.source_bound_header_signatures = tuple(signatures)
        region.source_bound_body_word_refs = scope.body_word_refs
        region.source_bound_structural_authority = True

    detached = tuple(_unique(detached_issues))
    if detached:
        for region in result:
            region.source_bound_issue_codes = tuple(
                _unique([*region.source_bound_issue_codes, *detached])
            )
    return result, detached


def _attach_source_bound_receipt(
    region: _Region,
    scope: SourceBoundTableScopeReceipt,
) -> None:
    """Retain the same-call receipt trace without granting table authority."""

    region.source_bound_scope_ref = scope.scope_ref
    region.source_bound_binding_status = scope.binding_status
    region.source_bound_proposal_sha256 = scope.proposal_sha256
    region.source_bound_raster_manifest_hash = scope.raster_manifest_hash
    region.source_bound_receipt_title_word_refs = scope.title_word_refs
    region.source_bound_receipt_header_word_ref_groups = (
        scope.header_word_ref_groups
    )
    region.source_bound_receipt_body_word_refs = scope.body_word_refs


def _source_bound_header_is_leading(
    region: _Region,
    *,
    header_word_ref_groups: tuple[tuple[str, ...], ...],
    body_word_refs: tuple[str, ...],
    title_word_refs: tuple[str, ...],
) -> bool:
    header_refs = {
        ref for group in header_word_ref_groups for ref in group
    }
    body_refs = set(body_word_refs)
    title_refs = set(title_word_refs)
    if not header_refs or not body_refs or header_refs.intersection(body_refs):
        return False

    header_indexes: list[int] = []
    body_indexes: list[int] = []
    prefix_indexes: list[int] = []
    seen_header_refs: set[str] = set()
    seen_body_refs: set[str] = set()
    for index, row in enumerate(region.rows):
        row_refs = {word.word_ref for word in row.words}
        if row_refs and row_refs.issubset(title_refs):
            prefix_indexes.append(index)
        elif row_refs and row_refs.issubset(header_refs):
            header_indexes.append(index)
            seen_header_refs.update(row_refs)
        elif row_refs and row_refs.issubset(body_refs):
            body_indexes.append(index)
            seen_body_refs.update(row_refs)

    prefix_count = len(prefix_indexes)
    return bool(
        header_indexes
        and body_indexes
        and prefix_indexes == list(range(prefix_count))
        and header_indexes
        == list(range(prefix_count, prefix_count + len(header_indexes)))
        and min(body_indexes) > max(header_indexes)
        and seen_header_refs == header_refs
        and seen_body_refs == body_refs
    )


def _validate_source_bound_table_scope(
    scope: Any,
    *,
    source_checksum_sha256: str,
    page_by_ref: dict[str, _Page],
    word_by_ref: dict[str, _Word],
) -> None:
    if not isinstance(scope, SourceBoundTableScopeReceipt):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )
    page = page_by_ref.get(scope.page_ref)
    all_groups = (
        scope.title_word_refs,
        *scope.header_word_ref_groups,
        scope.body_anchor_word_refs,
        scope.body_word_refs,
    )
    all_refs = [ref for group in all_groups for ref in group]
    if (
        scope.source_checksum_sha256 != source_checksum_sha256.lower()
        or page is None
        or page.page_number != scope.page_number
        or not re.fullmatch(r"[0-9a-f]{64}", scope.raster_manifest_hash)
        or not re.fullmatch(r"[0-9a-f]{64}", scope.proposal_sha256)
        or not scope.scope_ref.startswith("tablescopereceipt_")
        or scope.binding_status not in {"BOUND", "PARTIAL"}
        or scope.title_status not in {"PRESENT", "ABSENT"}
        or scope.header_status not in {"PRESENT", "ABSENT"}
        or any(ref not in word_by_ref for ref in all_refs)
        or any(word_by_ref[ref].page_ref != scope.page_ref for ref in all_refs)
        or any(ref not in word_by_ref for ref in scope.scope_word_refs)
        or len(scope.scope_word_refs) != len(set(scope.scope_word_refs))
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )
    title_refs = set(scope.title_word_refs)
    header_refs = {
        ref for group in scope.header_word_ref_groups for ref in group
    }
    body_anchor_refs = set(scope.body_anchor_word_refs)
    if (
        (scope.title_status == "PRESENT") != bool(title_refs)
        or (scope.header_status == "PRESENT") != bool(header_refs)
        or title_refs.intersection(header_refs | body_anchor_refs)
        or header_refs.intersection(body_anchor_refs)
        or len(header_refs)
        != sum(len(group) for group in scope.header_word_ref_groups)
        or not set(scope.body_word_refs).issubset(scope.scope_word_refs)
        or not title_refs.issubset(scope.scope_word_refs)
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )
    if scope.binding_status == "BOUND" and (
        scope.body_status != "HAS_DATA"
        or scope.locator_candidate_ref is None
        or not scope.body_word_refs
        or scope.issue_codes
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )
    if scope.binding_status == "PARTIAL" and not scope.issue_codes:
        raise LogicalRowTableRecoveryError(
            "logical_row_source_bound_table_scopes_invalid"
        )


def _source_bound_scope_issue_message(code: str) -> str:
    messages = {
        "source_bound_table_scope_empty_template_partial": (
            "The visible empty template is retained as unresolved structure."
        ),
        "source_bound_table_scope_explainer_non_authoritative": (
            "The explainer label is non-authoritative and cannot exclude source words."
        ),
        "source_bound_table_scope_uncertain": (
            "The reviewed table scope remains structurally uncertain."
        ),
        "source_bound_table_scope_locator_missing": (
            "The body anchor does not identify an existing FullSource candidate."
        ),
        "source_bound_table_scope_locator_ambiguous": (
            "The body anchor identifies more than one FullSource candidate."
        ),
        "source_bound_table_scope_region_ambiguous": (
            "The exact scope cannot be attached to one recovered region."
        ),
        "source_bound_table_scope_title_owner_conflict": (
            "Exact title words already belong to another recovered region."
        ),
        "source_bound_table_scope_title_partition_conflict": (
            "Exact title words cannot be retained as one source-bound title."
        ),
        "source_bound_table_scope_header_presence_conflict": (
            "Reviewed header presence conflicts with the source-proven leading stack."
        ),
    }
    return messages.get(code, "The source-bound table scope remains partial.")


def _group_continuations(
    regions: list[_Region],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[list[_Region]]:
    groups: list[list[_Region]] = []
    for region in sorted(regions, key=_region_key):
        decisions = [
            (
                group,
                _continuation_decision(
                group[-1],
                region,
                root=group[0],
                config=config,
                ),
            )
            for group in groups
        ]
        matches = [group for group, decision in decisions if decision == "MATCH"]
        uncertain = [
            group for group, decision in decisions if decision == "AMBIGUOUS"
        ]
        if len(matches) == 1 and not uncertain:
            matches[0].append(region)
        else:
            issue_code = None
            if len(matches) > 1 or (matches and uncertain):
                issue_code = "logical_table_continuation_ambiguous"
            elif uncertain:
                issue_code = "logical_table_continuation_header_ambiguous"
            if issue_code is not None:
                region.continuation_issue_codes = tuple(
                    _unique(
                        [
                            *region.continuation_issue_codes,
                            issue_code,
                        ]
                    )
                )
            groups.append([region])
    return sorted(groups, key=lambda group: _region_key(group[0]))


def _drop_external_title(region: _Region) -> None:
    retained_before, released_before = _source_accounting_scope([region])
    retained_rows = [
        row
        for row in region.rows
        if not row.external_title and not row.external_note
    ]
    if len(retained_rows) == len(region.rows) or not retained_rows:
        return
    retained_refs = frozenset(
        word.word_ref for row in retained_rows for word in row.words
    )
    released_now = tuple(
        word.word_ref
        for row in region.rows
        if row.external_title or row.external_note
        for word in row.words
    )
    retained_words = [
        word for word in region.words if word.word_ref in retained_refs
    ]
    rebuilt = copy.copy(region)
    rebuilt.rows = retained_rows
    rebuilt.words = retained_words
    rebuilt.bbox = _merge_bboxes([row.bbox for row in retained_rows])
    rebuilt.released_non_table_word_refs = (
        *region.released_non_table_word_refs,
        *released_now,
    )
    retained_after, released_after = _source_accounting_scope([rebuilt])
    if (
        {*retained_before, *released_before}
        != {*retained_after, *released_after}
        or retained_after.intersection(released_after)
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_accounting_scope_invalid"
        )
    region.rows = rebuilt.rows
    region.words = rebuilt.words
    region.bbox = rebuilt.bbox
    region.released_non_table_word_refs = (
        rebuilt.released_non_table_word_refs
    )


def _continuation_decision(
    left: _Region,
    right: _Region,
    *,
    root: _Region,
    config: LogicalRowTableRecoveryConfig,
) -> str:
    if right.page.page_number != left.page.page_number + 1:
        return "NO_MATCH"
    if root.source_bound_issue_codes or right.source_bound_issue_codes:
        return "AMBIGUOUS"
    # A source-bound title belongs to the following table scope.  Geometry or
    # a repeated header must never erase it to manufacture a continuation.
    if any(row.external_title for row in right.rows):
        return "NO_MATCH"
    if left.bbox[3] < left.page.height * config.continuation_bottom_ratio:
        return "NO_MATCH"
    if right.bbox[1] > right.page.height * config.continuation_top_ratio:
        return "NO_MATCH"
    left_centers = _region_alignment_signature(left)
    right_centers = _region_alignment_signature(right)
    if len(left_centers) < 2 or len(left_centers) != len(right_centers):
        return "NO_MATCH"
    if any(abs(a - b) > 0.055 for a, b in zip(left_centers, right_centers)):
        return "NO_MATCH"
    width_ratio = _bbox_width(left.bbox) / max(1.0, _bbox_width(right.bbox))
    if not 0.9 <= width_ratio <= 1.1:
        return "NO_MATCH"
    root_header = _stable_header_evidence(root, config=config)
    right_header = _stable_header_evidence(right, config=config)
    if not root_header.signatures or not root_header.body_supported:
        return "NO_MATCH"
    if right_header.signatures:
        if (
            right_header.body_supported
            and right_header.signatures == root_header.signatures
        ):
            return "MATCH"
        if right_header.body_supported and right_header.source_proven:
            return "NO_MATCH"
        return "AMBIGUOUS"
    if right_header.body_supported:
        return "MATCH"
    return "AMBIGUOUS"


def _stable_header_evidence(
    region: _Region,
    *,
    config: LogicalRowTableRecoveryConfig,
) -> _StableHeaderEvidence:
    if region.source_bound_header_status is not None:
        return _StableHeaderEvidence(
            signatures=(
                region.source_bound_header_signatures
                if region.source_bound_header_status == "PRESENT"
                else ()
            ),
            body_supported=bool(region.source_bound_body_word_refs),
            source_proven=True,
        )
    probe = copy.copy(region)
    probe.rows = copy.deepcopy(region.rows)
    _classify_rows(probe.rows)
    _refine_leading_ruled_header_roles(probe, config=config)
    index = 0
    while index < len(probe.rows) and probe.rows[index].role in {
        "TABLE_TITLE",
        "NOTE",
    }:
        index += 1
    header_indexes = []
    while index < len(probe.rows) and probe.rows[index].role == "COLUMN_HEADER":
        header_indexes.append(index)
        index += 1
    body_supported = any(
        row.role in {"DATA", "SUBTOTAL", "TOTAL"} for row in probe.rows[index:]
    )
    source_proven = bool(header_indexes) and all(
        _row_has_source_header_evidence(region.rows[header_index])
        for header_index in header_indexes
    )
    return _StableHeaderEvidence(
        signatures=tuple(
            _row_literal_signature(probe.rows[header_index])
            for header_index in header_indexes
        ),
        body_supported=body_supported,
        source_proven=source_proven,
    )


def _row_has_source_header_evidence(row: _RowBand) -> bool:
    return bool(
        row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
        or row.row_coalescence_kind in _PROVEN_HEADER_COALESCENCE_KINDS
        or row.proven_leading_suffix_header
        or row.sequential_marker_header
        or any(
            entry.proven_header_coverage_bbox is not None for entry in row.entries
        )
    )


def _apply_source_bound_row_roles(region: _Region) -> None:
    if region.source_bound_header_status is None:
        return
    title_refs = set(region.source_bound_title_word_refs)
    header_refs = {
        ref
        for group in region.source_bound_header_word_ref_groups
        for ref in group
    }
    body_refs = set(region.source_bound_body_word_refs)
    for row in region.rows:
        row_refs = {word.word_ref for word in row.words}
        if row_refs and row_refs.issubset(title_refs):
            row.external_title = True
            row.role = "TABLE_TITLE"
        elif row_refs and row_refs.issubset(header_refs):
            row.role = "COLUMN_HEADER"
        elif row_refs and row_refs.issubset(body_refs):
            row.role = "DATA"


def _materialize_logical_table(
    regions: list[_Region],
    *,
    state: _RecoveryState,
    config: LogicalRowTableRecoveryConfig,
) -> dict[str, Any]:
    expected_owned_word_refs, _ = _source_accounting_scope(regions)
    table_id = _identifier(
        "table",
        [
            state.source_checksum_sha256,
            *[region.source_ref for region in regions],
            *[word.word_ref for region in regions for word in region.words],
        ],
    )
    table_block_id = logical_table_block_id(table_id)
    for region in regions:
        _classify_rows(region.rows)
        _refine_leading_ruled_header_roles(region, config=config)
        _apply_source_bound_row_roles(region)
    if len(regions) > 1:
        first_header_stack = _leading_header_stack(regions[0].rows)
        first_header_signatures = tuple(
            _row_literal_signature(row) for row in first_header_stack
        )
        for region in regions[1:]:
            repeated_header_stack = _leading_header_stack(region.rows)
            if (
                first_header_signatures
                and tuple(
                    _row_literal_signature(row) for row in repeated_header_stack
                )
                == first_header_signatures
            ):
                for row in repeated_header_stack:
                    row.role = "CONTINUATION_HEADER"

    ordered_rows = [row for region in regions for row in region.rows]
    semantic_plan = _plan_ordered_row_semantics(
        ordered_rows,
        config=config,
    )
    table_issue_ids: list[str] = []
    for ordinal, row in enumerate(ordered_rows):
        row.row_id = _identifier(
            "row",
            [table_id, ordinal, *[word.word_ref for word in row.words]],
        )
    _apply_ordered_row_semantic_plan(ordered_rows, plan=semantic_plan)

    region_anchor_by_ref: dict[str, str] = {}
    region_geometry_by_ref: dict[str, str] = {}
    for region in regions:
        region_anchor = state.anchor_for_region(
            page=region.page,
            bbox=region.bbox,
            source_ref=region.source_ref,
        )
        region_anchor_by_ref[region.source_ref] = region_anchor
        region_geometry_by_ref[region.source_ref] = state.add_geometry(
            kind="TABLE_REGION",
            key=[table_id, region.source_ref],
            anchor_ids=[region_anchor],
            material={
                "page_ref": region.page.page_ref,
                "bbox": list(region.bbox),
                "source_ref": region.source_ref,
                "origin": region.origin,
                "confidence": region.confidence,
                "object_refs": region.object_refs,
                "word_refs": [word.word_ref for word in region.words],
                **(
                    {
                        "source_bound_scope_ref": region.source_bound_scope_ref,
                        "source_bound_binding_status": (
                            region.source_bound_binding_status
                        ),
                        "source_bound_structural_authority": (
                            region.source_bound_structural_authority
                        ),
                        "source_bound_proposal_sha256": (
                            region.source_bound_proposal_sha256
                        ),
                        "source_bound_raster_manifest_hash": (
                            region.source_bound_raster_manifest_hash
                        ),
                        "source_bound_receipt_title_word_refs": list(
                            region.source_bound_receipt_title_word_refs
                        ),
                        "source_bound_receipt_header_word_ref_groups": [
                            list(group)
                            for group in (
                                region.source_bound_receipt_header_word_ref_groups
                            )
                        ],
                        "source_bound_receipt_body_word_refs": list(
                            region.source_bound_receipt_body_word_refs
                        ),
                        "source_bound_title_word_refs": list(
                            region.source_bound_title_word_refs
                        ),
                        "source_bound_header_status": (
                            region.source_bound_header_status
                        ),
                        "source_bound_header_word_ref_groups": [
                            list(group)
                            for group in region.source_bound_header_word_ref_groups
                        ],
                        "source_bound_body_word_refs": list(
                            region.source_bound_body_word_refs
                        ),
                    }
                    if region.source_bound_scope_ref is not None
                    else {}
                ),
            },
        )

    continuation_issue_ids_by_ref: dict[str, list[str]] = {}
    for region in regions:
        issue_ids = []
        for code in _unique(
            [
                *region.continuation_issue_codes,
                *region.source_bound_issue_codes,
            ]
        ):
            issue_id = state.add_issue(
                code=code,
                message=(
                    "The fragment has no source-bound header-presence evidence; "
                    "text-only rows cannot prove continuation."
                    if code == "logical_table_continuation_header_ambiguous"
                    else (
                        "The fragment has more than one compatible predecessor; "
                        "table continuation is not deterministic."
                        if code == "logical_table_continuation_ambiguous"
                        else _source_bound_scope_issue_message(code)
                    )
                ),
                anchor_ids=[region_anchor_by_ref[region.source_ref]],
                block_ids=[table_block_id],
            )
            issue_ids.append(issue_id)
            table_issue_ids.append(issue_id)
        continuation_issue_ids_by_ref[region.source_ref] = issue_ids

    row_payloads: list[dict[str, Any]] = []
    word_owner_entry: dict[str, str] = {}
    row_region: dict[str, _Region] = {}
    for ordinal, row in enumerate(ordered_rows):
        region = next(region for region in regions if row in region.rows)
        row_region[str(row.row_id)] = region
        anchor_ids = [
            state.anchor_for_word(word, page_number=region.page.page_number)
            for word in row.words
        ]
        row.anchor_ids = _unique(anchor_ids)
        row.issue_ids = []
        if row.role == "UNKNOWN":
            issue_id = state.add_issue(
                code="logical_row_role_unknown",
                message=(
                    "The source row is preserved in order, but its logical role "
                    "is not deterministically proven."
                ),
                anchor_ids=row.anchor_ids,
                block_ids=[table_block_id],
            )
            row.issue_ids.append(issue_id)
            table_issue_ids.append(issue_id)
        for code in row.semantic_issue_codes:
            issue_id = state.add_issue(
                code=code,
                message=_semantic_issue_message(code),
                anchor_ids=row.anchor_ids,
                block_ids=[table_block_id],
            )
            row.issue_ids.append(issue_id)
            table_issue_ids.append(issue_id)
        row.geometry_evidence_id = state.add_geometry(
            kind="ROW_BAND",
            key=[table_id, row.row_id],
            anchor_ids=row.anchor_ids,
            material={
                "page_ref": region.page.page_ref,
                "bbox": list(row.bbox),
                "word_refs": [word.word_ref for word in row.words],
            },
            issue_ids=row.issue_ids,
        )
        entry_payloads = []
        for entry_ordinal, entry in enumerate(row.entries):
            _set_entry_column_binding(
                entry,
                payload=None,
                logical_column_id=None,
                covers_logical_column_ids=(),
            )
            entry.entry_id = _identifier(
                "entry",
                [row.row_id, entry_ordinal, *[word.word_ref for word in entry.words]],
            )
            entry.anchor_ids = [
                state.anchor_for_word(word, page_number=region.page.page_number)
                for word in entry.words
            ]
            entry.geometry_evidence_id = state.add_geometry(
                kind="ENTRY_REGION",
                key=[table_id, row.row_id, entry.entry_id],
                anchor_ids=entry.anchor_ids,
                material={
                    "page_ref": region.page.page_ref,
                    "bbox": list(entry.bbox),
                    "word_refs": [word.word_ref for word in entry.words],
                },
            )
            for word in entry.words:
                if word.word_ref in word_owner_entry:
                    raise LogicalRowTableRecoveryError(
                        "logical_row_multiple_word_owners"
                    )
                word_owner_entry[word.word_ref] = entry.entry_id
            entry_payloads.append(
                {
                    "entry_id": entry.entry_id,
                    "ordinal": entry_ordinal,
                    "kind": _entry_kind(entry.text, row.role, entry_ordinal),
                    "text": entry.text,
                    "origin": "DETERMINISTIC_DERIVED",
                    "column_binding_status": entry.column_binding_status,
                    "logical_column_id": entry.logical_column_id,
                    "covers_logical_column_ids": list(
                        entry.covers_logical_column_ids
                    ),
                    "source_anchor_ids": _unique(entry.anchor_ids),
                    "geometry_evidence_ids": [entry.geometry_evidence_id],
                    "issue_ids": [],
                }
            )
        row_payloads.append(
            {
                "row_id": row.row_id,
                "ordinal": ordinal,
                "role": row.role,
                "role_origin": "DETERMINISTIC_DERIVED",
                "nesting_level": row.nesting_level,
                "parent_row_id": row.parent_row_id,
                "entries": entry_payloads,
                "source_anchor_ids": row.anchor_ids,
                "geometry_evidence_ids": [row.geometry_evidence_id],
                "issue_ids": row.issue_ids,
            }
        )

    logical_columns = _materialize_columns(
        rows=ordered_rows,
        row_payloads=row_payloads,
        regions=regions,
        table_id=table_id,
        state=state,
        config=config,
    )
    _promote_and_bind_proven_suffix_headers(
        rows=ordered_rows,
        row_payloads=row_payloads,
        logical_columns=logical_columns,
    )
    _finalize_entry_kinds_after_binding(
        rows=ordered_rows,
        row_payloads=row_payloads,
        logical_columns=logical_columns,
    )
    finalized_column_issue_ids = _finalize_column_header_paths(
        rows=ordered_rows,
        row_payloads=row_payloads,
        logical_columns=logical_columns,
        state=state,
        table_id=table_id,
    )
    table_issue_ids.extend(finalized_column_issue_ids)
    entry_payload_by_id = {
        entry["entry_id"]: entry
        for row in row_payloads
        for entry in row["entries"]
    }
    if (
        len(word_owner_entry) != len(expected_owned_word_refs)
        or set(word_owner_entry) != expected_owned_word_refs
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_source_accounting_materialization_invalid"
        )
    source_word_id_by_ref = {
        word_ref: _identifier("source_word", [word_ref])
        for word_ref in word_owner_entry
    }
    if (
        len(source_word_id_by_ref) != len(set(source_word_id_by_ref.values()))
        or set(source_word_id_by_ref.values()).intersection(
            state.word_ref_by_source_word_id
        )
    ):
        raise LogicalRowTableRecoveryError(
            "logical_row_multiple_word_owners"
        )
    for word_ref, entry_id in word_owner_entry.items():
        word = next(
            word
            for region in regions
            for word in region.words
            if word.word_ref == word_ref
        )
        region = next(region for region in regions if word in region.words)
        source_word_id = source_word_id_by_ref[word_ref]
        anchor_id = state.anchor_for_word(
            word,
            page_number=region.page.page_number,
        )
        if anchor_id not in entry_payload_by_id[entry_id]["source_anchor_ids"]:
            raise LogicalRowTableRecoveryError(
                "logical_row_word_anchor_not_entry_bound"
            )
        state.source_word_ownership.append(
            {
                "information_class": "PRIVATE_SOURCE",
                "source_word_id": source_word_id,
                "table_id": table_id,
                "owner_status": "OWNED",
                "owner_entry_id": entry_id,
                "duplicate_of_source_word_id": None,
                "source_anchor_id": anchor_id,
                "issue_ids": [],
            }
        )
        state.word_ref_by_source_word_id[source_word_id] = word_ref

    source_parts = []
    continuation_evidence_by_index: dict[int, str] = {}
    for index in range(1, len(regions)):
        previous = regions[index - 1]
        current = regions[index]
        anchors = [
            region_anchor_by_ref[previous.source_ref],
            region_anchor_by_ref[current.source_ref],
        ]
        continuation_evidence_by_index[index] = state.add_geometry(
            kind="CONTINUATION",
            key=[table_id, previous.source_ref, current.source_ref],
            anchor_ids=anchors,
            material={
                "previous_page_ref": previous.page.page_ref,
                "current_page_ref": current.page.page_ref,
                "previous_bbox": list(previous.bbox),
                "current_bbox": list(current.bbox),
                "alignment_signature": _region_alignment_signature(current),
                "header_signature_sha256": _sha256_json(
                    _header_signature(current.rows)
                ),
            },
        )
    for index, region in enumerate(regions):
        region_rows = [
            row for row in ordered_rows if row_region[str(row.row_id)] is region
        ]
        if len(regions) == 1:
            status = "SINGLE"
        elif index == 0:
            status = "START"
        elif index == len(regions) - 1:
            status = "END"
        else:
            status = "CONTINUATION"
        source_parts.append(
            {
                "source_part_id": _identifier(
                    "source_part", [table_id, index, region.source_ref]
                ),
                "ordinal": index,
                "page": region.page.page_number,
                "region_anchor_id": region_anchor_by_ref[region.source_ref],
                "first_row_id": region_rows[0].row_id,
                "last_row_id": region_rows[-1].row_id,
                "continuation_status": status,
                "geometry_evidence_ids": [
                    region_geometry_by_ref[region.source_ref]
                ],
                "continuation_evidence_ids": _unique(
                    [
                        *(
                            [continuation_evidence_by_index[index]]
                            if index > 0
                            else []
                        ),
                        *(
                            [continuation_evidence_by_index[index + 1]]
                            if index + 1 < len(regions)
                            else []
                        ),
                    ]
                ),
                "issue_ids": continuation_issue_ids_by_ref[region.source_ref],
                **(
                    {
                        "source_bound_scope_ref": region.source_bound_scope_ref,
                        "source_bound_binding_status": (
                            region.source_bound_binding_status
                        ),
                        "source_bound_structural_authority": (
                            region.source_bound_structural_authority
                        ),
                        "source_bound_proposal_sha256": (
                            region.source_bound_proposal_sha256
                        ),
                        "source_bound_raster_manifest_hash": (
                            region.source_bound_raster_manifest_hash
                        ),
                        "source_bound_receipt_title_word_refs": list(
                            region.source_bound_receipt_title_word_refs
                        ),
                        "source_bound_receipt_header_word_ref_groups": [
                            list(group)
                            for group in (
                                region.source_bound_receipt_header_word_ref_groups
                            )
                        ],
                        "source_bound_receipt_body_word_refs": list(
                            region.source_bound_receipt_body_word_refs
                        ),
                        "source_bound_title_word_refs": list(
                            region.source_bound_title_word_refs
                        ),
                        "source_bound_header_status": (
                            region.source_bound_header_status
                        ),
                        "source_bound_header_word_ref_groups": [
                            list(group)
                            for group in region.source_bound_header_word_ref_groups
                        ],
                        "source_bound_body_word_refs": list(
                            region.source_bound_body_word_refs
                        ),
                    }
                    if region.source_bound_scope_ref is not None
                    else {}
                ),
            }
        )

    completeness = (
        "PARTIAL"
        if table_issue_ids
        or any(row["role"] == "UNKNOWN" for row in row_payloads)
        or any(row["issue_ids"] for row in row_payloads)
        or any(not column["header_path"] for column in logical_columns)
        else "COMPLETE"
    )
    return {
        "information_class": "CONTENT",
        "table_id": table_id,
        "completeness_status": completeness,
        "ordered_rows": row_payloads,
        "logical_columns": logical_columns,
        "source_parts": source_parts,
        "relations": [],
        "issues": _unique(table_issue_ids),
        "known_gap_ids": [],
    }


def _set_entry_column_binding(
    entry: _EntryBand,
    *,
    payload: dict[str, Any] | None,
    logical_column_id: str | None,
    covers_logical_column_ids: Sequence[str],
) -> None:
    """Synchronize one entry binding atomically with its public payload."""

    covers = _unique(covers_logical_column_ids)
    if logical_column_id is not None and covers:
        covers = [
            logical_column_id,
            *[column_id for column_id in covers if column_id != logical_column_id],
        ]
    status = "BOUND" if logical_column_id is not None or covers else "NOT_APPLICABLE"
    entry.logical_column_id = logical_column_id
    entry.covers_logical_column_ids = covers
    entry.column_binding_status = status
    if payload is None:
        return
    payload["logical_column_id"] = logical_column_id
    payload["covers_logical_column_ids"] = list(covers)
    payload["column_binding_status"] = status


def _column_evidence_lineage(
    rows: list[_RowBand],
) -> _ColumnEvidenceLineage | None:
    evidence_rows: list[_RowBand] = []
    children_by_parent: dict[int, tuple[_EntryBand, ...]] = {}
    parents_by_child: dict[int, list[_EntryBand]] = {
        id(entry): [] for row in rows for entry in row.entries
    }
    canonical_by_evidence_row: dict[int, _RowBand] = {}
    snapshot_backed_rows: set[int] = set()
    for canonical_row in rows:
        if not _row_has_exact_entry_word_partition(canonical_row):
            return None
        canonical_by_ref = {
            word.word_ref: entry
            for entry in canonical_row.entries
            for word in entry.words
        }
        if len(canonical_by_ref) != len(canonical_row.words):
            return None
        physical_rows = canonical_row.column_evidence_rows or (canonical_row,)
        if (
            canonical_row.column_evidence_rows is not None
            or canonical_row.column_evidence_entries is not None
            or any(row.column_evidence_entries is not None for row in physical_rows)
        ):
            snapshot_backed_rows.add(id(canonical_row))
        seen_refs: list[str] = []
        canonical_order = {
            id(entry): ordinal
            for ordinal, entry in enumerate(canonical_row.entries)
        }
        for physical_row in physical_rows:
            source_entries = list(
                physical_row.column_evidence_entries
                or tuple(physical_row.entries)
            )
            if not _entry_bands_partition_words(
                source_entries,
                physical_row.words,
            ):
                return None
            copied_entries: list[_EntryBand] = []
            for source_entry in source_entries:
                copied = copy.deepcopy(source_entry)
                copied.entry_id = None
                copied.geometry_evidence_id = None
                copied.anchor_ids = []
                copied.logical_column_id = None
                copied.covers_logical_column_ids = []
                copied.column_binding_status = "NOT_APPLICABLE"
                child_entries = _unique_objects(
                    canonical_by_ref.get(word.word_ref)
                    for word in copied.words
                )
                if any(child is None for child in child_entries):
                    return None
                ordered_children = tuple(
                    sorted(
                        (child for child in child_entries if child is not None),
                        key=lambda child: canonical_order[id(child)],
                    )
                )
                if not ordered_children:
                    return None
                copied_entries.append(copied)
                children_by_parent[id(copied)] = ordered_children
                for child in ordered_children:
                    parents_by_child[id(child)].append(copied)
                seen_refs.extend(word.word_ref for word in copied.words)
            evidence_row = copy.copy(physical_row)
            evidence_row.entries = copied_entries
            evidence_row.role = canonical_row.role
            evidence_row.column_evidence_entries = None
            evidence_row.column_evidence_rows = None
            evidence_rows.append(evidence_row)
            canonical_by_evidence_row[id(evidence_row)] = canonical_row
        canonical_refs = [word.word_ref for word in canonical_row.words]
        if (
            len(seen_refs) != len(set(seen_refs))
            or set(seen_refs) != set(canonical_refs)
        ):
            return None
    if any(not parents for parents in parents_by_child.values()):
        return None
    return _ColumnEvidenceLineage(
        rows=tuple(evidence_rows),
        canonical_children_by_parent=children_by_parent,
        parents_by_canonical_child={
            child_id: tuple(parents)
            for child_id, parents in parents_by_child.items()
        },
        canonical_row_by_evidence_row=canonical_by_evidence_row,
        snapshot_backed_canonical_rows=frozenset(snapshot_backed_rows),
    )


def _unique_objects(values: Sequence[Any]) -> list[Any]:
    result = []
    seen: set[int] = set()
    for value in values:
        if value is None or id(value) in seen:
            continue
        result.append(value)
        seen.add(id(value))
    return result


def _materialization_two_lane_evidence(
    lineage: _ColumnEvidenceLineage,
    *,
    width: float,
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowBand]:
    tolerance = max(3.0, width * config.column_tolerance_width_ratio * 0.55)
    result = []
    for row in lineage.rows:
        if len(row.entries) <= 2:
            result.append(row)
            continue
        gaps = [
            right.bbox[0] - left.bbox[2]
            for left, right in zip(row.entries, row.entries[1:])
        ]
        dominant = max(range(len(gaps)), key=gaps.__getitem__)
        ranked = sorted(gaps, reverse=True)
        if (
            dominant != 0
            or gaps[0] <= tolerance * 2.0
            or (
                len(ranked) > 1
                and ranked[0] - ranked[1] <= tolerance
            )
        ):
            result.append(row)
            continue
        right_entries = row.entries[1:]
        if max(
            (
                next_entry.bbox[0] - entry.bbox[2]
                for entry, next_entry in zip(right_entries, right_entries[1:])
            ),
            default=0.0,
        ) > tolerance * 4.0:
            result.append(row)
            continue
        merged_words = [word for entry in right_entries for word in entry.words]
        merged = _EntryBand(
            words=merged_words,
            bbox=_merge_bboxes([entry.bbox for entry in right_entries]),
            text=" ".join(entry.text for entry in right_entries).strip(),
            anchor_ids=[],
        )
        normalized = copy.copy(row)
        normalized.entries = [row.entries[0], merged]
        result.append(normalized)
    return result


def _track_center(track: _ColumnTrack) -> float:
    if track.entries:
        return statistics.median(
            _bbox_center_x(entry.bbox) for entry in track.entries
        )
    return track.coordinate


def _unique_track_index(
    entry: _EntryBand,
    tracks: Sequence[_ColumnTrack],
) -> int | None:
    distances = [
        abs(_entry_edge(entry, track.edge) - track.coordinate)
        / max(1.0, track.tolerance)
        for track in tracks
    ]
    ranked = sorted(range(len(distances)), key=distances.__getitem__)
    if not ranked or distances[ranked[0]] > 1.8:
        return None
    if (
        len(ranked) > 1
        and distances[ranked[1]] - distances[ranked[0]] <= 0.2
    ):
        return None
    return ranked[0]


def _covered_track_indexes(
    entry: _EntryBand,
    tracks: Sequence[_ColumnTrack],
    *,
    use_proven_coverage: bool = False,
) -> tuple[int, ...] | None:
    coverage_bbox = (
        entry.proven_header_coverage_bbox
        if use_proven_coverage
        and entry.proven_header_coverage_bbox is not None
        else entry.bbox
    )
    indexes = tuple(
        index
        for index, track in enumerate(tracks)
        if coverage_bbox[0] <= _track_center(track) <= coverage_bbox[2]
    )
    if not indexes:
        return ()
    if indexes != tuple(range(indexes[0], indexes[-1] + 1)):
        return None
    ambiguity = min(track.tolerance for track in tracks) * 0.15
    if any(
        min(
            abs(_track_center(tracks[index]) - coverage_bbox[0]),
            abs(_track_center(tracks[index]) - coverage_bbox[2]),
        ) <= ambiguity
        for index in indexes
    ):
        return None
    return indexes


def _entry_binding_plans_for_tracks(
    *,
    rows: list[_RowBand],
    lineage: _ColumnEvidenceLineage,
    tracks: list[_ColumnTrack],
) -> tuple[_EntryColumnBindingPlan, ...] | None:
    parent_track: dict[int, int | None] = {}
    for parents in lineage.parents_by_canonical_child.values():
        for parent in parents:
            parent_track.setdefault(id(parent), _unique_track_index(parent, tracks))

    direct_by_entry: dict[int, int | None] = {}
    covers_by_entry: dict[int, tuple[int, ...]] = {}
    for row in rows:
        for entry in row.entries:
            spanning_role = row.role in {
                "COLUMN_HEADER",
                "CONTINUATION_HEADER",
                "GROUP_HEADER",
                "SUBTOTAL",
                "TOTAL",
            }
            covered = (
                _covered_track_indexes(entry, tracks)
                if spanning_role
                else ()
            )
            if covered is None:
                return None
            if len(covered) >= 2 and spanning_role:
                covers_by_entry[id(entry)] = covered
                direct_by_entry[id(entry)] = (
                    covered[0]
                    if row.role in {"SUBTOTAL", "TOTAL"}
                    else None
                )
                continue
            candidates = {
                parent_track[id(parent)]
                for parent in lineage.parents_by_canonical_child[id(entry)]
                if parent_track[id(parent)] is not None
            }
            if len(candidates) == 1:
                direct_by_entry[id(entry)] = next(iter(candidates))
            elif len(candidates) > 1:
                direct_by_entry[id(entry)] = None
            else:
                direct_by_entry[id(entry)] = _unique_track_index(entry, tracks)
            covers_by_entry[id(entry)] = ()

    for row in rows:
        if row.role not in {
            "COLUMN_HEADER",
            "CONTINUATION_HEADER",
            "GROUP_HEADER",
            "DATA",
            "SUBTOTAL",
            "TOTAL",
        }:
            continue
        for left, right in zip(row.entries, row.entries[1:]):
            assigned = {
                direct_by_entry[id(item)]
                for item in (left, right)
                if direct_by_entry[id(item)] is not None
            }
            if len(assigned) > 1 or any(
                covers_by_entry[id(item)] for item in (left, right)
            ):
                continue
            gap = right.bbox[0] - left.bbox[2]
            merged = _EntryBand(
                words=[*left.words, *right.words],
                bbox=_merge_bboxes([left.bbox, right.bbox]),
                text=f"{left.text} {right.text}".strip(),
                anchor_ids=[],
            )
            covered = _covered_track_indexes(merged, tracks)
            target = _unique_track_index(merged, tracks)
            if (
                target is None
                or covered != (target,)
                or gap > tracks[target].tolerance * 4.0
                or (assigned and assigned != {target})
            ):
                continue
            direct_by_entry[id(left)] = target
            direct_by_entry[id(right)] = target

    return tuple(
        _EntryColumnBindingPlan(
            entry=entry,
            logical_column_ordinal=direct_by_entry[id(entry)],
            covered_column_ordinals=covers_by_entry[id(entry)],
        )
        for row in rows
        for entry in row.entries
    )


def _column_scope_entry_fingerprint_material(entry: _EntryBand) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "text": entry.text,
        "bbox": list(entry.bbox),
        "anchor_ids": list(entry.anchor_ids),
        "logical_column_id": entry.logical_column_id,
        "covers_logical_column_ids": list(entry.covers_logical_column_ids),
        "column_binding_status": entry.column_binding_status,
        "geometry_column_ordinals": entry.geometry_column_ordinals,
        "proven_header_coverage_bbox": (
            list(entry.proven_header_coverage_bbox)
            if entry.proven_header_coverage_bbox is not None
            else None
        ),
        "words": [
            {
                "word_ref": word.word_ref,
                "page_ref": word.page_ref,
                "text": word.text,
                "bbox": list(word.bbox),
                "order": word.order,
            }
            for word in entry.words
        ],
    }


def _column_scope_row_fingerprint_material(
    row: _RowBand,
    *,
    include_evidence: bool,
) -> dict[str, Any]:
    material: dict[str, Any] = {
        "page_ref": row.page_ref,
        "bbox": list(row.bbox),
        "words": [
            {
                "word_ref": word.word_ref,
                "page_ref": word.page_ref,
                "text": word.text,
                "bbox": list(word.bbox),
                "order": word.order,
            }
            for word in row.words
        ],
        "role": row.role,
        "nesting_level": row.nesting_level,
        "parent_row_id": row.parent_row_id,
        "row_id": row.row_id,
        "anchor_ids": row.anchor_ids,
        "entries": [
            _column_scope_entry_fingerprint_material(entry)
            for entry in row.entries
        ],
        "row_coalescence_kind": row.row_coalescence_kind,
        "sequential_marker_header": row.sequential_marker_header,
        "proven_leading_suffix_header": row.proven_leading_suffix_header,
        "semantic_issue_codes": list(row.semantic_issue_codes),
    }
    if include_evidence:
        material["column_evidence_entries"] = (
            [
                _column_scope_entry_fingerprint_material(entry)
                for entry in row.column_evidence_entries
            ]
            if row.column_evidence_entries is not None
            else None
        )
        material["column_evidence_rows"] = (
            [
                _column_scope_row_fingerprint_material(
                    evidence_row,
                    include_evidence=False,
                )
                for evidence_row in row.column_evidence_rows
            ]
            if row.column_evidence_rows is not None
            else None
        )
    return material


def _column_scope_source_fingerprint(
    rows: list[_RowBand],
    *,
    table_id: str,
    config: LogicalRowTableRecoveryConfig,
) -> str:
    return _sha256_json(
        {
            "table_id": table_id,
            "minimum_column_observations": config.minimum_column_observations,
            "column_tolerance_width_ratio": (
                config.column_tolerance_width_ratio
            ),
            "rows": [
                _column_scope_row_fingerprint_material(
                    row,
                    include_evidence=True,
                )
                for row in rows
            ]
        }
    )


def _column_scope_plan_fingerprint(
    *,
    columns: tuple[_LogicalColumnMaterializationPlan, ...],
    bindings: tuple[_EntryColumnBindingPlan, ...],
) -> str:
    return _sha256_json(
        {
            "columns": [
                {
                    "track": {
                        "edge": column.track.edge,
                        "coordinate": column.track.coordinate,
                        "tolerance": column.track.tolerance,
                        "row_indexes": sorted(column.track.row_indexes),
                        "entries": [
                            _column_scope_entry_fingerprint_material(entry)
                            for entry in column.track.entries
                        ],
                    },
                    "key": list(column.key),
                    "alignment_source": column.alignment_source,
                    "material": dict(column.material),
                }
                for column in columns
            ],
            "bindings": [
                {
                    "entry": _column_scope_entry_fingerprint_material(
                        binding.entry
                    ),
                    "logical_column_ordinal": binding.logical_column_ordinal,
                    "covered_column_ordinals": list(
                        binding.covered_column_ordinals
                    ),
                }
                for binding in bindings
            ],
        }
    )


def _sealed_column_materialization_scope_plan(
    *,
    rows: list[_RowBand],
    table_id: str,
    config: LogicalRowTableRecoveryConfig,
    columns: tuple[_LogicalColumnMaterializationPlan, ...],
    bindings: tuple[_EntryColumnBindingPlan, ...],
) -> _ColumnMaterializationScopePlan:
    return _ColumnMaterializationScopePlan(
        source_fingerprint_sha256=_column_scope_source_fingerprint(
            rows,
            table_id=table_id,
            config=config,
        ),
        plan_fingerprint_sha256=_column_scope_plan_fingerprint(
            columns=columns,
            bindings=bindings,
        ),
        columns=columns,
        bindings=bindings,
    )


def _accounting_label_value_scope_plan(
    *,
    rows: list[_RowBand],
    lineage: _ColumnEvidenceLineage,
    table_id: str,
    width: float,
    config: LogicalRowTableRecoveryConfig,
) -> _ColumnMaterializationScopePlan | None:
    """Prove one label lane and one optional-unit/value lane.

    This is deliberately a logical two-column proof.  A repeated accounting
    unit is an optional child of the terminal value lane; its own X position
    never creates a third logical column.
    """

    eligible_roles = {"DATA", "SUBTOTAL", "TOTAL"}
    candidates: list[tuple[int, _RowBand]] = []
    for row_index, row in enumerate(rows):
        if (
            row.role not in eligible_roles
            or len(row.entries) not in {2, 3}
            or not _row_has_exact_entry_word_partition(row)
        ):
            continue
        label = row.entries[0]
        terminal = row.entries[-1]
        if (
            _looks_value_like(label.text)
            or not _looks_value_like(terminal.text)
            or sum(_looks_value_like(entry.text) for entry in row.entries) != 1
            or label.bbox[2] >= terminal.bbox[0]
        ):
            continue
        if len(row.entries) == 3:
            unit = row.entries[1]
            normalized_unit = unicodedata.normalize("NFKC", unit.text).strip()
            if (
                _UNIT_PATTERN.fullmatch(normalized_unit) is None
                or label.bbox[2] >= unit.bbox[0]
                or unit.bbox[2] >= terminal.bbox[0]
            ):
                continue
        candidates.append((row_index, row))
    required = max(3, config.minimum_column_observations)
    if (
        len(candidates) < required
        or not any(len(row.entries) == 2 for _, row in candidates)
        or not any(len(row.entries) == 3 for _, row in candidates)
    ):
        return None
    right_edges = [row.entries[-1].bbox[2] for _, row in candidates]
    tolerance = max(3.0, width * config.column_tolerance_width_ratio * 0.55)
    right_coordinate = statistics.median(right_edges)
    if max(abs(edge - right_coordinate) for edge in right_edges) > tolerance * 1.8:
        return None
    candidate_row_ids = {id(row) for _, row in candidates}
    if len(candidate_row_ids) != len(candidates):
        return None
    lane_by_entry = {
        id(entry): lane
        for _, row in candidates
        for lane, entries in (
            (0, row.entries[:1]),
            (1, row.entries[1:]),
        )
        for entry in entries
    }
    candidate_parent_ids = {
        id(parent)
        for entry_id in lane_by_entry
        for parent in lineage.parents_by_canonical_child[entry_id]
    }
    if any(
        len(
            {
                lane_by_entry[id(child)]
                for child in lineage.canonical_children_by_parent[parent_id]
                if id(child) in lane_by_entry
            }
        )
        != 1
        for parent_id in candidate_parent_ids
    ):
        return None

    label_entries = [row.entries[0] for _, row in candidates]
    value_lane_entries = [
        entry
        for _, row in candidates
        for entry in row.entries[1:]
    ]
    label_coordinate = statistics.median(entry.bbox[0] for entry in label_entries)
    label_track = _ColumnTrack(
        edge="LEFT",
        coordinate=label_coordinate,
        tolerance=tolerance,
        entries=label_entries,
        row_indexes={row_index for row_index, _ in candidates},
    )
    value_track = _ColumnTrack(
        edge="RIGHT",
        coordinate=right_coordinate,
        tolerance=tolerance,
        entries=value_lane_entries,
        row_indexes={row_index for row_index, _ in candidates},
    )
    binding_by_entry: dict[int, _EntryColumnBindingPlan] = {}
    for row in rows:
        for entry in row.entries:
            binding_by_entry[id(entry)] = _EntryColumnBindingPlan(
                entry=entry,
                logical_column_ordinal=None,
                covered_column_ordinals=(),
            )
        if id(row) not in candidate_row_ids:
            continue
        binding_by_entry[id(row.entries[0])] = _EntryColumnBindingPlan(
            entry=row.entries[0],
            logical_column_ordinal=0,
            covered_column_ordinals=(),
        )
        for entry in row.entries[1:]:
            binding_by_entry[id(entry)] = _EntryColumnBindingPlan(
                entry=entry,
                logical_column_ordinal=1,
                covered_column_ordinals=(),
            )
    bindings = tuple(
        binding_by_entry[id(entry)]
        for row in rows
        for entry in row.entries
    )
    columns = (
        _LogicalColumnMaterializationPlan(
            track=label_track,
            key=(table_id, 0, "accounting_label_lane", round(label_coordinate, 4)),
            alignment_source="accounting_label_value_scope",
            material={
                "lane_role": "LABEL",
                "physical_row_observations": len(candidates),
            },
        ),
        _LogicalColumnMaterializationPlan(
            track=value_track,
            key=(table_id, 1, "accounting_value_lane", round(right_coordinate, 4)),
            alignment_source="accounting_label_value_scope",
            material={
                "lane_role": "VALUE_WITH_OPTIONAL_UNIT",
                "physical_row_observations": len(candidates),
            },
        ),
    )
    return _sealed_column_materialization_scope_plan(
        rows=rows,
        table_id=table_id,
        config=config,
        columns=columns,
        bindings=bindings,
    )


def _generic_column_scope_plan(
    *,
    rows: list[_RowBand],
    table_id: str,
    config: LogicalRowTableRecoveryConfig,
) -> _ColumnMaterializationScopePlan | None:
    lineage = _column_evidence_lineage(rows)
    if lineage is None:
        return None
    table_bbox = _merge_bboxes([row.bbox for row in rows])
    width = max(1.0, _bbox_width(table_bbox))
    allowed_roles = {
        "COLUMN_HEADER",
        "CONTINUATION_HEADER",
        "DATA",
        "SUBTOTAL",
        "TOTAL",
    }
    normalized = _materialization_two_lane_evidence(
        lineage,
        width=width,
        config=config,
    )
    evidence_rows = [row for row in normalized if row.role in allowed_roles]
    headers = [
        row
        for row in rows
        if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
    ]
    general_required = max(3, config.minimum_column_observations)
    headerless = not headers
    tracks: list[_ColumnTrack]
    required = general_required
    if headerless:
        tracks = _headerless_two_column_tracks(
            evidence_rows,
            width=width,
            config=config,
            required=general_required,
        )
        if not tracks:
            exact_pairs = [row for row in lineage.rows if row.role in allowed_roles]
            canonical_rows = {
                id(lineage.canonical_row_by_evidence_row[id(row)])
                for row in exact_pairs
            }
            if (
                len(exact_pairs) == 2
                and all(len(row.entries) == 2 for row in exact_pairs)
                and len(canonical_rows) == 2
                and canonical_rows.issubset(
                    lineage.snapshot_backed_canonical_rows
                )
            ):
                tracks = _headerless_two_column_tracks(
                    exact_pairs,
                    width=width,
                    config=config,
                    required=2,
                )
                required = 2
    else:
        tracks = _repeated_entry_tracks(
            [
                row
                for row in evidence_rows
                if row.role in {"DATA", "SUBTOTAL", "TOTAL"}
            ],
            width=width,
            config=replace(
                config,
                minimum_column_observations=general_required,
            ),
        )
    if len(tracks) < 2:
        return _accounting_label_value_scope_plan(
            rows=rows,
            lineage=lineage,
            table_id=table_id,
            width=width,
            config=config,
        )
    bindings = _entry_binding_plans_for_tracks(
        rows=rows,
        lineage=lineage,
        tracks=tracks,
    )
    if bindings is None:
        return None
    row_by_entry = {
        id(entry): row for row in rows for entry in row.entries
    }
    physical_support = [len(track.row_indexes) for track in tracks]
    if any(total < required for total in physical_support):
        return None
    header_support = [set() for _ in tracks]
    body_support = [set() for _ in tracks]
    for binding in bindings:
        row = row_by_entry[id(binding.entry)]
        indexes = {
            *binding.covered_column_ordinals,
            *(
                (binding.logical_column_ordinal,)
                if binding.logical_column_ordinal is not None
                else ()
            ),
        }
        for index in indexes:
            if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}:
                header_support[index].add(id(row))
            elif row.role in {"DATA", "SUBTOTAL", "TOTAL"}:
                body_support[index].add(id(row))
    if headers:
        unheaded = [
            index for index, support in enumerate(header_support) if not support
        ]
        if unheaded:
            if len(unheaded) != 1 or unheaded[0] not in {0, len(tracks) - 1}:
                return None
            exterior = unheaded[0]
            exterior_entries = [
                binding.entry
                for binding in bindings
                if row_by_entry[id(binding.entry)].role
                in {"DATA", "SUBTOTAL", "TOTAL"}
                and (
                    binding.logical_column_ordinal == exterior
                    or exterior in binding.covered_column_ordinals
                )
            ]
            legacy_leaf_lineage = any(
                row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
                and row.row_coalescence_kind == "LEAF_HEADER"
                and row.column_evidence_rows is not None
                for row in rows
            )
            has_header_snapshot_lineage = any(
                row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
                and row.column_evidence_rows is not None
                for row in rows
            )
            headed_centers = [
                _track_center(track)
                for index, track in enumerate(tracks)
                if index != exterior
            ]
            exterior_center = _track_center(tracks[exterior])
            outside = (
                exterior == 0
                and exterior_center
                < min(headed_centers) - tracks[exterior].tolerance
            ) or (
                exterior == len(tracks) - 1
                and exterior_center
                > max(headed_centers) + tracks[exterior].tolerance
            )
            if (
                (has_header_snapshot_lineage and not legacy_leaf_lineage)
                or not exterior_entries
                or any(_looks_value_like(entry.text) for entry in exterior_entries)
                or not outside
                or len(body_support[exterior]) < general_required
                or any(not support for index, support in enumerate(header_support) if index != exterior)
            ):
                return None
    columns = tuple(
        _LogicalColumnMaterializationPlan(
            track=track,
            key=(table_id, ordinal, track.edge, round(track.coordinate, 4)),
            alignment_source="stable_physical_row_tracks",
            material={
                "alignment_edge": track.edge,
                "alignment_coordinate": track.coordinate,
                "physical_row_observations": len(track.row_indexes),
            },
        )
        for ordinal, track in enumerate(tracks)
    )
    return _sealed_column_materialization_scope_plan(
        rows=rows,
        table_id=table_id,
        config=config,
        columns=columns,
        bindings=bindings,
    )


def _apply_column_scope_plan(
    *,
    plan: _ColumnMaterializationScopePlan,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    table_id: str,
    state: _RecoveryState,
    config: LogicalRowTableRecoveryConfig,
) -> list[dict[str, Any]]:
    entries = [entry for row in rows for entry in row.entries]
    expected = _generic_column_scope_plan(
        rows=rows,
        table_id=table_id,
        config=config,
    )
    if (
        expected is None
        or plan != expected
        or plan.source_fingerprint_sha256
        != _column_scope_source_fingerprint(
            rows,
            table_id=table_id,
            config=config,
        )
        or plan.plan_fingerprint_sha256
        != _column_scope_plan_fingerprint(
            columns=plan.columns,
            bindings=plan.bindings,
        )
        or len(plan.columns) < 2
        or len(plan.bindings) != len(entries)
        or {id(binding.entry) for binding in plan.bindings}
        != {id(entry) for entry in entries}
    ):
        raise LogicalRowTableRecoveryError(
            "column_materialization_scope_plan_invalid"
        )
    row_by_entry = {
        id(entry): row for row in rows for entry in row.entries
    }
    for binding in plan.bindings:
        direct = binding.logical_column_ordinal
        covers = binding.covered_column_ordinals
        if direct is not None and not 0 <= direct < len(plan.columns):
            raise LogicalRowTableRecoveryError(
                "column_materialization_scope_plan_invalid"
            )
        if covers:
            if (
                len(covers) < 2
                or covers != tuple(range(covers[0], covers[-1] + 1))
                or covers[-1] >= len(plan.columns)
            ):
                raise LogicalRowTableRecoveryError(
                    "column_materialization_scope_plan_invalid"
                )
            role = row_by_entry[id(binding.entry)].role
            if role in {"SUBTOTAL", "TOTAL"} and direct != covers[0]:
                raise LogicalRowTableRecoveryError(
                    "column_materialization_scope_plan_invalid"
                )
            if role in {
                "COLUMN_HEADER",
                "CONTINUATION_HEADER",
                "GROUP_HEADER",
            } and direct is not None:
                raise LogicalRowTableRecoveryError(
                    "column_materialization_scope_plan_invalid"
                )
    column_ids = [
        _identifier("column", column.key) for column in plan.columns
    ]
    if len(column_ids) != len(set(column_ids)) or len(rows) != len(row_payloads):
        raise LogicalRowTableRecoveryError(
            "column_materialization_scope_plan_invalid"
        )
    payload_by_entry_id: dict[str, dict[str, Any]] = {}
    for row, row_payload in zip(rows, row_payloads):
        payload_entries = _dicts(row_payload.get("entries"))
        if len(row.entries) != len(payload_entries):
            raise LogicalRowTableRecoveryError(
                "column_materialization_scope_plan_invalid"
            )
        for entry, payload_entry in zip(row.entries, payload_entries):
            entry_id = str(entry.entry_id or "")
            if (
                not entry_id
                or entry_id != str(payload_entry.get("entry_id") or "")
                or entry_id in payload_by_entry_id
                or entry.column_binding_status != "NOT_APPLICABLE"
                or entry.logical_column_id is not None
                or entry.covers_logical_column_ids
                or payload_entry.get("column_binding_status")
                != "NOT_APPLICABLE"
                or payload_entry.get("logical_column_id") is not None
                or payload_entry.get("covers_logical_column_ids")
            ):
                raise LogicalRowTableRecoveryError(
                    "column_materialization_scope_plan_invalid"
                )
            payload_by_entry_id[entry_id] = payload_entry
    bindings_by_entry = {
        id(binding.entry): binding for binding in plan.bindings
    }
    entries_by_column: list[list[_EntryBand]] = [
        [] for _ in plan.columns
    ]
    header_entries_by_column: list[list[_EntryBand]] = [
        [] for _ in plan.columns
    ]
    for binding in plan.bindings:
        indexes = list(binding.covered_column_ordinals)
        if binding.logical_column_ordinal is not None:
            indexes.append(binding.logical_column_ordinal)
        for index in sorted(set(indexes)):
            entries_by_column[index].append(binding.entry)
            if row_by_entry[id(binding.entry)].role in {
                "COLUMN_HEADER",
                "CONTINUATION_HEADER",
            }:
                header_entries_by_column[index].append(binding.entry)
    if any(
        not _unique(anchor for entry in bound for anchor in entry.anchor_ids)
        for bound in entries_by_column
    ):
        raise LogicalRowTableRecoveryError(
            "column_materialization_scope_plan_invalid"
        )

    commits: list[
        tuple[_EntryBand, dict[str, Any], str | None, list[str]]
    ] = []
    for entry in entries:
        binding = bindings_by_entry[id(entry)]
        commits.append(
            (
                entry,
                payload_by_entry_id[str(entry.entry_id)],
                (
                    column_ids[binding.logical_column_ordinal]
                    if binding.logical_column_ordinal is not None
                    else None
                ),
                [
                    column_ids[index]
                    for index in binding.covered_column_ordinals
                ],
            )
        )
    for entry, payload, logical_column_id, covers_logical_column_ids in commits:
        _set_entry_column_binding(
            entry,
            payload=payload,
            logical_column_id=logical_column_id,
            covers_logical_column_ids=covers_logical_column_ids,
        )

    result = []
    for ordinal, column in enumerate(plan.columns):
        bound = entries_by_column[ordinal]
        anchor_ids = _unique(
            anchor for entry in bound for anchor in entry.anchor_ids
        )
        issue_ids = []
        if not header_entries_by_column[ordinal]:
            issue_ids.append(
                state.add_issue(
                    code="logical_column_header_path_unknown",
                    message=(
                        "Repeated physical-row alignment proves the logical "
                        "column, but no source header entry is deterministic."
                    ),
                    anchor_ids=anchor_ids,
                    block_ids=[logical_table_block_id(table_id)],
                )
            )
        material = dict(column.material)
        material.update(
            {
                "alignment_source": column.alignment_source,
                "entry_ids": [entry.entry_id for entry in bound],
                "entry_bboxes": [list(entry.bbox) for entry in bound],
            }
        )
        geometry_id = state.add_geometry(
            kind="COLUMN_ALIGNMENT",
            key=[table_id, column_ids[ordinal]],
            anchor_ids=anchor_ids,
            material=material,
            issue_ids=issue_ids,
        )
        result.append(
            {
                "column_id": column_ids[ordinal],
                "ordinal": ordinal,
                "header_path": [
                    str(entry.entry_id)
                    for entry in header_entries_by_column[ordinal]
                ],
                "source_anchor_ids": anchor_ids,
                "geometry_evidence_ids": [geometry_id],
                "issue_ids": issue_ids,
            }
        )
    return result


def _plan_legacy_post_track_bindings(
    *,
    rows: list[_RowBand],
    tracks: list[_ColumnTrack],
    minimum_column_observations: int,
) -> _LegacyPostTrackBindingPlan:
    """Plan direct, compound-lane and monotonic-complement bindings.

    Track discovery is already complete.  This owner may consume those tracks
    but may not add, remove or move one.  Repeated prefix/value pairs and a
    repeated one-entry/one-track complement are the only recovery expansions
    beyond the legacy unique-nearest assignment.
    """

    fingerprint = _legacy_post_track_binding_source_fingerprint(
        rows,
        tracks=tracks,
        minimum_column_observations=minimum_column_observations,
    )
    if len(tracks) < 2 or minimum_column_observations <= 0:
        return _LegacyPostTrackBindingPlan(
            fingerprint,
            minimum_column_observations,
            (),
        )
    binding_row_indexes = [
        index
        for index, row in enumerate(rows)
        if (
            row.role
            in {
                "COLUMN_HEADER",
                "CONTINUATION_HEADER",
                "DATA",
                "SUBTOTAL",
                "TOTAL",
            }
            and len(row.entries) >= 2
        )
        or row.role == "COLUMN_HEADER"
        and row.proven_leading_suffix_header
    ]
    raw_track_by_entry: dict[tuple[int, int], int | None] = {}
    decisions: dict[tuple[int, int], _LegacyPostTrackBindingDecision] = {}
    for row_index in binding_row_indexes:
        row = rows[row_index]
        assignments: dict[int, list[int]] = {}
        for entry_index, entry in enumerate(row.entries):
            distances = [
                abs(_entry_edge(entry, track.edge) - track.coordinate)
                / max(1.0, track.tolerance)
                for track in tracks
            ]
            nearest = min(range(len(distances)), key=distances.__getitem__)
            target = nearest if distances[nearest] <= 1.8 else None
            raw_track_by_entry[(row_index, entry_index)] = target
            if target is not None:
                assignments.setdefault(target, []).append(entry_index)
        for target, entry_indexes in assignments.items():
            if len(entry_indexes) != 1:
                continue
            entry_index = entry_indexes[0]
            decisions[(row_index, entry_index)] = (
                _LegacyPostTrackBindingDecision(
                    row_index=row_index,
                    entry_index=entry_index,
                    track_ordinal=target,
                    proof_kind="UNIQUE_NEAREST_TRACK",
                )
            )

    compound_candidates: dict[
        tuple[int, int],
        list[tuple[int, int, int]],
    ] = {}
    for row_index in binding_row_indexes:
        row = rows[row_index]
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        for left_index in range(len(row.entries) - 1):
            right_index = left_index + 1
            left = row.entries[left_index]
            right = row.entries[right_index]
            prefix = unicodedata.normalize("NFKC", left.text).strip()
            if not (
                _MARKER_PATTERN.fullmatch(prefix)
                or _CURRENCY_MARKER_PATTERN.fullmatch(prefix)
                or _UNIT_PATTERN.fullmatch(prefix)
            ) or not _looks_numeric(right.text):
                continue
            merged = _EntryBand(
                words=[*left.words, *right.words],
                bbox=_merge_bboxes([left.bbox, right.bbox]),
                text=f"{left.text} {right.text}".strip(),
                anchor_ids=[],
            )
            target = _unique_track_index(merged, tracks)
            if target is None or _covered_track_indexes(merged, tracks) != (target,):
                continue
            assigned = {
                raw_track_by_entry.get((row_index, index))
                for index in (left_index, right_index)
                if raw_track_by_entry.get((row_index, index)) is not None
            }
            other_contenders = [
                entry_index
                for entry_index in range(len(row.entries))
                if entry_index not in {left_index, right_index}
                and raw_track_by_entry.get((row_index, entry_index)) == target
            ]
            gap = right.bbox[0] - left.bbox[2]
            gap_limit = max(
                12.0,
                _bbox_height(row.bbox) * 4.0,
                tracks[target].tolerance * 4.0,
            )
            if (
                assigned and assigned != {target}
                or other_contenders
                or gap < -max(1.0, tracks[target].tolerance * 0.1)
                or gap > gap_limit
            ):
                continue
            compound_candidates.setdefault((target, row_index), []).append(
                (row_index, left_index, right_index)
            )
    compound_by_track: dict[int, list[tuple[int, int, int]]] = {}
    for (target, _row_index), candidates in compound_candidates.items():
        if len(candidates) == 1:
            compound_by_track.setdefault(target, []).append(candidates[0])
    for target, candidates in compound_by_track.items():
        if len({row_index for row_index, _, _ in candidates}) < 2:
            continue
        for row_index, left_index, right_index in candidates:
            for entry_index in (left_index, right_index):
                decisions[(row_index, entry_index)] = (
                    _LegacyPostTrackBindingDecision(
                        row_index=row_index,
                        entry_index=entry_index,
                        track_ordinal=target,
                        proof_kind="REPEATED_PREFIX_VALUE_LANE",
                    )
                )

    complement_candidates: dict[
        tuple[int, int],
        list[tuple[int, int, int]],
    ] = {}
    for row_index in binding_row_indexes:
        row = rows[row_index]
        if (
            row.role not in {"DATA", "SUBTOTAL", "TOTAL"}
            or len(row.entries) != len(tracks)
            or len(tracks) < 3
        ):
            continue
        assigned = {
            entry_index: decision.track_ordinal
            for (decision_row, entry_index), decision in decisions.items()
            if decision_row == row_index
        }
        if len(set(assigned.values())) != len(assigned):
            continue
        missing_entries = [
            entry_index
            for entry_index in range(len(row.entries))
            if entry_index not in assigned
        ]
        missing_tracks = [
            track_index
            for track_index in range(len(tracks))
            if track_index not in assigned.values()
        ]
        if len(missing_entries) != 1 or len(missing_tracks) != 1:
            continue
        entry_index = missing_entries[0]
        target = missing_tracks[0]
        if (
            entry_index != target
            or entry_index == 0
            or entry_index == len(row.entries) - 1
            or assigned.get(entry_index - 1) != target - 1
            or assigned.get(entry_index + 1) != target + 1
            or [assigned[index] for index in sorted(assigned)]
            != sorted(assigned.values())
        ):
            continue
        entry = row.entries[entry_index]
        normalized_distance = (
            abs(_entry_edge(entry, tracks[target].edge) - tracks[target].coordinate)
            / max(1.0, tracks[target].tolerance)
        )
        center = _bbox_center_x(entry.bbox)
        left_boundary = (
            _track_center(tracks[target - 1]) + _track_center(tracks[target])
        ) / 2.0
        right_boundary = (
            _track_center(tracks[target]) + _track_center(tracks[target + 1])
        ) / 2.0
        if normalized_distance > 4.0 or not left_boundary < center < right_boundary:
            continue
        complement_candidates.setdefault((entry_index, target), []).append(
            (row_index, entry_index, target)
        )
    for candidates in complement_candidates.values():
        if len({row_index for row_index, _, _ in candidates}) < max(
            3,
            minimum_column_observations,
        ):
            continue
        for row_index, entry_index, target in candidates:
            decisions[(row_index, entry_index)] = (
                _LegacyPostTrackBindingDecision(
                    row_index=row_index,
                    entry_index=entry_index,
                    track_ordinal=target,
                    proof_kind="REPEATED_MONOTONIC_COMPLEMENT",
                )
            )

    return _LegacyPostTrackBindingPlan(
        source_fingerprint_sha256=fingerprint,
        minimum_column_observations=minimum_column_observations,
        decisions=tuple(decisions[key] for key in sorted(decisions)),
    )


def _plan_legacy_active_track_bindings(
    *,
    rows: list[_RowBand],
    tracks: list[_ColumnTrack],
    active_track_ordinals: set[int],
    minimum_column_observations: int,
) -> _LegacyActiveTrackBindingPlan:
    """Prove physical-subtrack aliases without creating logical columns."""

    active = tuple(sorted(active_track_ordinals))
    fingerprint = _sha256_json(
        {
            "legacy_source_fingerprint_sha256": (
                _legacy_post_track_binding_source_fingerprint(
                    rows,
                    tracks=tracks,
                    minimum_column_observations=minimum_column_observations,
                )
            ),
            "active_track_ordinals": active,
        }
    )
    if (
        len(active) < 2
        or minimum_column_observations <= 0
        or any(index < 0 or index >= len(tracks) for index in active)
    ):
        return _LegacyActiveTrackBindingPlan(
            fingerprint,
            minimum_column_observations,
            active,
            (),
        )

    binding_row_indexes = [
        index
        for index, row in enumerate(rows)
        if row.role
        in {
            "COLUMN_HEADER",
            "CONTINUATION_HEADER",
            "DATA",
            "SUBTOTAL",
            "TOTAL",
        }
        and len(row.entries) >= 2
    ]
    raw_track_by_entry: dict[tuple[int, int], int | None] = {}
    raw_support_rows: dict[int, set[int]] = {}
    for row_index in binding_row_indexes:
        for entry_index, entry in enumerate(rows[row_index].entries):
            distances = [
                abs(_entry_edge(entry, track.edge) - track.coordinate)
                / max(1.0, track.tolerance)
                for track in tracks
            ]
            nearest = min(range(len(distances)), key=distances.__getitem__)
            target = nearest if distances[nearest] <= 1.8 else None
            raw_track_by_entry[(row_index, entry_index)] = target
            if target is not None:
                raw_support_rows.setdefault(target, set()).add(row_index)

    near_alias: dict[int, int] = {}
    for track_index, support_rows in raw_support_rows.items():
        if (
            track_index in active_track_ordinals
            or len(support_rows)
            < max(2, minimum_column_observations)
        ):
            continue
        candidates = [
            active_index
            for active_index in active
            if abs(
                _track_center(tracks[track_index])
                - _track_center(tracks[active_index])
            )
            <= max(
                tracks[track_index].tolerance,
                tracks[active_index].tolerance,
            )
            * 0.5
        ]
        if len(candidates) == 1:
            near_alias[track_index] = candidates[0]

    def active_target(track_index: int | None) -> int | None:
        if track_index is None:
            return None
        if track_index in active_track_ordinals:
            return track_index
        return near_alias.get(track_index)

    pair_candidates: dict[
        tuple[int | None, int | None, int],
        list[tuple[int, int, int]],
    ] = {}
    active_tracks = [tracks[index] for index in active]
    for row_index in binding_row_indexes:
        row = rows[row_index]
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        for left_index in range(len(row.entries) - 1):
            right_index = left_index + 1
            left = row.entries[left_index]
            right = row.entries[right_index]
            prefix = unicodedata.normalize("NFKC", left.text).strip()
            currency_or_unit_prefix = bool(
                _CURRENCY_MARKER_PATTERN.fullmatch(prefix)
                or _UNIT_PATTERN.fullmatch(prefix)
            )
            generic_marker_prefix = bool(_MARKER_PATTERN.fullmatch(prefix))
            right_is_numeric = _looks_numeric(right.text)
            right_is_marker = _strict_dash_placeholder(right.text)
            if (
                not (currency_or_unit_prefix or generic_marker_prefix)
                or not (right_is_numeric or right_is_marker)
                or right_is_marker
                and not currency_or_unit_prefix
            ):
                continue
            gap = right.bbox[0] - left.bbox[2]
            gap_limit = max(
                12.0,
                _bbox_height(row.bbox) * 4.0,
                max(track.tolerance for track in tracks) * 4.0,
            )
            active_centers = sorted(
                _track_center(tracks[index]) for index in active
            )
            if len(active_centers) >= 3:
                gap_limit = max(
                    gap_limit,
                    statistics.median(
                        right_center - left_center
                        for left_center, right_center in zip(
                            active_centers,
                            active_centers[1:],
                        )
                    )
                    * 0.75,
                )
            if len(active) == 2:
                gap_limit = max(
                    gap_limit,
                    abs(
                        _track_center(tracks[active[1]])
                        - _track_center(tracks[active[0]])
                    )
                    * 0.55,
                )
            if gap < -max(1.0, gap_limit * 0.025) or gap > gap_limit:
                continue
            left_raw = raw_track_by_entry[(row_index, left_index)]
            right_raw = raw_track_by_entry[(row_index, right_index)]
            left_target = active_target(left_raw)
            right_target = active_target(right_raw)
            if (
                generic_marker_prefix
                and left_target is not None
                and right_target is not None
                and left_target != right_target
            ):
                continue
            target = right_target if right_target is not None else left_target
            if target is None:
                merged = _EntryBand(
                    words=[*left.words, *right.words],
                    bbox=_merge_bboxes([left.bbox, right.bbox]),
                    text=f"{left.text} {right.text}".strip(),
                    anchor_ids=[],
                )
                active_local = _unique_track_index(merged, active_tracks)
                if active_local is not None:
                    target = active[active_local]
            if target is None:
                continue
            pair_candidates.setdefault(
                (left_raw, right_raw, target), []
            ).append((row_index, left_index, right_index))

    repeated_pairs = {
        key: candidates
        for key, candidates in pair_candidates.items()
        if len({row_index for row_index, _, _ in candidates}) >= 2
    }
    edge_alias: dict[int, int] = {}
    active_centers_by_track = {
        index: _track_center(tracks[index]) for index in active
    }
    for track_index, support_rows in raw_support_rows.items():
        if (
            track_index in active_track_ordinals
            or len(support_rows) < max(2, minimum_column_observations)
            or tracks[track_index].edge not in {"LEFT", "RIGHT"}
        ):
            continue
        center = _track_center(tracks[track_index])
        if tracks[track_index].edge == "RIGHT":
            candidates = [
                active_index
                for active_index in active
                if tracks[active_index].edge == "LEFT"
                and active_centers_by_track[active_index] < center
                and not any(
                    active_centers_by_track[active_index]
                    < other_center
                    < center
                    for other_index, other_center in active_centers_by_track.items()
                    if other_index != active_index
                )
            ]
        else:
            candidates = [
                active_index
                for active_index in active
                if tracks[active_index].edge == "RIGHT"
                and active_centers_by_track[active_index] > center
                and not any(
                    center
                    < other_center
                    < active_centers_by_track[active_index]
                    for other_index, other_center in active_centers_by_track.items()
                    if other_index != active_index
                )
            ]
        if len(candidates) == 1:
            edge_alias[track_index] = candidates[0]
    physical_alias = {**edge_alias, **near_alias}

    baseline = _plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=minimum_column_observations,
    )
    combined_targets = {
        (decision.row_index, decision.entry_index): decision.track_ordinal
        for decision in baseline.decisions
        if decision.track_ordinal in active_track_ordinals
    }
    decisions: dict[tuple[int, int], _LegacyPostTrackBindingDecision] = {}
    for (row_index, entry_index), raw_track in raw_track_by_entry.items():
        target = physical_alias.get(raw_track) if raw_track is not None else None
        if target is None:
            continue
        combined_targets[(row_index, entry_index)] = target
        decisions[(row_index, entry_index)] = (
            _LegacyPostTrackBindingDecision(
                row_index,
                entry_index,
                target,
                "REPEATED_PHYSICAL_SUBTRACK_ALIAS",
            )
        )
    for row_index in binding_row_indexes:
        row = rows[row_index]
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"} or len(row.entries) != 2:
            continue
        left, right = row.entries
        prefix = unicodedata.normalize("NFKC", left.text).strip()
        if not (
            _CURRENCY_MARKER_PATTERN.fullmatch(prefix)
            or _UNIT_PATTERN.fullmatch(prefix)
        ):
            continue
        if not (_looks_numeric(right.text) or _strict_dash_placeholder(right.text)):
            continue
        left_key = (row_index, 0)
        right_key = (row_index, 1)
        right_target = combined_targets.get(right_key)
        if (
            left_key in combined_targets
            or right_target not in active_track_ordinals
            or right_target == active[0]
            or left.bbox[2] > right.bbox[0] + 1.0
        ):
            continue
        combined_targets[left_key] = right_target
        decisions[left_key] = _LegacyPostTrackBindingDecision(
            row_index,
            0,
            right_target,
            "BARE_PREFIX_VALUE_LANE",
        )
    pair_claims: dict[tuple[int, int], set[int]] = {}
    for (_left_raw, _right_raw, target), candidates in repeated_pairs.items():
        for row_index, left_index, right_index in candidates:
            for entry_index in (left_index, right_index):
                pair_claims.setdefault((row_index, entry_index), set()).add(
                    target
                )
    for key, targets in pair_claims.items():
        if len(targets) != 1:
            decisions.pop(key, None)
            combined_targets.pop(key, None)
            continue
        target = next(iter(targets))
        combined_targets[key] = target
        decisions[key] = _LegacyPostTrackBindingDecision(
            key[0],
            key[1],
            target,
            "REPEATED_ACTIVE_PREFIX_VALUE_LANE",
        )

    row_lane_candidates: dict[
        int, tuple[bool, tuple[tuple[int, ...], ...]]
    ] = {}
    exterior_lane_support = sum(
        raw_track_by_entry.get((row_index, 0)) not in active_track_ordinals
        for row_index in binding_row_indexes
        if rows[row_index].role in {"DATA", "SUBTOTAL", "TOTAL"}
        and rows[row_index].entries
        and not _looks_value_like(rows[row_index].entries[0].text)
        and rows[row_index].entries[0].bbox[2]
        < _track_center(tracks[active[0]])
    )
    allow_exterior_lane = (
        len(active) >= 3
        and exterior_lane_support >= max(3, minimum_column_observations)
    )
    for row_index in binding_row_indexes:
        row = rows[row_index]
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue

        parses: list[tuple[tuple[int, ...], ...]] = []

        def extend_groups(
            entry_index: int,
            groups: tuple[tuple[int, ...], ...],
        ) -> None:
            if entry_index == len(row.entries):
                parses.append(groups)
                return
            extend_groups(entry_index + 1, (*groups, (entry_index,)))
            if entry_index + 1 >= len(row.entries):
                return
            left = row.entries[entry_index]
            right = row.entries[entry_index + 1]
            prefix = unicodedata.normalize("NFKC", left.text).strip()
            currency_or_unit = bool(
                _CURRENCY_MARKER_PATTERN.fullmatch(prefix)
                or _UNIT_PATTERN.fullmatch(prefix)
            )
            generic_marker = bool(_MARKER_PATTERN.fullmatch(prefix))
            if not (
                (currency_or_unit or generic_marker)
                and (
                    _looks_numeric(right.text)
                    or currency_or_unit
                    and _strict_dash_placeholder(right.text)
                )
                and left.bbox[2] <= right.bbox[0] + 1.0
            ):
                return
            extend_groups(
                entry_index + 2,
                (*groups, (entry_index, entry_index + 1)),
            )

        extend_groups(0, ())
        valid: dict[
            tuple[bool, tuple[tuple[int, ...], ...]], None
        ] = {}
        first_text = unicodedata.normalize(
            "NFKC", row.entries[0].text
        ).strip()
        first_is_label_like = bool(
            first_text
            and not _looks_value_like(first_text)
            and _MARKER_PATTERN.fullmatch(first_text) is None
            and _UNIT_PATTERN.fullmatch(first_text) is None
        )
        for groups in parses:
            exterior = len(groups) == len(active) + 1
            if len(groups) == len(active):
                exterior = False
                if allow_exterior_lane:
                    continue
                if not (
                    combined_targets.get((row_index, 0)) == active[0]
                    or first_is_label_like
                ):
                    continue
            elif not (
                exterior
                and len(active) >= 3
                and allow_exterior_lane
                and groups[0] == (0,)
                and (row_index, 0) not in combined_targets
                and not _looks_value_like(row.entries[0].text)
                and len(groups) > 1
                and row.entries[0].bbox[2]
                < row.entries[groups[1][0]].bbox[0]
            ):
                continue
            valid[(exterior, groups)] = None
        if valid:
            pair_total = max(
                sum(len(group) == 2 for group in groups)
                for _exterior, groups in valid
            )
            strongest = [
                candidate
                for candidate in valid
                if sum(len(group) == 2 for group in candidate[1])
                == pair_total
            ]
            if len(strongest) == 1:
                row_lane_candidates[row_index] = strongest[0]

    lane_pattern_rows: dict[tuple[bool, tuple[int, ...]], set[int]] = {}
    for row_index, (exterior, groups) in row_lane_candidates.items():
        lane_pattern_rows.setdefault(
            (exterior, tuple(len(group) for group in groups)),
            set(),
        ).add(row_index)
    for row_index, (exterior, groups) in row_lane_candidates.items():
        pattern = (exterior, tuple(len(group) for group in groups))
        if len(lane_pattern_rows[pattern]) < 2:
            continue
        logical_groups = groups[1:] if exterior else groups
        for target, group in zip(active, logical_groups):
            for entry_index in group:
                key = (row_index, entry_index)
                combined_targets[key] = target
                decisions[key] = _LegacyPostTrackBindingDecision(
                    row_index,
                    entry_index,
                    target,
                    "ORDERED_ROW_LANE_COLLAPSE",
                )

    return _LegacyActiveTrackBindingPlan(
        fingerprint,
        minimum_column_observations,
        active,
        tuple(decisions[key] for key in sorted(decisions)),
    )


def _apply_legacy_post_track_binding_plan(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    tracks: list[_ColumnTrack],
    column_ids: list[str],
    active_track_ordinals: set[int],
    plan: _LegacyPostTrackBindingPlan,
    active_plan: _LegacyActiveTrackBindingPlan | None = None,
) -> None:
    expected = _plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=plan.minimum_column_observations,
    )
    expected_active = (
        _plan_legacy_active_track_bindings(
            rows=rows,
            tracks=tracks,
            active_track_ordinals=active_track_ordinals,
            minimum_column_observations=plan.minimum_column_observations,
        )
        if active_plan is not None
        else None
    )
    if (
        plan != expected
        or active_plan != expected_active
        or len(column_ids) != len(tracks)
        or len(column_ids) != len(set(column_ids))
        or any(
            track_index < 0 or track_index >= len(tracks)
            for track_index in active_track_ordinals
        )
        or len(rows) != len(row_payloads)
    ):
        raise LogicalRowTableRecoveryError(
            "legacy_post_track_binding_plan_invalid"
        )
    commits: list[tuple[_EntryBand, dict[str, Any], str]] = []
    for row, payload in zip(rows, row_payloads):
        payload_entries = _dicts(payload.get("entries"))
        if len(row.entries) != len(payload_entries):
            raise LogicalRowTableRecoveryError(
                "legacy_post_track_binding_plan_invalid"
            )
        for entry, entry_payload in zip(row.entries, payload_entries):
            if (
                str(entry.entry_id) != str(entry_payload.get("entry_id"))
                or entry.column_binding_status != "NOT_APPLICABLE"
                or entry.logical_column_id is not None
                or entry.covers_logical_column_ids
                or entry_payload.get("column_binding_status") != "NOT_APPLICABLE"
                or entry_payload.get("logical_column_id") is not None
                or entry_payload.get("covers_logical_column_ids")
            ):
                raise LogicalRowTableRecoveryError(
                    "legacy_post_track_binding_plan_invalid"
                )
    final_decisions = {
        (decision.row_index, decision.entry_index): decision
        for decision in plan.decisions
        if decision.track_ordinal in active_track_ordinals
    }
    if active_plan is not None:
        for decision in active_plan.decisions:
            final_decisions[(decision.row_index, decision.entry_index)] = decision
    for decision in final_decisions.values():
        if decision.track_ordinal not in active_track_ordinals:
            continue
        entry = rows[decision.row_index].entries[decision.entry_index]
        payload = _dicts(row_payloads[decision.row_index].get("entries"))[
            decision.entry_index
        ]
        commits.append((entry, payload, column_ids[decision.track_ordinal]))
    for entry, payload, column_id in commits:
        _set_entry_column_binding(
            entry,
            payload=payload,
            logical_column_id=column_id,
            covers_logical_column_ids=(),
        )


def _legacy_post_track_binding_source_fingerprint(
    rows: list[_RowBand],
    *,
    tracks: list[_ColumnTrack],
    minimum_column_observations: int,
) -> str:
    return _sha256_json(
        {
            "minimum_column_observations": minimum_column_observations,
            "rows": [
                {
                    "role": row.role,
                    "bbox": list(row.bbox),
                    "word_refs": [word.word_ref for word in row.words],
                    "proven_leading_suffix_header": (
                        row.proven_leading_suffix_header
                    ),
                    "entries": [
                        {
                            "entry_id": entry.entry_id,
                            "text": entry.text,
                            "bbox": list(entry.bbox),
                            "word_refs": [
                                word.word_ref for word in entry.words
                            ],
                        }
                        for entry in row.entries
                    ],
                }
                for row in rows
            ],
            "tracks": [
                {
                    "edge": track.edge,
                    "coordinate": track.coordinate,
                    "tolerance": track.tolerance,
                    "row_indexes": sorted(track.row_indexes),
                    "entries": sorted(
                        (
                            tuple(word.word_ref for word in entry.words),
                            tuple(entry.bbox),
                            entry.text,
                        )
                        for entry in track.entries
                    ),
                }
                for track in tracks
            ],
        }
    )


def _materialize_legacy_inferred_columns(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    regions: list[_Region],
    table_id: str,
    state: _RecoveryState,
    config: LogicalRowTableRecoveryConfig,
) -> list[dict[str, Any]]:
    """Preserve already-proven inferred columns before recovery expansion.

    DOC6 first established a conservative inferred-column path before the
    evidence-lineage expansion.  Existing accepted scopes remain on that
    path; the new atomic plan is allowed to recover only a scope for which
    this baseline produces no logical column at all.
    """

    headers = [row for row in rows if row.role == "COLUMN_HEADER"]
    column_evidence_rows = []
    for row in rows:
        physical_rows = row.column_evidence_rows or (row,)
        for physical_row in physical_rows:
            evidence_row = copy.copy(physical_row)
            evidence_row.entries = list(
                physical_row.column_evidence_entries
                or tuple(physical_row.entries)
            )
            evidence_row.column_evidence_rows = None
            column_evidence_rows.append(evidence_row)
    _classify_rows(column_evidence_rows)
    evidence_eligible = [
        row
        for row in column_evidence_rows
        if row.role
        in {"COLUMN_HEADER", "CONTINUATION_HEADER", "DATA", "SUBTOTAL", "TOTAL"}
        and len(row.entries) >= 2
    ]
    if len(evidence_eligible) < config.minimum_column_observations:
        return []
    table_bbox = _merge_bboxes([row.bbox for row in rows])
    headerless = not headers
    tracks = (
        _headerless_two_column_tracks(
            evidence_eligible,
            width=max(1.0, _bbox_width(table_bbox)),
            config=config,
            required=config.minimum_column_observations,
        )
        if headerless
        else _repeated_entry_tracks(
            evidence_eligible,
            width=max(1.0, _bbox_width(table_bbox)),
            config=config,
        )
    )
    if len(tracks) < 2:
        return []
    column_ids = [
        _identifier(
            "column",
            [table_id, ordinal, track.edge, round(track.coordinate, 4)],
        )
        for ordinal, track in enumerate(tracks)
    ]
    bound_by_column: dict[str, list[_EntryBand]] = {
        column_id: [] for column_id in column_ids
    }
    binding_plan = _plan_legacy_post_track_bindings(
        rows=rows,
        tracks=tracks,
        minimum_column_observations=config.minimum_column_observations,
    )
    decision_by_entry: dict[int, _LegacyPostTrackBindingDecision] = {}
    for decision in binding_plan.decisions:
        entry = rows[decision.row_index].entries[decision.entry_index]
        decision_by_entry[id(entry)] = decision
        bound_by_column[column_ids[decision.track_ordinal]].append(entry)

    leaf_complement_indexes = _leaf_header_complement_track_indexes(
        rows=rows,
        column_evidence_rows=column_evidence_rows,
        tracks=tracks,
        bound_by_column=bound_by_column,
        column_ids=column_ids,
        regions=regions,
        config=config,
    )
    result = []
    for ordinal, (column_id, track) in enumerate(zip(column_ids, tracks)):
        bound = bound_by_column[column_id]
        header_entries = [
            entry
            for row in headers
            for entry in row.entries
            if (
                (decision := decision_by_entry.get(id(entry))) is not None
                and decision.track_ordinal == ordinal
            )
        ]
        if (
            (
                not headerless
                and not header_entries
                and ordinal not in leaf_complement_indexes
            )
            or len(bound) < config.minimum_column_observations
        ):
            continue
        anchor_ids = _unique(
            anchor for entry in bound for anchor in entry.anchor_ids
        )
        issue_ids = []
        if not header_entries:
            issue_ids.append(
                state.add_issue(
                    code="logical_column_header_path_unknown",
                    message=(
                        "Repeated label/value alignment proves the logical "
                        "column, but no source header entry is deterministic."
                    ),
                    anchor_ids=anchor_ids,
                    block_ids=[logical_table_block_id(table_id)],
                )
            )
        geometry_id = state.add_geometry(
            kind="COLUMN_ALIGNMENT",
            key=[table_id, column_id],
            anchor_ids=anchor_ids,
            material={
                "alignment_edge": track.edge,
                "alignment_coordinate": track.coordinate,
                "entry_ids": [entry.entry_id for entry in bound],
                "entry_bboxes": [list(entry.bbox) for entry in bound],
            },
            issue_ids=issue_ids,
        )
        result.append(
            {
                "column_id": column_id,
                "ordinal": len(result),
                "header_path": [
                    str(entry.entry_id) for entry in header_entries
                ],
                "source_anchor_ids": anchor_ids,
                "geometry_evidence_ids": [geometry_id],
                "issue_ids": issue_ids,
            }
        )
    active_track_ordinals = {
        column_ids.index(str(item["column_id"])) for item in result
    }
    active_binding_plan = _plan_legacy_active_track_bindings(
        rows=rows,
        tracks=tracks,
        active_track_ordinals=active_track_ordinals,
        minimum_column_observations=config.minimum_column_observations,
    )
    _apply_legacy_post_track_binding_plan(
        rows=rows,
        row_payloads=row_payloads,
        tracks=tracks,
        column_ids=column_ids,
        active_track_ordinals=active_track_ordinals,
        plan=binding_plan,
        active_plan=active_binding_plan,
    )
    if len(result) != len(column_ids):
        for ordinal, item in enumerate(result):
            item["ordinal"] = ordinal
    return result


def _augment_unique_exterior_label_column(
    *,
    columns: list[dict[str, Any]],
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    table_id: str,
    state: _RecoveryState,
    config: LogicalRowTableRecoveryConfig,
) -> list[dict[str, Any]]:
    """Add one proven label lane strictly outside headed value columns."""

    if len(columns) < 3 or any(not column["header_path"] for column in columns):
        return columns
    header_snapshot_rows = [
        row
        for row in rows
        if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
        and row.column_evidence_rows is not None
    ]
    if any(
        row.row_coalescence_kind != "LEAF_HEADER"
        for row in header_snapshot_rows
    ):
        return columns
    existing_ids = {str(column["column_id"]) for column in columns}
    first_column_id = str(columns[0]["column_id"])
    first_column_entries = [
        entry
        for row in rows
        if row.role
        in {"COLUMN_HEADER", "CONTINUATION_HEADER", "DATA", "SUBTOTAL", "TOTAL"}
        for entry in row.entries
        if entry.logical_column_id == first_column_id
        and not entry.covers_logical_column_ids
    ]
    if len(first_column_entries) < max(3, config.minimum_column_observations):
        return columns
    first_track_center = statistics.median(
        _bbox_center_x(entry.bbox) for entry in first_column_entries
    )
    table_bbox = _merge_bboxes([row.bbox for row in rows])
    tolerance = max(
        3.0,
        _bbox_width(table_bbox) * config.column_tolerance_width_ratio * 0.55,
    )
    candidates: list[_EntryBand] = []
    candidate_rows: set[int] = set()
    for row in rows:
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"} or len(row.entries) < 2:
            continue
        bound_indexes = [
            index
            for index, entry in enumerate(row.entries)
            if entry.logical_column_id in existing_ids
            or existing_ids.intersection(entry.covers_logical_column_ids)
        ]
        if not bound_indexes or min(bound_indexes) != 1:
            continue
        prefix = row.entries[0]
        if (
            prefix.column_binding_status != "NOT_APPLICABLE"
            or prefix.logical_column_id is not None
            or prefix.covers_logical_column_ids
            or _looks_value_like(prefix.text)
            or prefix.bbox[2] >= first_track_center - tolerance
            or not any(
                _looks_value_like(entry.text)
                and (
                    entry.logical_column_id in existing_ids
                    or existing_ids.intersection(entry.covers_logical_column_ids)
                )
                for entry in row.entries[1:]
            )
        ):
            continue
        candidates.append(prefix)
        candidate_rows.add(id(row))
    required = max(3, config.minimum_column_observations)
    if len(candidates) < required or len(candidate_rows) != len(candidates):
        return columns
    candidate_lefts = [entry.bbox[0] for entry in candidates]
    if max(candidate_lefts) - min(candidate_lefts) > tolerance * 3.0:
        return columns
    if any(
        entry.column_binding_status == "NOT_APPLICABLE"
        and not _looks_value_like(entry.text)
        and _UNIT_PATTERN.fullmatch(
            unicodedata.normalize("NFKC", entry.text).strip()
        )
        is None
        and entry is not row.entries[0]
        and entry.bbox[0] < first_track_center - tolerance
        for row in rows
        if id(row) in candidate_rows
        for entry in row.entries
    ):
        return columns
    candidate_refs = [
        word.word_ref for entry in candidates for word in entry.words
    ]
    if len(candidate_refs) != len(set(candidate_refs)):
        return columns

    coordinate = statistics.median(entry.bbox[0] for entry in candidates)
    column_id = _identifier(
        "column",
        [table_id, "unique_exterior_label_lane", round(coordinate, 4)],
    )
    if column_id in existing_ids:
        return columns
    entry_payload_by_id = {
        str(entry["entry_id"]): entry
        for row in row_payloads
        for entry in row["entries"]
    }
    if any(str(entry.entry_id) not in entry_payload_by_id for entry in candidates):
        return columns
    anchor_ids = _unique(
        anchor for entry in candidates for anchor in entry.anchor_ids
    )
    if not anchor_ids:
        return columns
    issue_ids = [
        state.add_issue(
            code="logical_column_header_path_unknown",
            message=(
                "A repeated exterior label lane proves the logical column, "
                "but no source header entry is deterministic."
            ),
            anchor_ids=anchor_ids,
            block_ids=[logical_table_block_id(table_id)],
        )
    ]
    geometry_id = state.add_geometry(
        kind="COLUMN_ALIGNMENT",
        key=[table_id, column_id],
        anchor_ids=anchor_ids,
        material={
            "alignment_source": "unique_exterior_label_lane",
            "alignment_edge": "LEFT",
            "alignment_coordinate": coordinate,
            "physical_row_observations": len(candidates),
            "entry_ids": [entry.entry_id for entry in candidates],
            "entry_bboxes": [list(entry.bbox) for entry in candidates],
        },
        issue_ids=issue_ids,
    )
    for entry in candidates:
        _set_entry_column_binding(
            entry,
            payload=entry_payload_by_id[str(entry.entry_id)],
            logical_column_id=column_id,
            covers_logical_column_ids=(),
        )
    shifted = copy.deepcopy(columns)
    for ordinal, column in enumerate(shifted, start=1):
        column["ordinal"] = ordinal
    return [
        {
            "column_id": column_id,
            "ordinal": 0,
            "header_path": [],
            "source_anchor_ids": anchor_ids,
            "geometry_evidence_ids": [geometry_id],
            "issue_ids": issue_ids,
        },
        *shifted,
    ]


def _materialize_columns(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    regions: list[_Region],
    table_id: str,
    state: _RecoveryState,
    config: LogicalRowTableRecoveryConfig,
) -> list[dict[str, Any]]:
    ruled = _materialize_ruled_columns(
        rows=rows,
        row_payloads=row_payloads,
        regions=regions,
        table_id=table_id,
        state=state,
    )
    if ruled is not None:
        return ruled
    hinted = _materialize_hinted_columns(
        rows=rows,
        row_payloads=row_payloads,
        regions=regions,
        table_id=table_id,
        state=state,
    )
    if hinted is not None:
        return hinted
    baseline = _materialize_legacy_inferred_columns(
        rows=rows,
        row_payloads=row_payloads,
        regions=regions,
        table_id=table_id,
        state=state,
        config=config,
    )
    if baseline:
        return _augment_unique_exterior_label_column(
            columns=baseline,
            rows=rows,
            row_payloads=row_payloads,
            table_id=table_id,
            state=state,
            config=config,
        )
    plan = _generic_column_scope_plan(
        rows=rows,
        table_id=table_id,
        config=config,
    )
    if plan is None:
        return []
    return _apply_column_scope_plan(
        plan=plan,
        rows=rows,
        row_payloads=row_payloads,
        table_id=table_id,
        state=state,
        config=config,
    )


def _leaf_header_complement_track_indexes(
    *,
    rows: list[_RowBand],
    column_evidence_rows: list[_RowBand],
    tracks: list[_ColumnTrack],
    bound_by_column: dict[str, list[_EntryBand]],
    column_ids: list[str],
    regions: list[_Region],
    config: LogicalRowTableRecoveryConfig,
) -> set[int]:
    leaf_rows = [
        row
        for row in rows
        if row.row_coalescence_kind == "LEAF_HEADER"
        and row.role == "COLUMN_HEADER"
    ]
    if len(leaf_rows) != 1 or not regions:
        return set()
    leaf = leaf_rows[0]
    physical_rows = leaf.column_evidence_rows
    if physical_rows is None or not 3 <= len(leaf.entries) <= 12:
        return set()
    physical_refs = [
        word.word_ref for row in physical_rows for word in row.words
    ]
    canonical_refs = [
        word.word_ref for entry in leaf.entries for word in entry.words
    ]
    if (
        len(physical_refs) != len(set(physical_refs))
        or len(canonical_refs) != len(set(canonical_refs))
        or set(physical_refs) != set(canonical_refs)
        or any(
            not _row_has_exact_entry_word_partition(row)
            for row in physical_rows
        )
    ):
        return set()

    page_width = next(
        (
            region.page.width
            for region in regions
            if leaf in region.rows
        ),
        0.0,
    )
    if page_width <= 0.0:
        return set()
    tolerance = page_width * config.column_tolerance_width_ratio
    leaf_bboxes = [entry.bbox for entry in leaf.entries]
    body_first_entries = []
    all_leftmost_nonvalue_ref_sets: set[frozenset[str]] = set()
    for row in rows:
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        if row.entries and not _looks_value_like(row.entries[0].text):
            all_leftmost_nonvalue_ref_sets.add(
                frozenset(word.word_ref for word in row.entries[0].words)
            )
        macro_entries = list(
            row.column_evidence_entries or tuple(row.entries)
        )
        if (
            len(macro_entries) != len(leaf.entries) + 1
            or not _entry_bands_partition_words(macro_entries, row.words)
            or _looks_value_like(macro_entries[0].text)
            or not row.entries
        ):
            continue
        assignments = []
        valid = True
        for entry in macro_entries[1:]:
            distances = [
                min(
                    abs(entry.bbox[0] - leaf_bbox[0]),
                    abs(entry.bbox[2] - leaf_bbox[2]),
                    abs(
                        _bbox_center_x(entry.bbox)
                        - _bbox_center_x(leaf_bbox)
                    ),
                )
                for leaf_bbox in leaf_bboxes
            ]
            ranked = sorted(range(len(distances)), key=distances.__getitem__)
            if (
                len(ranked) < 2
                or distances[ranked[0]] > tolerance
                or distances[ranked[1]] - distances[ranked[0]]
                <= max(1.0, tolerance * 0.1)
            ):
                valid = False
                break
            assignments.append(ranked[0])
        macro_first_refs = frozenset(
            word.word_ref for word in macro_entries[0].words
        )
        actual_first_refs = frozenset(
            word.word_ref for word in row.entries[0].words
        )
        if (
            not valid
            or assignments != list(range(len(leaf.entries)))
            or not macro_first_refs
            or macro_first_refs != actual_first_refs
        ):
            continue
        body_first_entries.append(row.entries[0])
    if len(body_first_entries) < config.minimum_column_observations:
        return set()

    first_lefts = [entry.bbox[0] for entry in body_first_entries]
    first_track = statistics.median(first_lefts)
    if max(abs(value - first_track) for value in first_lefts) > tolerance:
        return set()
    region_lefts = [region.bbox[0] for region in regions]
    if min(abs(first_track - value) for value in region_lefts) > tolerance:
        return set()
    if (
        first_track >= min(bbox[0] for bbox in leaf_bboxes) - tolerance
        or max(entry.bbox[2] for entry in body_first_entries)
        >= min(bbox[0] for bbox in leaf_bboxes) - tolerance
    ):
        return set()

    physical_header_entry_ids = {
        id(entry)
        for row in column_evidence_rows
        if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
        for entry in row.entries
    }
    candidates = []
    for index, (column_id, track) in enumerate(zip(column_ids, tracks)):
        bound = bound_by_column[column_id]
        if (
            track.edge != "LEFT"
            or len(bound) < config.minimum_column_observations
            or abs(track.coordinate - first_track) > tolerance
            or track.coordinate
            >= min(bbox[0] for bbox in leaf_bboxes) - tolerance
            or any(id(entry) in physical_header_entry_ids for entry in track.entries)
            or any(_looks_value_like(entry.text) for entry in bound)
            or any(
                frozenset(word.word_ref for word in entry.words)
                not in all_leftmost_nonvalue_ref_sets
                for entry in bound
            )
        ):
            continue
        candidates.append(index)
    return {candidates[0]} if len(candidates) == 1 else set()


def _entry_bands_partition_words(
    entries: list[_EntryBand],
    words: list[_Word],
) -> bool:
    entry_refs = [
        word.word_ref for entry in entries for word in entry.words
    ]
    word_refs = [word.word_ref for word in words]
    return bool(
        len(entry_refs) == len(set(entry_refs))
        and len(word_refs) == len(set(word_refs))
        and set(entry_refs) == set(word_refs)
    )


def _materialize_hinted_columns(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    regions: list[_Region],
    table_id: str,
    state: _RecoveryState,
) -> list[dict[str, Any]] | None:
    if any(region.ruled_column_bands for region in regions):
        return None
    hinted_entries = [
        entry
        for row in rows
        if row.role != "GROUP_HEADER"
        for entry in row.entries
        if entry.geometry_column_ordinals is not None
    ]
    if not hinted_entries:
        return None
    if any(
        len(entry.geometry_column_ordinals or []) != 1
        for entry in hinted_entries
    ):
        return None
    hinted_rows = [row for row in rows if len(row.entries) >= 2]
    if any(
        entry.geometry_column_ordinals is None
        for row in hinted_rows
        for entry in row.entries
    ):
        return None
    ordinals = sorted(
        {
            int((entry.geometry_column_ordinals or [])[0])
            for entry in hinted_entries
        }
    )
    if ordinals != list(range(len(ordinals))) or len(ordinals) < 2:
        return None
    column_ids = [
        _identifier("column", [table_id, ordinal, "mirrored_lane_geometry"])
        for ordinal in ordinals
    ]
    entry_payload_by_id = {
        entry["entry_id"]: entry
        for row in row_payloads
        for entry in row["entries"]
    }
    entries_by_ordinal: dict[int, list[_EntryBand]] = {
        ordinal: [] for ordinal in ordinals
    }
    for entry in hinted_entries:
        ordinal = int((entry.geometry_column_ordinals or [])[0])
        entries_by_ordinal[ordinal].append(entry)
        payload = entry_payload_by_id[str(entry.entry_id)]
        _set_entry_column_binding(
            entry,
            payload=payload,
            logical_column_id=column_ids[ordinal],
            covers_logical_column_ids=(),
        )
    result = []
    for ordinal, column_id in enumerate(column_ids):
        entries = entries_by_ordinal[ordinal]
        header_entries = [
            entry
            for row in rows
            if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
            for entry in row.entries
            if entry.logical_column_id == column_id
        ]
        anchor_ids = _unique(
            anchor for entry in entries for anchor in entry.anchor_ids
        )
        issue_ids = []
        if not header_entries:
            issue_ids.append(
                state.add_issue(
                    code="logical_column_header_path_unknown",
                    message=(
                        "Mirrored lane geometry proves the logical column, "
                        "but no source header entry is deterministic."
                    ),
                    anchor_ids=anchor_ids,
                    block_ids=[logical_table_block_id(table_id)],
                )
            )
        geometry_id = state.add_geometry(
            kind="COLUMN_ALIGNMENT",
            key=[table_id, column_id],
            anchor_ids=anchor_ids,
            material={
                "alignment_source": "mirrored_lane_linearization",
                "column_ordinal": ordinal,
                "entry_ids": [entry.entry_id for entry in entries],
                "entry_bboxes": [list(entry.bbox) for entry in entries],
            },
            issue_ids=issue_ids,
        )
        result.append(
            {
                "column_id": column_id,
                "ordinal": ordinal,
                "header_path": [
                    str(entry.entry_id) for entry in header_entries
                ],
                "source_anchor_ids": anchor_ids,
                "geometry_evidence_ids": [geometry_id],
                "issue_ids": issue_ids,
            }
        )
    return result


def _materialize_ruled_columns(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    regions: list[_Region],
    table_id: str,
    state: _RecoveryState,
) -> list[dict[str, Any]] | None:
    bands_by_region = [region.ruled_column_bands for region in regions]
    if not bands_by_region or any(not bands for bands in bands_by_region):
        return None
    first_bands = bands_by_region[0] or []
    if any(len(bands or []) != len(first_bands) for bands in bands_by_region):
        return None
    column_ids = [
        _identifier("column", [table_id, ordinal, "ruled_geometry"])
        for ordinal in range(len(first_bands))
    ]
    entry_payload_by_id = {
        entry["entry_id"]: entry
        for row in row_payloads
        for entry in row["entries"]
    }
    entries_by_column: dict[int, list[_EntryBand]] = {
        ordinal: [] for ordinal in range(len(column_ids))
    }
    binding_plans: list[tuple[_RowBand, _EntryBand, list[int]]] = []
    for row in rows:
        region = next((item for item in regions if row in item.rows), None)
        if region is None or not region.ruled_column_bands:
            return None
        local_bands = list(region.ruled_column_bands)
        for entry in row.entries:
            source_ordinals = entry.geometry_column_ordinals
            if source_ordinals is None and row.role in {
                "DATA",
                "SUBTOTAL",
                "TOTAL",
            }:
                derived = _word_group_columns(
                    entry.words,
                    column_bands=local_bands,
                )
                source_ordinals = derived if len(derived) == 1 else []
            source_ordinals = source_ordinals or []
            if any(
                ordinal < 0 or ordinal >= len(column_ids)
                for ordinal in source_ordinals
            ):
                return None
            ordinals = sorted(set(source_ordinals))
            if not ordinals:
                continue
            if row.role == "GROUP_HEADER" and len(ordinals) == 1:
                continue
            if entry.geometry_evidence_id is None:
                return None
            binding_plans.append((row, entry, ordinals))
            for ordinal in ordinals:
                entries_by_column[ordinal].append(entry)
    if any(
        not _unique(
            anchor
            for entry in entries_by_column[ordinal]
            for anchor in entry.anchor_ids
        )
        for ordinal in range(len(column_ids))
    ):
        return None

    for row, entry, ordinals in binding_plans:
        payload = entry_payload_by_id[str(entry.entry_id)]
        if len(ordinals) == 1:
            _set_entry_column_binding(
                entry,
                payload=payload,
                logical_column_id=column_ids[ordinals[0]],
                covers_logical_column_ids=(),
            )
            continue
        covers = [column_ids[ordinal] for ordinal in ordinals]
        _set_entry_column_binding(
            entry,
            payload=payload,
            logical_column_id=(
                covers[0] if row.role in {"SUBTOTAL", "TOTAL"} else None
            ),
            covers_logical_column_ids=covers,
        )

    result = []
    for ordinal, (column_id, band) in enumerate(zip(column_ids, first_bands)):
        entries = entries_by_column[ordinal]
        anchor_ids = _unique(
            anchor for entry in entries for anchor in entry.anchor_ids
        )
        if not anchor_ids:
            return None
        header_entries = [
            entry
            for row in rows
            if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
            for entry in row.entries
            if entry.logical_column_id == column_id
            or column_id in entry.covers_logical_column_ids
        ]
        issue_ids: list[str] = []
        if not header_entries:
            issue_ids.append(
                state.add_issue(
                    code="logical_column_header_path_unknown",
                    message=(
                        "Repeated ruled alignment proves the logical column, "
                        "but no source header entry is deterministic."
                    ),
                    anchor_ids=anchor_ids,
                    block_ids=[logical_table_block_id(table_id)],
                )
            )
        geometry_id = state.add_geometry(
            kind="COLUMN_ALIGNMENT",
            key=[table_id, column_id],
            anchor_ids=anchor_ids,
            material={
                "alignment_source": "ruled_candidate_secondary_geometry",
                "column_ordinal": ordinal,
                "first_part_band": list(band),
                "part_bands": [list((bands or [])[ordinal]) for bands in bands_by_region],
                "entry_ids": [entry.entry_id for entry in entries],
            },
            issue_ids=issue_ids,
        )
        result.append(
            {
                "column_id": column_id,
                "ordinal": ordinal,
                "header_path": [str(entry.entry_id) for entry in header_entries],
                "source_anchor_ids": anchor_ids,
                "geometry_evidence_ids": [geometry_id],
                "issue_ids": issue_ids,
            }
        )
    return result


def _row_bands(
    words: list[_Word],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> list[_RowBand]:
    if not words:
        return []
    heights = [_bbox_height(word.bbox) for word in words]
    typical_height = statistics.median(heights) if heights else 1.0
    tolerance = max(1.5, typical_height * config.row_y_tolerance_ratio)
    groups: list[list[_Word]] = []
    for word in sorted(words, key=lambda item: (item.bbox[1], item.bbox[0], item.order)):
        center_y = _bbox_center_y(word.bbox)
        target = next(
            (
                group
                for group in reversed(groups)
                if abs(
                    center_y
                    - statistics.median(_bbox_center_y(item.bbox) for item in group)
                )
                <= tolerance
            ),
            None,
        )
        if target is None:
            groups.append([word])
        else:
            target.append(word)
    result = []
    for group in groups:
        ordered = sorted(group, key=lambda item: (item.bbox[0], item.order))
        entry_groups = _entry_word_groups(
            ordered,
            typical_height=typical_height,
            config=config,
        )
        entries = [
            _EntryBand(
                words=entry_words,
                bbox=_merge_bboxes([word.bbox for word in entry_words]),
                text=_render_source_word_sequence(entry_words),
                anchor_ids=[],
            )
            for entry_words in entry_groups
            if entry_words
        ]
        if entries:
            result.append(
                _RowBand(
                    page_ref=ordered[0].page_ref,
                    bbox=_merge_bboxes([word.bbox for word in ordered]),
                    words=ordered,
                    entries=entries,
                )
            )
    return sorted(result, key=lambda row: (row.bbox[1], row.bbox[0]))


def _entry_word_groups(
    words: list[_Word],
    *,
    typical_height: float,
    config: LogicalRowTableRecoveryConfig,
) -> list[list[_Word]]:
    if not words:
        return []
    threshold = max(6.0, typical_height * config.entry_gap_height_ratio)
    groups = [[words[0]]]
    for word in words[1:]:
        gap = word.bbox[0] - groups[-1][-1].bbox[2]
        if gap > threshold:
            groups.append([word])
        else:
            groups[-1].append(word)
    return groups


def _render_source_word_sequence(words: Sequence[_Word]) -> str:
    """Render source fragments without inventing spaces at touching seams."""

    if not words:
        return ""
    rendered = [words[0].text]
    for left, right in zip(words, words[1:]):
        height = max(
            1.0,
            min(_bbox_height(left.bbox), _bbox_height(right.bbox)),
        )
        same_baseline = abs(
            _bbox_center_y(left.bbox) - _bbox_center_y(right.bbox)
        ) <= max(0.5, height * 0.12)
        gap = right.bbox[0] - left.bbox[2]
        touching = gap <= max(0.2, height * 0.025)
        rendered.append("" if same_baseline and touching else " ")
        rendered.append(right.text)
    return "".join(rendered).strip()


def _classify_rows(rows: list[_RowBand]) -> None:
    if not rows:
        return
    indent_ranks = _indent_ranks(rows)
    first_data_index = next(
        (
            index
            for index, row in enumerate(rows)
            if len(row.entries) >= 2
            and any(_looks_value_like(entry.text) for entry in row.entries)
        ),
        len(rows),
    )
    header_indexes = {
        index
        for index, row in enumerate(rows[:first_data_index])
        if len(row.entries) >= 2
        and not any(_looks_value_like(entry.text) for entry in row.entries)
    }
    immutable_future_eligible = []
    for row in rows:
        normalized = _normalize_text(" ".join(entry.text for entry in row.entries))
        immutable_future_eligible.append(
            not row.external_note
            and not _starts_with(normalized, _NOTE_PREFIXES)
            and not _starts_with(normalized, _SUBTOTAL_PREFIXES)
            and not _starts_with(normalized, _TOTAL_PREFIXES)
        )
    for index, row in enumerate(rows):
        normalized = _normalize_text(" ".join(entry.text for entry in row.entries))
        if row.external_title:
            row.role = "TABLE_TITLE"
        elif row.external_note:
            row.role = "NOTE"
        elif _starts_with(normalized, _SUBTOTAL_PREFIXES):
            row.role = "SUBTOTAL"
        elif _starts_with(normalized, _TOTAL_PREFIXES):
            row.role = "TOTAL"
        elif _starts_with(normalized, _NOTE_PREFIXES) or normalized.startswith("*"):
            row.role = "NOTE"
        elif index in header_indexes:
            row.role = "COLUMN_HEADER"
        elif (
            index == 0
            and len(row.entries) == 1
            and any(len(candidate.entries) >= 2 for candidate in rows[1:3])
        ):
            row.role = "TABLE_TITLE"
        elif len(row.entries) >= 2:
            row.role = "DATA"
        elif len(row.entries) == 1:
            next_rank = next(
                (
                    indent_ranks[candidate_index]
                    for candidate_index in range(index + 1, len(rows))
                    if immutable_future_eligible[candidate_index]
                ),
                None,
            )
            if next_rank is not None and next_rank > indent_ranks[index]:
                row.role = "GROUP_HEADER"
            elif 0 < index < len(rows) - 1 and (
                rows[index - 1].role in {"DATA", "GROUP_HEADER"}
                or len(rows[index - 1].entries) >= 2
            ) and len(rows[index + 1].entries) >= 2:
                row.role = "DATA"
            else:
                row.role = "UNKNOWN"


_PROVEN_HEADER_COALESCENCE_KINDS = frozenset({"LEAF_HEADER", "NARROW_HEADER"})


def _refine_leading_ruled_header_roles(
    region: _Region,
    *,
    config: LogicalRowTableRecoveryConfig | None = None,
) -> None:
    """Apply one immutable leading-header plan, ruled or inferred."""

    plan = _plan_leading_header_roles(
        region,
        config=config or LogicalRowTableRecoveryConfig(),
    )
    if plan is not None:
        _apply_leading_header_role_plan(region, plan=plan)


def _plan_leading_header_roles(
    region: _Region,
    *,
    config: LogicalRowTableRecoveryConfig,
) -> _LeadingHeaderRolePlan | None:
    if len(region.rows) < 3:
        return None
    columns_total = len(region.ruled_column_bands or [])
    candidates: list[tuple[int, tuple[int, ...]]] = []
    for index, row in enumerate(region.rows):
        marker_values = _strict_sequential_marker_values(row)
        if marker_values is None or not _marker_band_is_leading(
            region.rows,
            marker_index=index,
        ):
            continue
        if columns_total:
            ruled_marker_valid = bool(
                len(marker_values) == columns_total
                and _strict_sequential_ruled_marker_band(
                    row,
                    columns_total=columns_total,
                )
            )
            if (
                not ruled_marker_valid
                and any(
                    entry.geometry_column_ordinals is not None
                    for entry in row.entries
                )
            ):
                continue
            if (
                not ruled_marker_valid
                or not _has_immediate_ruled_body_support(
                    region.rows,
                    marker_index=index,
                    columns_total=columns_total,
                )
            ):
                header_indexes = _inferred_leading_header_indexes(
                    region.rows,
                    marker_index=index,
                    config=config,
                )
            else:
                header_indexes = _leading_ruled_header_indexes(
                    region.rows,
                    marker_index=index,
                    columns_total=columns_total,
                )
                if not header_indexes:
                    header_indexes = _inferred_leading_header_indexes(
                        region.rows,
                        marker_index=index,
                        config=config,
                    )
        else:
            header_indexes = _inferred_leading_header_indexes(
                region.rows,
                marker_index=index,
                config=config,
            )
        if header_indexes:
            candidates.append((index, header_indexes))
    if len(candidates) == 1:
        marker_index, header_indexes = candidates[0]
        return _LeadingHeaderRolePlan(
            source_fingerprint_sha256=_leading_header_source_fingerprint(region),
            marker_row_index=marker_index,
            promoted_header_row_indexes=header_indexes,
        )
    if candidates:
        return None
    partial_header_indexes = _leading_right_suffix_header_indexes(region)
    if not partial_header_indexes:
        return None
    return _LeadingHeaderRolePlan(
        source_fingerprint_sha256=_leading_header_source_fingerprint(region),
        marker_row_index=None,
        promoted_header_row_indexes=partial_header_indexes,
    )


def _apply_leading_header_role_plan(
    region: _Region,
    *,
    plan: _LeadingHeaderRolePlan,
) -> None:
    marker_indexes = (
        (plan.marker_row_index,)
        if plan.marker_row_index is not None
        else ()
    )
    indexes = (*plan.promoted_header_row_indexes, *marker_indexes)
    if (
        plan.source_fingerprint_sha256
        != _leading_header_source_fingerprint(region)
        or len(indexes) != len(set(indexes))
        or any(index < 0 or index >= len(region.rows) for index in indexes)
    ):
        raise LogicalRowTableRecoveryError("leading_header_role_plan_invalid")
    for index in plan.promoted_header_row_indexes:
        region.rows[index].role = "COLUMN_HEADER"
    if plan.marker_row_index is not None:
        marker = region.rows[plan.marker_row_index]
        marker.role = "COLUMN_HEADER"
        marker.sequential_marker_header = True


def _leading_right_suffix_header_indexes(region: _Region) -> tuple[int, ...]:
    """Prove a row-zero header spanning every ruled column except the label lane."""

    columns_total = len(region.ruled_column_bands or [])
    if columns_total < 2 or len(region.rows) < 3:
        return ()
    candidate = region.rows[0]
    if (
        candidate.external_title
        or candidate.external_note
        or candidate.role not in {"TABLE_TITLE", "UNKNOWN"}
        or len(candidate.entries) != 1
        or any(_looks_value_like(entry.text) for entry in candidate.entries)
        or not _row_has_exact_entry_word_partition(candidate)
    ):
        return ()
    ordinals = tuple(
        sorted(set(candidate.entries[0].geometry_column_ordinals or []))
    )
    if ordinals != tuple(range(1, columns_total)):
        return ()

    full_body_support = 0
    for row in region.rows[1:]:
        if row.external_title or row.external_note:
            continue
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        partition = _ruled_row_partition(
            row,
            columns_total=columns_total,
            require_full=True,
        )
        if (
            partition is not None
            and len(partition) >= 2
            and all(len(group) == 1 for group in partition)
            and _row_has_exact_entry_word_partition(row)
        ):
            full_body_support += 1
            if full_body_support >= 2:
                return (0,)
    return ()


def _leading_header_source_fingerprint(region: _Region) -> str:
    return _sha256_json(
        [
            region.source_ref,
            [
                {
                    "role": row.role,
                    "external_title": row.external_title,
                    "external_note": row.external_note,
                    "word_refs": [word.word_ref for word in row.words],
                    "entries": [
                        {
                            "word_refs": [word.word_ref for word in entry.words],
                            "bbox": list(entry.bbox),
                            "text": entry.text,
                            "geometry_column_ordinals": entry.geometry_column_ordinals,
                        }
                        for entry in row.entries
                    ],
                }
                for row in region.rows
            ],
            region.ruled_column_bands,
        ]
    )


def _leading_ruled_header_indexes(
    rows: list[_RowBand],
    *,
    marker_index: int,
    columns_total: int,
) -> tuple[int, ...]:
    indexes: list[int] = []
    for index in range(marker_index - 1, -1, -1):
        row = rows[index]
        if row.external_title or row.external_note:
            break
        if row.role == "COLUMN_HEADER":
            partition = _ruled_row_partition(
                row,
                columns_total=columns_total,
                require_full=False,
            )
            covered = (
                {ordinal for group in partition for ordinal in group}
                if partition is not None
                else set()
            )
            if (
                partition is not None
                and len(row.entries) >= 2
                and len(covered) >= columns_total - 1
            ):
                indexes.append(index)
                continue
        if _strict_leading_ruled_header_spanner(
            row,
            row_index=index,
            columns_total=columns_total,
        ) or _strict_partial_ruled_header_spanner(
            row,
            row_index=index,
            columns_total=columns_total,
        ):
            indexes.append(index)
            continue
        break
    return tuple(indexes) if indexes and indexes[0] == marker_index - 1 else ()


def _inferred_leading_header_indexes(
    rows: list[_RowBand],
    *,
    marker_index: int,
    config: LogicalRowTableRecoveryConfig,
) -> tuple[int, ...]:
    if marker_index <= 0 or marker_index + 1 >= len(rows):
        return ()
    marker = rows[marker_index]
    header = rows[marker_index - 1]
    body = rows[marker_index + 1]
    columns_total = len(marker.entries)
    if (
        columns_total < 3
        or header.external_title
        or header.external_note
        or header.role != "COLUMN_HEADER"
        or len(header.entries) != columns_total
        or any(_looks_value_like(entry.text) for entry in header.entries)
        or body.external_title
        or body.external_note
        or body.role not in {"DATA", "SUBTOTAL", "TOTAL"}
        or len(body.entries) != columns_total
        or not any(_looks_value_like(entry.text) for entry in body.entries)
        or not all(
            _row_has_exact_entry_word_partition(row)
            for row in (header, marker, body)
        )
        or not _inferred_marker_lanes_match(
            marker=marker,
            support_rows=(header, body),
            config=config,
        )
    ):
        return ()
    return (marker_index - 1,)


def _inferred_marker_lanes_match(
    *,
    marker: _RowBand,
    support_rows: tuple[_RowBand, _RowBand],
    config: LogicalRowTableRecoveryConfig,
) -> bool:
    columns_total = len(marker.entries)
    if columns_total < 3 or any(
        len(row.entries) != columns_total for row in support_rows
    ):
        return False
    centers_by_row = [
        [_bbox_center_x(entry.bbox) for entry in row.entries]
        for row in support_rows
    ]
    if any(
        any(right <= left for left, right in zip(centers, centers[1:]))
        for centers in centers_by_row
    ):
        return False
    tracks = [
        statistics.median(centers[index] for centers in centers_by_row)
        for index in range(columns_total)
    ]
    gaps = [right - left for left, right in zip(tracks, tracks[1:])]
    if not gaps or min(gaps) <= 0.0:
        return False
    tolerance = max(
        3.0,
        min(gaps) * 0.45,
        _bbox_width(_merge_bboxes([row.bbox for row in support_rows]))
        * config.column_tolerance_width_ratio,
    )
    if any(
        abs(center - tracks[index]) > tolerance
        for centers in centers_by_row
        for index, center in enumerate(centers)
    ):
        return False
    marker_centers = [_bbox_center_x(entry.bbox) for entry in marker.entries]
    boundaries = [
        (left + right) / 2.0 for left, right in zip(tracks, tracks[1:])
    ]
    return bool(
        all(
            (index == 0 or marker_centers[index] > boundaries[index - 1])
            and (
                index == columns_total - 1
                or marker_centers[index] < boundaries[index]
            )
            and abs(marker_centers[index] - tracks[index]) <= max(
                tolerance,
                min(gaps) * 0.75,
            )
            for index in range(columns_total)
        )
        and all(
            right > left for left, right in zip(marker_centers, marker_centers[1:])
        )
    )


def _strict_sequential_marker_values(row: _RowBand) -> tuple[int, ...] | None:
    if (
        row.external_title
        or row.external_note
        or len(row.entries) < 3
        or not _row_has_exact_entry_word_partition(row)
    ):
        return None
    values: list[int] = []
    for entry in row.entries:
        if len(entry.words) != 1:
            return None
        normalized = unicodedata.normalize("NFKC", entry.text).strip()
        if not re.fullmatch(r"[1-9]\d*", normalized):
            return None
        values.append(int(normalized))
    expected = tuple(range(1, len(row.entries) + 1))
    return tuple(values) if tuple(values) == expected else None


def _strict_sequential_ruled_marker_band(
    row: _RowBand,
    *,
    columns_total: int,
) -> bool:
    if (
        row.external_title
        or row.external_note
        or len(row.entries) != columns_total
        or not _row_has_exact_entry_word_partition(row)
    ):
        return False
    groups = _ruled_row_partition(
        row,
        columns_total=columns_total,
        require_full=True,
    )
    if groups is None or any(len(group) != 1 for group in groups):
        return False
    values = _strict_sequential_marker_values(row)
    return values == tuple(range(1, columns_total + 1))


def _marker_band_is_leading(
    rows: list[_RowBand],
    *,
    marker_index: int,
) -> bool:
    if marker_index <= 0:
        return False
    return all(
        row.external_title
        or row.external_note
        or row.role in {"TABLE_TITLE", "COLUMN_HEADER", "NOTE", "UNKNOWN"}
        or row.row_coalescence_kind in _PROVEN_HEADER_COALESCENCE_KINDS
        for row in rows[:marker_index]
    )


def _has_immediate_ruled_body_support(
    rows: list[_RowBand],
    *,
    marker_index: int,
    columns_total: int,
) -> bool:
    if marker_index + 1 >= len(rows):
        return False
    body = rows[marker_index + 1]
    if (
        len(body.entries) == 1
        and _semantic_singleton_label(body)
        and marker_index + 2 < len(rows)
    ):
        body = rows[marker_index + 2]
    groups = _ruled_row_partition(
        body,
        columns_total=columns_total,
        require_full=False,
    )
    return bool(
        not body.external_title
        and not body.external_note
        and body.role in {"DATA", "SUBTOTAL", "TOTAL"}
        and groups is not None
        and len(groups) >= 2
        and all(len(group) == 1 for group in groups)
        and any(_looks_value_like(entry.text) for entry in body.entries)
    )


def _strict_leading_ruled_header_spanner(
    row: _RowBand,
    *,
    row_index: int,
    columns_total: int,
) -> bool:
    if (
        row.external_title
        or row.external_note
        or row.role not in {"TABLE_TITLE", "UNKNOWN"}
        or row.row_coalescence_kind not in _PROVEN_HEADER_COALESCENCE_KINDS
        or any(_looks_value_like(entry.text) for entry in row.entries)
        or not _row_has_exact_entry_word_partition(row)
    ):
        return False
    groups = _ruled_row_partition(
        row,
        columns_total=columns_total,
        require_full=False,
    )
    if groups is None or not any(len(group) >= 2 for group in groups):
        return False
    covered = {ordinal for group in groups for ordinal in group}
    # A full-width singleton at the first internal row remains title-like even
    # if a coalescence hint was copied accidentally.  External titles are
    # already rejected above; partial or multi-entry spanners remain eligible.
    return not (
        row_index == 0
        and len(row.entries) == 1
        and covered == set(range(columns_total))
    )


def _strict_partial_ruled_header_spanner(
    row: _RowBand,
    *,
    row_index: int,
    columns_total: int,
) -> bool:
    if (
        row_index <= 0
        or row.external_title
        or row.external_note
        or row.role not in {"TABLE_TITLE", "UNKNOWN"}
        or len(row.entries) != 1
        or any(_looks_value_like(entry.text) for entry in row.entries)
        or not _row_has_exact_entry_word_partition(row)
    ):
        return False
    ordinals = tuple(sorted(set(row.entries[0].geometry_column_ordinals or [])))
    return bool(
        2 <= len(ordinals) < columns_total
        and ordinals == tuple(range(ordinals[0], ordinals[-1] + 1))
        and all(0 <= ordinal < columns_total for ordinal in ordinals)
    )


def _ruled_row_partition(
    row: _RowBand,
    *,
    columns_total: int,
    require_full: bool,
) -> tuple[tuple[int, ...], ...] | None:
    groups: list[tuple[int, ...]] = []
    occupied: set[int] = set()
    for entry in row.entries:
        raw = entry.geometry_column_ordinals
        if raw is None:
            return None
        ordinals = tuple(sorted(set(raw)))
        if (
            not ordinals
            or ordinals != tuple(range(ordinals[0], ordinals[-1] + 1))
            or any(ordinal < 0 or ordinal >= columns_total for ordinal in ordinals)
            or occupied.intersection(ordinals)
        ):
            return None
        if groups and groups[-1][-1] >= ordinals[0]:
            return None
        groups.append(ordinals)
        occupied.update(ordinals)
    if require_full and occupied != set(range(columns_total)):
        return None
    return tuple(groups)


def _leading_context_role_overrides(
    rows: list[_RowBand],
    *,
    roles: list[str],
    typical_height: float,
    tolerance: float,
) -> list[str]:
    """Recognize one geometrically detached multi-line table preamble."""

    if len(rows) != len(roles) or len(rows) < 4:
        return list(roles)
    first_dense_index = next(
        (
            index
            for index, row in enumerate(rows)
            if _semantic_dense_data_row(row, roles[index])
        ),
        None,
    )
    if first_dense_index is None or first_dense_index < 2:
        return list(roles)
    body_x_values = [
        row.entries[0].bbox[0]
        for index, row in enumerate(rows[first_dense_index:], first_dense_index)
        if _semantic_dense_data_row(row, roles[index])
    ][:6]
    if len(body_x_values) < 2:
        return list(roles)
    body_x = statistics.median(body_x_values)
    detached_delta = max(tolerance * 3.0, typical_height * 5.0)
    detached_indexes = []
    for index in range(first_dense_index):
        row = rows[index]
        if (
            row.proven_leading_suffix_header
            or len(row.entries) != 1
            or not _row_has_exact_entry_word_partition(row)
            or row.entries[0].bbox[0] <= body_x + detached_delta
        ):
            break
        detached_indexes.append(index)
    if len(detached_indexes) < 2:
        return list(roles)
    allowed = {"UNKNOWN", "GROUP_HEADER", "TABLE_TITLE", "NOTE"}
    if any(roles[index] not in allowed for index in detached_indexes):
        return list(roles)

    result = list(roles)
    for index in detached_indexes:
        text = rows[index].entries[0].text.strip()
        parenthetical_note = bool(
            len(text) >= 3
            and (text[0], text[-1]) in {("(", ")"), ("[", "]"), ("{", "}")}
            and bool(re.search(r"[^\W\d_]", text, flags=re.UNICODE))
            and not _looks_value_like(text)
        )
        result[index] = (
            "NOTE"
            if rows[index].external_note or parenthetical_note
            else "TABLE_TITLE"
        )
    return result


def _plan_ordered_row_semantics(
    rows: list[_RowBand],
    *,
    config: LogicalRowTableRecoveryConfig,
) -> _OrderedRowSemanticPlan:
    """Plan roles and hierarchy for the whole ordered table before mutation."""

    fingerprint = _ordered_row_semantic_source_fingerprint(rows)
    if not rows:
        return _OrderedRowSemanticPlan(fingerprint, ())
    typical_height = statistics.median(
        _bbox_height(row.bbox) for row in rows if row.entries
    )
    tolerance = max(3.0, typical_height * config.indentation_height_ratio)
    preliminary_roles = _leading_context_role_overrides(
        rows,
        roles=[row.role for row in rows],
        typical_height=typical_height,
        tolerance=tolerance,
    )
    singleton_candidates = {
        index
        for index, row in enumerate(rows)
        if not row.proven_leading_suffix_header
        and preliminary_roles[index]
        not in {"COLUMN_HEADER", "CONTINUATION_HEADER", "NOTE"}
        and _semantic_singleton_label(row)
    }
    accepted_groups: set[int] = set()
    scope_hints: dict[int, int] = {}
    support_counts: dict[int, int] = {}
    accepted_group_x: dict[int, float] = {}

    # Backwards discovery makes a later proven peer/nested group available as
    # the unique boundary for an earlier opener without mutating either row.
    for index in reversed(range(len(rows))):
        if index not in singleton_candidates:
            continue
        support = _semantic_group_forward_support(
            rows,
            roles=preliminary_roles,
            index=index,
            accepted_groups=accepted_groups,
            scope_hints=scope_hints,
            tolerance=tolerance,
        )
        if support is None:
            continue
        (
            dense_count,
            scope_end,
            first_dense_x,
            boundary_group,
            closed_by_summary,
            ended_at_table,
        ) = support
        previous_role = preliminary_roles[index - 1] if index else None
        row_x = rows[index].entries[0].bbox[0]
        boundary_context = bool(
            index == 0
            or previous_role
            in {
                "TABLE_TITLE",
                "COLUMN_HEADER",
                "CONTINUATION_HEADER",
                "NOTE",
                "SUBTOTAL",
                "TOTAL",
            }
            or preliminary_roles[index] == "GROUP_HEADER"
            or closed_by_summary
            or first_dense_x is not None
            and row_x < first_dense_x - tolerance
            or ended_at_table
            and dense_count >= 3
            and first_dense_x is not None
            and row_x <= first_dense_x + tolerance
        )
        if preliminary_roles[index] == "TABLE_TITLE" and index == 0:
            # A true title may also precede dense rows.  Only an independently
            # visible outer indentation step can reinterpret it as a group.
            boundary_context = bool(
                closed_by_summary
                and first_dense_x is not None
                and row_x <= first_dense_x + tolerance
            )
        if not boundary_context:
            continue
        if dense_count == 0 and boundary_group is not None:
            boundary_x = accepted_group_x.get(boundary_group)
            if boundary_x is None or boundary_x < row_x - tolerance:
                continue
        accepted_groups.add(index)
        scope_hints[index] = scope_end
        support_counts[index] = dense_count
        accepted_group_x[index] = row_x

    final_roles = list(preliminary_roles)
    ambiguous_child_indexes: set[int] = set()
    first_dense_index = next(
        (
            index
            for index, row in enumerate(rows)
            if _semantic_dense_data_row(row, preliminary_roles[index])
        ),
        len(rows),
    )
    for index in accepted_groups:
        final_roles[index] = "GROUP_HEADER"
    for index, role in enumerate(preliminary_roles):
        if role != "GROUP_HEADER" or index in accepted_groups:
            continue
        child_index = _single_ambiguous_eof_child(
            rows,
            roles=preliminary_roles,
            index=index,
        )
        if child_index is not None and index >= first_dense_index:
            final_roles[index] = "UNKNOWN"
            ambiguous_child_indexes.add(child_index)

    decisions: list[dict[str, Any]] = [
        {
            "ordinal": index,
            "role": role,
            "nesting_level": 0,
            "parent_ordinal": None,
            "group_scope_end_ordinal": (
                scope_hints.get(index) if role == "GROUP_HEADER" else None
            ),
            "issue_codes": (),
        }
        for index, role in enumerate(final_roles)
    ]
    active: list[dict[str, Any]] = []
    nested_seen: set[int] = set()
    completed_root_groups = 0

    def pop_group() -> dict[str, Any]:
        nonlocal completed_root_groups
        popped = active.pop()
        if int(popped["level"]) == 0:
            completed_root_groups += 1
        return popped

    for index, row in enumerate(rows):
        decision = decisions[index]
        role = str(decision["role"])

        terminal_marker_value_total = bool(
            active
            and _semantic_terminal_marker_value_total(
                rows,
                roles=final_roles,
                index=index,
                scope_opener_ordinal=int(active[-1]["ordinal"]),
            )
        )
        if (
            role == "DATA"
            and len(active) == 1
            and terminal_marker_value_total
        ):
            role = "TOTAL"
            decision["role"] = role

        if role == "GROUP_HEADER":
            x0 = row.entries[0].bbox[0]
            while active and x0 < float(active[-1]["x0"]) - tolerance:
                pop_group()
            if active and abs(x0 - float(active[-1]["x0"])) <= tolerance and (
                len(active) > 1 or not bool(active[-1]["has_descendant"])
            ):
                # Equal-lane nesting needs an observed descendant.  Otherwise
                # two consecutive openers are peers and the first cannot be
                # promoted into a parent merely because it appeared first.
                pop_group()
            parent = active[-1] if active else None
            level = int(parent["level"]) + 1 if parent is not None else 0
            if parent is not None:
                nested_seen.add(int(parent["ordinal"]))
                parent["has_descendant"] = True
            decision["nesting_level"] = level
            decision["parent_ordinal"] = (
                int(parent["ordinal"]) if parent is not None else None
            )
            active.append(
                {
                    "ordinal": index,
                    "level": level,
                    "x0": x0,
                    "scope_end": max(index, int(scope_hints.get(index, index))),
                    "has_descendant": False,
                }
            )
            continue

        if role in {"SUBTOTAL", "TOTAL"}:
            x0 = row.entries[0].bbox[0] if row.entries else row.bbox[0]
            terminal_marker_value_shape = bool(
                index == len(rows) - 1
                and _semantic_marker_value_suffix(row)
            )
            bare_terminal_scope_closer = bool(
                role == "TOTAL"
                and terminal_marker_value_total
                and len(row.entries) == 2
            )
            strong_total = role == "TOTAL" and (
                _semantic_strong_total_row(row)
                or preliminary_roles[index] == "TOTAL"
                and terminal_marker_value_shape
            )
            has_later_body = any(
                candidate_role in {"DATA", "GROUP_HEADER", "SUBTOTAL", "TOTAL"}
                for candidate_role in final_roles[index + 1 :]
            )
            if role == "TOTAL":
                aligned_depth = len(active)
                while (
                    aligned_depth > 1
                    and x0
                    <= float(active[aligned_depth - 1]["x0"]) + tolerance
                ):
                    aligned_depth -= 1
                root_ordinal = (
                    int(active[0]["ordinal"]) if active else None
                )
                if strong_total:
                    parallel_subtotals = sum(
                        str(decisions[candidate_index]["role"])
                        == "SUBTOTAL"
                        and len(candidate.entries) == len(row.entries)
                        and _semantic_marker_value_suffix(candidate)
                        and abs(
                            candidate.entries[0].bbox[0]
                            - row.entries[0].bbox[0]
                        )
                        <= tolerance
                        for candidate_index, candidate in enumerate(
                            rows[:index]
                        )
                    )
                    role = (
                        "SUBTOTAL"
                        if active
                        and len(row.entries) > 2
                        and terminal_marker_value_shape
                        and parallel_subtotals >= 2
                        else "TOTAL"
                    )
                elif active:
                    has_future_group = any(
                        candidate_role == "GROUP_HEADER"
                        for candidate_role in final_roles[index + 1 :]
                    )
                    role = (
                        "TOTAL"
                        if (
                            aligned_depth == 1
                            and root_ordinal in nested_seen
                        )
                        or len(active) == 1
                        and (
                            root_ordinal in nested_seen
                            or (
                                completed_root_groups == 0
                                and not has_future_group
                            )
                        )
                        else "SUBTOTAL"
                    )
                elif has_later_body:
                    role = "SUBTOTAL"
            elif (
                not active
                and completed_root_groups > 0
                and not has_later_body
            ):
                role = "TOTAL"
            decision["role"] = role

            if bare_terminal_scope_closer:
                while active:
                    pop_group()
                continue

            if role == "SUBTOTAL":
                popped_for_alignment = False
                while (
                    len(active) > 1
                    and x0 <= float(active[-1]["x0"]) + tolerance
                ):
                    pop_group()
                    popped_for_alignment = True
                parent = active[-1] if active else None
                if parent is not None:
                    parent["has_descendant"] = True
                    decision["nesting_level"] = int(parent["level"]) + 1
                    decision["parent_ordinal"] = int(parent["ordinal"])
                    if not popped_for_alignment:
                        pop_group()
                continue

            while (
                len(active) > 1
                and x0 <= float(active[-1]["x0"]) + tolerance
            ):
                pop_group()
            parent = active[-1] if active else None
            if (
                parent is not None
                and (
                    not strong_total
                    or x0 > float(parent["x0"]) + tolerance
                )
            ):
                parent["has_descendant"] = True
                decision["nesting_level"] = int(parent["level"]) + 1
                decision["parent_ordinal"] = int(parent["ordinal"])
            while active:
                pop_group()
            continue

        if role == "DATA":
            if index in ambiguous_child_indexes:
                active.clear()
                decision["issue_codes"] = ("logical_row_parent_unresolved",)
            elif active:
                parent = active[-1]
                parent["has_descendant"] = True
                decision["nesting_level"] = int(parent["level"]) + 1
                decision["parent_ordinal"] = int(parent["ordinal"])
            continue

        if role in {"TABLE_TITLE", "COLUMN_HEADER", "NOTE", "UNKNOWN"}:
            while active:
                pop_group()
        # CONTINUATION_HEADER deliberately preserves an open cross-page scope.

    # Scope ends are derived from the accepted parent graph, not guessed from
    # the number of physical rows.  This makes validation independent of the
    # discovery hint and keeps all scopes laminar.
    for decision in decisions:
        if decision["role"] != "GROUP_HEADER":
            continue
        group_ordinal = int(decision["ordinal"])
        descendants = [
            int(candidate["ordinal"])
            for candidate in decisions
            if _decision_descends_from(
                candidate,
                ancestor_ordinal=group_ordinal,
                decisions=decisions,
            )
        ]
        decision["group_scope_end_ordinal"] = max(
            [group_ordinal, *descendants]
        )

    frozen = tuple(
        _OrderedRowSemanticDecision(
            ordinal=int(item["ordinal"]),
            role=str(item["role"]),
            nesting_level=int(item["nesting_level"]),
            parent_ordinal=(
                int(item["parent_ordinal"])
                if item["parent_ordinal"] is not None
                else None
            ),
            group_scope_end_ordinal=(
                int(item["group_scope_end_ordinal"])
                if item["group_scope_end_ordinal"] is not None
                else None
            ),
            issue_codes=tuple(item["issue_codes"]),
        )
        for item in decisions
    )
    _validate_ordered_row_semantic_decisions(frozen)
    return _OrderedRowSemanticPlan(fingerprint, frozen)


def _semantic_group_forward_support(
    rows: list[_RowBand],
    *,
    roles: list[str],
    index: int,
    accepted_groups: set[int],
    scope_hints: Mapping[int, int],
    tolerance: float,
) -> tuple[int, int, float | None, int | None, bool, bool] | None:
    dense_count = 0
    first_dense_x: float | None = None
    scope_end = index
    boundary_group: int | None = None
    for candidate_index in range(index + 1, len(rows)):
        role = roles[candidate_index]
        candidate = rows[candidate_index]
        if candidate_index in accepted_groups:
            boundary_group = candidate_index
            candidate_x = candidate.entries[0].bbox[0]
            opener_x = rows[index].entries[0].bbox[0]
            if candidate_x > opener_x + tolerance:
                scope_end = max(scope_end, int(scope_hints[candidate_index]))
            if dense_count >= 1:
                return (
                    dense_count,
                    scope_end,
                    first_dense_x,
                    boundary_group,
                    False,
                    False,
                )
            break
        if _semantic_singleton_label(candidate):
            break
        if role in {"TABLE_TITLE", "COLUMN_HEADER", "CONTINUATION_HEADER", "NOTE", "UNKNOWN"}:
            break
        if _semantic_dense_data_row(candidate, role):
            dense_count += 1
            first_dense_x = (
                candidate.entries[0].bbox[0]
                if first_dense_x is None
                else first_dense_x
            )
            scope_end = candidate_index
            continue
        if role in {"SUBTOTAL", "TOTAL"}:
            scope_end = candidate_index
            if dense_count >= 1:
                return (
                    dense_count,
                    scope_end,
                    first_dense_x,
                    boundary_group,
                    True,
                    candidate_index == len(rows) - 1,
                )
            break
        break
    if dense_count >= 2:
        return (
            dense_count,
            scope_end,
            first_dense_x,
            boundary_group,
            False,
            scope_end == len(rows) - 1,
        )
    if dense_count == 0 and boundary_group is not None:
        return dense_count, scope_end, first_dense_x, boundary_group, False, False
    return None


def _semantic_singleton_label(row: _RowBand) -> bool:
    if (
        row.external_title
        or row.external_note
        or len(row.entries) != 1
        or not _row_has_exact_entry_word_partition(row)
    ):
        return False
    text = row.entries[0].text.strip()
    normalized = _normalize_text(text)
    return bool(
        text
        and not _looks_numeric(text)
        and bool(re.search(r"[^\W\d_]", text, flags=re.UNICODE))
        and _UNIT_PATTERN.fullmatch(text) is None
        and _MARKER_PATTERN.fullmatch(text) is None
        and not _starts_with(normalized, _NOTE_PREFIXES)
        and not _starts_with(normalized, _SUBTOTAL_PREFIXES)
        and not _starts_with(normalized, _TOTAL_PREFIXES)
    )


def _semantic_dense_data_row(row: _RowBand, role: str) -> bool:
    return bool(
        role == "DATA"
        and len(row.entries) >= 2
        and _row_has_exact_entry_word_partition(row)
    )


def _semantic_terminal_marker_value_total(
    rows: list[_RowBand],
    *,
    roles: list[str],
    index: int,
    scope_opener_ordinal: int,
) -> bool:
    if index != len(rows) - 1:
        return False
    row = rows[index]
    if not _semantic_marker_value_suffix(row):
        return False
    preceding_dense = sum(
        _semantic_dense_data_row(rows[ordinal], roles[ordinal])
        for ordinal in range(scope_opener_ordinal + 1, index)
    )
    return preceding_dense >= 2


def _semantic_marker_value_suffix(row: _RowBand) -> bool:
    if len(row.entries) < 2 or not _row_has_exact_entry_word_partition(row):
        return False
    marker = row.entries[-2].text.strip()
    if not (
        _MARKER_PATTERN.fullmatch(marker)
        or _CURRENCY_MARKER_PATTERN.fullmatch(marker)
        or _UNIT_PATTERN.fullmatch(marker)
    ) or not _looks_numeric(row.entries[-1].text):
        return False
    return all(
        not _looks_numeric(entry.text)
        for entry in row.entries[:-2]
    )


def _semantic_strong_total_row(row: _RowBand) -> bool:
    normalized = _normalize_text(" ".join(entry.text for entry in row.entries))
    return _starts_with(
        normalized,
        ("grand total", "overall total", "общий итог", "всего"),
    )


def _single_ambiguous_eof_child(
    rows: list[_RowBand],
    *,
    roles: list[str],
    index: int,
) -> int | None:
    following = list(range(index + 1, len(rows)))
    if len(following) != 1:
        return None
    child_index = following[0]
    return (
        child_index
        if _semantic_dense_data_row(rows[child_index], roles[child_index])
        else None
    )


def _decision_descends_from(
    decision: Mapping[str, Any],
    *,
    ancestor_ordinal: int,
    decisions: list[dict[str, Any]],
) -> bool:
    parent = decision.get("parent_ordinal")
    visited: set[int] = set()
    while parent is not None:
        ordinal = int(parent)
        if ordinal == ancestor_ordinal:
            return True
        if ordinal in visited or not 0 <= ordinal < len(decisions):
            return False
        visited.add(ordinal)
        parent = decisions[ordinal].get("parent_ordinal")
    return False


def _ordered_row_semantic_source_fingerprint(rows: list[_RowBand]) -> str:
    return _sha256_json(
        [
            {
                "page_ref": row.page_ref,
                "bbox": list(row.bbox),
                "role": row.role,
                "external_title": row.external_title,
                "external_note": row.external_note,
                "row_coalescence_kind": row.row_coalescence_kind,
                "sequential_marker_header": row.sequential_marker_header,
                "words": [
                    [word.word_ref, word.text, word.order, list(word.bbox)]
                    for word in row.words
                ],
                "entries": [
                    {
                        "text": entry.text,
                        "bbox": list(entry.bbox),
                        "word_refs": [word.word_ref for word in entry.words],
                        "geometry_column_ordinals": entry.geometry_column_ordinals,
                    }
                    for entry in row.entries
                ],
            }
            for row in rows
        ]
    )


def _validate_ordered_row_semantic_decisions(
    decisions: tuple[_OrderedRowSemanticDecision, ...],
) -> None:
    if [decision.ordinal for decision in decisions] != list(range(len(decisions))):
        raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
    for decision in decisions:
        parent = decision.parent_ordinal
        if decision.nesting_level < 0 or parent is not None and parent >= decision.ordinal:
            raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
        if parent is None:
            if decision.nesting_level != 0:
                raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
        else:
            parent_decision = decisions[parent]
            if (
                parent_decision.role != "GROUP_HEADER"
                or parent_decision.nesting_level + 1 != decision.nesting_level
                or parent_decision.group_scope_end_ordinal is None
                or decision.ordinal > parent_decision.group_scope_end_ordinal
            ):
                raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
        if decision.role == "GROUP_HEADER":
            if (
                decision.group_scope_end_ordinal is None
                or decision.group_scope_end_ordinal < decision.ordinal
                or decision.group_scope_end_ordinal >= len(decisions)
            ):
                raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
        elif decision.group_scope_end_ordinal is not None:
            raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
        if "logical_row_parent_unresolved" in decision.issue_codes and not (
            decision.role == "DATA"
            and decision.nesting_level == 0
            and decision.parent_ordinal is None
        ):
            raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")


def _apply_ordered_row_semantic_plan(
    rows: list[_RowBand],
    *,
    plan: _OrderedRowSemanticPlan,
) -> None:
    if (
        plan.source_fingerprint_sha256
        != _ordered_row_semantic_source_fingerprint(rows)
        or len(plan.decisions) != len(rows)
        or any(row.row_id is None for row in rows)
        or len({str(row.row_id) for row in rows}) != len(rows)
    ):
        raise LogicalRowTableRecoveryError("ordered_row_semantic_plan_invalid")
    _validate_ordered_row_semantic_decisions(plan.decisions)
    for row, decision in zip(rows, plan.decisions):
        row.role = decision.role
        row.nesting_level = decision.nesting_level
        row.parent_row_id = (
            str(rows[decision.parent_ordinal].row_id)
            if decision.parent_ordinal is not None
            else None
        )
        row.semantic_issue_codes = decision.issue_codes


def _semantic_issue_message(code: str) -> str:
    if code == "logical_row_parent_unresolved":
        return (
            "The row is preserved as ordered DATA, but the preceding singleton "
            "does not prove a bounded parent scope."
        )
    raise LogicalRowTableRecoveryError("ordered_row_semantic_issue_unknown")


def _indent_ranks(rows: list[_RowBand]) -> list[int]:
    starts = [row.entries[0].bbox[0] for row in rows if row.entries]
    if not starts:
        return [0] * len(rows)
    typical_height = statistics.median(_bbox_height(row.bbox) for row in rows)
    tolerance = max(3.0, typical_height * 0.8)
    clusters: list[list[float]] = []
    for value in sorted(starts):
        target = next(
            (
                cluster
                for cluster in clusters
                if abs(value - statistics.median(cluster)) <= tolerance
            ),
            None,
        )
        if target is None:
            clusters.append([value])
        else:
            target.append(value)
    centers = sorted(statistics.median(cluster) for cluster in clusters)
    return [
        min(range(len(centers)), key=lambda index: abs(centers[index] - row.entries[0].bbox[0]))
        if row.entries
        else 0
        for row in rows
    ]


def _repeated_entry_centers(
    rows: list[_RowBand],
    *,
    width: float,
    config: LogicalRowTableRecoveryConfig,
) -> list[float]:
    tolerance = max(6.0, width * config.column_tolerance_width_ratio)
    clusters: list[list[tuple[float, int]]] = []
    for row_index, row in enumerate(rows):
        for entry in row.entries:
            center = _bbox_center_x(entry.bbox)
            target = next(
                (
                    cluster
                    for cluster in clusters
                    if abs(center - statistics.median(item[0] for item in cluster))
                    <= tolerance
                ),
                None,
            )
            if target is None:
                clusters.append([(center, row_index)])
            else:
                target.append((center, row_index))
    centers = [
        statistics.median(item[0] for item in cluster)
        for cluster in clusters
        if len({item[1] for item in cluster}) >= config.minimum_column_observations
    ]
    return sorted(centers)


def _headerless_two_column_tracks(
    rows: list[_RowBand],
    *,
    width: float,
    config: LogicalRowTableRecoveryConfig,
    required: int | None = None,
) -> list[_ColumnTrack]:
    paired = [row for row in rows if len(row.entries) == 2]
    required = required or max(3, config.minimum_column_observations)
    if len(paired) < required:
        return []
    tolerance = max(3.0, width * config.column_tolerance_width_ratio * 0.55)
    candidates_by_rows: dict[
        frozenset[int], tuple[tuple[float, int, int], list[_ColumnTrack]]
    ] = {}
    edges = ("LEFT", "RIGHT", "CENTER")
    for first_edge in edges:
        for second_edge in edges:
            coordinates = [
                (
                    _entry_edge(row.entries[0], first_edge),
                    _entry_edge(row.entries[1], second_edge),
                )
                for row in paired
            ]
            for first_seed, second_seed in coordinates:
                members = {
                    index
                    for index, (first, second) in enumerate(coordinates)
                    if abs(first - first_seed) <= tolerance * 1.8
                    and abs(second - second_seed) <= tolerance * 1.8
                }
                if len(members) < required:
                    continue
                first_coordinate = statistics.median(
                    coordinates[index][0] for index in members
                )
                second_coordinate = statistics.median(
                    coordinates[index][1] for index in members
                )
                members = {
                    index
                    for index in members
                    if abs(coordinates[index][0] - first_coordinate)
                    <= tolerance * 1.8
                    and abs(coordinates[index][1] - second_coordinate)
                    <= tolerance * 1.8
                }
                if len(members) < required:
                    continue
                first_center = statistics.median(
                    _bbox_center_x(paired[index].entries[0].bbox)
                    for index in members
                )
                second_center = statistics.median(
                    _bbox_center_x(paired[index].entries[1].bbox)
                    for index in members
                )
                if second_center - first_center <= tolerance * 2.0:
                    continue
                maximum_deviation = max(
                    max(
                        abs(coordinates[index][0] - first_coordinate),
                        abs(coordinates[index][1] - second_coordinate),
                    )
                    for index in members
                )
                tracks = [
                    _ColumnTrack(
                        edge=edge,
                        coordinate=coordinate,
                        tolerance=tolerance,
                        entries=[
                            paired[index].entries[ordinal]
                            for index in sorted(members)
                        ],
                        row_indexes=set(members),
                    )
                    for ordinal, (edge, coordinate) in enumerate(
                        (
                            (first_edge, first_coordinate),
                            (second_edge, second_coordinate),
                        )
                    )
                ]
                score = (
                    maximum_deviation,
                    sum(edge == "CENTER" for edge in (first_edge, second_edge)),
                    sum(edge == "RIGHT" for edge in (first_edge, second_edge)),
                )
                key = frozenset(members)
                existing = candidates_by_rows.get(key)
                if existing is None or score < existing[0]:
                    candidates_by_rows[key] = (score, tracks)
    if not candidates_by_rows:
        return []
    maximum_support = max(len(indexes) for indexes in candidates_by_rows)
    finalists = [
        (indexes, value)
        for indexes, value in candidates_by_rows.items()
        if len(indexes) == maximum_support
    ]
    if len(finalists) != 1:
        return []
    return finalists[0][1][1]


def _repeated_entry_tracks(
    rows: list[_RowBand],
    *,
    width: float,
    config: LogicalRowTableRecoveryConfig,
) -> list[_ColumnTrack]:
    """Infer optional columns from stable left or right source edges."""

    tolerance = max(
        3.0,
        width * config.column_tolerance_width_ratio * 0.45,
    )
    candidates: list[_ColumnTrack] = []
    for edge in ("LEFT", "RIGHT"):
        clusters: list[list[tuple[float, int, _EntryBand]]] = []
        for row_index, row in enumerate(rows):
            for entry in row.entries:
                coordinate = _entry_edge(entry, edge)
                target = next(
                    (
                        cluster
                        for cluster in clusters
                        if abs(
                            coordinate
                            - statistics.median(item[0] for item in cluster)
                        )
                        <= tolerance
                    ),
                    None,
                )
                if target is None:
                    clusters.append([(coordinate, row_index, entry)])
                else:
                    target.append((coordinate, row_index, entry))
        for cluster in clusters:
            row_indexes = {item[1] for item in cluster}
            if len(row_indexes) < config.minimum_column_observations:
                continue
            entries: list[_EntryBand] = []
            seen_entries: set[int] = set()
            for _, _, entry in cluster:
                if id(entry) not in seen_entries:
                    entries.append(entry)
                    seen_entries.add(id(entry))
            candidates.append(
                _ColumnTrack(
                    edge=edge,
                    coordinate=statistics.median(item[0] for item in cluster),
                    tolerance=tolerance,
                    entries=entries,
                    row_indexes=row_indexes,
                )
            )

    accepted: list[_ColumnTrack] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            -len(item.row_indexes),
            0 if item.edge == "LEFT" else 1,
            item.coordinate,
        ),
    ):
        candidate_entries = {id(entry) for entry in candidate.entries}
        duplicate = False
        for existing in accepted:
            existing_entries = {id(entry) for entry in existing.entries}
            overlap = len(candidate_entries & existing_entries)
            denominator = min(len(candidate_entries), len(existing_entries))
            if denominator and overlap / denominator >= 0.65:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    edge_tracks = sorted(
        accepted,
        key=lambda track: statistics.median(
            _bbox_center_x(entry.bbox) for entry in track.entries
        ),
    )
    center_tracks = _center_entry_tracks(
        rows,
        width=width,
        config=config,
    )
    return edge_tracks if len(edge_tracks) > len(center_tracks) else center_tracks


def _center_entry_tracks(
    rows: list[_RowBand],
    *,
    width: float,
    config: LogicalRowTableRecoveryConfig,
) -> list[_ColumnTrack]:
    tolerance = max(6.0, width * config.column_tolerance_width_ratio)
    clusters: list[list[tuple[float, int, _EntryBand]]] = []
    for row_index, row in enumerate(rows):
        for entry in row.entries:
            coordinate = _bbox_center_x(entry.bbox)
            target = next(
                (
                    cluster
                    for cluster in clusters
                    if abs(
                        coordinate
                        - statistics.median(item[0] for item in cluster)
                    )
                    <= tolerance
                ),
                None,
            )
            if target is None:
                clusters.append([(coordinate, row_index, entry)])
            else:
                target.append((coordinate, row_index, entry))
    result = []
    for cluster in clusters:
        row_indexes = {item[1] for item in cluster}
        if len(row_indexes) < config.minimum_column_observations:
            continue
        entries = []
        seen_entries: set[int] = set()
        for _, _, entry in cluster:
            if id(entry) not in seen_entries:
                entries.append(entry)
                seen_entries.add(id(entry))
        result.append(
            _ColumnTrack(
                edge="CENTER",
                coordinate=statistics.median(item[0] for item in cluster),
                tolerance=tolerance,
                entries=entries,
                row_indexes=row_indexes,
            )
        )
    return sorted(result, key=lambda track: track.coordinate)


def _entry_edge(entry: _EntryBand, edge: str) -> float:
    if edge == "LEFT":
        return entry.bbox[0]
    if edge == "RIGHT":
        return entry.bbox[2]
    return _bbox_center_x(entry.bbox)


def _region_alignment_signature(region: _Region) -> list[float]:
    rows = [row for row in region.rows if len(row.entries) >= 2]
    if not rows:
        return []
    left = region.bbox[0]
    width = max(1.0, _bbox_width(region.bbox))
    maximum = max(len(row.entries) for row in rows)
    complete = [row for row in rows if len(row.entries) == maximum]
    if not complete:
        return []
    return [
        round(
            statistics.median(
                (_bbox_center_x(row.entries[index].bbox) - left) / width
                for row in complete
            ),
            4,
        )
        for index in range(maximum)
    ]


def _header_signature(rows: list[_RowBand]) -> str:
    header = next(
        (
            row
            for row in rows
            if len(row.entries) >= 2
            and not any(_looks_value_like(entry.text) for entry in row.entries)
        ),
        None,
    )
    return _row_signature(header) if header is not None else ""


def _leading_header_stack(rows: list[_RowBand]) -> list[_RowBand]:
    index = 0
    while index < len(rows) and rows[index].role in {"TABLE_TITLE", "NOTE"}:
        index += 1
    result = []
    while index < len(rows) and rows[index].role == "COLUMN_HEADER":
        result.append(rows[index])
        index += 1
    return result


def _row_literal_signature(row: _RowBand) -> tuple[str, ...]:
    return tuple(entry.text for entry in row.entries)


def _row_signature(row: _RowBand | None) -> str:
    if row is None:
        return ""
    return "|".join(_normalize_text(entry.text) for entry in row.entries)


def _entry_kind(text: str, row_role: str, ordinal: int) -> str:
    stripped = text.strip()
    if row_role == "NOTE":
        return "NOTE"
    if _MARKER_PATTERN.fullmatch(stripped):
        return "MARKER"
    if _UNIT_PATTERN.fullmatch(stripped):
        return "UNIT"
    if _looks_value_like(stripped):
        return "VALUE"
    if ordinal == 0 or row_role in {
        "TABLE_TITLE",
        "COLUMN_HEADER",
        "CONTINUATION_HEADER",
        "GROUP_HEADER",
        "SUBTOTAL",
        "TOTAL",
    }:
        return "LABEL"
    return "LABEL"


def _promote_and_bind_proven_suffix_headers(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    logical_columns: list[dict[str, Any]],
) -> None:
    """Attach proven suffix headers only after body columns are immutable.

    Header proof must not participate in track discovery: otherwise a
    spanner's visual center can become a phantom logical column.  This pass
    reconstructs the already-materialized body tracks, plans every promoted
    binding, and commits roles/bindings only when the whole table is unique.
    """

    roots = [row for row in rows if row.proven_leading_suffix_header]
    if not roots:
        return
    column_ids = [str(column["column_id"]) for column in logical_columns]
    if len(column_ids) < 2 or len(column_ids) != len(set(column_ids)):
        return
    body_roles = {"DATA", "SUBTOTAL", "TOTAL"}
    support_by_column: dict[str, list[_EntryBand]] = {
        column_id: [] for column_id in column_ids
    }
    for row in rows:
        if row.role not in body_roles:
            continue
        for entry in row.entries:
            if entry.logical_column_id in support_by_column:
                support_by_column[str(entry.logical_column_id)].append(entry)
    if any(not support_by_column[column_id] for column_id in column_ids):
        return
    coordinates = [
        statistics.median(
            _bbox_center_x(entry.bbox)
            for entry in support_by_column[column_id]
        )
        for column_id in column_ids
    ]
    if any(right <= left for left, right in zip(coordinates, coordinates[1:])):
        return
    gaps = [right - left for left, right in zip(coordinates, coordinates[1:])]
    tolerance = max(1.0, min(gaps) * 0.2) if gaps else 1.0
    tracks = [
        _ColumnTrack(
            edge="CENTER",
            coordinate=coordinate,
            tolerance=tolerance,
            entries=list(support_by_column[column_id]),
            row_indexes=set(range(len(support_by_column[column_id]))),
        )
        for column_id, coordinate in zip(column_ids, coordinates)
    ]
    row_payload_by_id = {
        str(payload["row_id"]): payload for payload in row_payloads
    }
    entry_payload_by_id = {
        str(entry["entry_id"]): entry
        for payload in row_payloads
        for entry in payload["entries"]
    }
    decisions: list[
        tuple[_EntryBand, dict[str, Any], str | None, tuple[str, ...]]
    ] = []
    for row in rows:
        for entry in row.entries:
            coverage = entry.proven_header_coverage_bbox
            if coverage is None and not row.proven_leading_suffix_header:
                continue
            if coverage is None:
                track_index = _unique_track_index(entry, tracks)
                if track_index is None:
                    return
                logical_column_id: str | None = column_ids[track_index]
                covers: tuple[str, ...] = ()
            else:
                covered_indexes = _covered_track_indexes(
                    entry,
                    tracks,
                    use_proven_coverage=True,
                )
                if covered_indexes is None or not covered_indexes:
                    return
                if len(covered_indexes) == 1:
                    logical_column_id = column_ids[covered_indexes[0]]
                    covers = ()
                else:
                    logical_column_id = None
                    covers = tuple(
                        column_ids[index] for index in covered_indexes
                    )
            payload = entry_payload_by_id.get(str(entry.entry_id))
            if payload is None:
                return
            decisions.append((entry, payload, logical_column_id, covers))
    if not decisions or any(
        str(root.row_id) not in row_payload_by_id for root in roots
    ):
        return
    for root in roots:
        if root.role != "CONTINUATION_HEADER":
            root.role = "COLUMN_HEADER"
            row_payload_by_id[str(root.row_id)]["role"] = "COLUMN_HEADER"
    for entry, payload, logical_column_id, covers in decisions:
        _set_entry_column_binding(
            entry,
            payload=payload,
            logical_column_id=logical_column_id,
            covers_logical_column_ids=covers,
        )


def _finalize_entry_kinds_after_binding(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    logical_columns: list[dict[str, Any]] | None = None,
) -> None:
    """Finalize kinds from lexical evidence plus repeated neutral lane shape."""

    if len(rows) != len(row_payloads):
        raise LogicalRowTableRecoveryError("logical_row_kind_alignment_invalid")

    direct_body_by_column: dict[str, list[_EntryBand]] = {}
    for row, row_payload in zip(rows, row_payloads):
        payload_entries = _dicts(row_payload.get("entries"))
        if len(row.entries) != len(payload_entries):
            raise LogicalRowTableRecoveryError("logical_row_kind_alignment_invalid")
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        for entry, payload in zip(row.entries, payload_entries):
            column_id = payload.get("logical_column_id")
            if (
                payload.get("column_binding_status") == "BOUND"
                and column_id is not None
                and not payload.get("covers_logical_column_ids")
            ):
                direct_body_by_column.setdefault(str(column_id), []).append(entry)
    dedicated_unit_column_ids = {
        column_id
        for column_id, entries in direct_body_by_column.items()
        if len(entries) >= 3
        and sum(
            _UNIT_PATTERN.fullmatch(entry.text.strip()) is not None
            for entry in entries
        )
        / len(entries)
        >= 0.8
    }
    structural_unit_suffix_entry_ids = _repeated_unit_suffix_entry_ids(
        rows=rows,
        row_payloads=row_payloads,
    )

    planned: list[tuple[_RowBand, _EntryBand, dict[str, Any], str]] = []
    for row, row_payload in zip(rows, row_payloads):
        payload_entries = _dicts(row_payload.get("entries"))
        if len(row.entries) != len(payload_entries):
            raise LogicalRowTableRecoveryError("logical_row_kind_alignment_invalid")
        for ordinal, (entry, payload) in enumerate(
            zip(row.entries, payload_entries)
        ):
            planned.append(
                (
                    row,
                    entry,
                    payload,
                    _entry_kind_after_binding(
                        entry=entry,
                        row=row,
                        entry_ordinal=ordinal,
                        payload=payload,
                        payload_entries=payload_entries,
                        dedicated_unit_column_ids=dedicated_unit_column_ids,
                        structural_unit_suffix_entry_ids=(
                            structural_unit_suffix_entry_ids
                        ),
                    ),
                )
            )
    label_column_ids, value_column_ids = _semantic_column_kind_profiles(
        planned,
        dedicated_unit_column_ids=dedicated_unit_column_ids,
        logical_columns=logical_columns or [],
    )
    for row, _entry, payload, planned_kind in planned:
        kind = planned_kind
        column_id = payload.get("logical_column_id")
        if (
            row.role in {"DATA", "SUBTOTAL", "TOTAL"}
            and payload.get("column_binding_status") == "BOUND"
            and column_id is not None
            and not payload.get("covers_logical_column_ids")
        ):
            if str(column_id) in label_column_ids and kind == "VALUE":
                kind = "LABEL"
            elif str(column_id) in value_column_ids and kind == "LABEL":
                kind = "VALUE"
        payload["kind"] = kind


def _entry_kind_after_binding(
    *,
    entry: _EntryBand,
    row: _RowBand,
    entry_ordinal: int,
    payload: Mapping[str, Any],
    payload_entries: list[dict[str, Any]],
    dedicated_unit_column_ids: set[str],
    structural_unit_suffix_entry_ids: set[int],
) -> str:
    stripped = entry.text.strip()
    if row.role == "NOTE":
        return "NOTE"
    if row.sequential_marker_header:
        return "MARKER"
    if _MARKER_PATTERN.fullmatch(stripped):
        return "MARKER"
    if id(entry) in structural_unit_suffix_entry_ids:
        return "UNIT"
    if _UNIT_PATTERN.fullmatch(stripped):
        column_id = payload.get("logical_column_id")
        return (
            "MARKER"
            if str(column_id) not in dedicated_unit_column_ids
            and (
                _unit_prefix_has_right_numeric_same_binding(
                    row=row,
                    entry_ordinal=entry_ordinal,
                    payload=payload,
                    payload_entries=payload_entries,
                )
                or _currency_prefix_has_right_numeric(
                    row=row,
                    entry_ordinal=entry_ordinal,
                )
            )
            else "UNIT"
        )
    if row.role == "UNKNOWN" and len(row.entries) == 1:
        return "LABEL"

    return _entry_kind(entry.text, row.role, entry_ordinal)


def _repeated_unit_suffix_entry_ids(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
) -> set[int]:
    candidates_by_column: dict[str, list[tuple[int, _EntryBand]]] = {}
    for row, row_payload in zip(rows, row_payloads):
        if row.role not in {"DATA", "SUBTOTAL", "TOTAL"}:
            continue
        payload_entries = _dicts(row_payload.get("entries"))
        if len(row.entries) != len(payload_entries) or len(row.entries) < 3:
            continue
        right_index = len(row.entries) - 1
        left_index = right_index - 1
        left = row.entries[left_index]
        right = row.entries[right_index]
        left_payload = payload_entries[left_index]
        right_payload = payload_entries[right_index]
        column_id = right_payload.get("logical_column_id")
        text = right.text.strip()
        if (
            left_payload.get("column_binding_status") != "BOUND"
            or right_payload.get("column_binding_status") != "BOUND"
            or column_id is None
            or left_payload.get("logical_column_id") != column_id
            or left_payload.get("covers_logical_column_ids")
            or right_payload.get("covers_logical_column_ids")
            or not _looks_numeric(left.text)
            or not text
            or len(text) > 12
            or len(text.split()) != 1
            or _looks_numeric(text)
            or not any(not character.isdigit() for character in text)
        ):
            continue
        candidates_by_column.setdefault(str(column_id), []).append((id(row), right))
    return {
        id(entry)
        for candidates in candidates_by_column.values()
        if len({row_id for row_id, _entry in candidates}) >= 2
        for _row_id, entry in candidates
    }


def _semantic_column_kind_profiles(
    planned: list[tuple[_RowBand, _EntryBand, dict[str, Any], str]],
    *,
    dedicated_unit_column_ids: set[str],
    logical_columns: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    body_by_column: dict[
        str, list[tuple[_EntryBand, str]]
    ] = {}
    for row, entry, payload, kind in planned:
        column_id = payload.get("logical_column_id")
        if (
            row.role not in {"DATA", "SUBTOTAL", "TOTAL"}
            or payload.get("column_binding_status") != "BOUND"
            or column_id is None
            or payload.get("covers_logical_column_ids")
        ):
            continue
        body_by_column.setdefault(str(column_id), []).append((entry, kind))

    numeric_column_ids = {
        column_id
        for column_id, items in body_by_column.items()
        if len(items) >= 3
        and sum(kind == "VALUE" for _entry, kind in items)
        / len(items)
        >= 0.6
    }
    if not numeric_column_ids:
        return set(), set()

    label_column_ids: set[str] = set()
    for column_id, items in body_by_column.items():
        if len(items) < 3 or column_id in dedicated_unit_column_ids:
            continue
        single_ratio = sum(
            len(entry.text.split()) == 1 for entry, _kind in items
        ) / len(items)
        if single_ratio < 0.9 and any(kind == "LABEL" for _entry, kind in items):
            label_column_ids.add(column_id)

    value_column_ids: set[str] = set()
    if label_column_ids:
        for column_id, items in body_by_column.items():
            if (
                len(items) < 3
                or column_id in dedicated_unit_column_ids
                or column_id in label_column_ids
                or not any(kind == "LABEL" for _entry, kind in items)
            ):
                continue
            single_ratio = sum(
                len(entry.text.split()) == 1 for entry, _kind in items
            ) / len(items)
            lengths = [len(entry.text.strip()) for entry, _kind in items]
            median_length = statistics.median(lengths)
            if (
                single_ratio >= 0.9
                and median_length <= 24
            ):
                value_column_ids.add(column_id)
        ordinal_by_column_id = {
            str(column.get("column_id")): int(column.get("ordinal", -1))
            for column in logical_columns
        }
        column_id_by_ordinal = {
            ordinal: column_id
            for column_id, ordinal in ordinal_by_column_id.items()
            if ordinal >= 0
        }
        if len(logical_columns) >= 5:
            for column_id, items in body_by_column.items():
                ordinal = ordinal_by_column_id.get(column_id)
                if (
                    len(items) != 2
                    or ordinal is None
                    or ordinal <= 0
                    or ordinal >= len(logical_columns) - 1
                    or column_id in label_column_ids
                    or column_id in dedicated_unit_column_ids
                    or not all(kind == "LABEL" for _entry, kind in items)
                ):
                    continue
                neighbor_ids = {
                    column_id_by_ordinal.get(ordinal - 1),
                    column_id_by_ordinal.get(ordinal + 1),
                }
                if None not in neighbor_ids and neighbor_ids.issubset(
                    numeric_column_ids | value_column_ids
                ):
                    value_column_ids.add(column_id)
    return label_column_ids, value_column_ids


def _currency_prefix_has_right_numeric(
    *,
    row: _RowBand,
    entry_ordinal: int,
) -> bool:
    entry = row.entries[entry_ordinal]
    if (
        _CURRENCY_MARKER_PATTERN.fullmatch(entry.text.strip()) is None
        or entry_ordinal + 1 >= len(row.entries)
    ):
        return False
    sibling = row.entries[entry_ordinal + 1]
    gap = sibling.bbox[0] - entry.bbox[2]
    tolerance = max(12.0, _bbox_height(row.bbox) * 4.0)
    return bool(
        0.0 <= gap <= tolerance
        and _looks_numeric(sibling.text)
    )


def _unit_prefix_has_right_numeric_same_binding(
    *,
    row: _RowBand,
    entry_ordinal: int,
    payload: Mapping[str, Any],
    payload_entries: list[dict[str, Any]],
) -> bool:
    logical_column_id = payload.get("logical_column_id")
    if (
        payload.get("column_binding_status") != "BOUND"
        or logical_column_id is None
        or payload.get("covers_logical_column_ids")
        or entry_ordinal >= len(row.entries) - 1
        or len(row.entries) != len(payload_entries)
    ):
        return False
    entry = row.entries[entry_ordinal]
    return any(
        sibling_payload.get("column_binding_status") == "BOUND"
        and sibling_payload.get("logical_column_id") == logical_column_id
        and not sibling_payload.get("covers_logical_column_ids")
        and sibling.bbox[0] >= entry.bbox[2]
        and (
            _looks_numeric(sibling.text)
            or _strict_dash_placeholder(sibling.text)
        )
        for sibling, sibling_payload in zip(
            row.entries[entry_ordinal + 1 :],
            payload_entries[entry_ordinal + 1 :],
        )
    )


def _finalize_column_header_paths(
    *,
    rows: list[_RowBand],
    row_payloads: list[dict[str, Any]],
    logical_columns: list[dict[str, Any]],
    state: _RecoveryState,
    table_id: str,
) -> list[str]:
    """Atomically rebuild paths and their uncertainty issues after kinds."""

    if len(rows) != len(row_payloads):
        raise LogicalRowTableRecoveryError("logical_column_header_path_alignment_invalid")
    column_ids = [str(column.get("column_id")) for column in logical_columns]
    if (
        len(column_ids) != len(set(column_ids))
        or [int(column.get("ordinal", -1)) for column in logical_columns]
        != list(range(len(logical_columns)))
    ):
        raise LogicalRowTableRecoveryError("logical_column_header_path_columns_invalid")
    issue_by_id = {
        str(issue.get("issue_id")): issue for issue in state.issues
    }
    if len(issue_by_id) != len(state.issues):
        raise LogicalRowTableRecoveryError("logical_column_header_path_issues_invalid")
    header_unknown_ids = {
        issue_id
        for issue_id, issue in issue_by_id.items()
        if issue.get("code") == "logical_column_header_path_unknown"
    }
    geometry_by_id = {
        str(item.get("geometry_evidence_id")): item
        for item in state.geometry_evidence
    }
    if len(geometry_by_id) != len(state.geometry_evidence):
        raise LogicalRowTableRecoveryError("logical_column_header_path_geometry_invalid")
    scope_issue_ids = {
        issue_id
        for column in logical_columns
        for issue_id in _strings(column.get("issue_ids"))
    }
    for column in logical_columns:
        for geometry_id in _strings(column.get("geometry_evidence_ids")):
            if geometry_id in geometry_by_id:
                scope_issue_ids.update(
                    _strings(geometry_by_id[geometry_id].get("issue_ids"))
                )
    scope_unknown_ids = header_unknown_ids.intersection(scope_issue_ids)

    payload_rows: list[tuple[_RowBand, list[dict[str, Any]]]] = []
    for row, payload_row in zip(rows, row_payloads):
        entries = _dicts(payload_row.get("entries"))
        if len(entries) != len(row.entries):
            raise LogicalRowTableRecoveryError(
                "logical_column_header_path_alignment_invalid"
            )
        payload_rows.append((row, entries))

    plans: list[dict[str, Any]] = []
    planned_new_issues: dict[str, tuple[list[str], list[str]]] = {}
    active_unknown_ids: set[str] = set()
    for column in logical_columns:
        column_id = str(column["column_id"])
        path = _unique(
            str(entry_payload["entry_id"])
            for row, payload_entries in payload_rows
            if row.role in {"COLUMN_HEADER", "CONTINUATION_HEADER"}
            for entry_payload in payload_entries
            if entry_payload.get("kind") != "MARKER"
            and entry_payload.get("column_binding_status") == "BOUND"
            and (
                entry_payload.get("logical_column_id") == column_id
                or column_id
                in _strings(entry_payload.get("covers_logical_column_ids"))
            )
        )
        existing_issue_ids = _strings(column.get("issue_ids"))
        other_issue_ids = [
            issue_id
            for issue_id in existing_issue_ids
            if issue_id not in header_unknown_ids
        ]
        desired_unknown_id: str | None = None
        if not path:
            anchor_ids = _unique(_strings(column.get("source_anchor_ids")))
            if not anchor_ids:
                raise LogicalRowTableRecoveryError(
                    "logical_column_header_path_anchor_missing"
                )
            desired_unknown_id = _identifier(
                "issue",
                ["logical_column_header_path_unknown", *anchor_ids],
            )
            active_unknown_ids.add(desired_unknown_id)
            if desired_unknown_id not in issue_by_id:
                planned_new_issues[desired_unknown_id] = (
                    anchor_ids,
                    [logical_table_block_id(table_id)],
                )
        issue_ids = _unique(
            [
                *other_issue_ids,
                *([desired_unknown_id] if desired_unknown_id is not None else []),
            ]
        )
        geometry_ids = _strings(column.get("geometry_evidence_ids"))
        if any(geometry_id not in geometry_by_id for geometry_id in geometry_ids):
            raise LogicalRowTableRecoveryError(
                "logical_column_header_path_geometry_missing"
            )
        plans.append(
            {
                "column": column,
                "header_path": path,
                "issue_ids": issue_ids,
                "geometry_ids": geometry_ids,
            }
        )

    for issue_id, (anchor_ids, block_ids) in planned_new_issues.items():
        actual = state.add_issue(
            code="logical_column_header_path_unknown",
            message=(
                "Logical column geometry is proven, but no bound textual "
                "source header entry is deterministic."
            ),
            anchor_ids=anchor_ids,
            block_ids=block_ids,
        )
        if actual != issue_id:
            raise LogicalRowTableRecoveryError(
                "logical_column_header_path_issue_id_invalid"
            )

    stale_unknown_ids = scope_unknown_ids - active_unknown_ids
    for plan in plans:
        column = plan["column"]
        column["header_path"] = list(plan["header_path"])
        column["issue_ids"] = list(plan["issue_ids"])
        for geometry_id in plan["geometry_ids"]:
            geometry = geometry_by_id[geometry_id]
            geometry["issue_ids"] = _unique(
                [
                    issue_id
                    for issue_id in _strings(geometry.get("issue_ids"))
                    if issue_id not in header_unknown_ids
                ]
                + list(plan["issue_ids"])
            )
    if stale_unknown_ids:
        state.issues[:] = [
            issue
            for issue in state.issues
            if str(issue.get("issue_id")) not in stale_unknown_ids
        ]
        for geometry in state.geometry_evidence:
            geometry["issue_ids"] = [
                issue_id
                for issue_id in _strings(geometry.get("issue_ids"))
                if issue_id not in stale_unknown_ids
            ]
    return sorted(active_unknown_ids)


def _strict_dash_placeholder(value: str) -> bool:
    return unicodedata.normalize("NFKC", value).strip() in {
        "-",
        "−",
        "–",
        "—",
    }


def _looks_numeric(value: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if _NUMBER_PATTERN.fullmatch(normalized):
        return True
    normalized = re.sub(
        r"^([\(\[]?)\s*(?:usd|eur|gbp|rub|rur|cny|jpy|chf|cad|aud)\s*",
        r"\1",
        normalized,
    )
    normalized = re.sub(
        r"\s*(?:usd|eur|gbp|rub|rur|cny|jpy|chf|cad|aud)$",
        "",
        normalized,
    )
    compact = re.sub(r"[\s$€£¥]", "", normalized)
    scalar = r"[+\-−]?(?:\d{1,3}(?:[,.'’]\d{3})+|\d+)(?:[.,]\d+)?%?"
    return bool(
        re.fullmatch(rf"[\(\[]?{scalar}[\)\]]?(?:[*†‡]+)?", compact)
        or re.fullmatch(
            rf"[\(\[]?{scalar}(?:[-–—]|to){scalar}[\)\]]?(?:[*†‡]+)?",
            compact,
        )
    )


def _looks_value_like(value: str) -> bool:
    if _looks_numeric(value):
        return True
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not re.search(r"\d", normalized):
        return False
    compact = re.sub(r"\s+", "", normalized)
    if any(marker in compact for marker in ("$", "€", "£", "¥", "%")):
        return True
    if re.match(r"^[\(\[]?[+\-−]?\d", compact):
        return len(normalized) <= 160
    return bool(
        re.search(
            r"\b(?:usd|eur|gbp|rub|rur|cny|jpy|chf|cad|aud)\b",
            normalized,
        )
    )


def _starts_with(value: str, prefixes: Sequence[str]) -> bool:
    return any(value == prefix or value.startswith(prefix + " ") for prefix in prefixes)


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[\w%]+", text, flags=re.UNICODE))


def _overlapping_object_refs(
    *,
    page_ref: str,
    bbox: tuple[float, float, float, float],
    object_bboxes: list[_ObjectGeometry],
) -> list[str]:
    return sorted(
        item.object_ref
        for item in object_bboxes
        if item.page_ref == page_ref and _bbox_overlap(item.bbox, bbox)
    )


def _region_key(region: _Region) -> tuple[int, float, float, str]:
    return (
        region.page.page_number,
        region.bbox[1],
        region.bbox[0],
        region.source_ref,
    )


def _identifier(prefix: str, parts: Sequence[Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(list(parts))).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _valid_bbox(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise LogicalRowTableRecoveryError("logical_row_projection_bbox_invalid")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_bbox_invalid"
        ) from exc
    if (
        any(not math.isfinite(item) for item in result)
        or result[2] < result[0]
        or result[3] < result[1]
        or (result[2] == result[0] and result[3] == result[1])
    ):
        raise LogicalRowTableRecoveryError("logical_row_projection_bbox_invalid")
    return result


def _positive_number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_page_dimension_invalid"
        ) from exc
    if not math.isfinite(result) or result <= 0.0:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_page_dimension_invalid"
        )
    return result


def _positive_int(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_page_number_invalid"
        ) from exc
    if result <= 0:
        raise LogicalRowTableRecoveryError(
            "logical_row_projection_page_number_invalid"
        )
    return result


def _merge_bboxes(
    values: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    if not values:
        raise LogicalRowTableRecoveryError("logical_row_bbox_merge_empty")
    return (
        min(item[0] for item in values),
        min(item[1] for item in values),
        max(item[2] for item in values),
        max(item[3] for item in values),
    )


def _bbox_width(value: tuple[float, float, float, float]) -> float:
    return max(0.0, value[2] - value[0])


def _bbox_height(value: tuple[float, float, float, float]) -> float:
    return max(0.0, value[3] - value[1])


def _bbox_center_x(value: tuple[float, float, float, float]) -> float:
    return (value[0] + value[2]) / 2.0


def _bbox_center_y(value: tuple[float, float, float, float]) -> float:
    return (value[1] + value[3]) / 2.0


def _center_inside(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> bool:
    return (
        outer[0] <= _bbox_center_x(inner) <= outer[2]
        and outer[1] <= _bbox_center_y(inner) <= outer[3]
    )


def _bbox_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return not (
        left[2] <= right[0]
        or right[2] <= left[0]
        or left[3] <= right[1]
        or right[3] <= left[1]
    )


def _bbox_iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    if not _bbox_overlap(left, right):
        return 0.0
    intersection = max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1])
    )
    left_area = _bbox_width(left) * _bbox_height(left)
    right_area = _bbox_width(right) * _bbox_height(right)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if item is not None and str(item)] if isinstance(value, list) else []


def _unique(values: Sequence[str] | Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))
