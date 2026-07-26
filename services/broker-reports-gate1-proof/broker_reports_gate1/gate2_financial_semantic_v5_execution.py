from __future__ import annotations

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
V5_PROMPT_GIT_BLOB_SHA256 = "a9002b22a7f9b14122c7c2738307e39e425cc1356b7f38c9e48ff061aa23680c"
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
    b"c-nQ7&u-f=494$%3f^|f@)SD_=nCx5IbbB(W-C*!L?z3LzWYeUNs9ry$udR$zK`SsJ`-disI;Ic2Ut+U%rZfwz?H"
    b"MWm`e|dq*N9bt`>(WU0^M=Vxc&UEGU67!B}uwNOV68zbb*w1b9MDcue+nSqTD`Sb?SgyBAq8Jd*;}ex1d#W79bo)"
    b"{7H-D6tTV0q)_!QG0yNtpvIk2hBjgF{ov6@_z_W;&5b%*D~AN6Q)K`Xrw|Cs6sNG6uWwzQTx+R6-rK2_wb#x6#?w"
    b"mak%T~DbF)q<!z|I6`Jr%Bd^!iH5X5996%>37c2YH*o^GihuK_k?A7g7k968D`O&hLGgl|Q0*GY}32Wt%9rtF_JC"
    b"c{NXxuD+&-x$b*1De*X7MK9Vm9a<B)sINpSw&Sh@e(t*K1TQEf|!&+IR<CjyyGQp^b@^s5zZn4w<Vy9OjElr>cAS"
    b"l0mZCcgRvXlG~nrgl;T%MfD!ca<X>sY^G9Z36+dwnhH(*D7h?{_>UcZP`T{Dn^{n*)nA5>`d#(b(~pz$^~d8k$j2"
    b"ws2{!Wi?DUuG%$X(0EjQg99K5c^W<SDg%d{UhMvT!G#grIkmeG`%$veL?cI;<tk=2GpF`{Cpv{&rb`bsgS=zOoQ_"
    b"wF8U`+B&Ua=32L;i+bMdmH`&ZhLE{"
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
