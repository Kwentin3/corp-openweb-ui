from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    TOKEN_ESTIMATOR_ID,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ContextLintError,
    Gate2FinancialSemanticV6ContextLinterFactory,
    validate_financial_semantic_v6_context_v2_1_request_budget,
    validate_financial_semantic_v6_context_v2_1_sealed_request,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    CONTEXT_V2_1_FORBIDDEN_FIELDS,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (  # noqa: E402,E501
    V6_SEMANTIC_PROMPT_HASH,
    V6_SEMANTIC_PROMPT_VERSION,
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)


V6_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
V6_BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_KEY = b"v6-context-v2-1-linter-test-snapshot-key"
CONTINUATION_KEY = b"v6-context-v2-1-linter-test-continuation-key"
SEALED_REQUEST_SCHEMA_VERSION = (
    "broker_reports_gate2_llm_semantic_context_v2_1_"
    "sealed_request_receipt_v1"
)
SEALED_REQUEST_PROFILE = (
    "broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate"
)
SEALED_REQUEST_POLICY_VERSION = (
    "broker_reports_gate2_minimal_model_surface_v1"
)
SEALED_REQUEST_MAX_UTF8_BYTES = 4_500
GOVERNED_CASE_IDS = (
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_unique_printed_total",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_missing_discriminator",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
    "syn_successor_v2_optional_missing",
    "syn_successor_v2_forbidden_neighbour",
)
REQUEST_BASELINES = {
    "syn_successor_v2_unique_cash": (
        3_522,
        945,
        "68b9ca4e89e39a2ebca45867761d54bc1ed1afbe9d1994ddedd04e55b0982c3e",
    ),
    "syn_successor_v2_unique_printed_total": (
        3_520,
        944,
        "3f4ab178e4a7d66fb991ef579274a6cdf421fd1b8827d972a7f20865c37a1fcc",
    ),
    "syn_successor_v2_multiple_compatible": (
        3_359,
        904,
        "303681e6f94e012ba6891950fde6128dd533e23c5783f25a33b4e14efa54a161",
    ),
    "syn_successor_v2_no_registry_type": (
        3_517,
        944,
        "b2edde39e5ae1b9f1a871db49bdfb619dc5f7c719169ccd42231187cc0963a6a",
    ),
    "syn_successor_v2_missing_discriminator": (
        3_453,
        928,
        "9e7ec60708e70e786f4b2495585de34cfc77ff7b98d35eb6c3ce4654774856a8",
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        3_311,
        892,
        "c6f53bdf45df0ccbc26b67c71f48cc9b638d70132ed0f4f156b6e994c6a72116",
    ),
    "syn_successor_v2_adjacent_equal": (
        3_307,
        891,
        "e26f568b74bfe25a1fd3a542b4a34bc2fde5e53b9a8cbf76546ba15fbf444c09",
    ),
    "syn_successor_v2_adjacent_fx": (
        3_359,
        904,
        "1dd8bf625bf08beb2ca673e75d4b64018735f78bf793f19fb47031e000a3045f",
    ),
    "syn_successor_v2_optional_missing": (
        3_520,
        944,
        "86df255e64744dac204addba9f34170bf2593f0051fba35d627ca34df5f5dfe6",
    ),
    "syn_successor_v2_forbidden_neighbour": (
        3_521,
        945,
        "72e71a5382f90bedeb9baa8c0c6280481ca46bc54f8ee49ddda68dc494b56159",
    ),
}
RESPONSE_SCHEMA_HASH_BY_TYPED_CHOICES = {
    0: "bd17c1792c0b42e24c7639d4dc5614e1c961942245fca76a32a40566f8b5bb90",
    2: "0b726d1b40ceefee44abc53cdf9d343c09c06457201841ac30d84cb1bd05efc4",
}
INVARIANT_COUNTER_KEYS = (
    "opaque_global_ids",
    "backend_hashes",
    "duplicate_literals",
    "null_fields",
    "unused_or_orphan_keys",
    "unexplained_reason_codes",
    "semantic_literals_total",
    "semantic_literals_covered_total",
    "mapping_rows_total",
    "mapping_rows_covered_total",
)
ZERO_TARGET_COUNTERS = INVARIANT_COUNTER_KEYS[:6]
_HEX_SHA256_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


