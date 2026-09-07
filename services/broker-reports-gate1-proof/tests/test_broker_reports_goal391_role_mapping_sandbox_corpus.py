"""Frozen, synthetic inputs for the Goal #391 role-mapping R&D sandbox.

The corpus deliberately owns no provider call, prompt, runtime path, or
financial interpretation.  It exercises the existing Canonical normalizer so
the sandbox can later consume the same immutable artefact shape as product
code.  Expected semantic outcomes live beside the source artefacts rather
than inside Canonical: Canonical remains non-financial evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    validate_canonical_artifact,
)


FROZEN_ROLE_MAPPING_CORPUS_VERSION = "goal391_role_mapping_sandbox_corpus_v1"


@dataclass(frozen=True)
class FrozenRoleMappingCorpusCase:
    """One public synthetic source and its external R&D expectation."""

    case_id: str
    expected_table_disposition: str
    canonical: dict
    frozen_fixture: dict[str, Any] | None = None
    known_strict_response: dict[str, Any] | None = None


def build_frozen_role_mapping_corpus() -> tuple[FrozenRoleMappingCorpusCase, ...]:
    """Build the minimal positive and negative Canonical inputs for R&D.

    This uses the sole CanonicalArtifactV1 construction authority directly;
    the structured expectation is intentionally not persisted in the artifact.
    """

    return (
        _golden_complete_trade_case(),
        _csv_case(
            case_id="synthetic_explicit_sale_columns",
            expected_table_disposition="SECURITY_TRADES",
            csv_text=(
                "Action,Date Acquired,Date Sold or Disposed,Quantity Sold,"
                "Proceeds,Cost or Other Basis,Currency\n"
                "Sale,2024-01-15,2025-02-03,10,1250.00,900.00,USD\n"
            ),
        ),
        _csv_case(
            case_id="synthetic_non_financial_note",
            expected_table_disposition="NO_NAMED_CONSUMER",
            csv_text=(
                "Section,Description,Value\n"
                "Notice,Educational example only,No transaction data\n"
            ),
        ),
    )


def _golden_complete_trade_case() -> FrozenRoleMappingCorpusCase:
    """A fixed positive answer, never derived from a model response at runtime.

    The fixture is deliberately small but contains every required ordinary-trade
    role, its explicit currency bindings, and the sole observed side literal.
    Its expected verdict (including the literal hash) was recorded from this
    hand-authored strict answer, rather than from a live qualification run.
    """

    case = _csv_case(
        case_id="synthetic_golden_complete_trade",
        expected_table_disposition="SECURITY_TRADES",
        csv_text=(
            "Action,Asset,Trade Date,Quantity,Unit Price,Gross Amount,"
            "Broker Commission,Exchange Commission,Currency\n"
            "Sale,ACME,2025-02-03,10,125.00,1250.00,2.00,1.00,USD\n"
        ),
    )
    response = {
        "schema_version": "broker_reports_ordinary_trade_semantic_mapping_response_v4",
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": "table_1",
                "header_row": 1,
                "disposition": "SECURITY_TRADES",
                "columns": [
                    {"column": 1, "semantic_role": "side"},
                    {"column": 2, "semantic_role": "asset_name"},
                    {"column": 3, "semantic_role": "trade_date"},
                    {"column": 4, "semantic_role": "quantity"},
                    {"column": 5, "semantic_role": "unit_price"},
                    {"column": 6, "semantic_role": "gross_amount"},
                    {"column": 7, "semantic_role": "broker_commission"},
                    {"column": 8, "semantic_role": "exchange_commission"},
                    {"column": 9, "semantic_role": "currency"},
                ],
                "amount_currency_bindings": [
                    {"amount_column": 6, "currency_column": 9},
                    {"amount_column": 7, "currency_column": 9},
                    {"amount_column": 8, "currency_column": 9},
                ],
                "side_values": [
                    {"source_literal": "Sale", "normalized_value": "DISPOSAL"}
                ],
                "row_dispositions": [
                    {"row": 2, "disposition": "SECURITY_TRADES"}
                ],
            }
        ],
        "clarification": None,
        "message": "Synthetic mapping complete.",
    }
    fixture = {
        "canonical": case.canonical,
        "canonical_binding": {
            "document_id": "synthetic-golden-complete-trade",
            "canonical_version_id": "synthetic-golden-complete-trade-v1",
            "canonical_root_sha256": case.canonical["canonical_root_hash"],
            "source_artifact_ref": case.canonical["source"]["source_artifact_ref"],
            "source_sha256": case.canonical["source"]["source_sha256"],
        },
        "user_scope_sha256": hashlib.sha256(
            b"goal391-synthetic-ordinary-user"
        ).hexdigest(),
        "expected_verdict": {
            "status": "COMPLETE",
            "qualified_mapping_count": 1,
            "qualification_receipt_count": 1,
            "table_resolution_count": 1,
            "currency_table_count": 0,
            # Frozen literal: do not calculate expectations from a live call.
            "role_map_sha256": "b202e6c2e2df2626d5ad76d5e743550b4def64f0d50c3f3fc5521aabaf319952",
        },
        "confirmed_understandings": [],
        "target_table_node_ids": None,
        "frozen_mappings": [],
        "fixture_identity": {
            "fixture_id": "goal391-synthetic-golden-complete-trade-v1",
            "corpus_version": FROZEN_ROLE_MAPPING_CORPUS_VERSION,
        },
    }
    return FrozenRoleMappingCorpusCase(
        case_id=case.case_id,
        expected_table_disposition=case.expected_table_disposition,
        canonical=case.canonical,
        frozen_fixture=fixture,
        known_strict_response=response,
    )


def _csv_case(
    *, case_id: str, expected_table_disposition: str, csv_text: str
) -> FrozenRoleMappingCorpusCase:
    source_sha256 = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    rows = [line.split(",") for line in csv_text.strip().splitlines()]
    canonical = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version=FROZEN_ROLE_MAPPING_CORPUS_VERSION
        )
    ).create().build(
        tenant_id="goal391-sandbox-tenant",
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": source_sha256,
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=f"synthetic-goal391-source-{case_id}",
        source_payloads=[
            {
                "canonical_projection": {
                    "rows": rows,
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": True,
                    "duplicate_headers": False,
                },
                "source_location": {"dataset": case_id},
            }
        ],
        source_units=[],
        table_projections=[],
        created_at="2026-09-06T00:00:00+00:00",
    )
    return FrozenRoleMappingCorpusCase(
        case_id=case_id,
        expected_table_disposition=expected_table_disposition,
        canonical=canonical,
    )


def test_frozen_role_mapping_corpus_is_valid_non_financial_canonical_evidence() -> None:
    corpus = build_frozen_role_mapping_corpus()

    assert [case.case_id for case in corpus] == [
        "synthetic_golden_complete_trade",
        "synthetic_explicit_sale_columns",
        "synthetic_non_financial_note",
    ]
    assert [case.expected_table_disposition for case in corpus] == [
        "SECURITY_TRADES",
        "SECURITY_TRADES",
        "NO_NAMED_CONSUMER",
    ]
    for case in corpus:
        validation = validate_canonical_artifact(case.canonical)
        assert validation["passed"] is True
        assert case.canonical["source"]["source_format"] == "csv"
        assert "financial_role" not in str(case.canonical).lower()
        table = next(
            node for node in case.canonical["nodes"] if node["node_type"] == "TABLE"
        )
        assert table["content"]["cells"]
        assert all(cell["source_refs"] for cell in table["content"]["cells"])


def test_frozen_role_mapping_positive_case_preserves_explicit_source_cells() -> None:
    positive = build_frozen_role_mapping_corpus()[1]
    table = next(
        node for node in positive.canonical["nodes"] if node["node_type"] == "TABLE"
    )

    assert table["content"]["header"] == [
        "Action",
        "Date Acquired",
        "Date Sold or Disposed",
        "Quantity Sold",
        "Proceeds",
        "Cost or Other Basis",
        "Currency",
    ]
    assert table["content"]["rows"] == [
        ["Sale", "2024-01-15", "2025-02-03", "10", "1250.00", "900.00", "USD"]
    ]
    assert [
        cell["source_coordinate"] for cell in table["content"]["cells"]
    ] == [f"R{row}C{column}" for row in (1, 2) for column in range(1, 8)]


def test_golden_fixture_hash_is_independent_of_qualification_runner() -> None:
    golden = build_frozen_role_mapping_corpus()[0]
    response = golden.known_strict_response
    fixture = golden.frozen_fixture

    assert response is not None
    assert fixture is not None
    projection = [
        {
            "table_ref": "table_1",
            "header_row": 1,
            "disposition": "SECURITY_TRADES",
            "columns": response["table_decisions"][0]["columns"],
            "amount_currency_bindings": response["table_decisions"][0][
                "amount_currency_bindings"
            ],
            "side_values": response["table_decisions"][0]["side_values"],
            "row_dispositions": response["table_decisions"][0]["row_dispositions"],
        }
    ]
    independent_hash = hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert fixture["expected_verdict"]["role_map_sha256"] == independent_hash
