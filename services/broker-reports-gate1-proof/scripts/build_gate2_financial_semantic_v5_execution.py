#!/usr/bin/env python3
"""Build the closed-world Gate 2 V5 matching execution contract."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import textwrap
import zlib
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
PROMPT_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "prompts"
    / "broker_reports_gate2_financial_matching_prompt.v5.md"
)
RUNTIME_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_execution.py"
)
PROMPT_MARKER = "{{financial_semantic_decision_packet_json}}"


RUNTIME_TEMPLATE = '''from __future__ import annotations

import base64
import hashlib
import zlib
from dataclasses import dataclass


V5_EXECUTION_CONTRACT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_execution_contract_v1"
)
V5_PROMPT_CONTRACT_ID = (
    "broker_reports_gate2_financial_semantic_matching_prompt_v5"
)
V5_PROMPT_ASSET_ID = "broker_reports_gate2_financial_matching_prompt"
V5_PROMPT_VERSION = "5.0.0"
V5_PROMPT_REF = (
    "openwebui:broker-reports-gate2-financial-matching-v5@5.0.0"
)
V5_PROMPT_GIT_BLOB_SHA256 = "__PROMPT_GIT_BLOB_SHA256__"
V5_DECISION_PACKET_MARKER = (
    "{{financial_semantic_decision_packet_json}}"
)
V5_PROVIDER_CALL_COMPONENTS = (
    "managed_prompt",
    "decision_packet",
    "strict_response_schema",
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5ExecutionContractFactory.create is the only "
    "Gate 2 V5 matching execution-contract entrypoint"
)
FORBIDDEN = (
    "The V5 provider request must not include a Skill body, Tool call, Tool "
    "identity, duplicate instruction authority, runtime file read, or network "
    "lookup outside the canonical model-client factory"
)

_PROMPT_PAYLOAD_B85 = (
__PROMPT_PAYLOAD_LINES__
)


@dataclass(frozen=True)
class Gate2FinancialSemanticV5Prompt:
    prompt_ref: str
    content: str
    hash: str


@dataclass(frozen=True)
class Gate2FinancialSemanticV5ExecutionContract:
    schema_version: str
    prompt: Gate2FinancialSemanticV5Prompt
    provider_call_components: tuple[str, ...]
    instruction_authorities: tuple[str, ...]
    decision_packet_marker: str
    gate2_skill_body_required: bool
    gate2_tool_call_required: bool
    gate3_skill_preserved_separately: bool
    semantic_pack_delivery: str
    runtime_activation: bool


class Gate2FinancialSemanticV5ExecutionContractFactory:
    def create(self) -> Gate2FinancialSemanticV5ExecutionContract:
        content = _verified_prompt()
        return Gate2FinancialSemanticV5ExecutionContract(
            schema_version=V5_EXECUTION_CONTRACT_SCHEMA_VERSION,
            prompt=Gate2FinancialSemanticV5Prompt(
                prompt_ref=V5_PROMPT_REF,
                content=content,
                hash=V5_PROMPT_GIT_BLOB_SHA256,
            ),
            provider_call_components=V5_PROVIDER_CALL_COMPONENTS,
            instruction_authorities=("managed_prompt",),
            decision_packet_marker=V5_DECISION_PACKET_MARKER,
            gate2_skill_body_required=False,
            gate2_tool_call_required=False,
            gate3_skill_preserved_separately=True,
            semantic_pack_delivery="system_side_compact_projection",
            runtime_activation=False,
        )


def _verified_prompt() -> str:
    try:
        raw = zlib.decompress(base64.b85decode(_PROMPT_PAYLOAD_B85))
    except Exception as exc:
        raise RuntimeError("financial_semantic_v5_prompt_payload_invalid") from exc
    if hashlib.sha256(raw).hexdigest() != V5_PROMPT_GIT_BLOB_SHA256:
        raise RuntimeError("financial_semantic_v5_prompt_hash_mismatch")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("financial_semantic_v5_prompt_utf8_invalid") from exc
    lowered = content.casefold()
    if (
        content.count(V5_DECISION_PACKET_MARKER) != 1
        or "skill" in lowered
        or "tool" in lowered
        or "load_financial_semantic_pack" in lowered
    ):
        raise RuntimeError("financial_semantic_v5_prompt_contract_invalid")
    return content
'''


def _portable_text_blob(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _payload_lines(value: bytes) -> str:
    encoded = base64.b85encode(zlib.compress(value, level=9)).decode("ascii")
    return "\n".join(
        f'    b"{part}"'
        for part in textwrap.wrap(
            encoded,
            width=88,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )


def build() -> bytes:
    prompt_bytes = _portable_text_blob(PROMPT_PATH)
    content = prompt_bytes.decode("utf-8")
    lowered = content.casefold()
    if (
        content.count(PROMPT_MARKER) != 1
        or "skill" in lowered
        or "tool" in lowered
        or "load_financial_semantic_pack" in lowered
    ):
        raise ValueError("financial_semantic_v5_prompt_source_invalid")
    rendered = (
        RUNTIME_TEMPLATE.replace(
            "__PROMPT_GIT_BLOB_SHA256__",
            _sha256(prompt_bytes),
        )
        .replace("__PROMPT_PAYLOAD_LINES__", _payload_lines(prompt_bytes))
        .replace("\r\n", "\n")
    )
    return rendered.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless the generated closed-world contract is exact.",
    )
    args = parser.parse_args()
    expected = build()
    if args.check:
        if (
            not RUNTIME_PATH.is_file()
            or _portable_text_blob(RUNTIME_PATH) != expected
        ):
            raise ValueError(
                "financial_semantic_v5_execution_generated_content_mismatch"
            )
    else:
        RUNTIME_PATH.write_bytes(expected)
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "check" if args.check else "write",
                "runtime_projection_git_blob_sha256": _sha256(expected),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