@pytest.fixture(scope="module")
def v6_fixture():
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=json.loads(V6_MANIFEST_PATH.read_text(encoding="utf-8")),
        base_manifest=json.loads(
            V6_BASE_MANIFEST_PATH.read_text(encoding="utf-8")
        ),
    )


def _model_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _model_hash(value) -> str:
    return hashlib.sha256(_model_bytes(value)).hexdigest()


def _case_args(case) -> dict:
    return {
        "packet": case.packet,
        "choice_contract": case.choice_contract,
        "evidence_bundle": case.evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": case.compilation,
    }


def _response_format(case) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": copy.deepcopy(
                case.choice_contract.context_v2_1_response_profile.response_schema
            ),
        },
    }


def _serialized_context(case) -> str:
    return _model_bytes(case.packet.context_v2_candidate.payload).decode(
        "utf-8"
    )


def _create(factory, case, **overrides):
    return factory.create_context_v2_1(
        **_case_args(case),
        system_message=overrides.get(
            "system_message",
            V6_SEMANTIC_SYSTEM_PROMPT,
        ),
        serialized_context=overrides.get(
            "serialized_context",
            _serialized_context(case),
        ),
        response_format=overrides.get(
            "response_format",
            _response_format(case),
        ),
        mapping_receipt=overrides.get(
            "mapping_receipt",
            case.packet.context_v2_mapping_receipt,
        ),
    )


def _validate(sealed, case, v6_fixture) -> None:
    validate_financial_semantic_v6_context_v2_1_sealed_request(
        sealed_request=sealed,
        registry=v6_fixture.registry,
        **_case_args(case),
        system_message=V6_SEMANTIC_SYSTEM_PROMPT,
        mapping_receipt=case.packet.context_v2_mapping_receipt,
    )


def _mapping_rows_total(case) -> int:
    summary = case.packet.context_v2_mapping_receipt.safe_summary()
    return sum(
        (
            summary["source_occurrences_total"],
            summary["source_structures_total"],
            summary["type_mappings_total"],
            summary["choice_restoration_total"],
            summary["visible_differentiator_bindings_total"],
            summary["backend_only_bindings_total"],
        )
    )


