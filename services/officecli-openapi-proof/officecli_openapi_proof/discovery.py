"""Bounded access to installed OfficeCLI documentation and read-only objects."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


READ_COMMANDS = {"view", "query", "get"}
HELP_COMMANDS = READ_COMMANDS | {"add", "set", "remove", "move", "swap", "batch", "validate", "create", "raw", "raw-set", "add-part", "dump", "merge", "save", "close", "load_skill"}


def help_arguments(topic: str) -> tuple[str, ...]:
    """Validate tokens, never accept flags, filenames, or arbitrary CLI commands."""
    tokens = topic.split(" ")
    if topic == "help":
        return ("help",)
    if topic in {"docx /", "xlsx /", "pptx /"}:
        return ("help", *tokens)
    if re.fullmatch(r"(?:docx|xlsx|pptx) [A-Za-z][A-Za-z0-9-]{0,63} /", topic):
        return ("help", *tokens)
    if topic in HELP_COMMANDS:
        return topic, "--help"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", topic):
        return ("help", topic)
    if not re.fullmatch(r"(?:docx|xlsx|pptx)(?: [A-Za-z][A-Za-z0-9-]{0,63}){0,2}", topic):
        raise ValueError("Use FORMAT, FORMAT ELEMENT, or FORMAT VERB ELEMENT (docx, xlsx, pptx).")
    # Existing view aliases retain top-level usage; other format topics belong
    # to the installed CLI, including future elements and verbs.
    if len(tokens) == 2 and tokens[1] == "view":
        return tokens[1], "--help"
    return ("help", *tokens)


class ObjectReadPayload(BaseModel):
    command: Literal["view", "query", "get", "validate", "raw"]
    selector: str | None = Field(default=None, min_length=1, max_length=512,
        description="For query: official selector, e.g. picture, chart, table. Returns actual paths across the file; use these paths for edits.")
    path: str | None = Field(default=None, min_length=1, max_length=512,
        description="For get: an actual OfficeCLI object path, or /. For raw: an official part path from FORMAT raw help, e.g. /document or /workbook.")
    depth: int = Field(default=0, ge=0, le=2, description="For get: child depth; 0 reads only the node.")
    offset: int = Field(default=0, ge=0, description="For query: zero-based offset into the native result list.")
    limit: int = Field(default=50, ge=1, le=100, description="For query: page size. Follow next_offset until complete before making a file-wide claim.")
    text_offset: int = Field(default=0, ge=0, description="Character offset for an oversized JSON result. Follow next_text_offset and concatenate content fragments to recover the complete native result.")
    start: int | None = Field(default=None, ge=1, description="Native view --start.")
    end: int | None = Field(default=None, ge=1, description="Native view --end.")
    max_lines: int | None = Field(default=None, ge=1, description="Native view --max-lines; native output reports omitted content.")

    @model_validator(mode="after")
    def validate_object_read(self):
        if self.command == "query" and (not self.selector or self.path is not None):
            raise ValueError("query requires selector and does not accept path")
        if self.command in {"get", "raw"} and (not self.path or not self.path.startswith("/") or self.selector is not None):
            raise ValueError("get/raw requires an absolute object/part path and does not accept selector")
        if self.command in {"view", "validate"} and (self.selector is not None or self.path is not None):
            raise ValueError("view/validate does not accept selector or path")
        if self.command != "view" and any(v is not None for v in (self.start, self.end, self.max_lines)):
            raise ValueError("start, end and max_lines require view")
        for value in (self.selector, self.path):
            if value is not None and re.search(r"[\x00-\x1f\x7f]", value):
                raise ValueError("object selectors and paths must not contain control characters")
        return self


def object_arguments(source: str, payload: ObjectReadPayload) -> list[str]:
    if payload.command == "raw":
        return ["raw", source, payload.path, "--json"]
    if payload.command == "validate":
        return ["validate", source, "--json"]
    if payload.command == "view":
        arguments = ["view", source, payload.mode, "--json"]
        for name in ("start", "end", "max_lines"):
            value = getattr(payload, name)
            if value is not None:
                arguments.extend(["--" + name.replace("_", "-"), str(value)])
        return arguments
    if payload.command == "query":
        return ["query", source, payload.selector, "--json"]
    return ["get", source, payload.path, "--depth", str(payload.depth), "--json"]


def bounded_result(result, payload: ObjectReadPayload):
    """Keep native nodes intact; disclose pagination separately from native matches."""
    if isinstance(result, dict):
        data = result.get("data")
        key = "results" if payload.command == "query" else "sheets"
        if isinstance(data, dict) and isinstance(data.get(key), list):
            nodes = data[key]
            page = nodes[payload.offset:payload.offset + payload.limit]
            # Reduce whole-node pages to the context budget; never cut an object's properties.
            while len(page) > 1 and len(json.dumps({**result, "data": {**data, key: page}}, ensure_ascii=False)) > 15000:
                page = page[:-1]
            end = payload.offset + len(page)
            result = {**result, "data": {**data, key: page}, "pagination": {
                "offset": payload.offset, "returned": len(page), "total": len(nodes),
                "complete": payload.offset == 0 and end >= len(nodes),
                "next_offset": end if end < len(nodes) else None,
            }}
    serialized = json.dumps(result, ensure_ascii=False)
    if len(serialized) > 16000 or payload.text_offset:
        end = min(payload.text_offset + 12000, len(serialized))
        return {"encoding": "json-fragment", "content": serialized[payload.text_offset:end],
            "pagination": {"text_offset": payload.text_offset, "total_characters": len(serialized),
                "next_text_offset": end if end < len(serialized) else None,
                "complete": payload.text_offset == 0 and end == len(serialized)},
            "next_action": "Continue the same request with next_text_offset as text_offset; concatenate content fragments to recover the native JSON, including any node pagination."}
    return result
