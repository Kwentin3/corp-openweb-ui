from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import fitz


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACTS = _load("direct_pdf_plain_text_experiment_contracts")
TRANSPORTS = _load("direct_pdf_experiment_transports")
HARNESS = _load("local_direct_pdf_plain_text_experiment")


def test_table_parser_preserves_empty_cells_and_terminal_block() -> None:
    parsed = CONTRACTS.parse_table_text(
        "TABLE page=2 order=3\nHEADER_ROWS=1\nROW|A||C\nROW|1|2|\nEND_TABLE\n"
    )
    assert parsed["parse_status"] == "valid"
    assert parsed["validation_error"] is None
    assert parsed["tables"][0]["rows"][0]["cells"] == ["A", "", "C"]
    assert parsed["tables"][0]["rows"][1]["cells"] == ["1", "2", ""]
    assert parsed["tables"][0]["column_count"] == 3
    assert parsed["last_complete_table"] == "2:3"


def test_table_parser_rejects_inconsistent_width_missing_end_and_trailing_content() -> None:
    width = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|B\nROW|1\nEND_TABLE\n"
    )
    missing_end = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|B\n"
    )
    trailing = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|B\nEND_TABLE\ncommentary"
    )
    assert width["validation_error"] == "inconsistent_row_width"
    assert missing_end["validation_error"] == "end_table_missing"
    assert missing_end["last_row_seen"] == 1
    assert trailing["validation_error"] == "table_start_expected"
    assert trailing["trailing_content"] == "commentary"


def test_malformed_table_response_retains_only_complete_prefix_blocks() -> None:
    parsed = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|B\nEND_TABLE\n"
        "TABLE page=1 order=2\nHEADER_ROWS=1\nROW|C|D\nROW|broken\n"
    )
    assert parsed["parse_status"] == "malformed"
    assert parsed["validation_error"] == "inconsistent_row_width"
    assert len(parsed["tables"]) == 1
    assert parsed["tables"][0]["order_on_page"] == 1


def test_table_parser_distinguishes_valid_empty_from_malformed() -> None:
    empty_all = CONTRACTS.parse_table_text("NO_TABLES\n")
    empty_target = CONTRACTS.parse_table_text("NO_TABLE page=4 order=2\n")
    malformed = CONTRACTS.parse_table_text("There is no table.\n")
    assert empty_all["parse_status"] == "valid_empty"
    assert empty_target["parse_status"] == "valid_empty"
    assert empty_target["requested_page"] == 4
    assert empty_target["requested_order"] == 2
    assert malformed["parse_status"] == "malformed"


def test_inventory_parser_and_assessment_assert_observable_counts() -> None:
    parsed = CONTRACTS.parse_inventory_text(
        "PAGE 1\nTABLE 1\nPURPOSE: holdings\nROWS_VISIBLE: 2\nCOLUMNS_VISIBLE: 2\n"
        "HEADER_ROWS: 1\nCONTINUES_ON_PAGE: NONE\nUNCERTAINTY: NONE\n"
        "PAGE 2\nTABLE 1\nPURPOSE: continuation\nROWS_VISIBLE: 1\nCOLUMNS_VISIBLE: 2\n"
        "HEADER_ROWS: 0\nCONTINUES_ON_PAGE: 1\nUNCERTAINTY: NONE\n"
    )
    reference = {
        "1:1": {"cells": [["A", "B"], ["1", "2"]], "header_rows": 1},
        "2:1": {"cells": [["3", "4"]], "header_rows": 0},
    }
    assessment = CONTRACTS.assess_inventory(reference, parsed)
    assert parsed["parse_status"] == "valid"
    assert assessment["matched_tables"] == 2
    assert assessment["exact_row_counts"] == 2
    assert assessment["exact_column_counts"] == 2
    assert assessment["exact_header_counts"] == 2


def test_inventory_parser_rejects_missing_required_terminal_field() -> None:
    parsed = CONTRACTS.parse_inventory_text(
        "PAGE 1\nTABLE 1\nPURPOSE: holdings\nROWS_VISIBLE: 2\nCOLUMNS_VISIBLE: 2\n"
        "HEADER_ROWS: 1\nCONTINUES_ON_PAGE: NONE\n"
    )
    assert parsed["parse_status"] == "malformed"
    assert parsed["validation_error"] == "uncertainty_missing"


