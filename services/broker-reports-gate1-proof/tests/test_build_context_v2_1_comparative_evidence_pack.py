from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
BUILD_SCRIPT = (
    SERVICE_ROOT
    / "scripts"
    / "build_context_v2_1_comparative_evidence_pack.py"
)
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"
OUTPUT_STEM = (
    "BROKER_REPORTS_GATE2_CONTEXT_V2_1_"
    "EVIDENCE_FIRST_COMPARATIVE_REVIEW_GOAL14"
)
REPORT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.report.md"
TRANSPARENT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.transparent.json"
RECEIPT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.receipt.safe.json"
GOAL12_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".transparent.json"
)
AUDIT_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)

CASE_ORDER = [
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_no_registry_type",
]
EXPECTED_EXACT_OUTPUTS = {
    "syn_successor_v2_multiple_compatible": {
        "openai_gpt": {
            "choice": "unclassified",
            "reason": "single_registry_type_no_safe_record",
        },
        "anthropic_claude": (
            '{"choice": "unclassified", '
            '"reason": "ambiguous_registry_type"}'
        ),
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "openai_gpt": {
            "choice": "unclassified",
            "reason": "no_registry_type",
        },
        "anthropic_claude": (
            '{"choice": "unclassified", '
            '"reason": "single_registry_type_no_safe_record"}'
        ),
    },
    "syn_successor_v2_no_registry_type": {
        "openai_gpt": {
            "choice": "unclassified",
            "reason": "no_registry_type",
        },
        "anthropic_claude": (
            '{"choice":"unclassified","reason":"ambiguous_registry_type"}'
        ),
    },
}
EXPECTED_CONTEXT_HASHES = {
    "syn_successor_v2_multiple_compatible": (
        "4dd76de2e81a18d12af9c9a96702f975"
        "602fc1bece7ddaccc93aabef769984c2"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "bfbe343eff9f269cdbe87b677cd8a165"
        "7c75c4d7d4fb199c6edb83a79020eba0"
    ),
    "syn_successor_v2_no_registry_type": (
        "8475b9ce840a4801b4792a347306a5ba"
        "85a40a8d10e08e9cfcd80d5b914b1007"
    ),
}
EXPECTED_LOCAL_TYPES = {
    "syn_successor_v2_multiple_compatible": ["type_1", "type_2"],
    "syn_successor_v2_detail_vs_subtotal": ["type_2"],
    "syn_successor_v2_no_registry_type": [],
}
EXPECTED_ASSOCIATION_VISIBILITY = {
    "syn_successor_v2_multiple_compatible": "partial",
    "syn_successor_v2_detail_vs_subtotal": "partial",
    "syn_successor_v2_no_registry_type": "yes",
}
EXPECTED_GOAL14_PATHS = {
    ".gitattributes",
    ".github/workflows/broker-reports-ci.yml",
    (
        "docs/reports/2026-07-30/"
        f"{OUTPUT_STEM}.receipt.safe.json"
    ),
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.report.md",
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.transparent.json",
    "docs/stage2/CONTEXT_INDEX.md",
    (
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md"
    ),
    (
        "services/broker-reports-gate1-proof/scripts/"
        "build_context_v2_1_comparative_evidence_pack.py"
    ),
    (
        "services/broker-reports-gate1-proof/tests/"
        "test_build_context_v2_1_comparative_evidence_pack.py"
    ),
}


