from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    DOMAIN_QUALIFICATION_REQUEST_PROFILE,
    GATE2_REQUEST_PROFILES,
    Gate2OpenWebUIRequestBuilder,
)
from live_gate2_domain_economy_qualification import (  # noqa: E402
    DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION,
    DOMAIN_QUALIFICATION_OUTPUT_VERSION,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROVIDER_PROFILE_ID,
    build_domain_qualification_fixture,
    canonicalize_selection,
    domain_qualification_contract_identity,
    qualify_domain_model,
    validate_domain_qualification_output,
    write_safe_receipt_atomically,
)


MODULE_PATH = SCRIPT_DIR / "live_gate2_domain_economy_qualification.py"
GEMINI_MODEL = "models/gemini-3.1-flash-lite"


class _FakeClient:
    def __init__(self, fixture):
        self.contents = [
            copy.deepcopy(case.expected_selection) for case in fixture.cases
        ]
        self.calls = 0

    async def extract(self, **_kwargs):
        content = self.contents[self.calls]
        self.calls += 1
        profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
        return Gate2StructuredModelResult(
            content=content,
            fallback_used=False,
            repair_attempt_count=0,
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="google",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision=(gate2_provider_profile_revision(profile)),
                adapter_id=profile.adapter_id,
                adapter_version=profile.adapter_version,
                requested_model_id=GEMINI_MODEL,
                resolved_model_id=GEMINI_MODEL,
                structured_output_mode=("openwebui_response_format_json_schema"),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                canonical_request_schema_hash="a" * 64,
                adapted_request_schema_hash="b" * 64,
                schema_transform_count=2,
                duration_ms=10,
                input_tokens=400,
                output_tokens=120,
                total_tokens=520,
                reasoning_tokens=20,
                finish_reason="stop",
            ),
            economy_budget_receipt={
                "schema_version": "broker_reports_gate2_economy_budget_v1",
                "status": "passed",
                "input_tokens": 400,
                "output_tokens": 120,
                "actual_cost_usd": "0.000280000",
            },
        )


def test_fixture_is_frozen_domain_specific_and_expected_is_not_sent() -> None:
    fixture = build_domain_qualification_fixture()
    rendered_packages = json.dumps(
        [case.package["llm_context_package"] for case in fixture.cases],
        ensure_ascii=False,
        sort_keys=True,
    )

    assert len(fixture.cases) == 5
    assert len(fixture.manifest_hash) == 64
    assert {case.family for case in fixture.cases} == {
        "adjacent_currency_ownership",
        "allowed_forbidden_source_refs",
        "explicit_unclassified",
        "multiple_domain_hypotheses",
        "neighbouring_equal_values",
    }
    assert all(
        case.package["llm_context_package"]["contains_customer_data"] is False
        for case in fixture.cases
    )
    assert "expected_selection" not in rendered_packages
    assert '"expected"' not in rendered_packages
    assert "row_forbidden_tax" in rendered_packages
    assert "value_forbidden_tax_amount" in rendered_packages


def test_fixture_expected_outputs_pass_unchanged_canonical_factories() -> None:
    fixture = build_domain_qualification_fixture()

    for case in fixture.cases:
        receipt = validate_domain_qualification_output(
            case=case,
            content=copy.deepcopy(case.expected_selection),
            provider_execution={},
            budget_receipt={"status": "passed"},
        )
        assert receipt["status"] == "passed", receipt
        assert all(receipt["checks"].values()), receipt
        assert receipt["mismatch_paths"] == []
        assert receipt["metrics"]["cross_row_binding_count"] == 0
        assert receipt["metrics"]["lost_expected_candidate_count"] == 0
        assert receipt["metrics"]["invented_candidate_id_count"] == 0


def test_request_profile_is_qualification_only_and_budget_controlled() -> None:
    case = build_domain_qualification_fixture().cases[0]
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=DOMAIN_QUALIFICATION_REQUEST_PROFILE
    ).build(
        prompt=case.prompt,
        package=case.package,
        model_id=GEMINI_MODEL,
        response_format=case.response_format,
    )
    authorization = (
        Gate2EconomyBudgetSessionFactory()
        .create(request_profile=DOMAIN_QUALIFICATION_REQUEST_PROFILE)
        .prepare_call(
            form_data=form_data,
            model_id=GEMINI_MODEL,
            provider_profile_id=PROVIDER_PROFILE_ID,
            operation_identity="domain-qualification-test",
        )
    )

    assert DOMAIN_QUALIFICATION_REQUEST_PROFILE not in GATE2_REQUEST_PROFILES
    assert form_data["stream"] is False
    assert form_data["response_format"]["type"] == "json_schema"
    metadata = form_data["metadata"]["broker_reports_gate2"]
    assert metadata["domain_qualification"] is True
    assert metadata["synthetic_non_customer"] is True
    assert (
        "qualify_broker_reports_domain_candidate_binding_v1"
        in form_data["messages"][1]["content"]
    )
    assert (
        "extract_broker_reports_domain_source_facts_v0"
        not in form_data["messages"][1]["content"]
    )
    assert authorization.workload_class == "gate2_domain"
    assert authorization.prepared_form_data["reasoning_effort"] == "minimal"
    assert authorization.prepared_form_data["max_tokens"] == 4096
    assert "tools" not in authorization.prepared_form_data


