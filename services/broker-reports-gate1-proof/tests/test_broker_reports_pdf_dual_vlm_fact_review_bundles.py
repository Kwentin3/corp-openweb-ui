from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(name: str, filename: str) -> ModuleType:
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = _load(
    "dual_vlm_reference_pack_test",
    "local_pdf_dual_vlm_fact_reference_pack.py",
)
OPERATOR = _load(
    "dual_vlm_operator_bundle_test",
    "local_pdf_dual_vlm_fact_operator_bundle.py",
)
REPORT = _load(
    "dual_vlm_report_test",
    "local_pdf_dual_vlm_fact_report.py",
)


@pytest.mark.parametrize(
    ("visible", "numeric", "sign"),
    [
        ("$ 1,234", "1234", "positive"),
        ("(17,044)", "-17044", "negative"),
        ("0.00", "0.00", "zero"),
        ("-", None, None),
        ("n/a", None, None),
    ],
)
def test_proposed_numeric_values_preserve_visible_semantics(
    visible: str, numeric: str | None, sign: str | None
) -> None:
    parsed = REFERENCE._numeric_value(visible)
    assert parsed == numeric
    if parsed is not None:
        assert REFERENCE._sign(parsed) == sign


def test_proposed_facts_are_explicitly_unreviewed_and_source_linked() -> None:
    legacy_region = {
        "region_id": "r1",
        "header_rows": [1],
        "cells": [["", "2025"], ["Cash", "$ 100"]],
    }
    table = {
        "physical": {
            "cells": [
                {
                    "row_id": "header",
                    "text": "2025",
                    "bbox": [0.6, 0.1, 0.9, 0.2],
                },
                {
                    "row_id": "cash",
                    "text": "Cash",
                    "bbox": [0.1, 0.4, 0.4, 0.5],
                },
                {
                    "row_id": "cash",
                    "text": "$ 100",
                    "bbox": [0.6, 0.4, 0.9, 0.5],
                },
            ]
        }
    }

    facts = REFERENCE._proposed_facts(
        legacy_region=legacy_region,
        prior_tables=[table],
        crop_bbox=[0.0, 0.0, 1.0, 1.0],
        crop_sha256="a" * 64,
    )

    assert len(facts) == 1
    fact = facts[0]
    assert fact["header_path"] == ["2025"]
    assert fact["numeric_value"] == "100"
    assert fact["source_regions"]["row_label"]["visible_text"] == "Cash"
    assert fact["source_regions"]["value"]["artifact_sha256"] == "a" * 64
    assert "proposed_from_unreviewed_legacy_grid" in fact["uncertainty"]


