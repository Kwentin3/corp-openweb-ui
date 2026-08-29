from __future__ import annotations

import copy
import hashlib
import inspect
import json
from collections import Counter
from dataclasses import fields
from typing import Any

import pytest

from broker_reports_gate1.canonical_artifact import (
    CanonicalArtifactError,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    MANAGED_ENTRY_BINDING_SCHEMA_VERSION,
)
from broker_reports_gate1.managed_pdf_to_canonical import (
    ManagedPdfToCanonicalFactory,
)
from broker_reports_gate1.managed_document_contracts import (
    compute_document_integrity_sha256,
)
from broker_reports_gate1.managed_pdf_document_v2 import (
    ManagedPdfDocumentV2AdjudicatedBuildResult,
    ManagedPdfDocumentV2Factory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingFactory,
)
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
    _schema,
    _source_bound_case,
    _two_page_observations,
)
from tests.test_broker_reports_managed_whole_table_projection import (
    _headerless_pdf_with_paragraph,
)


def _adjudicated_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pdf_bytes: bytes,
    source_ref: str,
    observations: dict[str, Any],
):
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        return (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id=f"{source_ref}_canonical",
            )
        )


def _canonical_handoff(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pdf_bytes: bytes,
    source_ref: str,
    observations: dict[str, Any],
):
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        return (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            ._build_owned_source_for_canonical(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id=f"{source_ref}_canonical",
            )
        )


def _canonical_from_handoff(
    handoff,
    *,
    source_ref: str,
    managed_payload: dict[str, Any] | None = None,
    projections: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    assert handoff.result.managed_document is not None
    return (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="managed-canonical-test")
        )
        .create()
        ._build_pdf_from_managed_whole_table_projections(
            tenant_id="tenant",
            artifact_version=1,
            document=handoff.source_document,
            source_artifact_ref=source_ref,
            source_payloads=list(handoff.source_payloads),
            source_units=list(handoff.source_units),
            managed_document_payload=(
                handoff.result.managed_document.payload
                if managed_payload is None
                else managed_payload
            ),
            managed_whole_table_projections=(
                handoff.result.whole_table_projections
                if projections is None
                else projections
            ),
        )
    )


def _canonical_route_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pdf_bytes: bytes,
    source_ref: str,
    observations: dict[str, Any],
):
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        return (
            ManagedPdfToCanonicalFactory()
            .create_for_openwebui(
                _schema(),
                request,
                normalizer_config=CanonicalNormalizerConfig(
                    normalizer_version="managed-canonical-test"
                ),
            )
            .build(
                pdf_bytes,
                tenant_id="tenant",
                artifact_version=1,
                source_artifact_ref=source_ref,
                task_id=f"{source_ref}_canonical",
            )
        )


def _table_nodes(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in artifact["nodes"] if node["node_type"] == "TABLE"]


def _text_nodes(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in artifact["nodes"] if node["node_type"] == "TEXT"]


def _pdf_receipt(artifact: dict[str, Any]) -> dict[str, Any]:
    root = next(
        container
        for container in artifact["containers"]
        if container["container_id"] == artifact["root_container_ref"]
    )
    return root["metadata"]["pdf_completeness"]


def _table_source_locator(
    artifact: dict[str, Any],
    table: dict[str, Any],
) -> dict[str, Any]:
    provenance_by_id = {
        item["provenance_id"]: item for item in artifact["provenance"]
    }
    return provenance_by_id[table["source_refs"][0]]["source_locator"]


