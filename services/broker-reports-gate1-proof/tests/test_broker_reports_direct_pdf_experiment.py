from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import fitz


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACTS = _load("direct_pdf_experiment_contracts")
TRANSPORTS = _load("direct_pdf_experiment_transports")
HARNESS = _load("local_direct_pdf_multi_provider_experiment")


def _valid_table_output() -> dict:
    return {
        "schema_version": CONTRACTS.TABLE_SCHEMA_VERSION,
        "document_status": "completed",
        "tables": [{
            "page": 1,
            "order_on_page": 1,
            "boundary": [],
            "row_count": 2,
            "column_count": 2,
            "header_rows": 1,
            "rows": [
                {"row_kind": "header", "cells": ["Name", "Value"]},
                {"row_kind": "data", "cells": ["Alpha", "10.00"]},
            ],
            "continuation_page": 0,
            "continuation_order_on_page": 0,
            "uncertainty": [],
        }],
        "warnings": [],
    }


def _valid_business_output() -> dict:
    domains = []
    for domain in CONTRACTS.DOMAIN_IDS:
        domains.append({"domain": domain, "status": "no_fact", "facts": [], "uncertainty": []})
    domains[0] = {
        "domain": "trade_operation",
        "status": "typed_fact",
        "facts": [{
            "fact_type": "trade_operation",
            "fields": [{"name": "amount", "value": "10.00"}],
            "page": 1,
            "table_order_on_page": 1,
            "row_label": "Alpha",
            "column_label": "Value",
            "boundary": [],
            "provider_citation": "page 1",
            "uncertainty": [],
        }],
        "uncertainty": [],
    }
    return {"schema_version": CONTRACTS.BUSINESS_SCHEMA_VERSION, "domains": domains, "warnings": []}


def test_table_contract_requires_observable_shape() -> None:
    value = _valid_table_output()
    assert CONTRACTS.validate_table_output(value) is None
    value["tables"][0]["row_count"] = 3
    assert CONTRACTS.validate_table_output(value) == "row_count_mismatch"


def test_table_scorer_reports_detection_structure_and_values() -> None:
    reference = {"1:1": {"cells": [["Name", "Value"], ["Alpha", "10.00"]], "header_rows": 1}}
    result = CONTRACTS.score_tables(reference, _valid_table_output())
    assert result["matched_tables"] == 1
    assert result["exact_structures"] == 1
    assert result["cells_exact"] == 4
    assert result["numeric_exact"] == 1


def test_table_scorer_penalizes_invalid_output_as_omission() -> None:
    reference = {"1:1": {"cells": [["10.00"]], "header_rows": 0}}
    result = CONTRACTS.score_tables(reference, {"invalid": True})
    assert result["validation_error"] == "schema_version_mismatch"
    assert result["missed_tables"] == 1
    assert result["omitted_nonempty_cells"] == 1


def test_business_contract_and_exact_page_relocation() -> None:
    value = _valid_business_output()
    assert CONTRACTS.validate_business_output(value) is None
    result = CONTRACTS.assess_business(value, ["Alpha Value 10.00"])
    assert result["typed_facts"] == 1
    assert result["field_relocation_rate"] == 1.0
    assert result["numeric_relocation_rate"] == 1.0
    assert result["strongest_claimed_provenance_level"] == 3
    assert result["strongest_uniformly_verified_provenance_level"] == 1
    assert result["level_4_exact_source_ref"] is False
    assert result["authoritative_fact_acceptance"] == "rejected"


def test_non_fact_domain_cannot_carry_values() -> None:
    value = _valid_business_output()
    value["domains"][1]["facts"] = value["domains"][0]["facts"]
    assert CONTRACTS.validate_business_output(value) == "non_fact_status_has_facts"


def test_connections_are_derived_from_openwebui_config_and_secret_repr_is_redacted() -> None:
    config = {
        "OPENAI_API_BASE_URLS": [
            "https://api.openai.com/v1",
            "https://api.anthropic.com/v1",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ],
        "OPENAI_API_KEYS": ["openai-secret", "anthropic-secret", "google-secret"],
        "OPENAI_API_CONFIGS": {"0": {"enable": True}, "1": {}, "2": {}},
    }
    result = TRANSPORTS.connections_from_openwebui_config(config)
    assert set(result) == {"openai", "anthropic", "google"}
    assert "openai-secret" not in repr(result["openai"])


