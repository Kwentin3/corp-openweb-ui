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
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    InstructionalClassificationManagedPrompt,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseError,
    OrdinaryTradeMappingCaseFactory,
)

import test_broker_reports_issue312_mapping_case as mapping_case


def _snapshot() -> dict:
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
    ).snapshot()


def _state(*, pending: str | None = "table_1") -> dict:
    return {
        "schema_version": "broker_reports_instructional_table_classification_state_v1",
        "target_table_node_ids": ["table_1"],
        "completed_table_outcomes": [],
        "pending_table_node_id": pending,
    }


def test_instructional_progress_is_private_v5_and_not_published(tmp_path) -> None:
    store, context, document_id, *_ = mapping_case._unknown_case(tmp_path)
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()

    _record, payload = cases.save_instructional_classification_state(
        document_id=document_id,
        context=context,
        status="MAPPING_REQUIRED",
        message="Instructional classification is in progress.",
        instructional_classification_state=_state(),
        instructional_prompt_snapshot=_snapshot(),
        provider_calls_total=0,
    )

    # Instructional state has no physical-table sidecar binding.  It must
    # remain the v5 receipt instead of claiming the v6 continuation contract.
    assert payload["schema_version"] == "broker_reports_ordinary_trade_mapping_case_v5"
    assert payload["instructional_classification_state"]["pending_table_node_id"] == "table_1"
    assert payload["qualified_mappings"] == []
    assert payload["table_resolutions"] == []
    assert cases.qualified_material(document_id=document_id, context=context) is None


def test_instructional_progress_rejects_non_prefix_resume_state(tmp_path) -> None:
    store, context, document_id, *_ = mapping_case._unknown_case(tmp_path)
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()

    with pytest.raises(OrdinaryTradeMappingCaseError) as exc:
        cases.save_instructional_classification_state(
            document_id=document_id,
            context=context,
            status="MAPPING_REQUIRED",
            message="Invalid state.",
            instructional_classification_state=_state(pending=None),
            instructional_prompt_snapshot=_snapshot(),
            provider_calls_total=0,
        )
    assert exc.value.code == "ordinary_trade_mapping_case_instructional_state_invalid"