def test_terminal_qualification_uses_exactly_five_bounded_calls() -> None:
    fixture = build_domain_qualification_fixture()
    client = _FakeClient(fixture)

    result = asyncio.run(
        qualify_domain_model(
            model_client=client,
            model_id=GEMINI_MODEL,
            fixture=fixture,
        )
    )

    assert client.calls == 5
    assert result["provider_calls"] == 5
    assert result["status"] == "passed"
    assert result["input_tokens"] == 2000
    assert result["output_tokens"] == 600
    assert result["actual_cost_usd"] == "0.001400000"
    aggregate = result["qualification"]["aggregate_metrics"]
    assert aggregate["cases_passed"] == 5
    assert aggregate["canonical_selection_acceptance_rate"] == 1.0
    assert aggregate["exact_expected_selection_rate"] == 1.0
    assert aggregate["cross_row_binding_count"] == 0
    assert aggregate["forbidden_source_ref_count"] == 0
    assert aggregate["lost_expected_candidate_count"] == 0
    assert aggregate["invented_candidate_id_count"] == 0
    assert result["qualification"]["raw_provider_output_included"] is False


def test_live_qualification_checkpoints_before_and_after_every_call(tmp_path) -> None:
    fixture = build_domain_qualification_fixture()
    client = _FakeClient(fixture)
    checkpoints = []
    receipt_path = tmp_path / "domain-qualification.safe.json"

    def checkpoint(execution):
        checkpoints.append(copy.deepcopy(execution))
        write_safe_receipt_atomically(path=receipt_path, payload=execution)

    result = asyncio.run(
        qualify_domain_model(
            model_client=client,
            model_id=GEMINI_MODEL,
            fixture=fixture,
            checkpoint=checkpoint,
        )
    )
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert len(checkpoints) == 6
    assert checkpoints[0]["execution_state"] == "in_progress"
    assert checkpoints[0]["provider_calls"] == 0
    assert [item["provider_calls"] for item in checkpoints] == [0, 1, 2, 3, 4, 5]
    assert checkpoints[-1]["execution_state"] == "terminal"
    assert persisted == result
    assert persisted["status"] == "passed"
    assert not list(tmp_path.glob("*.tmp"))
    assert receipt_path.read_bytes()[:3] != b"\xef\xbb\xbf"


def test_value_free_mismatch_paths_fail_without_contract_weakening() -> None:
    case = build_domain_qualification_fixture().cases[0]
    changed = copy.deepcopy(case.expected_selection)
    changed["binding_results"][0]["confidence"] = "medium"

    receipt = validate_domain_qualification_output(
        case=case,
        content=changed,
        provider_execution={},
        budget_receipt={"status": "passed"},
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["canonical_selection_valid"] is True
    assert receipt["checks"]["exact_expected_selection"] is False
    assert receipt["mismatch_paths"] == ["$.binding_results[0].confidence"]
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert "medium" not in rendered
    assert "25.00" not in rendered


def test_cross_row_and_foreign_candidate_attempt_fails_closed() -> None:
    fixture = build_domain_qualification_fixture()
    case = next(
        item
        for item in fixture.cases
        if item.case_id == "syn_domain_forbidden_neighbour_ref"
    )
    changed = copy.deepcopy(case.expected_selection)
    changed["binding_results"][0]["source_ref"] = "row_forbidden_tax"

    receipt = validate_domain_qualification_output(
        case=case,
        content=changed,
        provider_execution={},
        budget_receipt={"status": "passed"},
    )

    assert receipt["status"] == "failed"
    assert receipt["checks"]["canonical_selection_valid"] is False
    assert receipt["metrics"]["foreign_source_ref_count"] == 1
    assert receipt["metrics"]["cross_row_binding_count"] > 0
    assert receipt["metrics"]["forbidden_source_ref_count"] > 0


def test_canonicalization_does_not_change_selection_meaning() -> None:
    case = build_domain_qualification_fixture().cases[1]
    left = copy.deepcopy(case.expected_selection)
    right = copy.deepcopy(left)
    right["binding_results"][0]["selected_bindings"].reverse()
    right["binding_results"][0]["selected_relation_ids"].reverse()

    assert canonicalize_selection(left) == canonicalize_selection(right)
    assert left != right


def test_contract_identity_uses_current_provider_manifest_and_validators() -> None:
    fixture = build_domain_qualification_fixture()
    identity = domain_qualification_contract_identity(
        manifest_hash=fixture.manifest_hash
    )
    values = identity.to_dict()

    assert values["provider_route_revision"] == (
        gate2_provider_profile_revision(gate2_provider_profile(PROVIDER_PROFILE_ID))
    )
    assert fixture.manifest_hash in values["input_contract_version"]
    assert (
        DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION
        in (values["input_contract_version"])
    )
    assert values["output_contract_version"] == (DOMAIN_QUALIFICATION_OUTPUT_VERSION)
    assert (
        "domain_qualification_comparator_v1" in (values["canonical_validator_revision"])
    )
    assert all(values.values())


def test_harness_is_factory_backed_and_has_no_vendor_sdk_bypass() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "only domain qualification" in FACTORY_REQUIRED
    assert "must not use customer data" in FORBIDDEN
    assert "Gate2EconomyQualificationPolicyFactory" in source
    assert "Gate2SourceUnitRouterFactory" in source
    assert "Gate2DomainPackageBuilderFactory" in source
    assert "Gate2CandidateBindingRuntimeFactory" in source
    assert "Gate2DomainCandidateFinalizerFactory" in source
    assert "_model_client" in source
    assert not any(
        name.startswith(("openai", "anthropic", "google.generativeai"))
        for name in imported
    )
    assert "api.anthropic.com" not in source


def test_manifest_is_valid_json_and_explicitly_non_customer() -> None:
    manifest = json.loads(
        (
            ROOT / "benchmarks" / "gate2_domain_qualification_v1" / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == (DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION)
    assert manifest["contains_customer_data"] is False
    assert manifest["frozen"] is True
    assert len(manifest["cases"]) == 5
