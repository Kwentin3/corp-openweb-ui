from __future__ import annotations

import asyncio
import hashlib

import pytest

from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingPromptError,
    OrdinaryTradeMappingPromptUserContext,
)
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG,
    PROMPT_SNAPSHOT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    DisabledPdfTableContinuationAnnotationPromptResolver,
    OpenWebUIServerPdfTableContinuationAnnotationPromptResolver,
    PdfTableContinuationAnnotationExecution,
    PdfTableContinuationAnnotationManagedPrompt,
    PdfTableContinuationAnnotationPromptConfig,
    PdfTableContinuationAnnotationPromptResolverFactory,
    StaticPdfTableContinuationAnnotationPromptResolver,
    pdf_table_continuation_annotation_prompt_hash,
    validate_pdf_table_continuation_annotation_prompt_snapshot,
)


def _prompt() -> PdfTableContinuationAnnotationManagedPrompt:
    content = "Classify physical table continuations only."
    return PdfTableContinuationAnnotationManagedPrompt(
        prompt_ref="prompt-1",
        command=PROMPT_COMMAND,
        version="history-1",
        content=content,
        hash=pdf_table_continuation_annotation_prompt_hash(content),
        source="test",
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_ID,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        tags=(PROMPT_REQUIRED_TAG,),
        safe_metadata={"name": "test"},
    )


def _user(user_id: str) -> OrdinaryTradeMappingPromptUserContext:
    return OrdinaryTradeMappingPromptUserContext(user_id=user_id)


def test_snapshot_is_own_contract_and_body_free() -> None:
    prompt = _prompt()
    snapshot = prompt.snapshot()

    assert snapshot["schema_version"] == PROMPT_SNAPSHOT_SCHEMA_VERSION
    assert "content" not in snapshot
    assert prompt.content not in str(snapshot)
    assert validate_pdf_table_continuation_annotation_prompt_snapshot(snapshot) == snapshot


def test_execution_binds_instruction_to_the_body_free_prompt_receipt() -> None:
    prompt = _prompt()
    execution = PdfTableContinuationAnnotationExecution.from_managed_prompt(prompt)

    assert execution.content == prompt.content
    assert execution.content_sha256 == hashlib.sha256(
        prompt.content.encode("utf-8")
    ).hexdigest()
    assert execution.prompt_snapshot == prompt.snapshot()

    snapshot = prompt.snapshot()
    snapshot["prompt_hash"] = "a" * 64
    with pytest.raises(OrdinaryTradeMappingPromptError) as mismatch:
        PdfTableContinuationAnnotationExecution(
            content=prompt.content,
            prompt_snapshot=snapshot,
        )
    assert mismatch.value.code == "pdf_table_continuation_annotation_execution_invalid"


def test_snapshot_rejects_foreign_identity_or_annotation_domain() -> None:
    snapshot = _prompt().snapshot()
    snapshot["prompt_contract_id"] = "broker_reports_ordinary_trade_mapping_prompt_v1"
    with pytest.raises(OrdinaryTradeMappingPromptError) as foreign:
        validate_pdf_table_continuation_annotation_prompt_snapshot(snapshot)
    assert foreign.value.code == "pdf_table_continuation_annotation_prompt_snapshot_invalid"

    snapshot = _prompt().snapshot()
    snapshot["safe_metadata"]["annotation_domain"] = "financial_roles"
    with pytest.raises(OrdinaryTradeMappingPromptError) as semantic_leak:
        validate_pdf_table_continuation_annotation_prompt_snapshot(snapshot)
    assert semantic_leak.value.code == "pdf_table_continuation_annotation_prompt_snapshot_invalid"


def test_static_and_disabled_resolvers_are_fail_closed_for_anonymous_user() -> None:
    static = StaticPdfTableContinuationAnnotationPromptResolver(_prompt())
    assert asyncio.run(static.resolve(_user("ordinary"))).prompt_ref == "prompt-1"
    with pytest.raises(OrdinaryTradeMappingPromptError) as anonymous:
        asyncio.run(static.resolve(_user("")))
    assert anonymous.value.code == "pdf_table_continuation_annotation_prompt_access_denied"

    with pytest.raises(OrdinaryTradeMappingPromptError) as disabled:
        asyncio.run(
            DisabledPdfTableContinuationAnnotationPromptResolver().resolve(_user("ordinary"))
        )
    assert disabled.value.code == "pdf_table_continuation_annotation_prompt_disabled"


@pytest.mark.parametrize(
    "config",
    [
        PdfTableContinuationAnnotationPromptConfig(source="openwebui_server"),
        PdfTableContinuationAnnotationPromptConfig(
            source="openwebui_server",
            release_prompt_version="history-1",
            release_prompt_hash="not-a-hash",
        ),
    ],
    ids=["missing-pin", "malformed-pin"],
)
def test_native_factory_requires_complete_release_pin(config) -> None:
    with pytest.raises(OrdinaryTradeMappingPromptError) as invalid:
        PdfTableContinuationAnnotationPromptResolverFactory(config).create_async()
    assert invalid.value.code == "pdf_table_continuation_annotation_prompt_release_pin_invalid"


def test_native_factory_exposes_only_native_server_or_explicit_disabled_mode() -> None:
    disabled = PdfTableContinuationAnnotationPromptResolverFactory(
        PdfTableContinuationAnnotationPromptConfig()
    ).create_async()
    assert isinstance(disabled, DisabledPdfTableContinuationAnnotationPromptResolver)

    resolver = PdfTableContinuationAnnotationPromptResolverFactory(
        PdfTableContinuationAnnotationPromptConfig(
            source="openwebui_server",
            release_prompt_version="history-1",
            release_prompt_hash="a" * 64,
        )
    ).create_async()
    assert isinstance(resolver, OpenWebUIServerPdfTableContinuationAnnotationPromptResolver)

    with pytest.raises(OrdinaryTradeMappingPromptError) as sqlite:
        PdfTableContinuationAnnotationPromptResolverFactory(
            PdfTableContinuationAnnotationPromptConfig(source="openwebui_sqlite")
        ).create_async()
    assert sqlite.value.code == "pdf_table_continuation_annotation_prompt_unavailable"


def test_native_adapter_accepts_instruction_only_contract_without_document_placeholder() -> None:
    resolver = PdfTableContinuationAnnotationPromptResolverFactory(
        PdfTableContinuationAnnotationPromptConfig(
            source="openwebui_server",
            release_prompt_version="history-1",
            release_prompt_hash="a" * 64,
        )
    ).create_async()
    content = "Assess only physical table continuations."
    metadata = {
        "template_id": PROMPT_TEMPLATE_ID,
        "template_kind": PROMPT_TEMPLATE_KIND,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "input_contract": INPUT_SCHEMA_VERSION,
        "output_schema_id": OUTPUT_SCHEMA_ID,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "structured_output_required": True,
        "annotation_domain": "physical_table_continuation",
    }
    snapshot = {
        "command": PROMPT_COMMAND,
        "content": content,
        "meta": metadata,
        "tags": [PROMPT_REQUIRED_TAG],
    }
    row = {"id": "prompt-1", "name": "Tables", **snapshot}

    assert resolver._matches_contract(snapshot)
    resolved = resolver._snapshot_to_prompt(row, snapshot, version="history-1")
    assert resolved.hash == pdf_table_continuation_annotation_prompt_hash(content)
    assert validate_pdf_table_continuation_annotation_prompt_snapshot(
        resolved.snapshot()
    ) == resolved.snapshot()

    metadata["annotation_domain"] = "financial_roles"
    assert not resolver._matches_contract(snapshot)
