from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ContextLintError,
    Gate2FinancialSemanticV6ContextLinterFactory,
    validate_financial_semantic_v6_linted_request,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (  # noqa: E402,E501
    financial_semantic_v6_prompt,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_source_fact_contracts import (  # noqa: E402
    Gate2PromptError,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-context-linter-test-snapshot-key"
CONTINUATION_KEY = b"v6-context-linter-test-continuation-key"
NO_PROVIDER_MODEL_ID = "context-lint-only-no-provider"


@pytest.fixture(scope="module")
def v6_fixture():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(
            V6_BASE_MANIFEST_PATH.read_text(encoding="utf-8")
        ),
    )


def _case_args(case) -> dict:
    assert case.packet is not None
    assert case.choice_contract is not None
    assert case.evidence_bundle is not None
    assert case.compilation is not None
    return {
        "packet": case.packet,
        "choice_contract": case.choice_contract,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }


def _create(factory, case, **overrides):
    args = _case_args(case)
    return factory.create(
        **args,
        candidate_payload=overrides.get(
            "candidate_payload",
            case.packet.slim_candidate.payload,
        ),
        response_schema=overrides.get(
            "response_schema",
            case.choice_contract.local_candidate.response_schema,
        ),
        alias_receipt=overrides.get(
            "alias_receipt",
            case.packet.slim_alias_receipt,
        ),
        exact_model_id=NO_PROVIDER_MODEL_ID,
    )


def _first_value(payload: dict) -> dict:
    pending = list(payload["source"]["document"]["children"])
    while pending:
        node = pending.pop(0)
        if node.get("values"):
            return node["values"][0]
        pending[0:0] = node.get("children", [])
    raise AssertionError("source_value_missing")


def test_all_frozen_requests_pass_lint_replay_and_totality(v6_fixture):
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )
    model_visible_bytes_total = 0
    estimated_tokens_total = 0
    local_outputs_total = 0
    materializations_total = 0

    for case in v6_fixture.semantic_cases:
        args = _case_args(case)
        linted = _create(factory, case)
        receipt = linted.lint_receipt

        assert receipt.status == "passed"
        assert receipt.semantic_literals_total > 0
        assert receipt.semantic_literals_covered_total == (
            receipt.semantic_literals_total
        )
        assert receipt.duplicate_literals_total == 0
        assert receipt.null_fields_total == 0
        assert receipt.opaque_ids_total == 0
        assert receipt.unmapped_aliases_total == 0
        assert receipt.orphan_aliases_total == 0
        assert receipt.alias_collisions_total == 0
        assert receipt.semantic_literal_coverage_complete is True
        assert receipt.structural_hierarchy_valid is True
        assert receipt.exact_option_coverage is True
        assert receipt.alias_receipt_integrity_valid is True
        assert receipt.provider_calls_total == 0
        assert linted.canonical_request["model"] == NO_PROVIDER_MODEL_ID
        assert linted.canonical_request["messages"][1]["content"] == (
            json.dumps(
                linted.package,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

        validate_financial_semantic_v6_linted_request(
            linted_request=linted,
            registry=v6_fixture.registry,
            **args,
        )
        totality = factory.prove_local_totality(
            linted_request=linted,
            **args,
        )
        assert totality.exact_replay is True
        assert totality.local_outputs_total == (
            len(case.choice_contract.local_candidate.choice_aliases)
            + len(
                case.choice_contract.local_candidate.unclassified_reason_codes
            )
        )
        assert totality.total_materializations_total == (
            totality.local_outputs_total
        )
        assert totality.validated_but_unmaterializable_total == 0
        assert totality.provider_calls_total == 0
        assert totality.integrity_hash == sha256_json(
            totality.integrity_payload()
        )

        model_visible_bytes_total += receipt.model_visible_utf8_bytes
        estimated_tokens_total += receipt.estimated_input_tokens
        local_outputs_total += totality.local_outputs_total
        materializations_total += totality.total_materializations_total

    assert model_visible_bytes_total == 26_404
    assert estimated_tokens_total == 7_247
    assert local_outputs_total == 32
    assert materializations_total == 32


def test_complete_model_view_contains_no_private_receipt_or_opaque_id(
    v6_fixture,
):
    case = v6_fixture.semantic_cases[0]
    linted = _create(
        Gate2FinancialSemanticV6ContextLinterFactory(
            registry=v6_fixture.registry
        ),
        case,
    )
    projection = {
        "messages": linted.canonical_request["messages"],
        "response_format": linted.canonical_request["response_format"],
    }
    serialized = json.dumps(
        projection,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    private_values = {
        case.packet.packet_hash,
        case.packet.slim_candidate.view_hash,
        case.packet.slim_alias_receipt.integrity_hash,
        case.evidence_bundle.bundle_id,
        case.evidence_bundle.document_ref,
        *case.packet.slim_alias_receipt.value_aliases.values(),
        *case.packet.slim_alias_receipt.type_aliases.values(),
        *case.packet.slim_alias_receipt.choice_aliases.values(),
    }
    assert all(value not in serialized for value in private_values)
    assert "context_lint_receipt" not in serialized
    assert "typed_option_id" not in serialized
    assert "source_value_ref" not in serialized


def test_builder_rejects_missing_or_resealed_tampered_lint_receipt(
    v6_fixture,
):
    case = v6_fixture.semantic_cases[0]
    builder = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "semantic_choice",
            "strict": True,
            "schema": case.choice_contract.local_candidate.response_schema,
        },
    }
    with pytest.raises(Gate2PromptError) as missing_receipt:
        builder.build(
            prompt=financial_semantic_v6_prompt(
                packet=case.packet,
                choice_contract=case.choice_contract,
            ),
            package=case.packet.slim_candidate.payload,
            model_id=NO_PROVIDER_MODEL_ID,
            response_format=response_format,
        )
    assert missing_receipt.value.code == (
        "gate2_financial_semantic_v6_context_lint_required"
    )

    linted = _create(
        Gate2FinancialSemanticV6ContextLinterFactory(
            registry=v6_fixture.registry
        ),
        case,
    )
    draft = replace(
        linted.lint_receipt,
        estimated_input_tokens=(
            linted.lint_receipt.estimated_input_tokens + 1
        ),
        integrity_hash="",
    )
    tampered_receipt = replace(
        draft,
        integrity_hash=sha256_json(draft.integrity_payload()),
    )
    tampered_prompt = replace(
        linted.prompt,
        context_lint_receipt=tampered_receipt,
    )
    with pytest.raises(Gate2PromptError) as tampered:
        builder.build(
            prompt=tampered_prompt,
            package=linted.package,
            model_id=NO_PROVIDER_MODEL_ID,
            response_format=linted.response_format,
        )
    assert tampered.value.code == (
        "gate2_financial_semantic_v6_context_lint_required"
    )


def test_negative_context_fixtures_fail_closed(v6_fixture):
    case = v6_fixture.semantic_cases[0]
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    _first_value(payload)["label"] = None
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_null_field",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    first_value = _first_value(payload)
    first_value["label"] = first_value["value"]
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_literal_duplicate",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    payload["choices"][0]["typed_option_id"] = next(
        iter(case.packet.slim_alias_receipt.choice_aliases.values())
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_forbidden_field",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    payload["source"]["document"]["children"][0]["label"] = next(
        iter(case.packet.slim_alias_receipt.choice_aliases.values())
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_opaque_id",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    role = payload["choices"][0]["bindings"][0].split("=", 1)[0]
    payload["choices"][0]["bindings"][0] = f"{role}=v999"
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_alias_unmapped",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    values = payload["source"]["document"]["children"][0]["children"][0][
        "values"
    ]
    values[1]["alias"] = values[0]["alias"]
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_alias_collision",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    row = payload["source"]["document"]["children"][0]["children"][0]
    row["kind"] = "section"
    row["alias"] = "s1"
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_hierarchy_invalid",
    ):
        _create(factory, case, candidate_payload=payload)

    payload = copy.deepcopy(case.packet.slim_candidate.payload)
    payload["choices"] = list(reversed(payload["choices"]))
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_option_coverage_invalid",
    ):
        _create(factory, case, candidate_payload=payload)


