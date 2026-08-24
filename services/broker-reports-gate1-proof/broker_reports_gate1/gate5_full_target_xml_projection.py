"""Representation-only XML projection; upstream owners must supply all meaning."""

from __future__ import annotations

import base64
import binascii
import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import resources
import json
import re
from typing import Any

from lxml import etree

from .gate5_declaration_semantic_input import (
    GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS,
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntime,
    Gate5DeclarationSemanticInputRuntimeFactory,
)


GATE5_FULL_TARGET_XML_PROJECTION_DEFINITION_SCHEMA_VERSION = (
    "broker_reports_gate5_full_target_xml_projection_definition_v0"
)
GATE5_FULL_TARGET_XML_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_full_target_xml_projection_receipt_v0"
)
GATE5_FULL_TARGET_XML_STATUS = "FULL_TARGET_XML_VALID"
GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE = (
    "gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json"
)
GATE5_FULL_TARGET_XML_PROJECTION_SHA256 = (
    "48109cc6b3de6fd4d242346648660d99b40863310e622ab2cec44dc641ec7b26"
)
GATE5_FULL_TARGET_XML_XSD_SHA256 = (
    "083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484"
)
GATE5_CONSUMER_FIRST_XML_PROJECTION_DEFINITION_SCHEMA_VERSION = (
    "broker_reports_gate5_consumer_first_xml_projection_definition_v0"
)
GATE5_CONSUMER_FIRST_XML_PROJECTION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_consumer_first_xml_projection_receipt_v0"
)
GATE5_CONSUMER_FIRST_XML_STATUS = "CONSUMER_FIRST_TARGET_XML_VALID"
GATE5_CONSUMER_FIRST_XML_PROJECTION_RESOURCE = (
    "gate5_consumer_first_xml_projection.ru_3ndfl_2025.v0.json"
)
GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256 = (
    "d6e29e91e68463184e79f5ce8a0c2cea9d3aacdaacb534a61faee54499854834"
)
GATE5_TARGET_MECHANICS_SCHEMA_VERSION = (
    "broker_reports_gate5_ru_3ndfl_2025_target_mechanics_v0"
)
GATE5_TARGET_MECHANICS_STATUS = "TARGET_MECHANICS_READY"

FACTORY_REQUIRED = (
    "Gate5FullTargetXmlProjectionRuntimeFactory.create owns legacy and inactive consumer-first projection loops",
    "the legacy and consumer-first Definition authority factories own their immutable resources",
    "Gate5DeclarationSemanticInputRuntimeFactory.create owns semantic-input validation",
)
FORBIDDEN = (
    "tax calculation, applicability reasoning, target rule in Python or fragment composition",
    "Gate 4, SQL, ArtifactStore, document, provider, LLM or network reads at case time",
    "PDF, filing, product activation, mutable registry or filesystem path injection",
)

_DEFINITION_KEYS = frozenset(
    {
        "schema_version",
        "projection_id",
        "projection_version",
        "status",
        "input_contract",
        "target",
        "authoritative_sources",
        "required_domain_states",
        "semantic_coverage",
        "tree",
    }
)
_INPUT_CONTRACT_KEYS = frozenset(
    {"schema_version", "status", "definition_id", "definition_version"}
)
_CONSUMER_DEFINITION_KEYS = frozenset(
    {
        "schema_version",
        "projection_id",
        "projection_version",
        "status",
        "input_contract",
        "target",
        "target_mechanics_contract",
        "authoritative_sources",
        "tree",
    }
)
_CONSUMER_INPUT_CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "value_contract_id",
        "value_contract_version",
    }
)
_TARGET_MECHANICS_CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "instance_fields",
        "budget_disposition_shaping",
        "collection_order",
        "supported_profile",
    }
)
_TARGET_MECHANICS_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "electronic_file_id",
        "target_mechanics_sha256",
    }
)
_TARGET_KEYS = frozenset(
    {
        "jurisdiction",
        "tax_period",
        "form",
        "knd",
        "order",
        "electronic_format_version",
        "xml_encoding",
        "xsd_name",
        "xsd_resource",
        "xsd_sha256",
        "schematron",
    }
)
_SOURCE_KEYS = frozenset({"source_ref", "url", "content_sha256"})
_COVERAGE_KEYS = frozenset(
    {"obligation_ref", "expected_state", "target_paths"}
)
_NODE_KEYS = frozenset(
    {"node_id", "element", "repeat", "attributes", "text_mapping", "children"}
)
_MAPPING_KEYS = frozenset(
    {"mapping_id", "name", "source", "transform", "evidence_refs"}
)
_TEXT_MAPPING_KEYS = frozenset(
    {"mapping_id", "source", "transform", "evidence_refs"}
)
_TRANSFORM_KINDS = frozenset(
    {
        "identity",
        "constant",
        "enum",
        "integer",
        "iso_date_to_ddmmyyyy",
        "money_decimal",
        "money_integer",
    }
)
_EXPECTED_COVERAGE_STATES = frozenset(
    {"PROJECTED", "NOT_APPLICABLE", "NOT_ACTIVATED_FOR_SUPPLIED_CASE"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5FullTargetXmlProjectionError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5FullTargetXmlProjectionDefinitionAuthorityFactory:
    @classmethod
    def create(cls) -> "Gate5FullTargetXmlProjectionDefinitionAuthority":
        return Gate5FullTargetXmlProjectionDefinitionAuthority()


class Gate5FullTargetXmlProjectionDefinitionAuthority:
    def resolve(self) -> dict[str, Any]:
        raw = _resource_bytes(GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE)
        if _sha256_bytes(raw) != GATE5_FULL_TARGET_XML_PROJECTION_SHA256:
            _fail("gate5_full_target_projection_definition_hash_mismatch")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_projection_definition_invalid"
            ) from exc
        _validate_definition(value)
        return copy.deepcopy(value)


class Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory:
    @classmethod
    def create(cls) -> "Gate5ConsumerFirstXmlProjectionDefinitionAuthority":
        return Gate5ConsumerFirstXmlProjectionDefinitionAuthority()


class Gate5ConsumerFirstXmlProjectionDefinitionAuthority:
    def resolve(self) -> dict[str, Any]:
        raw = _resource_bytes(GATE5_CONSUMER_FIRST_XML_PROJECTION_RESOURCE)
        if _sha256_bytes(raw) != GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256:
            _fail("gate5_consumer_first_projection_definition_hash_mismatch")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_consumer_first_projection_definition_invalid"
            ) from exc
        _validate_consumer_definition(value)
        return copy.deepcopy(value)