def _load_builder():
    name = "build_context_v2_1_comparative_evidence_pack_under_test"
    spec = importlib.util.spec_from_file_location(name, BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load_builder()


@pytest.fixture(scope="module")
def built_artifacts():
    return BUILDER.build_artifacts()


def test_pack_contains_exactly_three_comparative_cases_and_six_outputs(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts

    assert transparent["status"] == "completed_offline_comparative_review"
    assert transparent["active"] is False
    assert transparent["synthetic_evidence_only"] is True
    assert transparent["case_count"] == 3
    assert [item["case_id"] for item in transparent["cases"]] == CASE_ORDER
    assert receipt["case_count"] == 3
    assert transparent["model_ids"] == receipt["model_ids"] == [
        "gpt-5.4-nano-2026-03-17",
        "claude-haiku-4-5-20251001",
    ]

    outputs_total = 0
    for case in transparent["cases"]:
        assert [item["provider_profile_id"] for item in case["providers"]] == [
            "openai_gpt",
            "anthropic_claude",
        ]
        outputs_total += len(case["providers"])
        for provider in case["providers"]:
            expected = EXPECTED_EXACT_OUTPUTS[case["case_id"]][
                provider["provider_profile_id"]
            ]
            assert provider["exact_adapter_output"]["value"] == expected
    assert outputs_total == 6


def test_report_json_blocks_parse_and_match_exact_case_values(
    built_artifacts,
) -> None:
    report, transparent, _receipt = built_artifacts
    blocks = re.findall(r"```json\n(.*?)\n```", report, flags=re.DOTALL)

    assert len(blocks) == 9
    parsed = [json.loads(block) for block in blocks]
    for index, case in enumerate(transparent["cases"]):
        source, context, schema = parsed[index * 3 : index * 3 + 3]
        assert source == case["source"]["exact_source_json"]
        assert context == case["context"]["exact_semantic_context"]
        assert schema == case["context"]["exact_canonical_response_schema"]

        case_section = report.split(
            f"## Case {case['ordinal']} — `{case['case_id']}`", 1
        )[1].split("## Case ", 1)[0]
        section_a = case_section.split(
            "### A — Original source as a table", 1
        )[1].split("### B — Exact source JSON", 1)[0]
        table_rows = [
            {"meaning": match[0], "literal": match[1]}
            for match in re.findall(
                r"^\| `([^`]+)` \| `([^`]*)` \|$",
                section_a,
                flags=re.MULTILINE,
            )
        ]
        assert table_rows == case["source"]["table_rows"]
        assert (
            f"association visible: "
            f"{case['source']['association_visible']}"
        ) in section_a
        assert case["source"]["association_visible"] == (
            EXPECTED_ASSOCIATION_VISIBILITY[case["case_id"]]
        )


def test_table_json_parity_is_recomputed_from_exact_source(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts
    totals = {
        "table_rows_total": 0,
        "source_values_total": 0,
        "exact_matches_total": 0,
        "missing_total": 0,
        "duplicate_mappings_total": 0,
        "literal_mismatches_total": 0,
    }
    for case in transparent["cases"]:
        rebuilt = BUILDER._flatten_source(
            case["source"]["exact_source_json"]
        )
        assert rebuilt == case["source"]["table_rows"]
        parity = case["source"]["table_json_parity"]
        assert parity == {
            "table_rows_total": len(rebuilt),
            "source_values_total": len(rebuilt),
            "exact_matches_total": len(rebuilt),
            "missing_total": 0,
            "duplicate_mappings_total": 0,
            "literal_mismatches_total": 0,
        }
        for key in totals:
            totals[key] += parity[key]
    assert totals == receipt["table_json_parity"]
    assert totals["table_rows_total"] == 15


def test_context_hashes_and_exact_requests_match_goal12(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    goal12 = json.loads(GOAL12_PATH.read_text(encoding="utf-8"))
    terminal_by_slot = {
        item["slot_id"]: item for item in goal12["cases"]
    }

    for case in transparent["cases"]:
        case_id = case["case_id"]
        context = case["context"]
        assert (
            hashlib.sha256(
                context["exact_semantic_context_serialized"].encode("utf-8")
            ).hexdigest()
            == EXPECTED_CONTEXT_HASHES[case_id]
            == context["hashes"]["exact_user_content_utf8_sha256"]
        )
        openai = terminal_by_slot[f"openai_gpt:{case_id}"]
        anthropic = terminal_by_slot[f"anthropic_claude:{case_id}"]
        assert (
            openai["exact_system_message"]
            == anthropic["exact_system_message"]
            == context["exact_system_message"]
        )
        assert (
            openai["exact_user_content"]
            == anthropic["exact_user_content"]
            == context["exact_semantic_context_serialized"]
        )
        assert json.loads(openai["exact_user_content"]) == context[
            "exact_semantic_context"
        ]
        assert context["provider_semantic_context_byte_identical"] is True


def test_schema_availability_reasons_and_plausible_sets_are_exact(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    expected_availability = {
        "syn_successor_v2_multiple_compatible": (0, False),
        "syn_successor_v2_detail_vs_subtotal": (0, False),
        "syn_successor_v2_no_registry_type": (2, True),
    }
    reason_codes = [
        "no_registry_type",
        "single_registry_type_no_safe_record",
        "ambiguous_registry_type",
    ]

    for case in transparent["cases"]:
        choices_count, typed = expected_availability[case["case_id"]]
        context = case["context"]
        assert context["choices_count"] == choices_count
        assert context["typed_branch_present"] is typed
        assert context["unclassified_branch_present"] is True
        assert context["allowed_reason_codes"] == reason_codes
        assert case["comparison"]["plausible_local_type_set"] == (
            EXPECTED_LOCAL_TYPES[case["case_id"]]
        )


def test_expected_answers_and_mechanical_diffs_match_corrected_audit(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    audit_by_case = {item["case_id"]: item for item in audit["cases"]}

    for case in transparent["cases"]:
        audit_case = audit_by_case[case["case_id"]]
        expected = case["comparison"][
            "independently_audited_expected_answer"
        ]
        assert expected == {
            "disposition": audit_case["expected_disposition"],
            "reason_code": audit_case["expected_reason_code"],
        }
        assert len(case["comparison"]["plausible_local_type_set"]) == len(
            audit_case["plausible_type_ids"]
        )
        for provider in case["providers"]:
            assert provider["field_level_diff"] == BUILDER._mechanical_diff(
                expected,
                provider["normalized_canonical_answer"],
            )


def test_interpretation_is_bounded_and_facts_precede_it(
    built_artifacts,
) -> None:
    report, transparent, _receipt = built_artifacts
    forbidden_fact_phrases = (
        "likely",
        "probably",
        "model understood",
        "model was confused",
    )
    for case in transparent["cases"]:
        strengths = {
            item["layer"]: item["evidence_strength"]
            for item in case["bounded_interpretation"]
        }
        assert set(strengths) == {
            "source_projection",
            "type_glossary",
            "choices_presentation",
            "reason_contract",
            "model_capability",
            "expected_answer_defect",
        }
        assert strengths["reason_contract"] == "proven"
        assert strengths["expected_answer_defect"] == "not supported"
        facts = "\n".join(case["facts_before_interpretation"]).lower()
        assert not any(term in facts for term in forbidden_fact_phrases)
        assert "exact visible source literals" in facts
        assert (
            f"plausible type count is "
            f"{len(case['comparison']['plausible_local_type_set'])}"
        ) in facts
        assert (
            "expected canonical answer is "
            + BUILDER._compact_json(
                case["comparison"][
                    "independently_audited_expected_answer"
                ]
            ).lower()
        ) in facts
        case_start = report.index(f"## Case {case['ordinal']}")
        facts_start = report.index(
            "### G — Facts before interpretation", case_start
        )
        interpretation_start = report.index(
            "### H — Bounded interpretation", case_start
        )
        assert facts_start < interpretation_start
    assert "No row above establishes a causal root." in report
    assert "No final refactor is selected." in report


def test_receipt_integrity_and_safe_minimal_shape(
    built_artifacts,
) -> None:
    _report, _transparent, receipt = built_artifacts
    material = copy.deepcopy(receipt)
    supplied = material.pop("integrity_sha256")
    assert supplied == BUILDER._sha256_json(material)
    assert set(receipt) == {
        "schema_version",
        "source_evidence",
        "case_count",
        "model_ids",
        "case_hashes",
        "table_json_parity",
        "provider_calls_total",
        "runtime_changes_total",
        "historical_files_modified_total",
        "integrity_sha256",
    }
    assert receipt["provider_calls_total"] == 0
    assert receipt["runtime_changes_total"] == 0
    assert receipt["historical_files_modified_total"] == 0


def test_historical_authorities_and_privacy_remain_fail_closed(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts
    actual_hashes = BUILDER._validate_source_authorities()
    assert len(actual_hashes) == 11
    for identity, path, expected_hash in BUILDER.SOURCE_AUTHORITIES:
        repository_path = path.relative_to(REPO_ROOT).as_posix()
        repository_bytes = _git_bytes(
            "cat-file",
            "blob",
            f"HEAD:{repository_path}",
        )
        assert b"\r" not in repository_bytes, identity
        assert hashlib.sha256(repository_bytes).hexdigest() == expected_hash
    assert [
        item["repository_lf_sha256"]
        for item in receipt["source_evidence"]
    ] == list(actual_hashes.values())
    assert BUILDER._repository_lf_bytes(b"a\r\nb\n") == b"a\nb\n"
    with pytest.raises(
        ValueError,
        match="source_authority_lone_carriage_return",
    ):
        BUILDER._repository_lf_bytes(b"a\rb\n")

    for artifact in (transparent, receipt):
        BUILDER._validate_repository_safe_output(artifact)
        assert BUILDER._recursive_keys(artifact).isdisjoint(
            BUILDER._FORBIDDEN_OUTPUT_KEYS
        )
        assert "managed_to_local_type_mapping" not in (
            json.dumps(artifact, ensure_ascii=False)
        )
    assert transparent["execution_accounting"] == {
        "provider_calls_total": 0,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert set(transparent["change_accounting"].values()) == {0}


def test_builder_is_closed_world_offline_support_code() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imported_roots <= {
        "__future__",
        "argparse",
        "collections",
        "copy",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "typing",
    }
    for forbidden in (
        "sys.path",
        "execute_slot(",
        "extract_context_v2_1_once(",
        "Gate2OpenWebUIStructuredModelClient",
    ):
        assert forbidden not in source


def test_generated_files_and_check_mode_are_byte_exact(
    built_artifacts,
    tmp_path,
) -> None:
    report, transparent, receipt = built_artifacts
    assert REPORT_PATH.read_bytes() == report.encode("utf-8")
    assert TRANSPARENT_PATH.read_bytes() == BUILDER._json_bytes(transparent)
    assert RECEIPT_PATH.read_bytes() == BUILDER._json_bytes(receipt)

    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "passed"
    assert summary["mode"] == "check"
    assert summary["case_count"] == 3
    assert summary["provider_calls_total"] == 0
    assert summary["runtime_changes_total"] == 0
    assert summary["historical_files_modified_total"] == 0

    isolated = tmp_path / "artifact.json"
    expected = b'{\n  "status": "completed"\n}\n'
    outputs = {isolated: expected}
    BUILDER.write_or_check_outputs(outputs=outputs, check=False)
    BUILDER.write_or_check_outputs(outputs=outputs, check=True)
    isolated.write_bytes(expected + b"\r\n")
    with pytest.raises(
        SystemExit,
        match="context_v2_1_comparative_evidence_drift:artifact.json",
    ):
        BUILDER.write_or_check_outputs(outputs=outputs, check=True)


def test_goal14_diff_is_support_docs_evidence_only() -> None:
    changed = _goal14_changed_paths()
    report_path = REPORT_PATH.relative_to(REPO_ROOT).as_posix()
    if report_path not in changed:
        pytest.skip("not executing in the GOAL 14 change set")
    assert changed == EXPECTED_GOAL14_PATHS
    assert not any(
        path.startswith(
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
        )
        for path in changed
    )


def _goal14_changed_paths() -> set[str]:
    changed: set[str] = set()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        parents = _git("rev-list", "--parents", "-n", "1", "HEAD").split()
        if len(parents) == 3:
            changed.update(
                _git("diff", "--name-only", parents[1], "HEAD").splitlines()
            )
        else:
            changed.update(
                _git("diff", "--name-only", "origin/main...HEAD").splitlines()
            )
    else:
        changed.update(
            _git("diff", "--name-only", "origin/main...HEAD").splitlines()
        )
        changed.update(_git("diff", "--cached", "--name-only").splitlines())
        changed.update(_git("diff", "--name-only").splitlines())
        changed.update(
            _git("ls-files", "--others", "--exclude-standard").splitlines()
        )
    return {path.replace("\\", "/") for path in changed if path}


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout
