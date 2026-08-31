from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from decimal import Decimal

import pytest

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
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerError,
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
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


def _tbank_complete_mapping_response(mapping_package: dict) -> dict:
    roles = (
        "trade_id",
        "unmapped",
        "unmapped",
        "trade_date",
        "trade_time",
        "description",
        "venue",
        "side",
        "asset_name",
        "security_code",
        "unit_price",
        "currency",
        "quantity",
        "unmapped",
        "accrued_interest",
        "gross_amount",
        "currency",
        "broker_commission",
        "currency",
        "exchange_commission",
        "currency",
        "retained_transaction_charge",
        "currency",
        "unmapped",
        "description",
        "settlement_date",
        "unmapped",
        "status",
        "unmapped",
        "unmapped",
        "unmapped",
        "comment",
    )
    trade_table = mapping_package["case"]["tables"][0]
    side_literal = next(
        cell["literal"]
        for row in trade_table["rows"]
        for cell in row["cells"]
        if cell["column"] == 8 and cell["literal"]
    )
    decisions = [
        {
            "table_ref": "table_1",
            "disposition": "SECURITY_TRADES",
            "columns": [
                {"column": column, "semantic_role": role}
                for column, role in enumerate(roles, start=1)
            ],
            "amount_currency_bindings": [
                {"amount_column": 16, "currency_column": 17},
                {"amount_column": 18, "currency_column": 19},
                {"amount_column": 20, "currency_column": 21},
                {"amount_column": 22, "currency_column": 23},
            ],
            "side_values": [
                {"source_literal": side_literal, "normalized_value": "PURCHASE"}
            ],
        }
    ]
    decisions.extend(
        {
            "table_ref": f"table_{index}",
            "disposition": "NO_NAMED_CONSUMER",
            "columns": [],
            "amount_currency_bindings": [],
            "side_values": [],
        }
        for index in range(2, 16)
    )
    return {
        "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": decisions,
        "clarification": None,
        "message": "Complete document-wide mapping with retained clearing charges.",
    }


def _all_strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_all_strings(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_strings(item) for item in value), set())
    return set()


def _retained_mapping(*, bindings: list[dict[str, int]]) -> dict:
    headers = (
        "Asset",
        "Trade date",
        "Side",
        "Quantity",
        "Unit price",
        "Currency",
        "Gross amount",
        "Retained transaction charge",
    )
    roles = (
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "unit_price",
        "currency",
        "gross_amount",
        "retained_transaction_charge",
    )
    return compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": column, "literal": literal}
            for column, literal in enumerate(headers, start=1)
        ],
        model_columns=[
            {"column": column, "semantic_role": role}
            for column, role in enumerate(roles, start=1)
        ],
        amount_currency_bindings=bindings,
        side_values=[{"source_literal": "Buy", "normalized_value": "PURCHASE"}],
        qualification_ref={
            "qualification_id": "otqual_retained_charge_contract",
            "receipt_sha256": "a" * 64,
        },
    )


def test_retained_charge_requires_one_exact_currency_binding() -> None:
    valid = [
        {"amount_column": 7, "currency_column": 6},
        {"amount_column": 8, "currency_column": 6},
    ]
    mapping = _retained_mapping(bindings=valid)
    assert mapping["amount_currency_bindings"] == valid

    invalid_bindings = (
        [valid[0]],
        [*valid, valid[1]],
        [valid[0], {"amount_column": 8, "currency_column": 5}],
    )
    for bindings in invalid_bindings:
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as failure:
            _retained_mapping(bindings=bindings)
        assert failure.value.code == "ordinary_trade_mapping_currency_binding_invalid"


def test_existing_qualified_mapping_receipts_remain_byte_compatible() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    assert [
        item["receipt_sha256"] for item in authority.list_qualification_receipts()
    ] == [
        "cef0a8f0b181f207ee05005672e2d73a5abce02652589baf8133331b2b3c9c84",
        "26780d84ff7f2dab04ccea9e3d5587f94674aace1adff8010f35989ee059cdfd",
    ]


def test_tbank_semantic_response_rejects_bad_retained_currency_binding() -> None:
    canonical = _tbank_canonical()
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    package = semantic.build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
    )
    valid = _tbank_complete_mapping_response(package)
    invalid_responses = []

    missing = copy.deepcopy(valid)
    missing["table_decisions"][0]["amount_currency_bindings"] = [
        item
        for item in missing["table_decisions"][0]["amount_currency_bindings"]
        if item["amount_column"] != 22
    ]
    invalid_responses.append(missing)

    duplicate = copy.deepcopy(valid)
    duplicate["table_decisions"][0]["amount_currency_bindings"].append(
        {"amount_column": 22, "currency_column": 23}
    )
    invalid_responses.append(duplicate)

    wrong = copy.deepcopy(valid)
    next(
        item
        for item in wrong["table_decisions"][0]["amount_currency_bindings"]
        if item["amount_column"] == 22
    )["currency_column"] = 24
    invalid_responses.append(wrong)

    for response in invalid_responses:
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as failure:
            semantic.validate_mapping_response(
                response=response,
                canonical=canonical,
                canonical_binding=_binding(canonical),
                model_id="models/gemini-3.5-flash",
                provider_profile_id="google_gemini",
                execution_metadata=case_fixtures._metadata(),
                confirmed_understandings=[],
                user_scope_sha256="a" * 64,
                independent_review_confirmed=True,
            )
        assert failure.value.code == "ordinary_trade_mapping_currency_binding_invalid"