class Gate5FullTargetXmlProjectionRuntimeFactory:
    @classmethod
    def create(cls) -> "Gate5FullTargetXmlProjectionRuntime":
        definition = (
            Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
        )
        target = definition["target"]
        try:
            xsd_bytes = base64.b64decode(
                b"".join(_resource_bytes(target["xsd_resource"]).split()),
                validate=True,
            )
        except (ValueError, binascii.Error) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_xsd_resource_invalid"
            ) from exc
        if (
            target["xsd_sha256"] != GATE5_FULL_TARGET_XML_XSD_SHA256
            or _sha256_bytes(xsd_bytes) != target["xsd_sha256"]
        ):
            _fail("gate5_full_target_xsd_hash_mismatch")
        return Gate5FullTargetXmlProjectionRuntime(
            definition=definition,
            consumer_definition_authority=(
                Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory.create()
            ),
            semantic_runtime=Gate5DeclarationSemanticInputRuntimeFactory.create(),
            projector=Gate5FullTargetXmlTreeProjector(),
            serializer=Gate5FullTargetXmlSerializer(),
            validator=Gate5FullTargetXmlConformanceValidator(xsd_bytes=xsd_bytes),
        )


class Gate5FullTargetXmlProjectionRuntime:
    def __init__(
        self,
        *,
        definition: dict[str, Any],
        consumer_definition_authority: (
            Gate5ConsumerFirstXmlProjectionDefinitionAuthority
        ),
        semantic_runtime: Gate5DeclarationSemanticInputRuntime,
        projector: "Gate5FullTargetXmlTreeProjector",
        serializer: "Gate5FullTargetXmlSerializer",
        validator: "Gate5FullTargetXmlConformanceValidator",
    ) -> None:
        self._definition = copy.deepcopy(definition)
        self._consumer_definition_authority = consumer_definition_authority
        self._semantic_runtime = semantic_runtime
        self._projector = projector
        self._serializer = serializer
        self._validator = validator

    def project(self, *, semantic_input: dict[str, Any]) -> dict[str, Any]:
        try:
            sealed = self._semantic_runtime.validate_semantic_input(
                semantic_input=semantic_input
            )
        except Gate5DeclarationSemanticInputError as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_semantic_input_invalid", exc.code
            ) from exc
        _validate_input_binding(sealed, self._definition)
        source_root, obligation_states = _source_root(sealed)
        coverage_proof = _coverage_proof(
            definition=self._definition,
            semantic_input=sealed,
            obligation_states=obligation_states,
        )
        tree, mappings = self._projector.project(
            definition=self._definition,
            source_root=source_root,
        )
        xml_bytes = self._serializer.serialize(
            tree=tree,
            encoding=self._definition["target"]["xml_encoding"],
        )
        conformance = self._validator.validate(
            xml_bytes=xml_bytes,
            definition=self._definition,
        )
        mapping_base = {
            "status": "passed",
            "mapping_occurrences_total": len(mappings),
            "mapping_ids_total": len({item["mapping_id"] for item in mappings}),
            "projected_obligations_total": sum(
                item["expected_state"] == "PROJECTED" for item in coverage_proof
            ),
            "non_projected_terminal_obligations_total": sum(
                item["expected_state"] != "PROJECTED" for item in coverage_proof
            ),
            "coverage": coverage_proof,
            "mappings": mappings,
        }
        semantic_mapping_proof = {
            **mapping_base,
            "proof_sha256": _canonical_sha256(mapping_base),
        }
        receipt_base = {
            "schema_version": GATE5_FULL_TARGET_XML_RECEIPT_SCHEMA_VERSION,
            "status": GATE5_FULL_TARGET_XML_STATUS,
            "blockers": [],
            "projection_definition_binding": {
                "projection_id": self._definition["projection_id"],
                "projection_version": self._definition["projection_version"],
                "projection_definition_sha256": (
                    GATE5_FULL_TARGET_XML_PROJECTION_SHA256
                ),
            },
            "semantic_input_binding": {
                "semantic_input_sha256": sealed["semantic_input_sha256"],
                "definition_sha256": sealed["source_binding"]["definition_sha256"],
                "package_sha256": sealed["source_binding"]["package_sha256"],
            },
            "xml_binding": {
                "xml_sha256": _sha256_bytes(xml_bytes),
                "xml_bytes": len(xml_bytes),
                "root_element": tree.tag,
            },
            "semantic_mapping_proof": semantic_mapping_proof,
            "conformance_proof": conformance,
        }
        receipt = {
            **receipt_base,
            "receipt_sha256": _canonical_sha256(receipt_base),
        }
        return {"xml_tree": tree, "xml_bytes": xml_bytes, "receipt": receipt}

    def project_released(
        self,
        *,
        released_values: dict[str, Any],
        target_mechanics: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            released = self._semantic_runtime.validate_released_projection_input(
                projection_input=released_values
            )
        except Gate5DeclarationSemanticInputError as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_consumer_first_released_values_invalid", exc.code
            ) from exc
        definition = self._consumer_definition_authority.resolve()
        _validate_consumer_input_binding(released, definition)
        mechanics = _validated_target_mechanics(
            target_mechanics,
            definition=definition,
        )
        source_root = _consumer_source_root(
            declaration_values=released["declaration_values"],
            target_mechanics=mechanics,
        )
        tree, mappings = self._projector.project(
            definition=definition,
            source_root=source_root,
        )
        xml_bytes = self._serializer.serialize(
            tree=tree,
            encoding=definition["target"]["xml_encoding"],
        )
        conformance = self._validator.validate(
            xml_bytes=xml_bytes,
            definition=definition,
        )
        mapping_base = {
            "status": "passed",
            "mapping_occurrences_total": len(mappings),
            "mapping_ids_total": len({item["mapping_id"] for item in mappings}),
            "mappings": mappings,
        }
        semantic_mapping_proof = {
            **mapping_base,
            "proof_sha256": _canonical_sha256(mapping_base),
        }
        receipt_base = {
            "schema_version": (
                GATE5_CONSUMER_FIRST_XML_PROJECTION_RECEIPT_SCHEMA_VERSION
            ),
            "status": GATE5_CONSUMER_FIRST_XML_STATUS,
            "blockers": [],
            "projection_definition_binding": {
                "projection_id": definition["projection_id"],
                "projection_version": definition["projection_version"],
                "projection_definition_sha256": (
                    GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256
                ),
            },
            "released_value_binding": {
                "semantic_value_sha256": released["semantic_value_sha256"],
                "release_receipt_sha256": released["release_receipt_sha256"],
                "projection_input_sha256": released["projection_input_sha256"],
            },
            "target_mechanics_binding": {
                "schema_version": mechanics["schema_version"],
                "status": mechanics["status"],
                "target_mechanics_sha256": mechanics[
                    "target_mechanics_sha256"
                ],
            },
            "xml_binding": {
                "xml_sha256": _sha256_bytes(xml_bytes),
                "xml_bytes": len(xml_bytes),
                "root_element": tree.tag,
            },
            "semantic_mapping_proof": semantic_mapping_proof,
            "conformance_proof": conformance,
        }
        receipt = {
            **receipt_base,
            "receipt_sha256": _canonical_sha256(receipt_base),
        }
        return {"xml_tree": tree, "xml_bytes": xml_bytes, "receipt": receipt}

    def extract_supported_profile_values(
        self, *, xml_bytes: bytes
    ) -> dict[str, Any]:
        """Validate representation and extract literals without deriving tax meaning."""

        definition = self._consumer_definition_authority.resolve()
        conformance = self._validator.validate(
            xml_bytes=xml_bytes,
            definition=definition,
        )
        proof = _supported_profile_xml_values(xml_bytes)
        return {
            **proof,
            "xsd_valid": conformance["xsd_valid"],
            "proof_sha256": _canonical_sha256(proof),
        }


