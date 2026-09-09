from __future__ import annotations

import pytest

from broker_reports_gate1.instructional_table_classification import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_CONTRACT_ID,
)
from broker_reports_gate1.instructional_table_classification_prompt import (
    PROMPT_COMMAND,
    PROMPT_REQUIRED_TAG,
    PROMPT_SNAPSHOT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    InstructionalClassificationManagedPrompt,
    validate_instructional_classification_prompt_snapshot,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import OrdinaryTradeMappingPromptError


def _prompt() -> InstructionalClassificationManagedPrompt:
    return InstructionalClassificationManagedPrompt(
        prompt_ref="prompt-1",
        command=PROMPT_COMMAND,
        version="version-1",
        content="instruction",
        hash="a" * 64,
        source="test",
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        tags=(PROMPT_REQUIRED_TAG,),
        safe_metadata={"name": "test", "mapping_domain": "ordinary_trade"},
    )


def test_instructional_prompt_snapshot_is_separate_and_body_free() -> None:
    snapshot = _prompt().snapshot()
    assert snapshot["schema_version"] == PROMPT_SNAPSHOT_SCHEMA_VERSION
    assert "content" not in snapshot
    assert validate_instructional_classification_prompt_snapshot(snapshot) == snapshot


def test_instructional_prompt_snapshot_rejects_mapping_contract_identity() -> None:
    snapshot = _prompt().snapshot()
    snapshot["prompt_contract_id"] = "broker_reports_ordinary_trade_mapping_prompt_v1"
    with pytest.raises(OrdinaryTradeMappingPromptError):
        validate_instructional_classification_prompt_snapshot(snapshot)
