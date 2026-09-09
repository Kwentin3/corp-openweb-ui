from __future__ import annotations

import json
import sqlite3

import pytest

from broker_reports_gate1.instructional_table_classification import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_CONTRACT_ID,
    prompt_hash,
)
from broker_reports_gate1.instructional_table_classification_prompt import (
    PROMPT_COMMAND,
    PROMPT_REQUIRED_TAG,
    PROMPT_SNAPSHOT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    InstructionalClassificationManagedPrompt,
    InstructionalClassificationPromptConfig,
    InstructionalClassificationPromptResolverFactory,
    validate_instructional_classification_prompt_snapshot,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingPromptError,
    OrdinaryTradeMappingPromptUserContext,
)


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


def test_native_instructional_prompt_resolver_uses_openwebui_history_and_grant(
    tmp_path,
) -> None:
    db_path = tmp_path / "webui.db"
    content = "Classify " + "{{instructional_table_classification_case_json}}" + "."
    metadata = {
        "template_id": PROMPT_TEMPLATE_ID,
        "template_kind": PROMPT_TEMPLATE_KIND,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "input_contract": INPUT_SCHEMA_VERSION,
        "output_schema_id": OUTPUT_SCHEMA_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "structured_output_required": True,
        "mapping_domain": "ordinary_trade",
    }
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE prompt (id TEXT PRIMARY KEY, command TEXT, user_id TEXT,
              name TEXT, content TEXT, data JSON, meta JSON, tags JSON,
              version_id TEXT, is_active INTEGER);
            CREATE TABLE prompt_history (id TEXT PRIMARY KEY, prompt_id TEXT, snapshot JSON);
            CREATE TABLE access_grant (id TEXT PRIMARY KEY, resource_type TEXT,
              resource_id TEXT, principal_type TEXT, principal_id TEXT, permission TEXT);
            CREATE TABLE group_member (id TEXT PRIMARY KEY, group_id TEXT, user_id TEXT);
            """
        )
        conn.execute(
            "INSERT INTO prompt VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "instructional-prompt", PROMPT_COMMAND, "owner", "Instructional",
                content, "{}", json.dumps(metadata), json.dumps([PROMPT_REQUIRED_TAG]),
                "history-1", 1,
            ),
        )
        snapshot = {
            "command": PROMPT_COMMAND,
            "content": content,
            "meta": metadata,
            "tags": [PROMPT_REQUIRED_TAG],
        }
        conn.execute(
            "INSERT INTO prompt_history VALUES (?, ?, ?)",
            ("history-1", "instructional-prompt", json.dumps(snapshot)),
        )
        conn.execute(
            "INSERT INTO access_grant VALUES (?, ?, ?, ?, ?, ?)",
            ("grant-1", "prompt", "instructional-prompt", "user", "ordinary", "read"),
        )
    resolver = InstructionalClassificationPromptResolverFactory(
        InstructionalClassificationPromptConfig(
            db_path=db_path,
            prompt_id="instructional-prompt",
            release_prompt_version="history-1",
            release_prompt_hash=prompt_hash(content),
        )
    ).create()

    prompt = resolver.resolve(OrdinaryTradeMappingPromptUserContext(user_id="ordinary"))

    assert prompt.command == PROMPT_COMMAND
    assert prompt.version == "history-1"
    assert prompt.snapshot()["prompt_ref"] == "instructional-prompt"