class Gate5FullTargetXmlTreeProjector:
    def project(
        self,
        *,
        definition: dict[str, Any],
        source_root: dict[str, Any],
    ) -> tuple[etree._Element, list[dict[str, Any]]]:
        mappings: list[dict[str, Any]] = []
        roots = self._emit_node(
            node=definition["tree"],
            parent=None,
            source_root=source_root,
            item=source_root,
            item_path="$root",
            parent_path="",
            mappings=mappings,
        )
        if len(roots) != 1:
            _fail("gate5_full_target_tree_root_invalid")
        return roots[0], mappings

    def _emit_node(
        self,
        *,
        node: dict[str, Any],
        parent: etree._Element | None,
        source_root: dict[str, Any],
        item: Any,
        item_path: str,
        parent_path: str,
        mappings: list[dict[str, Any]],
    ) -> list[etree._Element]:
        repeat = node.get("repeat")
        items = (
            _resolved(source=repeat, source_root=source_root, item=item)
            if repeat is not None
            else [item]
        )
        if not isinstance(items, list):
            _fail("gate5_full_target_repeat_source_invalid", node["node_id"])
        emitted = []
        item_paths = (
            [item_path]
            if repeat is None
            else [f"{repeat}[{index}]" for index in range(len(items))]
        )
        for current, current_path in zip(items, item_paths, strict=True):
            element = (
                etree.Element(node["element"])
                if parent is None
                else etree.SubElement(parent, node["element"])
            )
            target_path = (
                f"{parent_path}/{node['element']}" if parent_path else node["element"]
            )
            for mapping in node["attributes"]:
                rendered, source_value = _render_mapping(
                    mapping=mapping,
                    source_root=source_root,
                    item=current,
                )
                element.set(mapping["name"], rendered)
                mappings.append(
                    _mapping_proof(
                        mapping=mapping,
                        source_value=source_value,
                        resolved_source=_resolved_source_path(
                            mapping.get("source"), current_path
                        ),
                        target=f"{target_path}/@{mapping['name']}",
                        rendered=rendered,
                    )
                )
            text_mapping = node.get("text_mapping")
            if text_mapping is not None:
                rendered, source_value = _render_mapping(
                    mapping=text_mapping,
                    source_root=source_root,
                    item=current,
                )
                element.text = rendered
                mappings.append(
                    _mapping_proof(
                        mapping=text_mapping,
                        source_value=source_value,
                        resolved_source=_resolved_source_path(
                            text_mapping.get("source"), current_path
                        ),
                        target=f"{target_path}/#text",
                        rendered=rendered,
                    )
                )
            for child in node["children"]:
                self._emit_node(
                    node=child,
                    parent=element,
                    source_root=source_root,
                    item=current,
                    item_path=current_path,
                    parent_path=target_path,
                    mappings=mappings,
                )
            emitted.append(element)
        return emitted