def test_orphan_collision_receipt_tamper_and_replay_tamper_fail_closed(
    v6_fixture,
):
    case = v6_fixture.semantic_cases[0]
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )
    receipt = case.packet.slim_alias_receipt

    orphan_receipt = replace(
        receipt,
        structural_aliases={
            **receipt.structural_aliases,
            "g99": {
                "kind": "evidence group",
                "association_ref": "private:orphan",
                "page_ref": None,
                "table_ref": None,
                "row_ref": None,
                "cell_ref": None,
                "text_segment_ref": None,
            },
        },
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_alias_orphan",
    ):
        _create(factory, case, alias_receipt=orphan_receipt)

    tampered_receipt = replace(receipt, integrity_hash="0" * 64)
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_receipt_integrity_invalid",
    ):
        _create(factory, case, alias_receipt=tampered_receipt)

    linted = _create(factory, case)
    tampered_linted = replace(
        linted,
        lint_receipt=replace(
            linted.lint_receipt,
            integrity_hash="0" * 64,
        ),
    )
    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_replay_mismatch",
    ):
        validate_financial_semantic_v6_linted_request(
            linted_request=tampered_linted,
            registry=v6_fixture.registry,
            **_case_args(case),
        )

    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_lint_replay_invalid",
    ):
        validate_financial_semantic_v6_linted_request(
            linted_request=replace(linted, response_format={}),
            registry=v6_fixture.registry,
            **_case_args(case),
        )


