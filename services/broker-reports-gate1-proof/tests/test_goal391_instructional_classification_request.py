from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import goal391_instructional_classification_contract as contract  # noqa: E402
import goal391_instructional_classification_request as request  # noqa: E402


def test_request_embeds_case_once_and_forbids_chat_persistence() -> None:
    value = request.build(prompt_content="Do it " + contract.PROMPT_PLACEHOLDER, case={"schema_version": contract.INPUT_SCHEMA_VERSION, "table": {}}, model_id="models/gemini-3.5-flash")
    assert contract.PROMPT_PLACEHOLDER not in value["messages"][0]["content"]
    assert value["stream"] is False and "chat_id" not in value


def test_request_rejects_unbound_prompt() -> None:
    with pytest.raises(ValueError):
        request.build(prompt_content="Do it", case={}, model_id="models/gemini-3.5-flash")
