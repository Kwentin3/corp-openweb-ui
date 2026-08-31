from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from decimal import Decimal

from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.canonical_store import (
    CanonicalArtifactStoreFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
)
from broker_reports_gate1.normalizer import Gate1Normalizer
from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
    structural_fingerprint,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    CRITIC_RESPONSE_SCHEMA_VERSION,
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.pdf_table_intake_runtime import (
    PdfTableIntakeConfig,
    PdfTableIntakeRuntimeFactory,
)

import test_broker_reports_pdf_table_intake_gate1 as tbank_fixtures
import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_broker_reports_issue312_mapping_case as case_fixtures
from test_broker_reports_issue312_mapping_runtime import BoundaryModelClient


def _tbank_canonical(
    *, tenant_id: str = "tenant", source_artifact_ref: str = "tbank-semantic-source"
) -> dict:
    pdf_bytes, digest = tbank_fixtures._public_tbank_control()
    provider = tbank_fixtures.FrozenPageDetectorProvider(
        tbank_fixtures.TBANK_FROZEN_LOCATOR_V2
    )
    intake = (
        PdfTableIntakeRuntimeFactory(PdfTableIntakeConfig(enabled=True))
        .create_with_provider(provider)
        .run(
            [
                {
                    "document_ref": "tbank-semantic-seam",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": digest,
                }
            ]
        )
    )
    normalized = Gate1Normalizer().normalize(
        [tbank_fixtures._tbank_input(pdf_bytes)],
        pdf_table_locator_pages_by_sha256={digest: intake.private_page_results},
    )
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="tbank-semantic-seam-v1")
    ).create().build(
        tenant_id=tenant_id,
        artifact_version=1,
        document=normalized.package["document_inventory"]["documents"][0],
        source_artifact_ref=source_artifact_ref,
        source_payloads=normalized.package["private_normalized_source_payloads"],
        source_units=normalized.package["private_normalized_source_units"],
        table_projections=normalized.package["private_normalized_table_projections"],
    )


def _persist_tbank_canonical(tmp_path):
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "issue317-tbank-semantic-document"
    source_ref = "issue317-tbank-semantic-source"
    retention = build_retention_policy(mode="api_smoke")
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"openwebui_file_id": "public-tbank-control"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"public_control": True},
        )
    )
    canonical = _tbank_canonical(
        tenant_id=context.user_id,
        source_artifact_ref=source_ref,
    )
    persisted = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=canonical,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="issue317-semantic-test",
        reason="prove Canonical semantic seam",
    )
    return store, context, document_id, persisted.artifact_ref


def _binding(canonical: dict) -> dict[str, str]:
    source = canonical["source"]
    return {
        "document_id": "tbank-semantic-document",
        "canonical_version_id": canonical["artifact_id"],
        "canonical_root_sha256": canonical["canonical_root_hash"],
        "source_artifact_ref": source["source_artifact_ref"],
        "source_sha256": source["source_sha256"],
    }


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_tbank_semantic_view_uses_proven_canonical_table_structure() -> None:
    canonical = _tbank_canonical()
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    package = semantic.build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
    )

    assert len(tables) == len(package["case"]["tables"]) == 15
    assert sum(len(table["content"]["cells"]) for table in tables) == 485
    assert all(table["content"]["title"] for table in tables)
    assert "RUB" in {table["content"]["title"] for table in tables}
    for canonical_table, model_table in zip(
        tables, package["case"]["tables"], strict=True
    ):
        assert model_table["title"] == canonical_table["content"]["title"]
        assert [item["literal"] for item in model_table["header"]] == (
            canonical_table["content"]["header"]
        )
        assert "cells" not in model_table
        assert "header_row" not in model_table
        assert model_table["header_row_count"] >= 1
        assert model_table["rows_total"] == len(canonical_table["content"]["rows"])

    critic_package = semantic.build_critic_package(
        mapping_package=package,
        proposal_response={
            "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
            "status": "SPECIALIST_REVIEW_REQUIRED",
            "table_decisions": [],
            "clarification": None,
            "message": "Review required.",
        },
    )
    assert critic_package["case"] == package["case"]
    assert _sha256_json(critic_package["case"]) == _sha256_json(package["case"])


def test_semantic_view_accepts_a_fully_spanned_final_body_row(tmp_path) -> None:
    _store, _context, _document_id, source, *_rest = case_fixtures._unknown_case(
        tmp_path
    )
    canonical = copy.deepcopy(source)
    table = next(node for node in canonical["nodes"] if node["node_type"] == "TABLE")
    if not table["content"]["header"]:
        table["content"]["header"] = copy.deepcopy(table["content"]["rows"][0])
        table["content"]["rows"] = copy.deepcopy(table["content"]["rows"][1:])
    source_ref = table["source_refs"][0]
    locator = next(
        item["source_locator"]
        for item in canonical["provenance"]
        if item["provenance_id"] == source_ref
    )
    locator["table_header_binding"] = {"bound_header_row_count": 1}
    cells = table["content"]["cells"]
    final_row = max(cell["row"] for cell in cells)
    spanning_row = final_row - 1
    table["content"]["rows"][-1] = copy.deepcopy(
        table["content"]["rows"][-2]
    )
    table["content"]["cells"] = [
        cell for cell in cells if cell["row"] != final_row
    ]
    for cell in table["content"]["cells"]:
        if cell["row"] == spanning_row:
            cell["row_span"] = 2

    package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
    )

    assert package["case"]["tables"][0]["rows_total"] == len(
        table["content"]["rows"]
    )


