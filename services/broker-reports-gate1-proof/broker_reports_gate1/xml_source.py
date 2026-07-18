from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.parsers import expat


XML_NEUTRAL_PROFILE_ID = "broker_reports_xml_neutral_event_memory_v1"
XML_EVENT_COLUMNS = [
    "event_ordinal",
    "depth",
    "event_type",
    "node_path",
    "name",
    "attribute_name",
    "value",
]

FACTORY_REQUIRED = (
    "XmlNeutralMemoryFactory.create is the only production XML neutral-memory "
    "parser entrypoint"
)
FORBIDDEN = (
    "Callers must not enable DTD/entity expansion or assign financial semantics "
    "inside Gate 1 XML parsing"
)


class XmlNeutralMemoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class XmlNeutralMemoryConfig:
    max_input_bytes: int = 5_000_000
    max_events: int = 100_000
    max_depth: int = 64
    max_attributes: int = 100_000
    max_value_characters: int = 5_000_000


@dataclass(frozen=True)
class XmlNeutralMemoryResult:
    rows: list[list[Any]]
    safe_inventory: dict[str, int | bool]


class XmlNeutralMemoryFactory:
    def __init__(self, config: XmlNeutralMemoryConfig | None = None) -> None:
        self.config = config or XmlNeutralMemoryConfig()

    def create(self) -> "XmlNeutralMemoryParser":
        for value, code in (
            (self.config.max_input_bytes, "xml_input_budget_invalid"),
            (self.config.max_events, "xml_event_budget_invalid"),
            (self.config.max_depth, "xml_depth_budget_invalid"),
            (self.config.max_attributes, "xml_attribute_budget_invalid"),
            (
                self.config.max_value_characters,
                "xml_value_character_budget_invalid",
            ),
        ):
            if value <= 0:
                raise ValueError(code)
        return XmlNeutralMemoryParser(self.config)