class Gate5FullTargetXmlSerializer:
    def serialize(self, *, tree: etree._Element, encoding: str) -> bytes:
        if not isinstance(tree, etree._Element) or not _nonempty(encoding):
            _fail("gate5_full_target_tree_invalid")
        return etree.tostring(
            tree,
            xml_declaration=True,
            encoding=encoding,
            pretty_print=False,
        )


class Gate5FullTargetXmlConformanceValidator:
    def __init__(self, *, xsd_bytes: bytes) -> None:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            self._schema = etree.XMLSchema(etree.fromstring(xsd_bytes, parser))
        except (etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_xsd_invalid"
            ) from exc

    def validate(
        self,
        *,
        xml_bytes: bytes,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            serialized_tree = etree.fromstring(xml_bytes, parser)
        except etree.XMLSyntaxError as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_xml_not_well_formed"
            ) from exc
        if not self._schema.validate(serialized_tree):
            error = self._schema.error_log.last_error
            detail = "xsd_validation_failed" if error is None else error.message
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_xml_xsd_invalid", detail
            )
        target = definition["target"]
        return {
            "status": "passed",
            "validator": "lxml.etree.XMLSchema",
            "xsd_name": target["xsd_name"],
            "xsd_sha256": target["xsd_sha256"],
            "schematron": target["schematron"],
            "xml_well_formed": True,
            "xsd_valid": True,
        }


def _supported_profile_xml_values(xml_bytes: bytes) -> dict[str, Any]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(xml_bytes, parser)
    except (TypeError, etree.XMLSyntaxError) as exc:
        raise Gate5FullTargetXmlProjectionError(
            "gate5_full_target_xml_semantics_invalid", "xml"
        ) from exc

    def one(path: str) -> etree._Element:
        values = root.findall(path)
        if len(values) != 1:
            _fail("gate5_full_target_xml_semantics_invalid", path)
        return values[0]

    def money(node: etree._Element, attribute: str) -> Decimal:
        literal = node.get(attribute)
        try:
            value = Decimal(str(literal))
        except (InvalidOperation, TypeError):
            _fail(
                "gate5_full_target_xml_semantics_invalid",
                f"{node.tag}@{attribute}",
            )
        if not value.is_finite() or value < 0:
            _fail(
                "gate5_full_target_xml_semantics_invalid",
                f"{node.tag}@{attribute}",
            )
        return value

    base = one(".//РасчНалБаза")
    settlement = one(".//РасчНалПУ")
    operation = one(".//ДохОперЦБ")
    source = one(".//ДоходИстРФ")
    budget = one(".//СумНалПуИскл227")
    income_group = one(".//НалБаза")
    if income_group.get("ГрупДоход") != "02" or source.get("ВидДоход") != "003":
        _fail("gate5_full_target_xml_semantics_invalid", "supported_profile")

    total_income = money(base, "СумДох")
    non_taxable = money(base, "СумДохНеНал")
    taxable_income = money(base, "СумДохНал")
    deductions = money(base, "СумНалВыч")
    expenses = money(base, "СумРасх")
    tax_base = money(base, "НалБаза")
    operation_income = money(operation, "ДохСовОпер")
    operation_expenses = money(operation, "РасхРеалЦБ")
    operation_allowable = money(operation, "РасхУмДохОпер")
    source_income = money(source, "Доход")
    calculated_tax = money(settlement, "Исчисл")
    credit_attributes = {
        "withheld_at_source": "Удерж",
        "material_benefit_withheld": "СумУдержМат",
        "trade_fee_credit": "ТСУплПерЗач",
        "fixed_advance_credit": "СумФиксАван",
        "foreign_tax_credit": "УплИнПодлЗач",
        "patent_credit": "УплПатентЗач",
    }
    payable = money(settlement, "ПодлУпл")
    refundable = money(settlement, "ПодлВозв")
    simplified = money(settlement, "СумВозвУпр")
    source_withheld = money(source, "НалУдерж")
    budget_payable = money(budget, "ПодлУпл")
    budget_refundable = money(budget, "ПодлВозв")

    def literal(value: Decimal) -> str:
        return format(value, "f")

    return {
        "schema_version": "broker_reports_gate5_serialized_xml_values_v1",
        "status": "extracted",
        "profile": "ordinary_trade_2025_supported_representation",
        "values": {
            "income_group": {
                "total_income": literal(total_income),
                "non_taxable_income": literal(non_taxable),
                "taxable_income": literal(taxable_income),
                "tax_deductions": literal(deductions),
                "accepted_expenses": literal(expenses),
                "tax_base": literal(tax_base),
                "calculated_tax": literal(calculated_tax),
                "settlement_amounts": {
                    key: literal(money(settlement, attribute))
                    for key, attribute in credit_attributes.items()
                },
                "tax_payable": literal(payable),
                "tax_refundable": literal(refundable),
                "simplified_procedure_returned_or_credited": literal(simplified),
            },
            "financial_investment": {
                "category_gross_income": literal(operation_income),
                "related_expenses": literal(operation_expenses),
                "allowable_expenses": literal(operation_allowable),
            },
            "russian_source": {
                "gross_income": literal(source_income),
                "withheld_tax": literal(source_withheld),
            },
            "budget": {
                "payable": literal(budget_payable),
                "refundable": literal(budget_refundable),
            },
        },
    }