def test_malformed_inventory_retains_complete_prefix_for_non_authoritative_diagnostic() -> None:
    parsed = CONTRACTS.parse_inventory_text(
        "PAGE 1\nTABLE 1\nPURPOSE: holdings\nROWS_VISIBLE: 2\nCOLUMNS_VISIBLE: 2\n"
        "HEADER_ROWS: 1\nCONTINUES_ON_PAGE: NONE\nUNCERTAINTY: NONE\n"
        "PAGE 2\nNo tables visible\n"
    )
    assessment = CONTRACTS.assess_inventory(
        {"1:1": {"cells": [["A", "B"], ["1", "2"]], "header_rows": 1}},
        parsed,
    )
    assert parsed["parse_status"] == "malformed"
    assert len(parsed["tables"]) == 1
    assert assessment["returned_tables"] == 0
    assert assessment["raw_complete_blocks_before_error"] == 1
    assert assessment["raw_prefix_matched_tables"] == 1
    assert assessment["raw_prefix_exact_row_counts"] == 1
    assert assessment["raw_prefix_exact_column_counts"] == 1
    assert assessment["raw_prefix_exact_header_counts"] == 1


def test_selected_reference_scorer_uses_exact_position_and_ignores_unreviewed_extra_rows() -> None:
    parsed = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|B\nROW|1|2\nROW|extra|row\nEND_TABLE\n"
    )
    reference = {"1:1": {"cells": [["A", "B"], ["1", "2"]], "header_rows": 1}}
    score = CONTRACTS.score_selected_reference(reference, parsed)
    assert score["cells_exact"] == 4
    assert score["cells_total"] == 4
    assert score["cell_accuracy"] == 1.0
    assert score["numeric_total"] == 2
    assert score["numeric_exact"] == 2
    assert score["exact_selected_prefix_structures"] == 1
    assert score["additional_rows_outside_selected_draft_scored"] is False


def test_selected_reference_scorer_reports_empty_cell_accuracy() -> None:
    parsed = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=1\nROW|A|\nROW|1|2\nEND_TABLE\n"
    )
    score = CONTRACTS.score_selected_reference(
        {"1:1": {"cells": [["A", ""], ["1", "2"]], "header_rows": 1}},
        parsed,
    )
    assert score["empty_cells_exact"] == 1
    assert score["empty_cells_total"] == 1
    assert score["empty_cell_accuracy"] == 1.0


def test_explanation_assessment_requires_page_refs_per_substantive_line() -> None:
    assessment = CONTRACTS.assess_explanation(
        "- [PAGE 1] Overview.\n- Missing reference.\n- [PAGE 2, PAGE 3] Continuation.\n",
        3,
    )
    assert assessment["substantive_lines"] == 3
    assert assessment["lines_with_page_reference"] == 2
    assert assessment["page_reference_coverage"] == 0.666667
    assert assessment["distinct_valid_pages_referenced"] == 3


def test_plain_text_transport_parser_preserves_provider_text_without_json_decoding() -> None:
    openai, openai_error = TRANSPORTS.parse_plain_text_payload(
        "openai", {"output": [{"content": [{"type": "output_text", "text": "TABLE\n"}]}]}
    )
    gemini, gemini_error = TRANSPORTS.parse_plain_text_payload(
        "google",
        {"candidates": [{"content": {"parts": [{"text": "ROW|1"}, {"text": "|2\n"}]}}]},
    )
    anthropic, anthropic_error = TRANSPORTS.parse_plain_text_payload(
        "anthropic", {"content": [{"type": "text", "text": "plain text"}]}
    )
    assert (openai, openai_error) == ("TABLE\n", None)
    assert (gemini, gemini_error) == ("ROW|1|2\n", None)
    assert (anthropic, anthropic_error) == ("plain text", None)