def _managed_entry_locators(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    locators = [
        item["source_locator"]
        for item in artifact["provenance"]
        if item["source_locator"].get("kind") == "managed_whole_table_entry"
    ]
    return {str(locator["managed_entry_id"]): locator for locator in locators}


def _reseal_projection(projection: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(projection)
    result.pop("projection_integrity_sha256", None)
    result["projection_integrity_sha256"] = hashlib.sha256(
        json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return result


def _synchronized_table_mutation(
    handoff,
    mutator,
) -> tuple[dict[str, Any], dict[str, Any]]:
    assert handoff.result.managed_document is not None
    managed_payload = copy.deepcopy(handoff.result.managed_document.payload)
    projection = copy.deepcopy(handoff.result.whole_table_projections[0])
    managed_table = next(
        block["content"]
        for block in managed_payload["blocks"]
        if block["block_type"] == "TABLE"
        and block["content"]["table_id"] == projection["table_id"]
    )
    mutator(managed_table)
    mutator(projection)
    managed_payload["integrity_sha256"] = compute_document_integrity_sha256(
        managed_payload
    )
    projection["managed_document_integrity_sha256"] = managed_payload[
        "integrity_sha256"
    ]
    return managed_payload, _reseal_projection(projection)


def _binding_handoff(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source_ref: str,
):
    pdf_bytes, _, _ = _source_bound_case(
        second_header_labels=("Instrument", "Currency")
    )
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    return _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=_two_page_observations(payload, repeated_header=True),
    )


def test_headerless_continuation_and_outside_paragraph_build_one_canonical_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = "private_pdf_managed_canonical_headerless"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(observation_payload)

    route = _canonical_route_result(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = route.managed_result
    artifact = route.canonical_artifact
    assert artifact is not None

    assert route.status == "COMPLETE"
    assert route.safe_diagnostics["canonical_artifacts_created"] == 1
    assert result.status == "COMPLETE"
    assert result.safe_diagnostics["whole_table_projection_status"] == "READY"
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0
    tables = _table_nodes(artifact)
    assert len(tables) == 1
    table = tables[0]["content"]
    assert table["header"] == ["Item", "Amount"]
    assert table["rows"] == [
        ["Cash", "10"],
        ["Bonds", "20"],
        ["Funds", "30"],
        ["Shares", "40"],
        ["Options", "50"],
    ]
    assert len(table["metadata"]["source_parts"]) == 2
    assert [node["content"]["text"] for node in _text_nodes(artifact)] == [
        "Portfolio note outside grid"
    ]
    assert all(
        "Item Amount" not in node["content"]["text"]
        for node in _text_nodes(artifact)
    )
    receipt = _pdf_receipt(artifact)
    assert receipt["source_atom_accounting_percent"] == 100.0
    assert receipt["unresolved_source_atoms_total"] == 0
    assert receipt["table_node_count"] == 1
    assert receipt["managed_whole_table_projections_total"] == 1
    assert receipt["represented_managed_whole_table_projection_units_total"] == 2
    mapping_package = (
        OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
            canonical=artifact,
            confirmed_understandings=[],
        )
    )
    assert [
        row["row"] for row in mapping_package["case"]["tables"][0]["rows"]
    ] == [1, 2, 3, 4, 5, 6]


def test_repeated_header_keeps_managed_role_and_is_not_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, _, _ = _source_bound_case(
        second_header_labels=("Instrument", "Currency")
    )
    source_ref = "private_pdf_managed_canonical_repeated_header"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(
        observation_payload,
        repeated_header=True,
    )

    route = _canonical_route_result(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = route.managed_result
    artifact = route.canonical_artifact
    assert artifact is not None

    table = _table_nodes(artifact)[0]["content"]
    projection_rows = result.whole_table_projections[0]["ordered_rows"]
    assert [
        item["role"] for item in table["metadata"]["managed_row_sequence"]
    ] == [row["role"] for row in projection_rows]
    assert table["header"] == ["Instrument", "Currency"]
    assert ["Instrument", "Currency"] not in table["rows"]
    assert table["rows"] == [
        ["Cash", "RUB"],
        ["Bonds", "RUB"],
        ["LKOH", "RUB"],
        ["ROSN", "RUB"],
    ]
    mapping_package = (
        OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
            canonical=artifact,
            confirmed_understandings=[],
        )
    )
    assert [
        row["row"] for row in mapping_package["case"]["tables"][0]["rows"]
    ] == [1, 2, 3, 5, 6]


def test_canonical_provenance_preserves_direct_owner_column_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_ref = "private_pdf_managed_canonical_direct_bindings"
    handoff = _binding_handoff(monkeypatch, source_ref=source_ref)
    artifact = _canonical_from_handoff(handoff, source_ref=source_ref)
    projection = handoff.result.whole_table_projections[0]
    locators = _managed_entry_locators(artifact)

    for row in projection["ordered_rows"]:
        for entry in row["entries"]:
            locator = locators[entry["entry_id"]]
            assert locator["managed_entry_binding_schema_version"] == (
                MANAGED_ENTRY_BINDING_SCHEMA_VERSION
            )
            assert locator["managed_logical_column_id"] == entry[
                "logical_column_id"
            ]
            assert locator["managed_covers_logical_column_ids"] == entry[
                "covers_logical_column_ids"
            ]
            assert locator["managed_column_binding_status"] == entry[
                "column_binding_status"
            ]


def test_canonical_provenance_preserves_owner_spanning_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_ref = "private_pdf_managed_canonical_spanning_binding"
    handoff = _binding_handoff(monkeypatch, source_ref=source_ref)
    original = handoff.result.whole_table_projections[0]
    column_ids = [column["column_id"] for column in original["logical_columns"]]
    entry_id = original["ordered_rows"][0]["entries"][0]["entry_id"]

    def span(table: dict[str, Any]) -> None:
        entry = table["ordered_rows"][0]["entries"][0]
        entry["covers_logical_column_ids"] = list(column_ids)
        entry["column_binding_status"] = "BOUND"
        table["logical_columns"][1]["header_path"].insert(0, entry["entry_id"])

    managed_payload, projection = _synchronized_table_mutation(handoff, span)
    artifact = _canonical_from_handoff(
        handoff,
        source_ref=source_ref,
        managed_payload=managed_payload,
        projections=(projection,),
    )
    locator = _managed_entry_locators(artifact)[entry_id]
    assert locator["managed_logical_column_id"] == column_ids[0]
    assert locator["managed_covers_logical_column_ids"] == column_ids
    assert locator["managed_column_binding_status"] == "BOUND"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            "missing_logical_id",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "missing_status",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "foreign",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "duplicate_covers",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "singleton_covers",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "reordered_covers",
            "canonical_managed_whole_table_projection_entry_binding_invalid",
        ),
        (
            "swapped_header_paths",
            "canonical_managed_whole_table_projection_header_path_invalid",
        ),
        (
            "empty_header_path",
            "canonical_managed_whole_table_projection_header_path_invalid",
        ),
    ],
)
def test_self_consistent_invalid_owner_binding_blocks_canonical_candidate(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_code: str,
) -> None:
    source_ref = f"private_pdf_managed_canonical_binding_{mutation}"
    handoff = _binding_handoff(monkeypatch, source_ref=source_ref)

    def mutate(table: dict[str, Any]) -> None:
        entry = table["ordered_rows"][0]["entries"][0]
        column_ids = [column["column_id"] for column in table["logical_columns"]]
        if mutation == "missing_logical_id":
            entry.pop("logical_column_id")
        elif mutation == "missing_status":
            entry.pop("column_binding_status")
        elif mutation == "foreign":
            entry["covers_logical_column_ids"] = ["column_foreign"]
        elif mutation == "duplicate_covers":
            entry["covers_logical_column_ids"] = [column_ids[0], column_ids[0]]
        elif mutation == "singleton_covers":
            entry["covers_logical_column_ids"] = [column_ids[0]]
        elif mutation == "reordered_covers":
            entry["covers_logical_column_ids"] = list(reversed(column_ids))
        elif mutation == "swapped_header_paths":
            first, second = table["logical_columns"][:2]
            first["header_path"], second["header_path"] = (
                second["header_path"],
                first["header_path"],
            )
        else:
            for row in table["ordered_rows"]:
                if row["role"] in {"COLUMN_HEADER", "CONTINUATION_HEADER"}:
                    header_entry = row["entries"][0]
                    header_entry["logical_column_id"] = None
                    header_entry["covers_logical_column_ids"] = []
                    header_entry["column_binding_status"] = "NOT_APPLICABLE"
            table["logical_columns"][0]["header_path"] = []

    managed_payload, projection = _synchronized_table_mutation(handoff, mutate)
    with pytest.raises(CanonicalArtifactError) as exc:
        _canonical_from_handoff(
            handoff,
            source_ref=source_ref,
            managed_payload=managed_payload,
            projections=(projection,),
        )
    assert exc.value.code == expected_code