def _validate_definition(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _DEFINITION_KEYS
        or value.get("schema_version")
        != GATE5_FULL_TARGET_XML_PROJECTION_DEFINITION_SCHEMA_VERSION
        or value.get("status") != "trusted_hash_bound_inactive_proof"
        or not _identifier(value.get("projection_id"))
        or not _nonempty(value.get("projection_version"))
    ):
        _fail("gate5_full_target_projection_definition_invalid")
    contract = value.get("input_contract")
    target = value.get("target")
    if (
        not isinstance(contract, dict)
        or set(contract) != _INPUT_CONTRACT_KEYS
        or not all(_nonempty(item) for item in contract.values())
        or not isinstance(target, dict)
        or set(target) != _TARGET_KEYS
        or target.get("xsd_sha256") != GATE5_FULL_TARGET_XML_XSD_SHA256
        or target.get("schematron") is not None
        or not all(
            _nonempty(target.get(key)) for key in _TARGET_KEYS - {"schematron"}
        )
    ):
        _fail("gate5_full_target_projection_definition_invalid")
    seen_sources = _validated_authoritative_sources(
        value.get("authoritative_sources")
    )
    states = value.get("required_domain_states")
    if (
        not isinstance(states, dict)
        or len(states) != 11
        or not all(_identifier(key) and _nonempty(item) for key, item in states.items())
    ):
        _fail("gate5_full_target_projection_domain_profile_invalid")
    coverage = value.get("semantic_coverage")
    if not isinstance(coverage, list) or len(coverage) != 25:
        _fail("gate5_full_target_projection_coverage_invalid")
    seen_obligations = set()
    for row in coverage:
        if (
            not isinstance(row, dict)
            or set(row) != _COVERAGE_KEYS
            or not _identifier(row.get("obligation_ref"))
            or row["obligation_ref"] in seen_obligations
            or row.get("expected_state") not in _EXPECTED_COVERAGE_STATES
            or not isinstance(row.get("target_paths"), list)
            or (row["expected_state"] == "PROJECTED") != bool(row["target_paths"])
            or not all(_nonempty(path) for path in row["target_paths"])
        ):
            _fail("gate5_full_target_projection_coverage_invalid")
        seen_obligations.add(row["obligation_ref"])
    node_ids: set[str] = set()
    mapping_ids: set[str] = set()
    _validate_node(
        value.get("tree"),
        source_refs=seen_sources,
        node_ids=node_ids,
        mapping_ids=mapping_ids,
        is_root=True,
    )
    target_paths = _tree_paths(value["tree"])
    if any(
        path not in target_paths for row in coverage for path in row["target_paths"]
    ):
        _fail("gate5_full_target_projection_coverage_invalid")


def _validate_consumer_definition(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _CONSUMER_DEFINITION_KEYS
        or value.get("schema_version")
        != GATE5_CONSUMER_FIRST_XML_PROJECTION_DEFINITION_SCHEMA_VERSION
        or value.get("status") != "trusted_hash_bound_inactive_proof"
        or not _identifier(value.get("projection_id"))
        or not _nonempty(value.get("projection_version"))
    ):
        _fail("gate5_consumer_first_projection_definition_invalid")
    contract = value.get("input_contract")
    target = value.get("target")
    mechanics = value.get("target_mechanics_contract")
    if (
        not isinstance(contract, dict)
        or set(contract) != _CONSUMER_INPUT_CONTRACT_KEYS
        or contract
        != {
            "schema_version": (
                GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION
            ),
            "status": GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS,
            "value_contract_id": (
                "ru_3ndfl_2025_supplied_case_declaration_values"
            ),
            "value_contract_version": "2026-08-14.0-g545-bounded",
        }
        or not isinstance(target, dict)
        or set(target) != _TARGET_KEYS
        or target.get("xsd_sha256") != GATE5_FULL_TARGET_XML_XSD_SHA256
        or target.get("schematron") is not None
        or not all(
            _nonempty(target.get(key)) for key in _TARGET_KEYS - {"schematron"}
        )
        or not isinstance(mechanics, dict)
        or set(mechanics) != _TARGET_MECHANICS_CONTRACT_KEYS
        or mechanics
        != {
            "schema_version": GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
            "status": GATE5_TARGET_MECHANICS_STATUS,
            "instance_fields": ["electronic_file_id"],
            "budget_disposition_shaping": (
                "released_kind_to_dual_target_amounts_v0"
            ),
            "collection_order": "preserve_released_order",
            "supported_profile": "payable_single_allocation_supplied_case_v0",
        }
    ):
        _fail("gate5_consumer_first_projection_definition_invalid")
    source_refs = _validated_authoritative_sources(
        value.get("authoritative_sources")
    )
    node_ids: set[str] = set()
    mapping_ids: set[str] = set()
    _validate_node(
        value.get("tree"),
        source_refs=source_refs,
        node_ids=node_ids,
        mapping_ids=mapping_ids,
        is_root=True,
    )
    if len(mapping_ids) != 49:
        _fail("gate5_consumer_first_projection_definition_invalid")


