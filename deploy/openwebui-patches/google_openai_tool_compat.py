"""Representation adapter for Google's OpenAI-compatible tool protocol.

OpenWebUI remains the owner of tool execution and conversation state. This
module neither executes tools nor stores signatures outside native output.
"""
from __future__ import annotations

import copy
import json
from typing import Any


def google_tool_call_index(model_id: str, call: dict, accumulated: list[dict]) -> int | None:
    """Index a complete Gemini call; never guess the identity of a fragment."""
    if not model_id.startswith("models/gemini-"):
        return None
    function = call.get("function") or {}
    if not call.get("id") or not function.get("name") or not isinstance(function.get("arguments"), str):
        return None
    try:
        arguments = json.loads(function["arguments"])
    except (ValueError, TypeError):
        return None
    if not isinstance(arguments, dict):
        return None
    for previous in accumulated:
        if previous.get("id") == call["id"]:
            return previous.get("index")
    occupied = {item.get("index") for item in accumulated}
    index = 0
    while index in occupied:
        index += 1
    return index


def google_tool_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Carry Google's opaque provider fields unchanged through native storage."""
    extra = item.get("extra_content")
    if isinstance(extra, dict) and isinstance(extra.get("google"), dict):
        return {"extra_content": copy.deepcopy(extra)}
    return {}
