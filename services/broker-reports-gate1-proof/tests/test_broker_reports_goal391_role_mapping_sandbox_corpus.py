"""Frozen, synthetic inputs for the Goal #391 role-mapping R&D sandbox.

The corpus deliberately owns no provider call, prompt, runtime path, or
financial interpretation.  It exercises the existing Canonical normalizer so
the sandbox can later consume the same immutable artefact shape as product
code.  Expected semantic outcomes live beside the source artefacts rather
than inside Canonical: Canonical remains non-financial evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

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


def build_frozen_role_mapping_corpus() -> tuple[FrozenRoleMappingCorpusCase, ...]:
    """Build the minimal positive and negative Canonical inputs for R&D.

    This uses the sole CanonicalArtifactV1 construction authority directly;
    the structured expectation is intentionally not persisted in the artifact.
    """

    return (
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
        "synthetic_explicit_sale_columns",
        "synthetic_non_financial_note",
    ]
    assert [case.expected_table_disposition for case in corpus] == [
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
    positive = build_frozen_role_mapping_corpus()[0]
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
