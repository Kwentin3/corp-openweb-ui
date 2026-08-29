"""Research-only bridge from one source-bound logical table to Canonical.

The bridge selects a table only by exact parser-word evidence from a visual
header projection.  It never repairs values, assigns financial roles or makes
the resulting partial document publishable.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .logical_row_table_recovery import LogicalRowTableRecoveryResult
from .table_projection import (
    NormalizedTableProjectionFactory,
    TableProjectionBuildResult,
)


SCOPE_SCHEMA_VERSION = "broker_reports_table_scoped_role_research_v1"
ENVELOPE_SCHEMA_VERSION = "broker_reports_table_scoped_role_envelope_v1"

FACTORY_REQUIRED = (
    "TableScopedRoleResearchFactory.create is the only research bridge from "
    "a full logical-row recovery to one non-publishing Canonical table scope"
)
FORBIDDEN = (
    "research-only: no value repair, financial-role assignment, fact "
    "publication, document-complete claim or product activation"
)


class TableScopedRoleResearchError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TableScopedRoleResearchResult:
    projection_result: TableProjectionBuildResult
    canonical_source_units: list[dict[str, Any]]
    selected_table_id: str
    bound_structure: dict[str, Any]
    scope_binding: dict[str, Any]


class TableScopedRoleResearchFactory:
    def create(self) -> "TableScopedRoleResearch":
        return TableScopedRoleResearch()


class TableScopedRoleResearch:
    """Select and represent one table while preserving every source word."""

    def build(
        self,
        *,
        recovery: Any,
        payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
        bound_visual_projection: Mapping[str, Any],
        source_checksum_sha256: str,
    ) -> TableScopedRoleResearchResult:
        recovery_value = (
            recovery.as_dict()
            if callable(getattr(recovery, "as_dict", None))
            else None
        )
        if (
            not isinstance(recovery_value, dict)
            or recovery_value.get("schema_version")
            != "broker_reports_logical_row_table_recovery_v1"
        ):
            raise TableScopedRoleResearchError("table_scope_recovery_invalid")
        if not _sha256(source_checksum_sha256):
            raise TableScopedRoleResearchError("table_scope_source_sha256_invalid")

        words, page_number_by_ref = _word_inventory(payloads)
        anchors = _index_unique(recovery_value.get("anchors"), "anchor_id")
        ownership = _dicts(recovery_value.get("source_word_ownership"))
        global_table_word_refs = _validate_global_partition(
            recovery=recovery_value,
            words=words,
            anchors=anchors,
            ownership=ownership,
        )
        bound_structure, target = _select_unique_table(
            recovery=recovery_value,
            bound_visual_projection=bound_visual_projection,
            anchors=anchors,
            source_checksum_sha256=source_checksum_sha256,
        )
        table_id = str(target.get("table_id") or "")
        selected_ownership = [
            copy.deepcopy(item)
            for item in ownership
            if str(item.get("table_id") or "") == table_id
        ]
        selected_anchor_ids = {
            str(item.get("source_anchor_id") or "") for item in selected_ownership
        }
        selected_anchors = [
            copy.deepcopy(item)
            for anchor_id, item in anchors.items()
            if anchor_id in selected_anchor_ids
        ]
        selected_word_refs = {
            _anchor_word_ref(anchors[anchor_id]) for anchor_id in selected_anchor_ids
        }
        if (
            not selected_word_refs
            or selected_word_refs - global_table_word_refs
            or len(selected_word_refs) != len(selected_anchor_ids)
        ):
            raise TableScopedRoleResearchError(
                "table_scope_selected_word_partition_invalid"
            )
        all_word_refs = set(words)
        complement_refs = all_word_refs - selected_word_refs
        if selected_word_refs & complement_refs or selected_word_refs | complement_refs != all_word_refs:
            raise TableScopedRoleResearchError("table_scope_partition_invalid")

        title_refs = _required_unique_strings(bound_structure.get("title_word_refs"))
        if not set(title_refs) <= complement_refs:
            raise TableScopedRoleResearchError("table_scope_title_partition_invalid")

        geometry_ids = _nested_refs(target, "geometry_evidence_ids")
        issue_ids = _nested_refs(target, "issue_ids") | set(
            _strings(target.get("known_gap_ids"))
        )
        scoped_recovery = LogicalRowTableRecoveryResult(
            schema_version=str(recovery_value["schema_version"]),
            recovery_policy_version=str(
                recovery_value.get("recovery_policy_version") or ""
            ),
            tables=[copy.deepcopy(target)],
            anchors=selected_anchors,
            geometry_evidence=[
                copy.deepcopy(item)
                for item in _dicts(recovery_value.get("geometry_evidence"))
                if str(item.get("geometry_evidence_id") or "") in geometry_ids
            ],
            source_word_ownership=selected_ownership,
            issues=[
                copy.deepcopy(item)
                for item in _dicts(recovery_value.get("issues"))
                if str(item.get("issue_id") or "") in issue_ids
            ],
            paragraph_owned_word_refs=_ordered_word_refs(complement_refs, words),
            unowned_word_refs=[],
            diagnostics={
                "scope": "TABLE_SCOPED_RESEARCH_ONLY",
                "document_complete": False,
                "publication_allowed": False,
                "product_reachability": False,
            },
        )
        canonical_source_units = _canonical_source_units(
            source_units=source_units,
            words=words,
            page_number_by_ref=page_number_by_ref,
            complement_refs=complement_refs,
            title_refs=set(title_refs),
        )
        projection_result = (
            NormalizedTableProjectionFactory()
            .create()
            .build_research_projection_for_logical_row_recovery(
                recovery=scoped_recovery,
                payloads=payloads,
                source_units=canonical_source_units,
            )
        )
        if len(projection_result.projections) != 1:
            raise TableScopedRoleResearchError("table_scope_projection_invalid")
        projection = projection_result.projections[0]
        scope_binding = {
            "schema_version": SCOPE_SCHEMA_VERSION,
            "scope": "TABLE_SCOPED_RESEARCH_ONLY",
            "source_checksum_sha256": source_checksum_sha256.lower(),
            "selected_table_id": table_id,
            "selected_visual_table_order": int(
                bound_structure.get("table_order") or 0
            ),
            "table_projection_id": projection["table_projection_id"],
            "bound_visual_projection_sha256": _stable_sha256(
                bound_visual_projection
            ),
            "selected_source_word_refs_sha256": _stable_sha256(
                sorted(selected_word_refs)
            ),
            "complement_source_word_refs_sha256": _stable_sha256(
                sorted(complement_refs)
            ),
            "source_words_total": len(all_word_refs),
            "selected_table_words_total": len(selected_word_refs),
            "complement_words_total": len(complement_refs),
            "document_complete": False,
            "publication_allowed": False,
            "product_reachability": False,
            "facts_published": 0,
            "private_values_committed": False,
        }
        return TableScopedRoleResearchResult(
            projection_result=projection_result,
            canonical_source_units=canonical_source_units,
            selected_table_id=table_id,
            bound_structure=copy.deepcopy(bound_structure),
            scope_binding=scope_binding,
        )

    def bind_canonical(
        self, *, scope_binding: Mapping[str, Any], canonical: Mapping[str, Any]
    ) -> dict[str, Any]:
        if scope_binding.get("schema_version") != SCOPE_SCHEMA_VERSION:
            raise TableScopedRoleResearchError("table_scope_binding_invalid")
        root_hash = str(canonical.get("canonical_root_hash") or "")
        artifact_id = str(canonical.get("artifact_id") or "")
        source = canonical.get("source")
        nodes = canonical.get("nodes")
        if (
            canonical.get("status") != "validated"
            or not _sha256(root_hash)
            or not artifact_id
            or not isinstance(source, Mapping)
            or str(source.get("source_sha256") or "").lower()
            != str(scope_binding.get("source_checksum_sha256") or "").lower()
            or not isinstance(nodes, list)
        ):
            raise TableScopedRoleResearchError("table_scope_canonical_invalid")
        table_nodes = [
            item
            for item in nodes
            if isinstance(item, dict) and item.get("node_type") == "TABLE"
        ]
        if len(table_nodes) != 1:
            raise TableScopedRoleResearchError("table_scope_canonical_table_invalid")
        metadata = _object(table_nodes[0].get("content")).get("metadata")
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("table_projection_id")
            != scope_binding.get("table_projection_id")
        ):
            raise TableScopedRoleResearchError("table_scope_canonical_table_invalid")
        envelope = {
            **copy.deepcopy(dict(scope_binding)),
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "canonical_artifact_id": artifact_id,
            "canonical_root_hash": root_hash,
        }
        envelope["envelope_sha256"] = _stable_sha256(envelope)
        return envelope

    def validate_envelope(
        self, *, envelope: Mapping[str, Any], canonical: Mapping[str, Any]
    ) -> None:
        unsigned = {
            key: copy.deepcopy(value)
            for key, value in envelope.items()
            if key != "envelope_sha256"
        }
        if (
            envelope.get("schema_version") != ENVELOPE_SCHEMA_VERSION
            or envelope.get("envelope_sha256") != _stable_sha256(unsigned)
            or envelope.get("canonical_root_hash")
            != canonical.get("canonical_root_hash")
            or envelope.get("document_complete") is not False
            or envelope.get("publication_allowed") is not False
            or envelope.get("product_reachability") is not False
            or envelope.get("facts_published") != 0
        ):
            raise TableScopedRoleResearchError("table_scope_envelope_invalid")


def _select_unique_table(
    *,
    recovery: Mapping[str, Any],
    bound_visual_projection: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
    source_checksum_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    visual_tables = _dicts(bound_visual_projection.get("tables"))
    if not visual_tables:
        raise TableScopedRoleResearchError("table_scope_visual_projection_invalid")
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for visual in visual_tables:
        if (
            visual.get("header_status") != "PRESENT"
            or visual.get("body_status") != "HAS_DATA"
        ):
            continue
        visual_refs = set(_required_unique_strings(visual.get("header_word_refs")))
        visual_page = int(bound_visual_projection.get("page_number") or 0)
        for table in _dicts(recovery.get("tables")):
            if table.get("completeness_status") != "COMPLETE":
                continue
            pages = {
                int(item.get("page") or 0)
                for item in _dicts(table.get("source_parts"))
                if item.get("page")
            }
            header_rows = [
                row
                for row in _dicts(table.get("ordered_rows"))
                if row.get("role") == "COLUMN_HEADER"
            ]
            header_refs = {
                _anchor_word_ref(anchors[anchor_id])
                for row in header_rows
                for entry in _dicts(row.get("entries"))
                for anchor_id in _strings(entry.get("source_anchor_ids"))
                if anchor_id in anchors
            }
            if pages == {visual_page} and header_refs == visual_refs:
                matches.append((copy.deepcopy(visual), copy.deepcopy(table)))
    if not matches:
        raise TableScopedRoleResearchError("table_scope_header_not_matched")
    if len(matches) != 1:
        raise TableScopedRoleResearchError("table_scope_header_ambiguous")
    visual, table = matches[0]
    title_refs = _required_unique_strings(visual.get("title_word_refs"))
    if not title_refs:
        raise TableScopedRoleResearchError("table_scope_title_required")
    if bound_visual_projection.get("source_sha256") not in {None, source_checksum_sha256}:
        raise TableScopedRoleResearchError("table_scope_visual_source_mismatch")
    return visual, table


def _validate_global_partition(
    *,
    recovery: Mapping[str, Any],
    words: Mapping[str, dict[str, Any]],
    anchors: Mapping[str, dict[str, Any]],
    ownership: list[dict[str, Any]],
) -> set[str]:
    if recovery.get("unowned_word_refs") != []:
        raise TableScopedRoleResearchError("table_scope_global_unowned_words")
    anchor_ids = [str(item.get("source_anchor_id") or "") for item in ownership]
    if any(not item for item in anchor_ids) or len(anchor_ids) != len(set(anchor_ids)):
        raise TableScopedRoleResearchError("table_scope_global_ownership_invalid")
    table_word_refs = {
        _anchor_word_ref(anchors[anchor_id])
        for anchor_id in anchor_ids
        if anchor_id in anchors
    }
    paragraph_refs = set(
        _required_unique_strings(recovery.get("paragraph_owned_word_refs"))
    )
    if (
        len(table_word_refs) != len(anchor_ids)
        or not table_word_refs <= set(words)
        or table_word_refs & paragraph_refs
        or table_word_refs | paragraph_refs != set(words)
    ):
        raise TableScopedRoleResearchError("table_scope_global_partition_invalid")
    return table_word_refs


def _canonical_source_units(
    *,
    source_units: list[dict[str, Any]],
    words: Mapping[str, dict[str, Any]],
    page_number_by_ref: Mapping[str, int],
    complement_refs: set[str],
    title_refs: set[str],
) -> list[dict[str, Any]]:
    visual_units = [
        copy.deepcopy(unit)
        for unit in source_units
        if isinstance(unit, dict)
        and unit.get("pdf_unit_type") == "pdf_visual_page_unit"
    ]
    visual_by_page = {
        int(_object(unit.get("source_location")).get("page") or 0): unit
        for unit in visual_units
    }
    if not visual_by_page:
        raise TableScopedRoleResearchError("table_scope_visual_units_missing")
    identity_unit = visual_units[0]
    page_by_word_ref = {
        ref: page_number_by_ref.get(str(word.get("page_ref") or ""), 0)
        for ref, word in words.items()
    }
    if any(page < 1 for page in page_by_word_ref.values()):
        raise TableScopedRoleResearchError("table_scope_word_page_invalid")

    result = visual_units

    def add_text_unit(kind: str, page: int, refs: set[str]) -> None:
        if not refs:
            return
        ordered = _ordered_word_refs(refs, words)
        digest = _stable_sha256([kind, page, ordered])[:24]
        result.append(
            {
                "unit_ref": f"tablescope_{kind}_{digest}",
                "document_id": identity_unit.get("document_id"),
                "parent_payload_ref": identity_unit.get("parent_payload_ref"),
                "normalization_run_id": identity_unit.get("normalization_run_id"),
                "source_location": {
                    "kind": "pdf_text_layer",
                    "page": page,
                    "line_start": 1,
                },
                "text": " ".join(str(words[ref].get("text") or "") for ref in ordered),
                "coverage": {"selected_source_refs": ordered},
                "research_scope": "TABLE_SCOPED_RESEARCH_ONLY",
            }
        )

    title_pages = {page_by_word_ref[ref] for ref in title_refs}
    if len(title_pages) != 1:
        raise TableScopedRoleResearchError("table_scope_title_page_invalid")
    add_text_unit("title", next(iter(title_pages)), title_refs)
    remainder = complement_refs - title_refs
    for page in sorted(set(page_by_word_ref[ref] for ref in remainder)):
        add_text_unit(
            "remainder",
            page,
            {ref for ref in remainder if page_by_word_ref[ref] == page},
        )
    return result


def _word_inventory(
    payloads: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    words: dict[str, dict[str, Any]] = {}
    page_number_by_ref: dict[str, int] = {}
    for payload in payloads:
        projection = _object(_object(payload).get("pdf_text_layer_projection"))
        for page in _dicts(projection.get("page_inventory")):
            page_ref = str(page.get("page_ref") or "")
            page_number = int(page.get("page_number") or 0)
            if not page_ref or page_number < 1 or page_ref in page_number_by_ref:
                raise TableScopedRoleResearchError("table_scope_page_inventory_invalid")
            page_number_by_ref[page_ref] = page_number
        for word in _dicts(projection.get("word_inventory")):
            word_ref = str(word.get("word_ref") or "")
            if not word_ref or word_ref in words:
                raise TableScopedRoleResearchError("table_scope_word_inventory_invalid")
            words[word_ref] = copy.deepcopy(word)
    if not words:
        raise TableScopedRoleResearchError("table_scope_word_inventory_empty")
    return words, page_number_by_ref


def _index_unique(value: Any, key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _dicts(value):
        ref = str(item.get(key) or "")
        if not ref or ref in result:
            raise TableScopedRoleResearchError("table_scope_index_invalid")
        result[ref] = copy.deepcopy(item)
    return result


def _anchor_word_ref(anchor: Mapping[str, Any]) -> str:
    ref = str(_object(anchor.get("locator")).get("source_block_ref") or "")
    if not ref:
        raise TableScopedRoleResearchError("table_scope_anchor_invalid")
    return ref


def _ordered_word_refs(
    refs: set[str], words: Mapping[str, dict[str, Any]]
) -> list[str]:
    return sorted(
        refs,
        key=lambda ref: (
            str(words[ref].get("page_ref") or ""),
            int(words[ref].get("parser_ordinal") or 0),
            ref,
        ),
    )


def _nested_refs(value: Any, key: str) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for name, item in value.items():
            if name == key and isinstance(item, list):
                result.update(str(ref) for ref in item if str(ref))
            else:
                result.update(_nested_refs(item, key))
    elif isinstance(value, list):
        for item in value:
            result.update(_nested_refs(item, key))
    return result


def _required_unique_strings(value: Any) -> list[str]:
    result = _strings(value)
    if not result or len(result) != len(set(result)):
        raise TableScopedRoleResearchError("table_scope_refs_invalid")
    return result


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)


def _stable_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "SCOPE_SCHEMA_VERSION",
    "TableScopedRoleResearchError",
    "TableScopedRoleResearchFactory",
    "TableScopedRoleResearchResult",
]