def test_tbank_current_compiler_characterization_is_zero_records_five_unmapped() -> None:
    canonical = _tbank_canonical()
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    provenance = {
        item["provenance_id"]: item["source_locator"]
        for item in canonical["provenance"]
    }
    resolutions = []
    for index, table in enumerate(tables):
        headers = [
            {"column": column, "literal": str(literal or "")}
            for column, literal in enumerate(table["content"]["header"], start=1)
        ]
        header_count = provenance[table["source_refs"][0]][
            "table_header_binding"
        ]["bound_header_row_count"]
        resolutions.append(
            {
                "table_node_id": table["node_id"],
                "header_row": header_count,
                "structural_fingerprint": structural_fingerprint(
                    title_literal=None,
                    columns=[
                        {
                            "column": item["column"],
                            "header_literal": item["literal"],
                        }
                        for item in headers
                    ],
                ),
                "evidence_surface": {
                    "title_literal": None,
                    "headers": headers,
                },
                "disposition": (
                    "UNSUPPORTED_FINANCIAL_MEANING"
                    if index == 0
                    else "NO_NAMED_CONSUMER"
                ),
            }
        )
    projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=canonical,
        canonical_binding=_binding(canonical),
        mappings=OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings(),
        table_resolutions=resolutions,
    )
    assert projection["runtime_records"] == []
    relevant = [
        item
        for item in projection["source_observations"]
        if item["disposition"] == "RELEVANT_UNMAPPED"
    ]
    assert len(relevant) == 5
    assert {item["reason_code"] for item in relevant} == {
        "UNSUPPORTED_FINANCIAL_MEANING"
    }


def test_tbank_two_phase_runtime_stops_on_unowned_clearing_fee(tmp_path) -> None:
    store, context, _document_id, canonical_ref = _persist_tbank_canonical(tmp_path)
    proposal = {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": f"table_{index}",
                "disposition": "NO_NAMED_CONSUMER",
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
            }
            for index in range(1, 16)
        ],
        "clarification": None,
        "message": "Initial proposal would exclude all tables.",
    }
    reviewed = {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "SPECIALIST_REVIEW_REQUIRED",
        "table_decisions": [],
        "clarification": None,
        "message": (
            "The trade rows contain a third clearing-fee amount column. "
            "Its five literals total 0.20 RUB and no admitted compiler role owns it."
        ),
    }
    proposal_client = BoundaryModelClient([proposal])
    critic_client = BoundaryModelClient(
        [
            {
                "schema_version": CRITIC_RESPONSE_SCHEMA_VERSION,
                "verdict": "REJECT_UNSAFE",
                "reviewed_response": reviewed,
                "message": "The proposed exclusion would silently lose a fee.",
            }
        ]
    )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        mapping_model_client=proposal_client,
        mapping_critic_model_client=critic_client,
        mapping_answer_model_client=BoundaryModelClient([]),
        mapping_model_id="models/gemini-3.5-flash",
        mapping_provider_profile_id="google_gemini",
    ).create()

    result = asyncio.run(
        runtime.run_with_automatic_mapping(
            canonical_artifact_refs=[canonical_ref],
            context=context,
        )
    )

    assert result["semantic_mapping"]["status"] == "SPECIALIST_REVIEW_REQUIRED"
    assert result["provider_calls_total"] == 2
    assert result["product"]["gate4"]["facts_total"] == 0
    proposal_package = proposal_client.calls[0]["package"]
    assert proposal_package["case"] == critic_client.calls[0]["package"]["case"]
    assert all(
        "header_row" not in decision for decision in proposal["table_decisions"]
    )

    trade_table = proposal_package["case"]["tables"][0]
    clearing_header = next(
        item for item in trade_table["header"] if item["column"] == 22
    )
    canonical_trade_table = next(
        node for node in _tbank_canonical()["nodes"] if node["node_type"] == "TABLE"
    )
    assert clearing_header["literal"] == canonical_trade_table["content"]["header"][21]
    assert clearing_header["literal"]
    clearing_literals = [
        next(cell for cell in row["cells"] if cell["column"] == 22)["literal"]
        for row in trade_table["rows"]
    ]
    clearing_currencies = [
        next(cell for cell in row["cells"] if cell["column"] == 23)["literal"]
        for row in trade_table["rows"]
    ]
    assert clearing_literals == ["0.03", "0.03", "0.03", "0.08", "0.03"]
    assert clearing_currencies == ["RUB"] * 5
    assert sum(map(Decimal, clearing_literals), Decimal("0")) == Decimal("0.20")

    semantic_hash = _sha256_json(proposal_package["case"])
    mapping_cases = store.list_by_type(
        context.normalization_run_id,
        "broker_reports_ordinary_trade_mapping_case_v3",
    )
    assert len(mapping_cases) == 1
    assert store.read_payload(mapping_cases[0])["semantic_evidence_sha256"] == (
        semantic_hash
    )