def test_job_plan_separates_four_arms_and_required_repeats() -> None:
    jobs = HARNESS._jobs(("openai", "google", "anthropic"), 32768)
    assert len(jobs) == 45
    for provider in ("openai", "google", "anthropic"):
        provider_jobs = [item for item in jobs if item["provider"] == provider]
        assert len(provider_jobs) == 15
        assert sum(item["arm"] == "explanation" for item in provider_jobs) == 1
        assert sum(item["arm"] == "inventory" for item in provider_jobs) == 1
        assert sum(item["arm"] == "monolithic" for item in provider_jobs) == 1
        assert sum(item["arm"] == "targeted" for item in provider_jobs) == 12
        repeated = {
            f"{item['page']}:{item['order']}"
            for item in provider_jobs
            if item["arm"] == "targeted" and item["repeat"] == 2
        }
        assert repeated == set(CONTRACTS.REPEAT_TARGET_KEYS)


def test_targeted_prompt_example_uses_requested_identity() -> None:
    prompt = CONTRACTS.transcription_prompt(page=4, order=2)
    assert "transcribe only table 2 on page 4" in prompt
    assert "TABLE page=4 order=2" in prompt
    assert "TABLE page=1 order=1" not in prompt


def test_safe_identity_proves_native_unchanged_pdf_and_no_schema_or_preprocessing() -> None:
    job = HARNESS._jobs(("openai",), 32768)[0]
    identity = HARNESS._safe_identity(
        job,
        "gpt-5.4-mini-2026-03-17",
        "openai_responses_input_file_inline_pdf",
        "abc",
        176458,
        6,
        "prompt",
    )
    assert identity["input_pdf_bytes"] == 176458
    assert identity["input_pdf_pages"] == 6
    assert identity["strict_json_schema_used"] is False
    assert identity["crop"] is False
    assert identity["local_text_attached"] is False
    assert identity["table_projection_attached"] is False
    assert identity["hidden_failover"] is False
    assert identity["silent_retry"] is False
    assert identity["prompt_sha256"] == hashlib.sha256(b"prompt").hexdigest()


def test_posthoc_relocation_uses_exact_words_and_marks_duplicate_ambiguity(tmp_path: Path) -> None:
    pdf = tmp_path / "relocation.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Alpha 10")
    page.insert_text((72, 100), "Beta 10")
    document.save(pdf)
    document.close()
    document = fitz.open(pdf)
    parsed = CONTRACTS.parse_table_text(
        "TABLE page=1 order=1\nHEADER_ROWS=0\nROW|Alpha|10\nEND_TABLE\n"
    )
    safe, private = HARNESS._assess_relocation(
        document,
        parsed,
        {"1:1": (60.0, 50.0, 150.0, 120.0)},
    )
    document.close()
    assert safe["returned_nonempty_cells"] == 2
    assert safe["exact_relocated_cells"] == 2
    assert safe["unique_exact_relocated_cells"] == 1
    assert safe["ambiguous_exact_relocated_cells"] == 1
    assert safe["fuzzy_matching_used"] is False
    assert len(private["bindings"]) == 2


def test_terminal_output_limit_detection_is_provider_specific() -> None:
    assert HARNESS._output_truncated("openai", {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}})
    assert HARNESS._output_truncated("google", {"candidates": [{"finishReason": "MAX_TOKENS"}]})
    assert HARNESS._output_truncated("anthropic", {"stop_reason": "max_tokens"})
    assert not HARNESS._output_truncated("anthropic", {"stop_reason": "end_turn"})


def test_usage_details_separates_visible_output_from_reasoning_tokens() -> None:
    google = HARNESS._usage_details(
        "google",
        {"usageMetadata": {"candidatesTokenCount": 100, "thoughtsTokenCount": 300}},
        {"output_tokens": 100},
    )
    anthropic = HARNESS._usage_details(
        "anthropic",
        {"usage": {"output_tokens_details": {"thinking_tokens": 250}}},
        {"output_tokens": 400},
    )
    assert google == {"reasoning_tokens": 300, "visible_output_tokens": 100}
    assert anthropic == {"reasoning_tokens": 250, "visible_output_tokens": 150}