def _resealed_mapping_receipt_tamper(case):
    receipt = case.packet.context_v2_mapping_receipt
    identities = copy.deepcopy(receipt.identities)
    identities["context_view_hash"] = "0" * 64
    draft = replace(
        receipt,
        identities=identities,
        integrity_hash="",
    )
    material = draft.to_private_dict()
    material.pop("integrity_hash")
    return replace(draft, integrity_hash=sha256_json(material))


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def test_all_governed_context_v2_1_requests_are_exact_sealed_and_within_budget(
    v6_fixture,
):
    assert tuple(
        case.case_id for case in v6_fixture.semantic_cases
    ) == GOVERNED_CASE_IDS
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )
    request_bytes_total = 0
    estimated_tokens_total = 0
    semantic_literals_total = 0
    mapping_rows_total = 0

    for case in v6_fixture.semantic_cases:
        sealed = _create(factory, case)
        receipt = sealed.sealed_request_receipt
        response_profile = (
            case.choice_contract.context_v2_1_response_profile
        )
        expected_response_format = _response_format(case)
        expected_serialized_context = _serialized_context(case)
        expected_request = {
            "messages": [
                {
                    "role": "system",
                    "content": V6_SEMANTIC_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": expected_serialized_context,
                },
            ],
            "response_format": expected_response_format,
        }
        expected_bytes, expected_tokens, expected_hash = REQUEST_BASELINES[
            case.case_id
        ]
        request_bytes = _model_bytes(expected_request)
        counters = receipt.invariant_counters
        expected_semantic_literals = (
            case.packet.context_v2_mapping_receipt.safe_summary()[
                "source_occurrences_total"
            ]
        )
        expected_mapping_rows = _mapping_rows_total(case)

        assert sealed.serialized_context == expected_serialized_context
        assert sealed.response_format == expected_response_format
        assert sealed.model_visible_request == expected_request
        assert sealed.active is False
        assert sealed.transport_eligible is False
        assert tuple(sealed.model_visible_request) == (
            "messages",
            "response_format",
        )
        assert tuple(sealed.response_format) == ("type", "json_schema")
        assert tuple(sealed.response_format["json_schema"]) == (
            "strict",
            "schema",
        )
        assert "name" not in sealed.response_format["json_schema"]
        assert "title" not in json.dumps(
            response_profile.response_schema,
            ensure_ascii=False,
        )
        assert len(request_bytes) == receipt.model_visible_utf8_bytes
        assert len(request_bytes) == expected_bytes
        assert len(request_bytes) <= SEALED_REQUEST_MAX_UTF8_BYTES
        assert _model_hash(expected_request) == expected_hash
        assert receipt.model_visible_request_hash == expected_hash
        assert receipt.schema_version == SEALED_REQUEST_SCHEMA_VERSION
        assert receipt.policy_version == SEALED_REQUEST_POLICY_VERSION
        assert receipt.request_profile == SEALED_REQUEST_PROFILE
        assert receipt.mapping_receipt_integrity_hash == (
            case.packet.context_v2_mapping_receipt.integrity_hash
        )
        assert receipt.context_view_hash == (
            case.packet.context_v2_candidate.view_hash
        )
        assert receipt.system_prompt_version == V6_SEMANTIC_PROMPT_VERSION
        assert receipt.system_prompt_hash == V6_SEMANTIC_PROMPT_HASH
        assert receipt.local_response_profile_identity == (
            response_profile.schema_version
        )
        assert receipt.response_schema_hash == (
            response_profile.response_schema_hash
        )
        assert receipt.response_schema_hash == (
            RESPONSE_SCHEMA_HASH_BY_TYPED_CHOICES[
                len(case.choice_contract.local_candidate.choice_aliases)
            ]
        )
        assert receipt.response_format_hash == _model_hash(
            expected_response_format
        )
        assert receipt.token_estimator_id == TOKEN_ESTIMATOR_ID
        assert receipt.estimated_input_tokens == expected_tokens
        assert tuple(counters) == INVARIANT_COUNTER_KEYS
        assert counters["semantic_literals_total"] == (
            expected_semantic_literals
        )
        assert counters["semantic_literals_covered_total"] == (
            expected_semantic_literals
        )
        assert counters["mapping_rows_total"] == expected_mapping_rows
        assert counters["mapping_rows_covered_total"] == (
            expected_mapping_rows
        )
        assert all(counters[key] == 0 for key in ZERO_TARGET_COUNTERS)
        assert receipt.status == "passed"
        assert receipt.provider_calls_total == 0
        assert sealed.safe_summary()["provider_calls_total"] == 0
        receipt_material = asdict(receipt)
        receipt_integrity = receipt_material.pop("integrity_hash")
        assert receipt_integrity == sha256_json(receipt_material)

        _validate(sealed, case, v6_fixture)
        request_bytes_total += expected_bytes
        estimated_tokens_total += expected_tokens
        semantic_literals_total += expected_semantic_literals
        mapping_rows_total += expected_mapping_rows

    assert request_bytes_total == 34_389
    assert estimated_tokens_total == 9_241
    assert semantic_literals_total == 45
    assert mapping_rows_total == 156


def test_complete_request_has_no_private_refs_hashes_or_forbidden_fields(
    v6_fixture,
):
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )

    for case in v6_fixture.semantic_cases:
        sealed = _create(factory, case)
        serialized_request = _model_bytes(
            sealed.model_visible_request
        ).decode("utf-8")
        private_values = {
            case.packet.packet_hash,
            case.packet.context_v2_candidate.view_hash,
            case.packet.context_v2_mapping_receipt.integrity_hash,
            case.evidence_bundle.bundle_id,
            case.evidence_bundle.integrity_hash,
            case.compilation.integrity_hash,
            *(
                option.typed_option_id
                for option in case.compilation.typed_options
            ),
            *(
                item["source_value_ref"]
                for item in case.packet.context_v2_mapping_receipt.source_mappings[
                    "occurrences"
                ]
            ),
        }
        parsed_context = json.loads(sealed.serialized_context)

        assert _HEX_SHA256_RE.search(serialized_request) is None
        assert all(value not in serialized_request for value in private_values)
        assert all(
            CONTEXT_V2_1_FORBIDDEN_FIELDS.isdisjoint(item)
            for item in _walk_dicts(parsed_context)
        )
        assert "integrity_hash" not in serialized_request
        assert "mapping_receipt" not in serialized_request
        assert "typed_option_id" not in serialized_request
        assert "source_value_ref" not in serialized_request


