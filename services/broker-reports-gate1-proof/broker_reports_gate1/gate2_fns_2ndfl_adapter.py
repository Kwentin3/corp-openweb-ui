from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .contracts import stable_digest
from .gate2_fns_2ndfl_contracts import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    FACT_RESTRICTIONS,
    FNS_SCHEMA_FAMILY,
    TYPED_FACTS_SCHEMA_VERSION,
    XML_EVENT_COLUMNS,
    integrity_ref,
    validate_fns_2ndfl_typed_output,
)


FACTORY_REQUIRED = (
    "Gate2Fns2NdflAdapterFactory.create is the only production typed FNS "
    "adapter entrypoint"
)
FORBIDDEN = (
    "The adapter must consume Gate 1 neutral events and existing source refs; "
    "it must not import an XML parser, call a provider, calculate tax, or "
    "silently fall back for unknown schemas"
)


class Gate2Fns2NdflError(RuntimeError):
    def __init__(self, code: str, subject: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.subject = subject


@dataclass(frozen=True)
class Gate2Fns2NdflAdapterConfig:
    minimum_report_year: int = 2016
    maximum_report_year: int = 2025
    allow_vendor_extensions: bool = False


@dataclass(frozen=True)
class _SchemaPolicy:
    first_year: int
    last_year: int
    schema_version_id: str
    official_basis: str


_SCHEMA_POLICIES = (
    _SchemaPolicy(
        2016,
        2017,
        "fns_2ndfl_mmv_7_11_485_document_fragment_5_04",
        "FNS order 30.10.2015 N MMV-7-11/485@, Appendix 3, format 5.04",
    ),
    _SchemaPolicy(
        2018,
        2018,
        "fns_2ndfl_mmv_7_11_566_document_fragment",
        "FNS order 02.10.2018 N MMV-7-11/566@, Appendix 3",
    ),
    _SchemaPolicy(
        2019,
        2025,
        "fns_lk_signed_2ndfl_certificate_document_fragment_v1",
        "FNS signed-certificate PDF/XML/P7S export lineage; period selected from source",
    ),
)

_ALLOWED_ATTRIBUTES = {
    "Документ": {"ДатаДок", "ОтчетГод", "Признак"},
    "НДФЛ-2": {"НомКорр", "НомСпр"},
    "СвНА": {"ОКТМО", "Тлф"},
    "СвНАЮЛ": {"ИННЮЛ", "КПП", "НаимОрг"},
    "СвРеоргЮЛ": set(),
    "ПолучДох": {"Гражд", "ДатаРожд", "ИННФЛ", "Статус"},
    "УдЛичнФЛ": {"КодУдЛичн", "СерНомДок"},
    "ФИО": {"Имя", "Отчество", "Фамилия"},
    "СведДох": {"Ставка"},
    "ДохВыч": set(),
    "СвСумДох": {"Месяц", "КодДоход", "СумДоход"},
    "СвСумВыч": {"КодВычет", "СумВычет"},
    "НалВычССИ": set(),
    "СумИтНалПер": {
        "СумДохОбщ",
        "НалБаза",
        "НалИсчисл",
        "СумФикс",
        "НалУдерж",
        "НалУдержЛиш",
        "СумНалПрибЗач",
        "СумНалИнГос",
        "НалПеречисл",
        "НалНеУдерж",
        "АвансПлатФикс",
    },
    "СумДохНеУд": {"СумДохНеУдерж", "СумНеУдНал"},
}

_SINGLETON_ELEMENT_NAMES = {
    "СвНА",
    "НДФЛ-2",
    "ПолучДох",
    "УдЛичнФЛ",
    "ФИО",
    "СвНАЮЛ",
}

_AMOUNT_FIELDS = {
    "СумДоход",
    "СумВычет",
    "СумДохОбщ",
    "НалБаза",
    "НалИсчисл",
    "СумФикс",
    "НалУдерж",
    "НалУдержЛиш",
    "СумНалПрибЗач",
    "СумНалИнГос",
    "НалПеречисл",
    "НалНеУдерж",
    "АвансПлатФикс",
    "СумДохНеУдерж",
    "СумНеУдНал",
}

_CODE_RULES: dict[str, re.Pattern[str]] = {
    "Признак": re.compile(r"^[1-9][0-9]?$"),
    "НомКорр": re.compile(r"^[0-9]{1,3}$"),
    "ОКТМО": re.compile(r"^[0-9]{8}(?:[0-9]{3})?$"),
    "ИННЮЛ": re.compile(r"^[0-9]{10}$"),
    "КПП": re.compile(r"^[0-9]{9}$"),
    "ИННФЛ": re.compile(r"^[0-9]{12}$"),
    "Гражд": re.compile(r"^[0-9]{3}$"),
    "Статус": re.compile(r"^[1-9][0-9]?$"),
    "КодУдЛичн": re.compile(r"^[0-9]{2}$"),
    "КодДоход": re.compile(r"^[0-9]{4}$"),
    "КодВычет": re.compile(r"^[0-9]{3,4}$"),
    "Месяц": re.compile(r"^(?:0?[1-9]|1[0-2])$"),
}


@dataclass
class _Attribute:
    name: str
    value: str
    node_ref: str
    value_ref: str
    value_checksum_ref: str


@dataclass
class _Node:
    name: str
    path: str
    parent_path: str
    name_ref: str
    path_ref: str
    attributes: dict[str, _Attribute]


class Gate2Fns2NdflAdapterFactory:
    def __init__(self, config: Gate2Fns2NdflAdapterConfig | None = None) -> None:
        self.config = config or Gate2Fns2NdflAdapterConfig()

    def create(self) -> "Gate2Fns2NdflAdapter":
        if self.config.minimum_report_year > self.config.maximum_report_year:
            raise ValueError("fns_2ndfl_report_year_policy_invalid")
        return Gate2Fns2NdflAdapter(self.config)


class Gate2Fns2NdflAdapter:
    def __init__(self, config: Gate2Fns2NdflAdapterConfig) -> None:
        self.config = config

    def adapt(
        self,
        *,
        source_package_ref: str,
        source_unit: dict[str, Any],
    ) -> dict[str, Any]:
        if not source_package_ref:
            raise Gate2Fns2NdflError("fns_2ndfl_source_package_ref_missing")
        document_ref = str(source_unit.get("document_id") or "")
        source_unit_ref = str(source_unit.get("unit_ref") or "")
        source_checksum_ref = str(source_unit.get("source_checksum_ref") or "")
        source_unit_checksum_ref = str(
            source_unit.get("source_unit_checksum_ref") or ""
        )
        if not all(
            (document_ref, source_unit_ref, source_checksum_ref, source_unit_checksum_ref)
        ):
            raise Gate2Fns2NdflError("fns_2ndfl_source_integrity_identity_missing")
        if source_unit.get("parser") != "python_expat_neutral_events":
            raise Gate2Fns2NdflError("fns_2ndfl_neutral_event_parser_required")
        if (source_unit.get("source_location") or {}).get(
            "kind"
        ) != "xml_neutral_event_rows":
            raise Gate2Fns2NdflError("fns_2ndfl_neutral_event_scope_required")

        rows = source_unit.get("cells")
        if not isinstance(rows, list) or not rows or tuple(rows[0]) != XML_EVENT_COLUMNS:
            raise Gate2Fns2NdflError("fns_2ndfl_neutral_event_header_invalid")
        ref_index = _source_ref_index(source_unit)
        nodes = _build_nodes(rows, ref_index)
        _validate_schema_shape(nodes, self.config)
        if any(
            isinstance(row, list)
            and len(row) == len(XML_EVENT_COLUMNS)
            and row[2] == "text"
            and str(row[6]).strip()
            for row in rows[1:]
        ):
            raise Gate2Fns2NdflError("fns_2ndfl_unexpected_text_value")

        root = _single_node(nodes, "/Документ[1]")
        year_attr = _required_attribute(root, "ОтчетГод")
        report_year = _report_year(year_attr.value, self.config)
        policy = _schema_policy(report_year)

        facts: list[dict[str, Any]] = []
        facts.append(
            self._fact(
                family="source_certificate_identity",
                ordinal=1,
                node=root,
                fields=_fields(
                    root,
                    ("ОтчетГод", "Признак"),
                    required={"ОтчетГод"},
                ),
                document_ref=document_ref,
                package_ref=source_package_ref,
                source_checksum_ref=source_checksum_ref,
                schema_version_id=policy.schema_version_id,
            )
        )

        ndfl = _single_node(nodes, "/Документ[1]/НДФЛ-2[1]")
        metadata_fields = _fields(root, ("ДатаДок",)) + _fields(
            ndfl, ("НомСпр", "НомКорр")
        )
        metadata_fields.append(_presence_field(ndfl, "ndfl2_section_present"))
        facts.append(
            self._fact(
                family="certificate_metadata",
                ordinal=1,
                node=ndfl,
                fields=metadata_fields,
                document_ref=document_ref,
                package_ref=source_package_ref,
                source_checksum_ref=source_checksum_ref,
                schema_version_id=policy.schema_version_id,
            )
        )

        tax_agent_nodes = _nodes_under(nodes, "/Документ[1]/СвНА[1]")
        tax_agent_fields = [
            field
            for node in tax_agent_nodes
            for field in _fields(node, tuple(sorted(_ALLOWED_ATTRIBUTES[node.name])))
        ]
        if not tax_agent_fields:
            tax_agent_fields = [_presence_field(tax_agent_nodes[0], "tax_agent_section_present")]
        facts.append(
            self._fact(
                family="tax_agent_identity",
                ordinal=1,
                node=tax_agent_nodes[0],
                fields=tax_agent_fields,
                document_ref=document_ref,
                package_ref=source_package_ref,
                source_checksum_ref=source_checksum_ref,
                schema_version_id=policy.schema_version_id,
                related_nodes=tax_agent_nodes,
            )
        )

        recipient_nodes = _nodes_under(
            nodes, "/Документ[1]/НДФЛ-2[1]/ПолучДох[1]"
        )
        recipient_fields = [
            field
            for node in recipient_nodes
            for field in _fields(node, tuple(sorted(_ALLOWED_ATTRIBUTES[node.name])))
        ]
        if not recipient_fields:
            raise Gate2Fns2NdflError("fns_2ndfl_recipient_identity_missing")
        facts.append(
            self._fact(
                family="recipient_identity",
                ordinal=1,
                node=recipient_nodes[0],
                fields=recipient_fields,
                document_ref=document_ref,
                package_ref=source_package_ref,
                source_checksum_ref=source_checksum_ref,
                schema_version_id=policy.schema_version_id,
                related_nodes=recipient_nodes,
            )
        )

        all_income_nodes = [node for node in nodes.values() if node.name == "СвСумДох"]
        income_nodes = [node for node in all_income_nodes if "СумДоход" in node.attributes]
        non_fact_source_nodes = [
            {
                "node_ref": node.name_ref,
                "node_path_ref": node.path_ref,
                "attribute_name_refs": sorted(
                    attribute.node_ref for attribute in node.attributes.values()
                ),
                "attribute_value_refs": sorted(
                    attribute.value_ref for attribute in node.attributes.values()
                ),
                "reason_code": "income_row_without_amount_not_material_source_fact",
            }
            for node in sorted(
                (item for item in all_income_nodes if item not in income_nodes),
                key=lambda item: item.path,
            )
        ]
        for ordinal, node in enumerate(sorted(income_nodes, key=lambda item: item.path), 1):
            section = nodes.get(_ancestor_path(node.path, "СведДох"))
            fields = _fields(
                node,
                ("Месяц", "КодДоход", "СумДоход"),
                required={"Месяц", "КодДоход", "СумДоход"},
            )
            if section:
                fields += _fields(section, ("Ставка",), required={"Ставка"})
            facts.append(
                self._fact(
                    family="income_source_row",
                    ordinal=ordinal,
                    node=node,
                    fields=fields,
                    document_ref=document_ref,
                    package_ref=source_package_ref,
                    source_checksum_ref=source_checksum_ref,
                    schema_version_id=policy.schema_version_id,
                    related_nodes=[section] if section else [],
                    source_section_ref=section.path_ref if section else None,
                )
            )

        deduction_nodes = [
            node for node in nodes.values() if node.name == "СвСумВыч"
        ]
        for ordinal, node in enumerate(
            sorted(deduction_nodes, key=lambda item: item.path), 1
        ):
            income_parent = nodes.get(node.parent_path)
            section = nodes.get(_ancestor_path(node.path, "СведДох"))
            fields = _fields(
                node,
                ("КодВычет", "СумВычет"),
                required={"КодВычет", "СумВычет"},
            )
            facts.append(
                self._fact(
                    family="deduction_source_row",
                    ordinal=ordinal,
                    node=node,
                    fields=fields,
                    document_ref=document_ref,
                    package_ref=source_package_ref,
                    source_checksum_ref=source_checksum_ref,
                    schema_version_id=policy.schema_version_id,
                    related_nodes=[income_parent, section],
                    source_section_ref=section.path_ref if section else None,
                )
            )

        summary_nodes = [
            node
            for node in nodes.values()
            if node.name in {"СумИтНалПер", "СумДохНеУд"}
        ]
        for ordinal, node in enumerate(
            sorted(summary_nodes, key=lambda item: item.path), 1
        ):
            section = nodes.get(_ancestor_path(node.path, "СведДох"))
            fields = _fields(node, tuple(sorted(_ALLOWED_ATTRIBUTES[node.name])))
            if section:
                fields += _fields(section, ("Ставка",), required={"Ставка"})
            if not fields:
                raise Gate2Fns2NdflError("fns_2ndfl_tax_summary_values_missing")
            facts.append(
                self._fact(
                    family="tax_summary_source_fact",
                    ordinal=ordinal,
                    node=node,
                    fields=fields,
                    document_ref=document_ref,
                    package_ref=source_package_ref,
                    source_checksum_ref=source_checksum_ref,
                    schema_version_id=policy.schema_version_id,
                    related_nodes=[section] if section else [],
                    source_section_ref=section.path_ref if section else None,
                )
            )

        payload = {
            "schema_version": TYPED_FACTS_SCHEMA_VERSION,
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "source_document_ref": document_ref,
            "source_package_ref": source_package_ref,
            "source_unit_ref": source_unit_ref,
            "source_checksum_ref": source_checksum_ref,
            "source_unit_checksum_ref": source_unit_checksum_ref,
            "schema_family": FNS_SCHEMA_FAMILY,
            "schema_version_id": policy.schema_version_id,
            "schema_selection_basis": policy.official_basis,
            "report_period": str(report_year),
            "terminal_status": "validated",
            "facts": facts,
            "non_fact_source_nodes": non_fact_source_nodes,
            "vendor_extensions": [],
            "restrictions": list(FACT_RESTRICTIONS),
            "provider_accounting": {
                "calls": 0,
                "tokens": 0,
                "cost": 0,
                "llm_fallback_allowed": False,
            },
            "privacy": {
                "visibility": "private_case",
                "safe_report_contains_customer_values": False,
            },
        }
        payload["integrity_ref"] = integrity_ref("fnsoutchk", payload)
        validation = validate_fns_2ndfl_typed_output(
            payload,
            allowed_source_value_refs=[
                str(item) for item in source_unit.get("source_value_refs") or []
            ],
        )
        if validation.get("validator_status") != "passed":
            code = str((validation.get("errors") or [{}])[0].get("code") or "")
            raise Gate2Fns2NdflError(code or "fns_2ndfl_typed_output_invalid")
        return payload

    @staticmethod
    def _fact(
        *,
        family: str,
        ordinal: int,
        node: _Node,
        fields: list[dict[str, Any]],
        document_ref: str,
        package_ref: str,
        source_checksum_ref: str,
        schema_version_id: str,
        related_nodes: list[_Node | None] | None = None,
        source_section_ref: str | None = None,
    ) -> dict[str, Any]:
        related = [item for item in related_nodes or [] if item is not None]
        node_refs = sorted(
            {
                node.name_ref,
                node.path_ref,
                *[item.name_ref for item in related],
                *[item.path_ref for item in related],
                *[str(item["original_node_ref"]) for item in fields],
            }
        )
        value_refs = sorted(
            {str(item["original_value_ref"]) for item in fields}
        )
        fact_id = f"fnsfact_{stable_digest([document_ref, package_ref, family, ordinal, node.path], length=24)}"
        fact = {
            "fact_id": fact_id,
            "fact_family": family,
            "fact_ordinal": ordinal,
            "source_document_ref": document_ref,
            "source_package_ref": package_ref,
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "schema_family": FNS_SCHEMA_FAMILY,
            "schema_version_id": schema_version_id,
            "source_checksum_ref": source_checksum_ref,
            "original_node_refs": node_refs,
            "original_value_refs": value_refs,
            "source_section_ref": source_section_ref,
            "fields": fields,
            "validation_status": "validated",
            "restrictions": list(FACT_RESTRICTIONS),
        }
        fact["integrity_ref"] = integrity_ref("fnsfactchk", fact)
        return fact


def _source_ref_index(source_unit: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for item in source_unit.get("source_value_index") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("value_path") or {}
        if path.get("kind") != "table_cell":
            continue
        key = (int(path.get("row_index", -1)), int(path.get("column_index", -1)))
        if key in result:
            raise Gate2Fns2NdflError("fns_2ndfl_source_ref_duplicate")
        result[key] = item
    return result


def _ref(
    ref_index: dict[tuple[int, int], dict[str, Any]], row_index: int, column_index: int
) -> tuple[str, str]:
    item = ref_index.get((row_index, column_index))
    if not item:
        raise Gate2Fns2NdflError("fns_2ndfl_source_ref_missing")
    return str(item.get("source_value_ref") or ""), str(
        item.get("value_checksum_ref") or ""
    )


def _build_nodes(
    rows: list[Any], ref_index: dict[tuple[int, int], dict[str, Any]]
) -> dict[str, _Node]:
    nodes: dict[str, _Node] = {}
    stack: list[_Node] = []
    expected_ordinal = 1
    for row_index, row in enumerate(rows[1:], 1):
        if not isinstance(row, list) or len(row) != len(XML_EVENT_COLUMNS):
            raise Gate2Fns2NdflError("fns_2ndfl_neutral_event_row_invalid")
        ordinal, depth, event_type, path, name, attribute_name, value = row
        if ordinal != expected_ordinal:
            raise Gate2Fns2NdflError("fns_2ndfl_event_ordinal_invalid")
        expected_ordinal += 1
        path = str(path)
        name = str(name)
        if event_type == "start_element":
            if int(depth) != len(stack) + 1:
                raise Gate2Fns2NdflError("fns_2ndfl_event_depth_invalid")
            if path in nodes:
                raise Gate2Fns2NdflError("fns_2ndfl_duplicate_node_path")
            name_ref, _ = _ref(ref_index, row_index, 4)
            path_ref, _ = _ref(ref_index, row_index, 3)
            node = _Node(
                name=name,
                path=path,
                parent_path=stack[-1].path if stack else "",
                name_ref=name_ref,
                path_ref=path_ref,
                attributes={},
            )
            nodes[path] = node
            stack.append(node)
        elif event_type == "attribute":
            if not stack or stack[-1].path != path or stack[-1].name != name:
                raise Gate2Fns2NdflError("fns_2ndfl_attribute_scope_invalid")
            attribute_name = str(attribute_name)
            if attribute_name in stack[-1].attributes:
                raise Gate2Fns2NdflError("fns_2ndfl_duplicate_attribute")
            node_ref, _ = _ref(ref_index, row_index, 5)
            value_ref, checksum_ref = _ref(ref_index, row_index, 6)
            stack[-1].attributes[attribute_name] = _Attribute(
                name=attribute_name,
                value=str(value),
                node_ref=node_ref,
                value_ref=value_ref,
                value_checksum_ref=checksum_ref,
            )
        elif event_type == "end_element":
            if not stack or stack[-1].path != path or stack[-1].name != name:
                raise Gate2Fns2NdflError("fns_2ndfl_event_structure_unbalanced")
            stack.pop()
        elif event_type in {
            "text",
            "comment",
            "processing_instruction",
            "xml_declaration",
        }:
            pass
        else:
            raise Gate2Fns2NdflError("fns_2ndfl_event_type_unknown")
    if stack:
        raise Gate2Fns2NdflError("fns_2ndfl_event_structure_unbalanced")
    return nodes


def _validate_schema_shape(
    nodes: dict[str, _Node], config: Gate2Fns2NdflAdapterConfig
) -> None:
    roots = [node for node in nodes.values() if not node.parent_path]
    if len(roots) != 1 or roots[0].name != "Документ" or roots[0].path != "/Документ[1]":
        raise Gate2Fns2NdflError("fns_2ndfl_schema_family_unknown")
    unknown_elements = sorted(set(node.name for node in nodes.values()) - set(_ALLOWED_ATTRIBUTES))
    unknown_attributes = sorted(
        f"{node.name}@{attribute}"
        for node in nodes.values()
        for attribute in set(node.attributes) - _ALLOWED_ATTRIBUTES.get(node.name, set())
    )
    if unknown_elements or unknown_attributes:
        if not config.allow_vendor_extensions:
            raise Gate2Fns2NdflError(
                "fns_2ndfl_vendor_extension_not_allowed",
                ",".join(unknown_elements + unknown_attributes),
            )
        raise Gate2Fns2NdflError("fns_2ndfl_vendor_extension_unmapped")
    singleton_counts: dict[tuple[str, str], int] = {}
    for node in nodes.values():
        if node.name not in _SINGLETON_ELEMENT_NAMES:
            continue
        key = (node.parent_path, node.name)
        singleton_counts[key] = singleton_counts.get(key, 0) + 1
    for count in singleton_counts.values():
        if count > 1:
            raise Gate2Fns2NdflError("fns_2ndfl_duplicate_singleton_node")
    for path in (
        "/Документ[1]/СвНА[1]",
        "/Документ[1]/СвНА[1]/СвНАЮЛ[1]",
        "/Документ[1]/НДФЛ-2[1]",
        "/Документ[1]/НДФЛ-2[1]/ПолучДох[1]",
        "/Документ[1]/НДФЛ-2[1]/ПолучДох[1]/ФИО[1]",
    ):
        _single_node(nodes, path)
    if not any(node.name == "СведДох" for node in nodes.values()):
        raise Gate2Fns2NdflError("fns_2ndfl_income_section_missing")
    if not any(node.name == "СвСумДох" for node in nodes.values()):
        raise Gate2Fns2NdflError("fns_2ndfl_income_rows_missing")
    if not any(node.name in {"СумИтНалПер", "СумДохНеУд"} for node in nodes.values()):
        raise Gate2Fns2NdflError("fns_2ndfl_tax_summary_missing")


def _single_node(nodes: dict[str, _Node], path: str) -> _Node:
    node = nodes.get(path)
    if not node:
        raise Gate2Fns2NdflError("fns_2ndfl_required_node_missing", path)
    return node


def _nodes_under(nodes: dict[str, _Node], root_path: str) -> list[_Node]:
    root = _single_node(nodes, root_path)
    return [
        root,
        *sorted(
            (node for path, node in nodes.items() if path.startswith(root_path + "/")),
            key=lambda item: item.path,
        ),
    ]


def _required_attribute(node: _Node, name: str) -> _Attribute:
    attribute = node.attributes.get(name)
    if not attribute or not attribute.value.strip():
        raise Gate2Fns2NdflError("fns_2ndfl_required_attribute_missing", name)
    return attribute


def _fields(
    node: _Node,
    names: tuple[str, ...],
    *,
    required: set[str] | None = None,
) -> list[dict[str, Any]]:
    required = required or set()
    result: list[dict[str, Any]] = []
    for name in names:
        attribute = node.attributes.get(name)
        if not attribute:
            if name in required:
                raise Gate2Fns2NdflError("fns_2ndfl_required_attribute_missing", name)
            continue
        value_type, value = _typed_value(name, attribute.value)
        result.append(
            {
                "field_code": name,
                "value_type": value_type,
                "value": value,
                "source_lexeme": attribute.value,
                "source_lexeme_checksum_ref": attribute.value_checksum_ref,
                "original_node_ref": attribute.node_ref,
                "original_value_ref": attribute.value_ref,
            }
        )
    return result


def _presence_field(node: _Node, field_code: str) -> dict[str, Any]:
    return {
        "field_code": field_code,
        "value_type": "boolean",
        "value": True,
        "source_lexeme_checksum_ref": None,
        "original_node_ref": node.name_ref,
        "original_value_ref": node.path_ref,
    }


def _typed_value(name: str, value: str) -> tuple[str, Any]:
    compact = value.strip()
    if name in _AMOUNT_FIELDS or name == "Ставка":
        return "decimal", _decimal_value(compact, field=name)
    rule = _CODE_RULES.get(name)
    if rule and not rule.fullmatch(compact):
        raise Gate2Fns2NdflError("fns_2ndfl_code_value_invalid", name)
    if name == "Месяц":
        return "month", f"{int(compact):02d}"
    if name == "ОтчетГод":
        return "report_year", compact
    if name in _CODE_RULES:
        return "code", compact
    return "string", compact


def _decimal_value(value: str, *, field: str) -> str:
    normalized = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", normalized):
        raise Gate2Fns2NdflError("fns_2ndfl_amount_invalid", field)
    try:
        decimal = Decimal(normalized)
    except InvalidOperation as exc:
        raise Gate2Fns2NdflError("fns_2ndfl_amount_invalid", field) from exc
    return format(decimal, "f")


def _report_year(value: str, config: Gate2Fns2NdflAdapterConfig) -> int:
    if not re.fullmatch(r"[0-9]{4}", value):
        raise Gate2Fns2NdflError("fns_2ndfl_report_period_invalid")
    year = int(value)
    if year < config.minimum_report_year or year > config.maximum_report_year:
        raise Gate2Fns2NdflError("fns_2ndfl_report_period_unknown")
    return year


def _schema_policy(year: int) -> _SchemaPolicy:
    matches = [policy for policy in _SCHEMA_POLICIES if policy.first_year <= year <= policy.last_year]
    if len(matches) != 1:
        raise Gate2Fns2NdflError("fns_2ndfl_schema_version_unknown")
    return matches[0]


def _ancestor_path(path: str, name: str) -> str:
    parts = path.split("/")
    selected: list[str] = []
    for part in parts:
        if not part:
            continue
        selected.append(part)
        if part.startswith(name + "["):
            return "/" + "/".join(selected)
    return ""
