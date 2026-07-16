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


def test_proposed_facts_select_value_column_and_join_split_header_cells() -> None:
    legacy_region = {
        "region_id": "r1",
        "header_rows": [1, 2],
        "cells": [
            ["", "Minimum Lease Payments", ""],
            ["", "Office Space", "Retail Space"],
            ["2026", "$ 446,880", "$ 338,333"],
        ],
    }
    table = {
        "physical": {
            "cells": [
                {
                    "row_id": "header_1",
                    "column_id": "col_1",
                    "text": "Minimum",
                    "bbox": [0.4, 0.1, 0.55, 0.15],
                },
                {
                    "row_id": "header_2",
                    "column_id": "col_1",
                    "text": "Lease Payments",
                    "bbox": [0.4, 0.15, 0.6, 0.2],
                },
                {
                    "row_id": "header_3",
                    "column_id": "col_1",
                    "text": "Office Space",
                    "bbox": [0.4, 0.2, 0.6, 0.25],
                },
                {
                    "row_id": "header_3",
                    "column_id": "col_2",
                    "text": "Retail Space",
                    "bbox": [0.7, 0.2, 0.9, 0.25],
                },
                {
                    "row_id": "row_2026",
                    "column_id": "col_0",
                    "text": "2026",
                    "bbox": [0.1, 0.3, 0.2, 0.4],
                },
                {
                    "row_id": "row_2026",
                    "column_id": "col_1",
                    "text": "$",
                    "bbox": [0.4, 0.3, 0.45, 0.4],
                },
                {
                    "row_id": "row_2026",
                    "column_id": "col_1",
                    "text": "446,880",
                    "bbox": [0.46, 0.3, 0.6, 0.4],
                },
                {
                    "row_id": "row_2026",
                    "column_id": "col_2",
                    "text": "$",
                    "bbox": [0.7, 0.3, 0.75, 0.4],
                },
                {
                    "row_id": "row_2026",
                    "column_id": "col_2",
                    "text": "338,333",
                    "bbox": [0.76, 0.3, 0.9, 0.4],
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

    assert len(facts) == 2
    office, retail = facts
    assert office["source_regions"]["value"]["visible_text"] == "$ 446,880"
    assert office["source_regions"]["value"]["bbox_normalized"] == [
        0.4,
        0.3,
        0.6,
        0.4,
    ]
    assert retail["source_regions"]["value"]["visible_text"] == "$ 338,333"
    assert retail["source_regions"]["value"]["bbox_normalized"] == [
        0.7,
        0.3,
        0.9,
        0.4,
    ]
    assert [item["visible_text"] for item in office["source_regions"]["header"]] == [
        "Minimum Lease Payments",
        "Office Space",
    ]
    assert [item["visible_text"] for item in retail["source_regions"]["header"]] == [
        "Retail Space"
    ]
    assert "source_locator_requires_human_correction" not in office["uncertainty"]
    assert "source_locator_requires_human_correction" not in retail["uncertainty"]


def test_proposed_headerless_fact_records_explicit_source_classification() -> None:
    facts = REFERENCE._proposed_facts(
        legacy_region={
            "region_id": "r1",
            "header_rows": [],
            "cells": [["Cash", "$ 100"]],
        },
        prior_tables=[
            {
                "physical": {
                    "cells": [
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
        ],
        crop_bbox=[0.0, 0.0, 1.0, 1.0],
        crop_sha256="a" * 64,
    )

    assert len(facts) == 1
    assert facts[0]["header_path"] == []
    assert facts[0]["source_regions"]["header"] == []
    assert "header_not_present_in_source" in facts[0]["uncertainty"]


def test_proposed_fact_uses_structural_value_column_only_with_human_warning() -> None:
    facts = REFERENCE._proposed_facts(
        legacy_region={
            "region_id": "r1",
            "header_rows": [1],
            "cells": [
                ["", "Office Space", "Retail Space"],
                ["Interest", "(17,044)", "(849,477)"],
            ],
        },
        prior_tables=[
            {
                "physical": {
                    "cells": [
                        {
                            "row_id": "header",
                            "column_id": "col_1",
                            "text": "Office Space",
                            "bbox": [0.4, 0.1, 0.6, 0.2],
                        },
                        {
                            "row_id": "header",
                            "column_id": "col_2",
                            "text": "Retail Space",
                            "bbox": [0.7, 0.1, 0.9, 0.2],
                        },
                        {
                            "row_id": "interest",
                            "column_id": "col_0",
                            "text": "Interest",
                            "bbox": [0.1, 0.3, 0.3, 0.4],
                        },
                        {
                            "row_id": "interest",
                            "column_id": "col_1",
                            "text": "(17,044)",
                            "bbox": [0.4, 0.3, 0.6, 0.4],
                        },
                        {
                            "row_id": "interest",
                            "column_id": "col_2",
                            "text": "(849,777)",
                            "bbox": [0.7, 0.3, 0.9, 0.4],
                        },
                    ]
                }
            }
        ],
        crop_bbox=[0.0, 0.0, 1.0, 1.0],
        crop_sha256="a" * 64,
    )

    retail = facts[1]
    assert retail["visible_value"] == "(849,477)"
    assert retail["source_regions"]["value"]["bbox_normalized"] == [
        0.7,
        0.3,
        0.9,
        0.4,
    ]
    assert (
        "source_locator_text_mismatch_requires_human_confirmation"
        in retail["uncertainty"]
    )
    assert "source_locator_requires_human_correction" not in retail["uncertainty"]


def test_exact_value_match_cannot_jump_to_another_physical_column() -> None:
    facts = REFERENCE._proposed_facts(
        legacy_region={
            "region_id": "r1",
            "header_rows": [],
            "cells": [["Cash", "100", "100"]],
        },
        prior_tables=[
            {
                "physical": {
                    "cells": [
                        {
                            "row_id": "cash",
                            "column_id": "col_0",
                            "text": "Cash",
                            "bbox": [0.1, 0.3, 0.3, 0.4],
                        },
                        {
                            "row_id": "cash",
                            "column_id": "col_1",
                            "text": "100",
                            "bbox": [0.4, 0.3, 0.6, 0.4],
                        },
                        {
                            "row_id": "cash",
                            "column_id": "col_2",
                            "text": "101",
                            "bbox": [0.7, 0.3, 0.9, 0.4],
                        },
                    ]
                }
            }
        ],
        crop_bbox=[0.0, 0.0, 1.0, 1.0],
        crop_sha256="a" * 64,
    )

    second_column = facts[1]
    assert second_column["source_regions"]["value"]["bbox_normalized"] == [
        0.7,
        0.3,
        0.9,
        0.4,
    ]
    assert (
        "source_locator_text_mismatch_requires_human_confirmation"
        in second_column["uncertainty"]
    )


def test_expected_structural_locator_mismatch_set_is_frozen() -> None:
    case_id, region_id, fact_id = next(
        iter(REFERENCE.EXPECTED_STRUCTURAL_LOCATOR_TEXT_MISMATCHES)
    ).split(":")
    matching = [
        {
            "case_id": case_id,
            "regions": [
                {
                    "region_id": region_id,
                    "facts": [
                        {
                            "fact_id": fact_id,
                            "uncertainty": [
                                "source_locator_text_mismatch_requires_human_confirmation"
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    REFERENCE._require_expected_structural_locator_text_mismatches(matching)
    matching[0]["regions"][0]["facts"].append(
        {
            "fact_id": "unexpected",
            "uncertainty": ["source_locator_text_mismatch_requires_human_confirmation"],
        }
    )
    with pytest.raises(
        REFERENCE.ReferencePackError,
        match="reference_pack_unexpected_locator_text_mismatch",
    ):
        REFERENCE._require_expected_structural_locator_text_mismatches(matching)


def test_exact_value_match_wins_over_earlier_structural_fallback() -> None:
    def table(value: str, x0: float) -> dict:
        return {
            "physical": {
                "cells": [
                    {
                        "row_id": "row",
                        "column_id": "col_0",
                        "text": "Interest",
                        "bbox": [0.1, 0.3, 0.3, 0.4],
                    },
                    {
                        "row_id": "row",
                        "column_id": "col_1",
                        "text": value,
                        "bbox": [x0, 0.3, x0 + 0.2, 0.4],
                    },
                ]
            }
        }

    facts = REFERENCE._proposed_facts(
        legacy_region={
            "region_id": "r1",
            "header_rows": [],
            "cells": [["Interest", "218"]],
        },
        prior_tables=[table("219", 0.4), table("218", 0.7)],
        crop_bbox=[0.0, 0.0, 1.0, 1.0],
        crop_sha256="a" * 64,
    )

    assert facts[0]["source_regions"]["value"]["bbox_normalized"] == [
        0.7,
        0.3,
        0.9,
        0.4,
    ]
    assert (
        "source_locator_text_mismatch_requires_human_confirmation"
        not in facts[0]["uncertainty"]
    )


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
                        "gemini": {
                            "status": "completed",
                            "output": {"facts": []},
                            "operation": {
                                "attempt": {
                                    "canonical_schema_hash": "d" * 64,
                                    "adapted_schema_hash": "e" * 64,
                                }
                            },
                        },
                        "openai": {
                            "status": "completed",
                            "output": {"facts": []},
                            "operation": {
                                "attempt": {
                                    "canonical_schema_hash": "f" * 64,
                                    "adapted_schema_hash": "f" * 64,
                                }
                            },
                        },
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
    assert "Распарсенный ответ до проверки общего контракта" in rendered
    assert "Служебные данные API и адаптации схемы Gemini" in rendered
    assert "Служебные данные API и адаптации схемы OpenAI" in rendered
    assert "Схема была адаптирована под API провайдера" in rendered
    assert "Схема передана без адаптации" in rendered
    assert "Полный служебный ответ API здесь не показан" in rendered
    assert index["cards"][0]["gemini"]["output"] == {"facts": []}
    assert index["cards"][0]["gemini"]["operation"]["attempt"] == {
        "canonical_schema_hash": "d" * 64,
        "adapted_schema_hash": "e" * 64,
    }
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
        "detection": {
            "false_candidates": [
                {"case_id": "betterment_p02", "candidate_id": "table_0"}
            ],
            "missed_regions": [
                {"case_id": "ibkr_midyear_p03", "reference_region_id": "r1"}
            ],
            "cut_regions": [
                {
                    "case_id": "drivewealth_p07",
                    "reference_region_id": "r1",
                    "candidate_id": "table_1",
                    "iou": 0.91,
                }
            ],
            "detection_contract_failure_details": [
                {
                    "case_id": "ibkr_midyear_p03",
                    "status": "contract_invalid",
                    "contract_errors": ["dual_vlm_detection_candidate_0_bbox_invalid"],
                }
            ],
        },
        "operational": {},
        "provider_structured_output_comparability": {
            "comparison_scope": "model_provider_api_schema_adapter_bundle",
            "paired_extraction_operations": 9,
            "complete_pair_coverage": True,
            "identical_crop_sha256_for_all_pairs": True,
            "identical_model_view_hash_for_all_pairs": True,
            "identical_canonical_schema_hash_for_all_pairs": True,
            "identical_adapted_schema_hash_for_all_pairs": False,
            "shared_prompt_contract_version": "dual_vlm_fact_extraction_v1",
            "schema_projection_causal_effect": "not_established",
            "detection": {
                "operations": 8,
                "schema_metadata_valid_operations": 8,
                "schema_metadata_invalid_operations": 0,
                "schema_transform_count_histogram": {"9": 8},
                "canonical_schema_equals_adapted_operations": 0,
                "canonical_schema_differs_from_adapted_operations": 8,
            },
            "gemini_extraction": {
                "operations": 9,
                "schema_metadata_valid_operations": 9,
                "schema_metadata_invalid_operations": 0,
                "schema_transform_count_histogram": {"67": 9},
                "canonical_schema_equals_adapted_operations": 0,
                "canonical_schema_differs_from_adapted_operations": 9,
            },
            "openai_extraction": {
                "operations": 9,
                "schema_metadata_valid_operations": 9,
                "schema_metadata_invalid_operations": 0,
                "schema_transform_count_histogram": {"0": 9},
                "canonical_schema_equals_adapted_operations": 9,
                "canonical_schema_differs_from_adapted_operations": 0,
            },
        },
        "reference_contract": {
            "reference_fact_type_counts": {"financial_numeric_fact": 83},
            "unsupported_reference_fact_types": ["financial_numeric_fact"],
            "fact_type_contract_compatible": False,
            "provider_precision_recall_interpretation": "contract_limited",
            "null_field_counts": {"period": 83},
        },
        "previous_benchmark_comparison": {
            "status": "not_established",
            "current_material_improvement_comparator": "current_provider_arms_only",
        },
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
    assert "## Exact detection failures" in rendered
    assert "`betterment_p02` | 2 | `table_0`" in rendered
    assert "`ibkr_midyear_p03` | 3 | `r1`" in rendered
    assert "`drivewealth_p07` | 7 | `r1` / `table_1`" in rendered
    assert "dual_vlm_detection_candidate_0_bbox_invalid" in rendered
    assert "## Reference/scoring contract limitation" in rendered
    assert "zero provider precision/recall is contract-dominated" in rendered
    assert "not evidence of improvement over the prior benchmark" in rendered
    assert "## Provider-side structured-output comparability" in rendered
    assert "identical model-view hashes: `True`" in rendered
    assert "identical provider-adapted schema hashes: `False`" in rendered
    assert 'schema-keyword transformations `{"67": 9}`' in rendered
    assert 'schema-keyword transformations `{"0": 9}`' in rendered
    assert "not isolated model capability" in rendered
    assert "does not establish that schema projection caused" in rendered
    assert "Detection (Gemini-only" in rendered
    assert 'schema-keyword transformations `{"9": 8}`' in rendered


def test_report_does_not_claim_comparability_from_empty_metadata() -> None:
    rendered = "\n".join(REPORT._structured_output_comparability_lines({}))

    assert "model-only comparability is not established" in rendered
    assert "same visual evidence and business questions" not in rendered
    assert "schema-projection metadata incomplete or invalid" in rendered


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


def test_report_refuses_completed_score_without_provider_comparability(
    tmp_path: Path,
) -> None:
    score = {
        "schema_version": REPORT.SCORE_SCHEMA,
        "scoring_status": "completed",
        "gates": {
            "TABLE_DETECTION_AND_CROPPING": "FAILED",
            "DUAL_VLM_FINANCIAL_FACT_EXTRACTION": "FAILED",
            "FACT_EVIDENCE_VERIFICATION": "FAILED",
        },
        "architectural_conclusion": "DUAL_VLM_FACT_ARCHITECTURE_NOT_JUSTIFIED",
    }
    score["score_checksum"] = REPORT._sha256_json(score)
    score_path = tmp_path / "score.json"
    score_path.write_bytes(REPORT._canonical_json(score))

    with pytest.raises(
        REPORT.ReportError,
        match="dual_vlm_report_provider_comparability_required",
    ):
        REPORT.render_report(
            score_path=score_path,
            output_path=tmp_path / "report.md",
        )