def _validated_authoritative_sources(value: Any) -> set[str]:
    if not isinstance(value, list) or len(value) < 4:
        _fail("gate5_full_target_projection_evidence_invalid")
    seen_sources: set[str] = set()
    hashed_files = 0
    for source in value:
        if (
            not isinstance(source, dict)
            or set(source) != _SOURCE_KEYS
            or not _identifier(source.get("source_ref"))
            or source["source_ref"] in seen_sources
            or not isinstance(source.get("url"), str)
            or not source["url"].startswith("https://www.nalog.gov.ru/")
            or (
                source.get("content_sha256") is not None
                and not _sha256(source.get("content_sha256"))
            )
        ):
            _fail("gate5_full_target_projection_evidence_invalid")
        seen_sources.add(source["source_ref"])
        hashed_files += source["content_sha256"] is not None
    if hashed_files < 3 or "fns_xsd_5_20_01" not in seen_sources:
        _fail("gate5_full_target_projection_evidence_invalid")
    return seen_sources


def _validate_node(
    value: Any,
    *,
    source_refs: set[str],
    node_ids: set[str],
    mapping_ids: set[str],
    is_root: bool,
) -> None:
    if not isinstance(value, dict):
        _fail("gate5_full_target_projection_tree_invalid")
    normalized = {
        **value,
        "repeat": value.get("repeat"),
        "text_mapping": value.get("text_mapping"),
    }
    if (
        set(normalized) != _NODE_KEYS
        or not _identifier(normalized.get("node_id"))
        or normalized["node_id"] in node_ids
        or not _nonempty(normalized.get("element"))
        or (is_root and normalized["repeat"] is not None)
        or (
            normalized["repeat"] is not None
            and not _source_path(normalized["repeat"])
        )
        or not isinstance(normalized.get("attributes"), list)
        or not isinstance(normalized.get("children"), list)
    ):
        _fail("gate5_full_target_projection_tree_invalid")
    node_ids.add(normalized["node_id"])
    seen_attributes = set()
    for mapping in normalized["attributes"]:
        _validate_mapping(
            mapping,
            keys=_MAPPING_KEYS,
            source_refs=source_refs,
            mapping_ids=mapping_ids,
        )
        if mapping["name"] in seen_attributes:
            _fail("gate5_full_target_projection_tree_invalid")
        seen_attributes.add(mapping["name"])
    if normalized["text_mapping"] is not None:
        _validate_mapping(
            normalized["text_mapping"],
            keys=_TEXT_MAPPING_KEYS,
            source_refs=source_refs,
            mapping_ids=mapping_ids,
        )
    for child in normalized["children"]:
        _validate_node(
            child,
            source_refs=source_refs,
            node_ids=node_ids,
            mapping_ids=mapping_ids,
            is_root=False,
        )


def _validate_mapping(
    value: Any,
    *,
    keys: frozenset[str],
    source_refs: set[str],
    mapping_ids: set[str],
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or not _identifier(value.get("mapping_id"))
        or value["mapping_id"] in mapping_ids
        or ("name" in keys and not _nonempty(value.get("name")))
        or not isinstance(value.get("evidence_refs"), list)
        or not value["evidence_refs"]
        or not set(value["evidence_refs"]) <= source_refs
        or not isinstance(value.get("transform"), dict)
        or value["transform"].get("kind") not in _TRANSFORM_KINDS
    ):
        _fail("gate5_full_target_projection_mapping_invalid")
    transform = value["transform"]
    kind = transform["kind"]
    source = value.get("source")
    if kind == "constant":
        if source is not None or set(transform) != {"kind", "value"} or not _nonempty(
            transform.get("value")
        ):
            _fail("gate5_full_target_projection_mapping_invalid")
    elif not _source_path(source):
        _fail("gate5_full_target_projection_mapping_invalid")
    elif kind == "enum" and (
        set(transform) != {"kind", "values"}
        or not isinstance(transform.get("values"), dict)
        or not transform["values"]
        or not all(_nonempty(k) and _nonempty(v) for k, v in transform["values"].items())
    ):
        _fail("gate5_full_target_projection_mapping_invalid")
    elif kind in {"money_decimal", "money_integer"} and (
        not isinstance(transform.get("currency"), str)
        or re.fullmatch(r"[A-Z]{3}", transform["currency"]) is None
        or set(transform)
        != (
            {"kind", "currency", "scale"}
            if kind == "money_decimal"
            else {"kind", "currency"}
        )
        or (kind == "money_decimal" and transform.get("scale") != 2)
    ):
        _fail("gate5_full_target_projection_mapping_invalid")
    elif kind not in {"constant", "enum", "money_decimal", "money_integer"} and set(
        transform
    ) != {"kind"}:
        _fail("gate5_full_target_projection_mapping_invalid")
    mapping_ids.add(value["mapping_id"])


def _validate_input_binding(
    semantic_input: dict[str, Any], definition: dict[str, Any]
) -> None:
    contract = definition["input_contract"]
    declaration = semantic_input["declaration_semantics"]
    if (
        semantic_input["schema_version"] != contract["schema_version"]
        or semantic_input["status"] != contract["status"]
        or declaration["definition_id"] != contract["definition_id"]
        or declaration["definition_version"] != contract["definition_version"]
        or declaration["jurisdiction"] != definition["target"]["jurisdiction"]
        or declaration["tax_period"] != definition["target"]["tax_period"]
        or declaration["declaration_kind"] != definition["target"]["form"]
    ):
        _fail("gate5_full_target_projection_input_contract_mismatch")


