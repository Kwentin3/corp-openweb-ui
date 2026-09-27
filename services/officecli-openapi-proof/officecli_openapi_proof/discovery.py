"""Bounded access to installed OfficeCLI documentation and read-only objects."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


READ_COMMANDS = {"view", "query", "get"}
HELP_COMMANDS = READ_COMMANDS | {"add", "set", "remove", "move", "swap", "batch", "validate", "create"}


def help_arguments(topic: str) -> tuple[str, ...]:
    """Validate tokens, never accept flags, filenames, or arbitrary CLI commands."""
    tokens = topic.split(" ")
    if topic in HELP_COMMANDS:
        return topic, "--help"
    if not re.fullmatch(r"(?:docx|xlsx|pptx)(?: [A-Za-z][A-Za-z0-9-]{0,63}){0,2}", topic):
        raise ValueError("Use FORMAT, FORMAT ELEMENT, or FORMAT VERB ELEMENT (docx, xlsx, pptx).")
    # Existing view aliases retain top-level usage; other format topics belong
    # to the installed CLI, including future elements and verbs.
    if len(tokens) == 2 and tokens[1] == "view":
        return tokens[1], "--help"
    return ("help", *tokens)


class ObjectReadPayload(BaseModel):
    command: Literal["view", "query", "get"]
    selector: str | None = Field(default=None, min_length=1, max_length=512,
        description="For query: official selector, e.g. picture, chart, table. Returns actual paths across the file; use these paths for edits.")
    path: str | None = Field(default=None, min_length=1, max_length=512,
        description="For get: an actual OfficeCLI object path, or / for the document root.")
    depth: int = Field(default=0, ge=0, le=2, description="For get: child depth; 0 reads only the node.")
    offset: int = Field(default=0, ge=0, description="For query: zero-based offset into the native result list.")
    limit: int = Field(default=50, ge=1, le=100, description="For query: page size. Follow next_offset until complete before making a file-wide claim.")

    @model_validator(mode="after")
    def validate_object_read(self):
        if self.command == "query" and (not self.selector or self.path is not None):
            raise ValueError("query requires selector and does not accept path")
        if self.command == "get" and (not self.path or not self.path.startswith("/") or self.selector is not None):
            raise ValueError("get requires an absolute object path and does not accept selector")
        if self.command == "view" and (self.selector is not None or self.path is not None):
            raise ValueError("view does not accept selector or path")
        for value in (self.selector, self.path):
            if value is not None and re.search(r"[\x00-\x1f\x7f]", value):
                raise ValueError("object selectors and paths must not contain control characters")
        return self


def object_arguments(source: str, payload: ObjectReadPayload) -> list[str]:
    if payload.command == "query":
        return ["query", source, payload.selector, "--json"]
    return ["get", source, payload.path, "--depth", str(payload.depth), "--json"]


def bounded_result(result, payload: ObjectReadPayload):
    """Keep native nodes intact; disclose pagination separately from native matches."""
    if payload.command == "query" and isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            nodes = data["results"]
            page = nodes[payload.offset:payload.offset + payload.limit]
            # Reduce whole-node pages to the context budget; never cut an object's properties.
            while len(page) > 1 and len(json.dumps({**result, "data": {**data, "results": page}}, ensure_ascii=False)) > 15000:
                page = page[:-1]
            end = payload.offset + len(page)
            result = {**result, "data": {**data, "results": page}, "pagination": {
                "offset": payload.offset, "returned": len(page), "total": len(nodes),
                "complete": payload.offset == 0 and end >= len(nodes),
                "next_offset": end if end < len(nodes) else None,
            }}
    if len(json.dumps(result, ensure_ascii=False)) > 16000:
        return {"success": True, "content_included": False,
            "reason": "inspection_exceeds_context_budget",
            "next_action": "Use a narrower query selector or get an actual object path with depth=0; for cells use outline then mode=text with a smaller sheet-qualified range. Source data has not been discarded."}
    return result