class XmlNeutralMemoryParser:
    def __init__(self, config: XmlNeutralMemoryConfig) -> None:
        self.config = config

    def parse(self, content_bytes: bytes) -> XmlNeutralMemoryResult:
        if len(content_bytes) > self.config.max_input_bytes:
            raise XmlNeutralMemoryError("xml_input_byte_budget_exceeded")
        lowered = content_bytes.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise XmlNeutralMemoryError("xml_dtd_or_entity_forbidden")

        rows: list[list[Any]] = [list(XML_EVENT_COLUMNS)]
        stack: list[dict[str, Any]] = []
        root_counts: dict[str, int] = {}
        event_ordinal = 0
        attributes_total = 0
        value_characters_total = 0
        elements_total = 0
        text_events_total = 0
        comments_total = 0
        processing_instructions_total = 0

        def append_event(
            event_type: str,
            *,
            name: str = "",
            attribute_name: str = "",
            value: str = "",
            depth: int | None = None,
            node_path: str | None = None,
            coalesce_text: bool = False,
        ) -> None:
            nonlocal event_ordinal, value_characters_total, text_events_total
            event_depth = len(stack) if depth is None else depth
            path = node_path if node_path is not None else (
                str(stack[-1]["path"]) if stack else "/"
            )
            if coalesce_text and len(rows) > 1:
                previous = rows[-1]
                if (
                    previous[2] == "text"
                    and previous[1] == event_depth
                    and previous[3] == path
                ):
                    previous[6] = str(previous[6]) + value
                    value_characters_total += len(value)
                    if value_characters_total > self.config.max_value_characters:
                        raise XmlNeutralMemoryError(
                            "xml_value_character_budget_exceeded"
                        )
                    return
            event_ordinal += 1
            if event_ordinal > self.config.max_events:
                raise XmlNeutralMemoryError("xml_event_budget_exceeded")
            value_characters_total += len(value)
            if value_characters_total > self.config.max_value_characters:
                raise XmlNeutralMemoryError("xml_value_character_budget_exceeded")
            rows.append(
                [
                    event_ordinal,
                    event_depth,
                    event_type,
                    path,
                    name,
                    attribute_name,
                    value,
                ]
            )
            if event_type == "text":
                text_events_total += 1

        parser = expat.ParserCreate()
        parser.buffer_text = True
        parser.ordered_attributes = True

        def start_element(name: str, attributes: list[str]) -> None:
            nonlocal elements_total, attributes_total
            depth = len(stack) + 1
            if depth > self.config.max_depth:
                raise XmlNeutralMemoryError("xml_depth_budget_exceeded")
            siblings = stack[-1]["child_counts"] if stack else root_counts
            sibling_index = int(siblings.get(name, 0)) + 1
            siblings[name] = sibling_index
            parent_path = str(stack[-1]["path"]) if stack else ""
            node_path = f"{parent_path}/{name}[{sibling_index}]"
            stack.append({"path": node_path, "child_counts": {}})
            elements_total += 1
            append_event(
                "start_element",
                name=name,
                depth=depth,
                node_path=node_path,
            )
            pairs = list(zip(attributes[0::2], attributes[1::2]))
            attributes_total += len(pairs)
            if attributes_total > self.config.max_attributes:
                raise XmlNeutralMemoryError("xml_attribute_budget_exceeded")
            for attribute_name, value in pairs:
                append_event(
                    "attribute",
                    name=name,
                    attribute_name=str(attribute_name),
                    value=str(value),
                    depth=depth,
                    node_path=node_path,
                )

        def end_element(name: str) -> None:
            if not stack:
                raise XmlNeutralMemoryError("xml_structure_unbalanced")
            node_path = str(stack[-1]["path"])
            append_event(
                "end_element",
                name=name,
                depth=len(stack),
                node_path=node_path,
            )
            stack.pop()

        def character_data(value: str) -> None:
            if not value:
                return
            append_event("text", value=value, coalesce_text=True)

        def comment(value: str) -> None:
            nonlocal comments_total
            comments_total += 1
            append_event("comment", value=value)

        def processing_instruction(target: str, data: str) -> None:
            nonlocal processing_instructions_total
            processing_instructions_total += 1
            append_event("processing_instruction", name=target, value=data)

        def xml_decl(version: str, encoding: str | None, standalone: int) -> None:
            append_event(
                "xml_declaration",
                name=version,
                value=f"encoding={encoding or ''};standalone={standalone}",
                depth=0,
                node_path="/",
            )

        def forbidden(*_args: Any) -> None:
            raise XmlNeutralMemoryError("xml_dtd_or_entity_forbidden")

        parser.StartElementHandler = start_element
        parser.EndElementHandler = end_element
        parser.CharacterDataHandler = character_data
        parser.CommentHandler = comment
        parser.ProcessingInstructionHandler = processing_instruction
        parser.XmlDeclHandler = xml_decl
        parser.StartDoctypeDeclHandler = forbidden
        parser.EntityDeclHandler = forbidden
        parser.ExternalEntityRefHandler = lambda *_args: 0
        try:
            parser.Parse(content_bytes, True)
        except XmlNeutralMemoryError:
            raise
        except expat.ExpatError as exc:
            raise XmlNeutralMemoryError("xml_parse_failed") from exc
        if stack:
            raise XmlNeutralMemoryError("xml_structure_unbalanced")
        return XmlNeutralMemoryResult(
            rows=rows,
            safe_inventory={
                "events_total": len(rows) - 1,
                "elements_total": elements_total,
                "attributes_total": attributes_total,
                "text_events_total": text_events_total,
                "comments_total": comments_total,
                "processing_instructions_total": processing_instructions_total,
                "max_depth_observed": max((int(row[1]) for row in rows[1:]), default=0),
                "rows_total_including_header": len(rows),
                "cells_total": sum(len(row) for row in rows),
                "private_values_in_inventory": False,
                "dtd_or_entity_expansion_performed": False,
                "financial_semantics_assigned": False,
            },
        )