def _validate_consumer_input_binding(
    released_values: dict[str, Any],
    definition: dict[str, Any],
) -> None:
    contract = definition["input_contract"]
    value_contract = released_values["value_contract"]
    if (
        released_values["schema_version"] != contract["schema_version"]
        or released_values["status"] != contract["status"]
        or value_contract.get("id") != contract["value_contract_id"]
        or value_contract.get("version") != contract["value_contract_version"]
        or released_values["declaration_values"].get("tax_period")
        != definition["target"]["tax_period"]
    ):
        _fail("gate5_consumer_first_projection_input_contract_mismatch")


def _validated_target_mechanics(
    value: Any,
    *,
    definition: dict[str, Any],
) -> dict[str, Any]:
    contract = definition["target_mechanics_contract"]
    if (
        not isinstance(value, dict)
        or set(value) != _TARGET_MECHANICS_KEYS
        or value.get("schema_version") != contract["schema_version"]
        or value.get("status") != contract["status"]
        or not _identifier(value.get("electronic_file_id"))
    ):
        _fail("gate5_consumer_first_target_mechanics_invalid")
    base = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "target_mechanics_sha256"
    }
    if (
        not _sha256(value.get("target_mechanics_sha256"))
        or value["target_mechanics_sha256"] != _canonical_sha256(base)
    ):
        _fail("gate5_consumer_first_target_mechanics_hash_mismatch")
    return copy.deepcopy(value)


def _consumer_source_root(
    *,
    declaration_values: dict[str, Any],
    target_mechanics: dict[str, Any],
) -> dict[str, Any]:
    budget_rows = declaration_values.get("budget_dispositions")
    if not isinstance(budget_rows, list) or len(budget_rows) != 1:
        _fail("gate5_consumer_first_projection_profile_unproven", "budget_dispositions")
    if not isinstance(budget_rows[0], dict) or set(budget_rows[0]) != {
        "kbk",
        "oktmo",
        "payable",
        "refundable",
    }:
        _fail(
            "gate5_consumer_first_projection_profile_unproven",
            "budget_dispositions[0]",
        )
    for collection in (
        "income_group_results",
        "russian_source_income",
        "financial_investment_results",
    ):
        rows = declaration_values.get(collection)
        if not isinstance(rows, list) or len(rows) != 1:
            _fail("gate5_consumer_first_projection_profile_unproven", collection)
    return {
        "declaration_values": copy.deepcopy(declaration_values),
        "target_mechanics": copy.deepcopy(target_mechanics),
    }


def _source_root(
    semantic_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    domain_payloads: dict[str, dict[str, Any]] = {}
    domain_states: dict[str, str] = {}
    obligation_states: dict[str, str] = {}
    for domain in semantic_input["domains"]:
        domain_id = domain["domain_id"]
        domain_states[domain_id] = domain["state"]
        for obligation_ref in domain["obligation_refs"]:
            obligation_states[obligation_ref] = domain["state"]
        if domain["state"] == "RESOLVED":
            components = domain["typed_components"]
            if len(components) != 1:
                _fail("gate5_full_target_projection_component_ambiguous", domain_id)
            payload = copy.deepcopy(components[0]["semantic_payload"])
            domain_payloads[domain_id] = payload
            seen_resolution_refs: set[str] = set()
            for resolution in payload.get("obligation_resolutions", []):
                obligation_ref = resolution.get("obligation_ref")
                if (
                    obligation_ref not in domain["obligation_refs"]
                    or obligation_ref in seen_resolution_refs
                    or resolution.get("state")
                    not in {"RESOLVED", "NOT_ACTIVATED_FOR_SUPPLIED_CASE"}
                ):
                    _fail(
                        "gate5_full_target_projection_obligation_resolution_invalid",
                        domain_id,
                    )
                seen_resolution_refs.add(obligation_ref)
                obligation_states[obligation_ref] = resolution["state"]
    return (
        {
            **copy.deepcopy(semantic_input),
            "domain_payloads": domain_payloads,
            "domain_states": domain_states,
        },
        obligation_states,
    )


def _coverage_proof(
    *,
    definition: dict[str, Any],
    semantic_input: dict[str, Any],
    obligation_states: dict[str, str],
) -> list[dict[str, Any]]:
    actual_domain_states = {
        row["domain_id"]: row["state"] for row in semantic_input["domains"]
    }
    if actual_domain_states != definition["required_domain_states"]:
        _fail("gate5_full_target_projection_domain_profile_mismatch")
    definition_obligations = {
        row["obligation_ref"] for row in definition["semantic_coverage"]
    }
    if definition_obligations != set(obligation_states):
        _fail("gate5_full_target_projection_obligation_accounting_invalid")
    proof = []
    for row in definition["semantic_coverage"]:
        actual = obligation_states[row["obligation_ref"]]
        expected = row["expected_state"]
        if (expected == "PROJECTED" and actual != "RESOLVED") or (
            expected != "PROJECTED" and actual != expected
        ):
            _fail(
                "gate5_full_target_projection_obligation_state_mismatch",
                row["obligation_ref"],
            )
        proof.append(
            {
                "obligation_ref": row["obligation_ref"],
                "expected_state": expected,
                "source_state": actual,
                "target_paths": copy.deepcopy(row["target_paths"]),
                "status": "passed",
            }
        )
    return proof


def _render_mapping(
    *,
    mapping: dict[str, Any],
    source_root: dict[str, Any],
    item: Any,
) -> tuple[str, Any]:
    transform = mapping["transform"]
    source_value = (
        None
        if transform["kind"] == "constant"
        else _resolved(
            source=mapping["source"], source_root=source_root, item=item
        )
    )
    return _transformed(value=source_value, transform=transform), source_value


def _transformed(*, value: Any, transform: dict[str, Any]) -> str:
    kind = transform["kind"]
    if kind == "constant":
        return transform["value"]
    if kind == "identity":
        if not isinstance(value, str) or not value:
            _fail("gate5_full_target_projection_value_invalid")
        return value
    if kind == "enum":
        if not isinstance(value, str) or value not in transform["values"]:
            _fail("gate5_full_target_projection_enum_unmapped")
        return transform["values"][value]
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            _fail("gate5_full_target_projection_integer_invalid")
        rendered = str(value)
        if not rendered.isdigit():
            _fail("gate5_full_target_projection_integer_invalid")
        return rendered
    if kind == "iso_date_to_ddmmyyyy":
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_projection_date_invalid"
            ) from exc
        return parsed.strftime("%d.%m.%Y")
    if kind in {"money_decimal", "money_integer"}:
        if (
            not isinstance(value, dict)
            or set(value) != {"kind", "amount", "currency"}
            or value.get("kind") != "money"
            or value.get("currency") != transform["currency"]
        ):
            _fail("gate5_full_target_projection_money_invalid")
        try:
            amount = Decimal(value["amount"])
        except (InvalidOperation, TypeError) as exc:
            raise Gate5FullTargetXmlProjectionError(
                "gate5_full_target_projection_money_invalid"
            ) from exc
        if not amount.is_finite() or amount < 0:
            _fail("gate5_full_target_projection_money_invalid")
        if kind == "money_integer":
            if amount != amount.to_integral_value():
                _fail("gate5_full_target_projection_money_not_integral")
            return str(int(amount))
        quantum = Decimal("0.01")
        if amount != amount.quantize(quantum):
            _fail("gate5_full_target_projection_money_scale_invalid")
        return f"{amount:.2f}"
    _fail("gate5_full_target_projection_transform_invalid")


