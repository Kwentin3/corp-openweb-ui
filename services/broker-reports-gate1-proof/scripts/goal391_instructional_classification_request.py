"""Representation-only request builder for the Goal #391 instructional lab."""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from goal391_instructional_classification_contract import PROMPT_PLACEHOLDER, response_format


def build(*, prompt_content: str, case: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    if not isinstance(prompt_content, str) or prompt_content.count(PROMPT_PLACEHOLDER) != 1:
        raise ValueError("instructional_classification_prompt_contract_invalid")
    package = json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if PROMPT_PLACEHOLDER in package or not isinstance(model_id, str) or not model_id:
        raise ValueError("instructional_classification_request_invalid")
    return {
        "model": model_id,
        "messages": [
            {"role": "system", "content": prompt_content.replace(PROMPT_PLACEHOLDER, package)},
            {"role": "user", "content": "Classify the supplied table."},
        ],
        "stream": False,
        "response_format": copy.deepcopy(response_format()),
        "metadata": {"broker_reports_goal391": {"instructional_classification": True, "chat_persistence": "forbidden"}},
    }