def test_retained_charge_row_is_unmapped_when_trade_or_currency_is_blank() -> None:
    source = _tbank_canonical()
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    package = semantic.build_mapping_package(
        canonical=source,
        confirmed_understandings=[],
    )
    outcome = semantic.validate_mapping_response(
        response=_tbank_complete_mapping_response(package),
        canonical=source,
        canonical_binding=_binding(source),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(),
        confirmed_understandings=[],
        user_scope_sha256="a" * 64,
        independent_review_confirmed=True,
    )
    mapping = outcome["qualified_mappings"][0]

    for blank_column in (9, 23):
        canonical = copy.deepcopy(source)
        table = next(
            node for node in canonical["nodes"] if node["node_type"] == "TABLE"
        )
        canonical["nodes"] = [table]
        table["content"]["rows"] = [copy.deepcopy(table["content"]["rows"][0])]
        table["content"]["rows"][0][blank_column - 1] = ""
        table["content"]["cells"] = [
            cell for cell in table["content"]["cells"] if cell["row"] <= 2
        ]
        blank = next(
            cell
            for cell in table["content"]["cells"]
            if cell["row"] == 2 and cell["column"] == blank_column
        )
        blank["value"] = ""
        blank["displayed_value"] = ""

        projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding=_binding(canonical),
            mappings=[],
            scoped_mappings=[
                {"table_node_id": table["node_id"], "mapping": mapping}
            ],
        )

        assert projection["runtime_records"] == []
        assert len(projection["source_observations"]) == 1
        observation = projection["source_observations"][0]
        assert observation["disposition"] == "RELEVANT_UNMAPPED"
        assert observation["reason_code"] == "ORDINARY_TRADE_ROW_CONTRACT_INCOMPLETE"
        retained = next(
            field
            for field in observation["fields"]
            if field["semantic_role"] == "retained_transaction_charge"
        )
        assert retained["canonical_cell"]["column"] == 22


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


def test_tbank_two_phase_runtime_retains_unconsumed_clearing_fee(tmp_path) -> None:
    store, context, _document_id, canonical_ref = _persist_tbank_canonical(tmp_path)
    canonical = _tbank_canonical()
    mapping_package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
    )
    proposal = _tbank_complete_mapping_response(mapping_package)
    proposal_client = BoundaryModelClient([proposal])
    critic_client = BoundaryModelClient(
        [
            {
                "schema_version": CRITIC_RESPONSE_SCHEMA_VERSION,
                "verdict": "APPROVE",
                "reviewed_response": copy.deepcopy(proposal),
                "message": "The complete mapping retains the unconsumed charge.",
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

    assert result["semantic_mapping"]["status"] == "COMPLETE"
    assert result["provider_calls_total"] == 2
    assert result["documents"][0]["runtime_ready_observations"] == 5
    assert result["documents"][0]["relevant_unmapped_observations"] == 0
    assert result["product"]["gate4"] == {
        "status": "candidate_projection_facts",
        "facts_total": 15,
        "security_facts_total": 5,
        "transaction_charge_facts_total": 10,
    }
    proposal_package = proposal_client.calls[0]["package"]
    assert proposal_package["case"] == critic_client.calls[0]["package"]["case"]
    assert proposal_package["case"] == mapping_package["case"]

    trade_table = proposal_package["case"]["tables"][0]
    clearing_header = next(
        item for item in trade_table["header"] if item["column"] == 22
    )
    canonical_trade_table = next(
        node for node in canonical["nodes"] if node["node_type"] == "TABLE"
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

    projection = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().current_case(context=context)[0][1]
    ready = [
        item
        for item in projection["source_observations"]
        if item["disposition"] == "RUNTIME_READY"
    ]
    retained = [
        field
        for observation in ready
        for field in observation["fields"]
        if field["semantic_role"] == "retained_transaction_charge"
    ]
    retained_currency = [
        field
        for observation in ready
        for field in observation["fields"]
        if field["semantic_role"] == "currency"
        and field["canonical_cell"]["column"] == 23
    ]
    assert [item["literal"] for item in retained] == clearing_literals
    assert [item["literal"] for item in retained_currency] == clearing_currencies
    assert len({item["source_ref"] for item in retained}) == 5
    assert {item["canonical_cell"]["column"] for item in retained} == {22}
    assert {item["canonical_cell"]["column"] for item in retained_currency} == {23}
    assert len(projection["runtime_records"]) == 15
    assert [
        item["record_type"] for item in projection["runtime_records"]
    ].count("SECURITY_PURCHASE") == 5
    assert [
        item["record_type"] for item in projection["runtime_records"]
    ].count("TRANSACTION_CHARGE") == 10

    facts = Gate4OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create().list_facts(context=context)
    retained_refs = {item["source_ref"] for item in retained}
    assert retained_refs.isdisjoint(_all_strings(projection["runtime_records"]))
    assert retained_refs.isdisjoint(_all_strings(facts))

    mapping_cases = store.list_by_type(
        context.normalization_run_id,
        "broker_reports_ordinary_trade_mapping_case_v3",
    )
    assert len(mapping_cases) == 1
    case_payload = store.read_payload(mapping_cases[0])
    receipt = case_payload["qualification_receipts"][0]
    clearing_claim = next(
        claim for claim in receipt["relation_claims"] if claim["amount_column"] == 22
    )
    assert clearing_claim["currency_column"] == 23
    assert clearing_claim["consumer_contract"] == (
        "broker_reports_source_observation_v1.retained_amount_currency"
    )

    semantic_hash = _sha256_json(proposal_package["case"])
    assert store.read_payload(mapping_cases[0])["semantic_evidence_sha256"] == (
        semantic_hash
    )