def _resolved(*, source: str, source_root: dict[str, Any], item: Any) -> Any:
    if source == "$root":
        return source_root
    if source == "$item":
        return item
    if source.startswith("$root."):
        current: Any = source_root
        segments = source[6:].split(".")
    elif source.startswith("$item."):
        current = item
        segments = source[6:].split(".")
    else:
        _fail("gate5_full_target_projection_source_path_invalid", source)
    for segment in segments:
        if not isinstance(current, dict) or segment not in current:
            _fail("gate5_full_target_projection_source_value_missing", source)
        current = current[segment]
    return current


def _mapping_proof(
    *,
    mapping: dict[str, Any],
    source_value: Any,
    resolved_source: str | None,
    target: str,
    rendered: str,
) -> dict[str, Any]:
    return {
        "mapping_id": mapping["mapping_id"],
        "source": mapping.get("source"),
        "resolved_source": resolved_source,
        "source_value_sha256": (
            None if mapping.get("source") is None else _canonical_sha256(source_value)
        ),
        "target": target,
        "target_value_sha256": _sha256_bytes(rendered.encode("utf-8")),
        "evidence_refs": copy.deepcopy(mapping["evidence_refs"]),
        "status": "passed",
    }


def _resolved_source_path(source: Any, item_path: str) -> str | None:
    if source is None:
        return None
    if source == "$item":
        return item_path
    if source.startswith("$item."):
        return item_path + source[5:]
    return source


def _tree_paths(node: dict[str, Any], parent: str = "") -> set[str]:
    path = f"{parent}/{node['element']}" if parent else node["element"]
    result = {path}
    for child in node["children"]:
        result.update(_tree_paths(child, path))
    return result


def _resource_bytes(name: str) -> bytes:
    try:
        return resources.files(__package__).joinpath(name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5FullTargetXmlProjectionError(
            "gate5_full_target_projection_resource_unavailable", name
        ) from exc


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _source_path(value: Any) -> bool:
    return isinstance(value, str) and (
        value in {"$root", "$item"}
        or value.startswith("$root.")
        or value.startswith("$item.")
    )


def _fail(code: str, field: str = "") -> None:
    raise Gate5FullTargetXmlProjectionError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_CONSUMER_FIRST_XML_PROJECTION_DEFINITION_SCHEMA_VERSION",
    "GATE5_CONSUMER_FIRST_XML_PROJECTION_RECEIPT_SCHEMA_VERSION",
    "GATE5_CONSUMER_FIRST_XML_PROJECTION_RESOURCE",
    "GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256",
    "GATE5_CONSUMER_FIRST_XML_STATUS",
    "GATE5_FULL_TARGET_XML_PROJECTION_DEFINITION_SCHEMA_VERSION",
    "GATE5_FULL_TARGET_XML_PROJECTION_RESOURCE",
    "GATE5_FULL_TARGET_XML_PROJECTION_SHA256",
    "GATE5_FULL_TARGET_XML_RECEIPT_SCHEMA_VERSION",
    "GATE5_FULL_TARGET_XML_STATUS",
    "GATE5_FULL_TARGET_XML_XSD_SHA256",
    "GATE5_TARGET_MECHANICS_SCHEMA_VERSION",
    "GATE5_TARGET_MECHANICS_STATUS",
    "Gate5ConsumerFirstXmlProjectionDefinitionAuthority",
    "Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory",
    "Gate5FullTargetXmlConformanceValidator",
    "Gate5FullTargetXmlProjectionDefinitionAuthority",
    "Gate5FullTargetXmlProjectionDefinitionAuthorityFactory",
    "Gate5FullTargetXmlProjectionError",
    "Gate5FullTargetXmlProjectionRuntime",
    "Gate5FullTargetXmlProjectionRuntimeFactory",
    "Gate5FullTargetXmlSerializer",
    "Gate5FullTargetXmlTreeProjector",
]