def test_distinct_titled_similar_tables_build_two_canonical_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, _, _ = _source_bound_case(distinct_second_title=True)
    source_ref = "private_pdf_managed_canonical_distinct_titles"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(
        observation_payload,
        second_title=True,
    )

    route = _canonical_route_result(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = route.managed_result
    artifact = route.canonical_artifact
    assert artifact is not None

    tables = _table_nodes(artifact)
    assert len(tables) == 2
    assert len(result.whole_table_projections) == 2
    titles = [table["content"]["title"] for table in tables]
    assert titles.count("Completed position transfers") == 1
    unit_counter: Counter[str] = Counter()
    atom_counter: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()
    for table in tables:
        locator = _table_source_locator(artifact, table)
        unit_counter.update(locator["source_unit_refs"])
        atom_counter.update(locator["source_atom_refs"])
        word_counter.update(locator["source_word_refs"])
    expected_units = Counter(
        ref
        for projection in result.whole_table_projections
        for ref in projection["covered_source_unit_refs"]
    )
    expected_atoms = Counter(
        ref
        for projection in result.whole_table_projections
        for ref in projection["covered_source_atom_refs"]
    )
    expected_words = Counter(
        ref
        for projection in result.whole_table_projections
        for ref in projection["covered_source_word_refs"]
    )
    assert unit_counter == expected_units
    assert atom_counter == expected_atoms
    assert word_counter == expected_words
    assert all(count == 1 for count in unit_counter.values())
    assert all(count == 1 for count in atom_counter.values())
    assert all(count == 1 for count in word_counter.values())


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            "partial",
            "canonical_managed_whole_table_projection_contract_invalid",
        ),
        (
            "unknown_unit",
            "canonical_managed_whole_table_projection_managed_mismatch",
        ),
        (
            "atom_mismatch",
            "canonical_managed_whole_table_projection_managed_mismatch",
        ),
        (
            "overlap",
            "canonical_managed_whole_table_projection_unit_overlap",
        ),
        (
            "invented_text",
            "canonical_managed_whole_table_projection_managed_mismatch",
        ),
    ],
)
def test_invalid_whole_projection_blocks_canonical_candidate(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_code: str,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = f"private_pdf_managed_canonical_invalid_{mutation}"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(observation_payload)
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = handoff.result
    assert result.managed_document is not None
    projection = copy.deepcopy(result.whole_table_projections[0])
    projections = [projection]
    if mutation == "partial":
        projection["completeness_status"] = "PARTIAL"
        projections[0] = _reseal_projection(projection)
    elif mutation == "unknown_unit":
        projection["covered_source_unit_refs"][0] = "srcunit_unknown"
        projection["source_parts"][0]["covered_source_units"][0][
            "unit_ref"
        ] = "srcunit_unknown"
        projections[0] = _reseal_projection(projection)
    elif mutation == "atom_mismatch":
        projection["source_parts"][0]["covered_source_units"][0][
            "selected_source_atom_refs"
        ][0] = "textseg_unknown"
        projection["covered_source_atom_refs"] = sorted(
            atom
            for part in projection["source_parts"]
            for unit in part["covered_source_units"]
            for atom in unit["selected_source_atom_refs"]
        )
        projections[0] = _reseal_projection(projection)
    elif mutation == "invented_text":
        projection["ordered_rows"][1]["entries"][0]["text"] = (
            "INVENTED_SECRET_VALUE"
        )
        projections[0] = _reseal_projection(projection)
    else:
        projections = [
            _reseal_projection(projection),
            _reseal_projection(projection),
        ]

    with pytest.raises(CanonicalArtifactError) as exc:
        (
            CanonicalNormalizerFactory(
                CanonicalNormalizerConfig(
                    normalizer_version="managed-canonical-test"
                )
            )
            .create()
            ._build_pdf_from_managed_whole_table_projections(
                tenant_id="tenant",
                artifact_version=1,
                document=handoff.source_document,
                source_artifact_ref=source_ref,
                source_payloads=list(handoff.source_payloads),
                source_units=list(handoff.source_units),
                managed_document_payload=result.managed_document.payload,
                managed_whole_table_projections=tuple(projections),
            )
        )
    assert exc.value.code == expected_code


def test_source_unit_atom_overlap_blocks_canonical_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = "private_pdf_managed_canonical_source_overlap"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(observation_payload)
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = handoff.result
    assert result.managed_document is not None
    source_units = copy.deepcopy(list(handoff.source_units))
    source_units[1]["coverage"]["selected_source_refs"][0] = source_units[0][
        "coverage"
    ]["selected_source_refs"][0]

    with pytest.raises(CanonicalArtifactError) as exc:
        (
            CanonicalNormalizerFactory(
                CanonicalNormalizerConfig(
                    normalizer_version="managed-canonical-test"
                )
            )
            .create()
            ._build_pdf_from_managed_whole_table_projections(
                tenant_id="tenant",
                artifact_version=1,
                document=handoff.source_document,
                source_artifact_ref=source_ref,
                source_payloads=list(handoff.source_payloads),
                source_units=source_units,
                managed_document_payload=result.managed_document.payload,
                managed_whole_table_projections=result.whole_table_projections,
            )
        )
    assert (
        exc.value.code
        == "canonical_managed_whole_table_projection_source_atom_overlap"
    )


def test_resealed_role_mutation_blocks_before_canonical_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = "private_pdf_managed_canonical_role_mutation"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(observation_payload)
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = handoff.result
    assert result.managed_document is not None
    projection = copy.deepcopy(result.whole_table_projections[0])
    projection["ordered_rows"][1]["role"] = "NOTE"

    with pytest.raises(CanonicalArtifactError) as exc:
        (
            CanonicalNormalizerFactory(
                CanonicalNormalizerConfig(
                    normalizer_version="managed-canonical-test"
                )
            )
            .create()
            ._build_pdf_from_managed_whole_table_projections(
                tenant_id="tenant",
                artifact_version=1,
                document=handoff.source_document,
                source_artifact_ref=source_ref,
                source_payloads=list(handoff.source_payloads),
                source_units=list(handoff.source_units),
                managed_document_payload=result.managed_document.payload,
                managed_whole_table_projections=(
                    _reseal_projection(projection),
                ),
            )
        )
    assert (
        exc.value.code
        == "canonical_managed_whole_table_projection_managed_mismatch"
    )


def test_foreign_source_ref_blocks_managed_to_canonical_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = "private_pdf_managed_canonical_source_ref"
    observation_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(observation_payload)
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations=observations,
    )
    result = handoff.result
    assert result.managed_document is not None

    with pytest.raises(CanonicalArtifactError) as exc:
        (
            CanonicalNormalizerFactory(
                CanonicalNormalizerConfig(
                    normalizer_version="managed-canonical-test"
                )
            )
            .create()
            ._build_pdf_from_managed_whole_table_projections(
                tenant_id="tenant",
                artifact_version=1,
                document=handoff.source_document,
                source_artifact_ref="foreign_source_ref",
                source_payloads=list(handoff.source_payloads),
                source_units=list(handoff.source_units),
                managed_document_payload=result.managed_document.payload,
                managed_whole_table_projections=result.whole_table_projections,
            )
        )
    assert (
        exc.value.code
        == "canonical_managed_whole_table_projection_managed_source_mismatch"
    )


