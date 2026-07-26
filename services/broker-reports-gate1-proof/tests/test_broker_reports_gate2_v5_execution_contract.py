from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_semantic_v5_execution import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_PROVIDER_CALL_COMPONENTS,
    V5_PROMPT_GIT_BLOB_SHA256,
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_source_fact_contracts import (  # noqa: E402
    Gate2PromptError,
)


PROMPT_PATH = (
    ROOT
    / "managed_assets"
    / "prompts"
    / "broker_reports_gate2_financial_matching_prompt.v5.md"
)
SKILL_PATH = (
    ROOT
    / "managed_assets"
    / "skills"
    / "broker_reports_financial_domain_skill.v1.md"
)
RUNTIME_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_execution.py"
)
BUILD_SCRIPT = (
    ROOT / "scripts" / "build_gate2_financial_semantic_v5_execution.py"
)
SKILL_GIT_BLOB_SHA256 = (
    "08a405c69b66aac2fcc1ed0be355a59e2df8e2b012fc7d107fdb2243208e02d5"
)


def _portable_bytes(path: Path) -> bytes:
    return (
        path.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def _strict_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "broker_reports_gate2_v5_test",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["decision"],
                "properties": {
                    "decision": {"type": "string"},
                },
            },
        },
    }


def test_v5_execution_contract_has_one_instruction_authority():
    contract = Gate2FinancialSemanticV5ExecutionContractFactory().create()

    assert contract.provider_call_components == V5_PROVIDER_CALL_COMPONENTS
    assert contract.instruction_authorities == ("managed_prompt",)
    assert contract.gate2_skill_body_required is False
    assert contract.gate2_tool_call_required is False
    assert contract.gate3_skill_preserved_separately is True
    assert contract.semantic_pack_delivery == "system_side_compact_projection"
    assert contract.runtime_activation is False
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not include a Skill body" in FORBIDDEN


def test_v5_managed_prompt_is_self_contained_and_has_no_unavailable_refs():
    contract = Gate2FinancialSemanticV5ExecutionContractFactory().create()
    source = _portable_bytes(PROMPT_PATH)

    assert contract.prompt.content.encode("utf-8") == source
    assert hashlib.sha256(source).hexdigest() == V5_PROMPT_GIT_BLOB_SHA256
    assert contract.prompt.content.count(contract.decision_packet_marker) == 1
    lowered = contract.prompt.content.casefold()
    for unavailable in ("skill", "tool", "load_financial_semantic_pack"):
        assert unavailable not in lowered

    skill = _portable_bytes(SKILL_PATH)
    assert hashlib.sha256(skill).hexdigest() == SKILL_GIT_BLOB_SHA256


def test_v5_actual_request_equals_declared_three_component_execution():
    contract = Gate2FinancialSemanticV5ExecutionContractFactory().create()
    packet = {
        "task": {"operation": "classify_financial_evidence"},
        "source_fragment": {"values": []},
        "available_types": [],
        "binding_options": {},
    }
    response_format = _strict_response_format()
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    ).build(
        prompt=contract.prompt,
        package=packet,
        model_id="synthetic-v5-model",
        response_format=response_format,
    )

    assert set(request) == {
        "model",
        "messages",
        "stream",
        "response_format",
        "metadata",
    }
    assert request["messages"] == [
        {
            "role": "system",
            "content": contract.prompt.content.replace(
                contract.decision_packet_marker,
                json.dumps(packet, ensure_ascii=False, sort_keys=True),
            ),
        }
    ]
    assert request["response_format"] == response_format
    assert "tools" not in request
    serialized = json.dumps(request, ensure_ascii=False, sort_keys=True)
    assert contract.decision_packet_marker not in serialized
    for unavailable in (
        "skill_body",
        "tool_call",
        "tool_identity",
        "load_financial_semantic_pack",
    ):
        assert unavailable not in serialized.casefold()
    metadata = request["metadata"]["broker_reports_gate2"]
    assert metadata["execution_components"] == list(
        V5_PROVIDER_CALL_COMPONENTS
    )
    assert metadata["semantic_selection_owner"] == "llm"


def test_v5_request_rejects_non_strict_schema_and_missing_packet():
    contract = Gate2FinancialSemanticV5ExecutionContractFactory().create()
    builder = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    )
    with pytest.raises(Gate2PromptError) as missing_packet:
        builder.build(
            prompt=contract.prompt,
            package={},
            model_id="synthetic-v5-model",
            response_format=_strict_response_format(),
        )
    assert missing_packet.value.code == (
        "gate2_financial_semantic_v5_packet_invalid"
    )
    invalid = _strict_response_format()
    invalid["json_schema"]["strict"] = False
    with pytest.raises(Gate2PromptError) as non_strict_schema:
        builder.build(
            prompt=contract.prompt,
            package={"packet": True},
            model_id="synthetic-v5-model",
            response_format=invalid,
        )
    assert non_strict_schema.value.code == (
        "gate2_financial_semantic_v5_response_schema_not_strict"
    )


def test_v5_runtime_projection_is_closed_world_and_deterministic():
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imported_roots == {
        "__future__",
        "base64",
        "dataclasses",
        "hashlib",
        "zlib",
    }
    for forbidden in ("Path(", "open(", "requests", "urllib", "socket"):
        assert forbidden not in source

    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["mode"] == "check"