@pytest.mark.parametrize(
    ("field", "mutate"),
    (
        (
            "system_message",
            lambda case: V6_SEMANTIC_SYSTEM_PROMPT + " ",
        ),
        (
            "serialized_context",
            lambda case: _serialized_context(case) + " ",
        ),
        (
            "response_format",
            lambda case: {
                "json_schema": {
                    "schema": copy.deepcopy(
                        case.choice_contract.context_v2_1_response_profile.response_schema
                    ),
                    "strict": True,
                },
                "type": "json_schema",
            },
        ),
        (
            "mapping_receipt",
            _resealed_mapping_receipt_tamper,
        ),
    ),
)
def test_authority_input_tampering_fails_closed(
    v6_fixture,
    field,
    mutate,
):
    case = v6_fixture.semantic_cases[0]
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=v6_fixture.registry
    )

    with pytest.raises(Gate2FinancialSemanticV6ContextLintError):
        _create(factory, case, **{field: mutate(case)})


def test_request_schema_and_resealed_receipt_tampering_fail_closed(
    v6_fixture,
):
    case = v6_fixture.semantic_cases[0]
    sealed = _create(
        Gate2FinancialSemanticV6ContextLinterFactory(
            registry=v6_fixture.registry
        ),
        case,
    )
    tampered_request = copy.deepcopy(sealed.model_visible_request)
    tampered_request["messages"][1]["content"] += " "

    with pytest.raises(Gate2FinancialSemanticV6ContextLintError):
        _validate(
            replace(sealed, model_visible_request=tampered_request),
            case,
            v6_fixture,
        )

    reordered_request = {
        "response_format": copy.deepcopy(sealed.response_format),
        "messages": [
            {
                "content": message["content"],
                "role": message["role"],
            }
            for message in sealed.model_visible_request["messages"]
        ],
    }
    assert reordered_request == sealed.model_visible_request
    assert _model_bytes(reordered_request) != _model_bytes(
        sealed.model_visible_request
    )
    with pytest.raises(Gate2FinancialSemanticV6ContextLintError):
        _validate(
            replace(sealed, model_visible_request=reordered_request),
            case,
            v6_fixture,
        )

    draft_receipt = replace(
        sealed.sealed_request_receipt,
        estimated_input_tokens=(
            sealed.sealed_request_receipt.estimated_input_tokens + 1
        ),
        integrity_hash="",
    )
    receipt_material = asdict(draft_receipt)
    receipt_material.pop("integrity_hash")
    forged_receipt = replace(
        draft_receipt,
        integrity_hash=sha256_json(receipt_material),
    )
    with pytest.raises(Gate2FinancialSemanticV6ContextLintError):
        _validate(
            replace(sealed, sealed_request_receipt=forged_receipt),
            case,
            v6_fixture,
        )


def test_complete_request_budget_guard_rejects_overflow():
    oversized = {
        "messages": [
            {"role": "system", "content": V6_SEMANTIC_SYSTEM_PROMPT},
            {"role": "user", "content": ""},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": {
                    "anyOf": [],
                },
            },
        },
    }
    exact_overflow_bytes = SEALED_REQUEST_MAX_UTF8_BYTES + 1
    envelope_bytes = len(_model_bytes(oversized))
    oversized["messages"][1]["content"] = "x" * (
        exact_overflow_bytes - envelope_bytes
    )
    assert len(_model_bytes(oversized)) == exact_overflow_bytes

    with pytest.raises(
        Gate2FinancialSemanticV6ContextLintError,
        match="financial_semantic_v6_context_v2_1_request_budget_exceeded",
    ):
        validate_financial_semantic_v6_context_v2_1_request_budget(
            oversized
        )