def test_operator_bundle_preserves_sealed_lineage_and_review_controls(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    artifact_dir = run_dir / "artifacts" / "case_1"
    artifact_dir.mkdir(parents=True)
    png = b"\x89PNG\r\n\x1a\nreview-fixture"
    (artifact_dir / "page.private.png").write_bytes(png)
    (artifact_dir / "crop.private.png").write_bytes(png)
    terminal = {
        "schema_version": OPERATOR.TERMINAL_SCHEMA,
        "manifest_sha256": "b" * 64,
        "reference_accessed": False,
        "cases": [
            {
                "case_id": "case_1",
                "terminal_status": "completed",
                "input": {
                    "page_number": 1,
                    "pdf_sha256": "c" * 64,
                    "page_artifact": "artifacts/case_1/page.private.png",
                },
                "detection": {"status": "completed", "output": {}},
                "crops": [
                    {
                        "candidate": {
                            "candidate_id": "table_1",
                            "bbox": [0.1, 0.2, 0.9, 0.8],
                        },
                        "crop_artifact": "artifacts/case_1/crop.private.png",
                        "terminal_status": "completed",
                        "evidence_medium": "text_layer",
                        "gemini": {"status": "completed", "output": {"facts": []}},
                        "openai": {"status": "completed", "output": {"facts": []}},
                        "consensus": {
                            "entries": [
                                {
                                    "consensus_id": "consensus_0001",
                                    "status": "models_exactly_agree",
                                    "runtime_disposition": "evidence_eligible",
                                    "material_differences": [],
                                }
                            ]
                        },
                        "evidence": {
                            "source_maps": [
                                {
                                    "fact_id": "consensus_0001",
                                    "evidence_status": "parser_source_verified",
                                    "automatic_acceptance_eligible": True,
                                    "reason_codes": [],
                                    "relation_candidates": [{"row_label": {}}],
                                    "evidence_requests": {
                                        "row_label": {
                                            "crop_normalized_bbox": [0.1, 0.4, 0.4, 0.5]
                                        },
                                        "value": {
                                            "crop_normalized_bbox": [0.6, 0.4, 0.9, 0.5]
                                        },
                                        "headers": [],
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }
    terminal_bytes = OPERATOR._canonical_json(terminal)
    terminal_path = run_dir / "terminal.private.json"
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": OPERATOR.SEAL_SCHEMA,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path = run_dir / "terminal.private.sha256.json"
    seal_path.write_bytes(OPERATOR._canonical_json(seal))

    result = OPERATOR.build_operator_bundle(
        terminal_path=terminal_path,
        seal_path=seal_path,
        output_dir=tmp_path / "bundle",
    )

    index = json.loads(Path(result["index"]).read_text(encoding="utf-8"))
    rendered = Path(result["html"]).read_text(encoding="utf-8")
    assert index["terminal_sha256"] == seal["terminal_sha256"]
    assert index["reference_available"] is False
    assert index["cards"][0]["outcomes"][0]["automatic_acceptance_eligible"] is True
    assert '<html lang="ru">' in rendered
    assert "Проверка данных из таблиц PDF" in rendered
    assert "Ответ Gemini" in rendered and "Ответ OpenAI" in rendered
    assert "Сравнение ответов моделей" in rendered
    assert "Проверка по исходному PDF" in rendered
    assert "Подтвердить" in rendered and "Неоднозначно" in rendered
    assert "Нет пропущенных или придуманных фактов" in rendered
    assert "Загружаем карточки для проверки" in rendered
    assert "Карточек для проверки нет" in rendered
    assert "Не удалось открыть данные проверки" in rendered
    assert "Готовим файл с решениями" in rendered
    assert "button:disabled" in rendered and ":focus-visible" in rendered
    assert 'value="confirm"' in rendered and 'value="ambiguous"' in rendered


def test_operator_bundle_rejects_unsealed_terminal(tmp_path: Path) -> None:
    terminal_path = tmp_path / "terminal.json"
    terminal_path.write_text(
        json.dumps(
            {
                "schema_version": OPERATOR.TERMINAL_SCHEMA,
                "reference_accessed": False,
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(
        json.dumps(
            {
                "schema_version": OPERATOR.SEAL_SCHEMA,
                "terminal_sha256": "0" * 64,
                "terminal_size_bytes": 1,
                "reference_accessed": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        OPERATOR.OperatorBundleError,
        match="operator_bundle_terminal_seal_mismatch",
    ):
        OPERATOR.build_operator_bundle(
            terminal_path=terminal_path,
            seal_path=seal_path,
            output_dir=tmp_path / "bundle",
        )


def test_report_starts_with_three_independent_results_and_conclusion(
    tmp_path: Path,
) -> None:
    score = {
        "schema_version": REPORT.SCORE_SCHEMA,
        "scoring_status": "completed",
        "gates": {
            "TABLE_DETECTION_AND_CROPPING": "PASSED",
            "DUAL_VLM_FINANCIAL_FACT_EXTRACTION": "FAILED",
            "FACT_EVIDENCE_VERIFICATION": "FAILED",
        },
        "architectural_conclusion": (
            "DUAL_VLM_FACT_ARCHITECTURE_PROMISING_BUT_NOT_READY"
        ),
        "facts": {},
        "detection": {},
        "operational": {},
    }
    score["score_checksum"] = REPORT._sha256_json(score)
    score_path = tmp_path / "score.json"
    score_path.write_bytes(REPORT._canonical_json(score))
    output_path = tmp_path / (
        "OPENWEBUI_PDF_TABLE_DUAL_VLM_FACT_AND_EVIDENCE_BENCHMARK.report.md"
    )

    REPORT.render_report(score_path=score_path, output_path=output_path)

    rendered = output_path.read_text(encoding="utf-8")
    assert rendered.startswith(
        "TABLE_DETECTION_AND_CROPPING:\nPASSED\n\n"
        "DUAL_VLM_FINANCIAL_FACT_EXTRACTION:\nFAILED\n\n"
        "FACT_EVIDENCE_VERIFICATION:\nFAILED\n\n"
        "DUAL_VLM_FACT_ARCHITECTURE_PROMISING_BUT_NOT_READY"
    )
    assert "does not establish production readiness" in rendered


def test_report_refuses_blocked_human_reference_score(tmp_path: Path) -> None:
    score = {
        "schema_version": REPORT.SCORE_SCHEMA,
        "scoring_status": "blocked_human_reference_required",
    }
    score["score_checksum"] = REPORT._sha256_json(score)
    score_path = tmp_path / "score.json"
    score_path.write_bytes(REPORT._canonical_json(score))
    with pytest.raises(
        REPORT.ReportError,
        match="dual_vlm_report_completed_score_required",
    ):
        REPORT.render_report(
            score_path=score_path,
            output_path=tmp_path / "report.md",
        )