def test_provider_payload_parsers_require_one_structured_text_block() -> None:
    parsed, error = TRANSPORTS._parse_anthropic({"content": [{"type": "text", "text": '{"ok":true}'}]})
    assert parsed == {"ok": True}
    assert error is None
    parsed, error = TRANSPORTS._parse_openai({"output": []})
    assert parsed is None
    assert error == "structured_text_block_count_invalid"


def test_gemini_parser_concatenates_sequential_text_parts() -> None:
    payload = {"candidates": [{"content": {"parts": [{"text": '{"ok":'}, {"text": "true}"}]}}]}
    parsed, error = TRANSPORTS._parse_gemini(payload)
    assert parsed == {"ok": True}
    assert error is None


def test_anthropic_schema_projection_removes_only_vendor_unsupported_keywords() -> None:
    schema = CONTRACTS.table_schema()
    adapted = __import__("copy").deepcopy(schema)
    count = TRANSPORTS._project_anthropic_schema(adapted)
    rendered = __import__("json").dumps(adapted)
    assert count > 0
    assert '"minimum"' not in rendered
    assert adapted["properties"]["tables"]["items"]["required"] == schema["properties"]["tables"]["items"]["required"]
    assert adapted["properties"]["tables"]["items"]["additionalProperties"] is False


def test_job_plan_has_three_table_repeats_and_separate_business_and_gridless_arms() -> None:
    jobs = HARNESS._jobs(3)
    assert len(jobs) == 15
    for provider in {item.provider for item in TRANSPORTS.PROVIDER_SPECS}:
        provider_jobs = [item for item in jobs if item["provider"] == provider]
        assert sum(item["arm"] == "tables" for item in provider_jobs) == 3
        assert sum(item["arm"] == "business" for item in provider_jobs) == 1
        assert sum(item["arm"] == "gridless" for item in provider_jobs) == 1


def test_safe_request_identity_proves_no_preprocessing() -> None:
    identity = HARNESS._safe_identity(
        {"provider": "openai", "arm": "tables", "document": "broker_pdf", "repeat": 1},
        "model", "native_pdf", b"%PDF-test", "hash", CONTRACTS.table_prompt(), CONTRACTS.table_schema(),
    )
    assert identity["input_mime_type"] == "application/pdf"
    assert identity["crop"] is False
    assert identity["raster_preprocessing"] is False
    assert identity["local_text_attached"] is False
    assert identity["normalized_payload_attached"] is False
    assert identity["hidden_failover"] is False


def test_controlled_gridless_fixture_has_no_vector_rules(tmp_path: Path) -> None:
    path = tmp_path / "gridless.pdf"
    HARNESS._create_gridless_fixture(path)
    document = fitz.open(path)
    assert len(document) == 1
    assert document[0].get_drawings() == []
    assert "Alpha" in document[0].get_text("text")


def test_checkpoint_revalidation_is_terminal_and_fail_closed() -> None:
    checkpoint = {
        "private": {"provider": "openai", "arm": "tables", "response": {"output": []}},
        "safe": {"provider": "openai", "arm": "tables", "http_status": 200},
    }
    result = HARNESS._revalidate_checkpoint(checkpoint)
    assert result["safe"]["provider_status"] == "failed"
    assert result["safe"]["parse_error"] == "structured_text_block_count_invalid"
    assert result["safe"]["validation_error"] == "output_not_object"


def test_raw_shape_diagnostic_does_not_accept_invalid_counts() -> None:
    value = _valid_table_output()
    value["tables"][0]["row_count"] = 3
    diagnostic = HARNESS._raw_table_shape_diagnostic(
        value,
        {"1:1": {"cells": [], "header_rows": 0}},
    )
    assert diagnostic["returned_tables"] == 1
    assert diagnostic["contains_all_reference_identities"] is True
    assert diagnostic["declared_row_count_mismatches"] == 1
