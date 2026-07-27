from __future__ import annotations

from dataclasses import dataclass

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
)


V6_SEMANTIC_PROMPT_VERSION = "financial_semantic_v6_candidate_choice_v1"
V6_SEMANTIC_SYSTEM_PROMPT = (
    "Return exactly one JSON object that conforms to the supplied strict "
    "response schema. Use only the task and evidence in the user message."
)
V6_SEMANTIC_PROMPT_HASH = sha256_json(V6_SEMANTIC_SYSTEM_PROMPT)


@dataclass(frozen=True)
class Gate2FinancialSemanticV6QualificationPrompt:
    version: str
    content: str
    hash: str
    packet_hash: str
    choice_schema_hash: str


def financial_semantic_v6_prompt(
    *,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
) -> Gate2FinancialSemanticV6QualificationPrompt:
    return Gate2FinancialSemanticV6QualificationPrompt(
        version=V6_SEMANTIC_PROMPT_VERSION,
        content=V6_SEMANTIC_SYSTEM_PROMPT,
        hash=V6_SEMANTIC_PROMPT_HASH,
        packet_hash=packet.packet_hash,
        choice_schema_hash=choice_contract.choice_schema_hash,
    )