def test_public_build_contract_stays_legacy_and_bridge_has_no_runtime_imports() -> None:
    import broker_reports_gate1.canonical_artifact as module

    normalizer = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="managed-canonical-test")
    ).create()
    public_parameters = inspect.signature(normalizer.build).parameters
    source = module.__loader__.get_source(module.__name__)  # type: ignore[attr-defined]

    assert list(public_parameters) == [
        "tenant_id",
        "artifact_version",
        "document",
        "source_artifact_ref",
        "source_payloads",
        "source_units",
        "table_projections",
        "created_at",
        "previous_version_ref",
    ]
    assert hasattr(normalizer, "_build_pdf_from_managed_whole_table_projections")
    assert "from .managed_pdf_document_v2" not in source
    assert "from .managed_whole_table_projection" not in source
    assert "CanonicalArtifactStore" not in source
    assert "put_candidate" not in source
    assert "Gate4" not in source
    assert "openwebui_actions" not in source


def test_same_call_route_does_not_accept_caller_source_or_projections() -> None:
    from broker_reports_gate1.managed_pdf_to_canonical import (
        ManagedPdfToCanonicalFactory,
    )

    request = _openwebui_request()
    builder = ManagedPdfToCanonicalFactory().create_for_openwebui(
        _schema(),
        request,
        normalizer_config=CanonicalNormalizerConfig(
            normalizer_version="managed-canonical-test"
        ),
    )
    route_parameters = inspect.signature(builder.build).parameters

    assert "source_payloads" not in route_parameters
    assert "source_units" not in route_parameters
    assert "managed_document_payload" not in route_parameters
    assert "managed_whole_table_projections" not in route_parameters
    public_result_fields = {
        field.name for field in fields(ManagedPdfDocumentV2AdjudicatedBuildResult)
    }
    assert "private_source_document" not in public_result_fields
    assert "private_source_payloads" not in public_result_fields
    assert "private_source_units" not in public_result_fields