def test_reversed_option_projection_is_linted_and_total(v6_fixture):
    case = next(
        item
        for item in v6_fixture.semantic_cases
        if item.case_id == "syn_successor_v2_unique_cash"
    )
    exact_ids = tuple(
        option.typed_option_id for option in case.compilation.typed_options
    )
    packet = Gate2FinancialSemanticV6PacketFactory(
        registry=v6_fixture.registry
    ).create(
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
        slim_choice_order=tuple(reversed(exact_ids)),
    )
    choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=v6_fixture.registry
    ).create(
        packet=packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )
    args = {
        "packet": packet,
        "choice_contract": choice_contract,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )
    linted = factory.create(
        **args,
        candidate_payload=packet.slim_candidate.payload,
        response_schema=choice_contract.local_candidate.response_schema,
        alias_receipt=packet.slim_alias_receipt,
        exact_model_id=NO_PROVIDER_MODEL_ID,
    )
    totality = factory.prove_local_totality(
        linted_request=linted,
        **args,
    )

    assert tuple(packet.slim_alias_receipt.choice_aliases.values()) == (
        tuple(reversed(exact_ids))
    )
    assert linted.lint_receipt.status == "passed"
    assert linted.lint_receipt.provider_calls_total == 0
    assert totality.local_outputs_total == 4
    assert totality.total_materializations_total == 4


def test_generated_domain_bundle_loads_linted_profile_and_fails_closed():
    bundle_path = (
        ROOT
        / "openwebui_actions"
        / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
    )
    script = """
import importlib.util
import sys
from types import SimpleNamespace

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("closed_world_bundle", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_source_fact_contracts import Gate2PromptError

builder = Gate2OpenWebUIRequestBuilder(
    request_profile=FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
)
try:
    builder.build(
        prompt=SimpleNamespace(content="x"),
        package={"choices": []},
        model_id="none",
        response_format={},
    )
except Gate2PromptError as exc:
    assert exc.code == "gate2_financial_semantic_v6_context_lint_required"
else:
    raise AssertionError("missing_lint_receipt_was_accepted")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(bundle_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, (
        completed.stdout,
        completed.stderr,
    )
