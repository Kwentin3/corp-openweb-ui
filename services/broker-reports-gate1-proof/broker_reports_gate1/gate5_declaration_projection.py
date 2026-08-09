"""Validate and execute one inactive declaration-projection proof artifact."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import resources
import json
import re
from typing import Any


GATE5_DECLARATION_PROJECTION_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_evidence_v0"
)
GATE5_DECLARATION_PROJECTION_SPEC_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_spec_v0"
)
GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_proof_input_v0"
)
GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_fragment_v0"
)
GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE = (
    "gate5_declaration_projection_evidence.ru_3ndfl_2025_appendix8.v0.json"
)
GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE_SHA256 = (
    "36d301bb9666d0f61213ccce95b016e7a674d30d1e0841cea0d8ebc59977f4d7"
)
GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE = (
    "gate5_declaration_projection_spec.ru_3ndfl_2025_appendix8.v0.json"
)

FACTORY_REQUIRED = (
    "Gate5DeclarationProjectionRuntimeFactory.create is the only G5.12 "
    "candidate-validation and projector construction entrypoint",
)
FORBIDDEN = (
    "LLM, official-source, XSD, Gate 4, Tax Methodology, Tax Model persistence "
    "or database reads during project",
    "declaration target paths, field names or codes embedded in projector control flow",
    "best-effort output after invalid candidate, input, target, code or "
    "evidence binding",
)

_MONEY = re.compile(r"^(?:0|[1-9][0-9]*)\.[0-9]{2}$")
_SPEC_KEYS = {
    "schema_version",
    "spec_id",
    "spec_version",
    "status",
    "declaration",
    "input_contract",
    "target",
    "mappings",
}
_DECLARATION_KEYS = {
    "jurisdiction",
    "tax_period",
    "form",
    "knd",
    "order",
    "electronic_format_version",
    "xsd",
}
_TARGET_KEYS = {"path", "element", "min_occurs", "max_occurs"}
_MAPPING_KEYS = {
    "mapping_id",
    "source_concept",
    "target_attribute",
    "target_use",
    "transform",
    "evidence_refs",
}


class Gate5DeclarationProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate5DeclarationProjectionRuntimeFactory:
    @staticmethod
    def create(
        *,
        candidate_spec: dict[str, Any] | None = None,
    ) -> "Gate5DeclarationProjectionRuntime":
        evidence, evidence_sha256 = _read_evidence_resource()
        spec = (
            _read_json_resource(GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE)
            if candidate_spec is None
            else copy.deepcopy(candidate_spec)
        )
        _validate_candidate(spec, evidence)
        return Gate5DeclarationProjectionRuntime(
            spec=copy.deepcopy(spec),
            evidence_pack=copy.deepcopy(evidence),
            spec_sha256=_canonical_sha256(spec),
            evidence_pack_sha256=evidence_sha256,
        )


class Gate5DeclarationProjectionRuntime:
    def __init__(
        self,
        *,
        spec: dict[str, Any],
        evidence_pack: dict[str, Any],
        spec_sha256: str,
        evidence_pack_sha256: str,
    ) -> None:
        self._spec = spec
        self._evidence_pack = evidence_pack
        self._spec_sha256 = spec_sha256
        self._evidence_pack_sha256 = evidence_pack_sha256

    def project(self, *, proof_input: dict[str, Any]) -> dict[str, Any]:
        values = _validated_input(proof_input, self._spec)
        fields = {
            item["attribute"]: item
            for item in self._evidence_pack["target_contract"]["fields"]
        }
        attributes: dict[str, str] = {}
        provenance: list[dict[str, Any]] = []
        for mapping in self._spec["mappings"]:
            rendered = _render(
                value=values[mapping["source_concept"]],
                transform=mapping["transform"],
            )
            _validate_rendered(rendered, fields[mapping["target_attribute"]])
            attributes[mapping["target_attribute"]] = rendered
            provenance.append(
                {
                    "mapping_id": mapping["mapping_id"],
                    "source_concept": mapping["source_concept"],
                    "target_attribute": mapping["target_attribute"],
                    "evidence_refs": copy.deepcopy(mapping["evidence_refs"]),
                }
            )
        return {
            "schema_version": GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION,
            "status": "projected",
            "declaration": copy.deepcopy(self._spec["declaration"]),
            "target": {
                "path": self._spec["target"]["path"],
                "element": self._spec["target"]["element"],
                "occurrence": 1,
            },
            "attributes": attributes,
            "projection_binding": {
                "spec_id": self._spec["spec_id"],
                "spec_version": self._spec["spec_version"],
                "spec_sha256": self._spec_sha256,
                "evidence_pack_id": self._evidence_pack["evidence_pack_id"],
                "evidence_pack_sha256": self._evidence_pack_sha256,
            },
            "provenance": provenance,
            "validation": {
                "candidate": "passed",
                "input": "passed",
                "xsd_claim": "structurally_consistent_not_full_xml_validated",
            },
        }


def _read_evidence_resource() -> tuple[dict[str, Any], str]:
    raw = _read_resource_bytes(GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE_SHA256:
        _fail("gate5_declaration_projection_evidence_hash_mismatch")
    evidence = _decode_json(raw)
    if evidence.get(
        "schema_version"
    ) != GATE5_DECLARATION_PROJECTION_EVIDENCE_SCHEMA_VERSION or not _clean(
        evidence.get("evidence_pack_id")
    ):
        _fail("gate5_declaration_projection_evidence_invalid")
    return evidence, digest


def _read_json_resource(resource_name: str) -> dict[str, Any]:
    return _decode_json(_read_resource_bytes(resource_name))


def _read_resource_bytes(resource_name: str) -> bytes:
    try:
        return resources.files(__package__).joinpath(resource_name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5DeclarationProjectionError(
            "gate5_declaration_projection_resource_unavailable"
        ) from exc


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        value: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate5DeclarationProjectionError(
            "gate5_declaration_projection_resource_invalid"
        ) from exc
    if not isinstance(value, dict):
        _fail("gate5_declaration_projection_resource_invalid")
    return value


def _validate_candidate(spec: Any, evidence: dict[str, Any]) -> None:
    _keys(spec, _SPEC_KEYS, "gate5_declaration_projection_spec_invalid")
    if (
        spec["schema_version"] != GATE5_DECLARATION_PROJECTION_SPEC_SCHEMA_VERSION
        or not _clean(spec["spec_id"])
        or not _clean(spec["spec_version"])
        or spec["status"] != "inactive_agent_generated_candidate"
    ):
        _fail("gate5_declaration_projection_spec_invalid")
    _keys(
        spec["declaration"],
        _DECLARATION_KEYS,
        "gate5_declaration_projection_spec_invalid",
    )
    if spec["declaration"] != evidence["declaration"]:
        _fail("gate5_declaration_projection_identity_mismatch")

    contract = spec["input_contract"]
    _keys(
        contract,
        {"schema_version", "concepts"},
        "gate5_declaration_projection_spec_invalid",
    )
    if contract[
        "schema_version"
    ] != GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION or not isinstance(
        contract["concepts"], list
    ):
        _fail("gate5_declaration_projection_spec_invalid")
    concept_kinds: dict[str, str] = {}
    for concept in contract["concepts"]:
        _keys(
            concept,
            {"concept", "value_kind"},
            "gate5_declaration_projection_spec_invalid",
        )
        name = concept["concept"]
        kind = concept["value_kind"]
        if (
            not _clean(name)
            or name in concept_kinds
            or kind
            not in {
                "stable_enum",
                "money",
            }
        ):
            _fail("gate5_declaration_projection_spec_invalid")
        concept_kinds[name] = kind

    _keys(
        spec["target"],
        _TARGET_KEYS,
        "gate5_declaration_projection_spec_invalid",
    )
    target = evidence["target_contract"]
    if any(spec["target"][key] != target[key] for key in _TARGET_KEYS):
        _fail("gate5_declaration_projection_invalid_target")
    fields = {item["attribute"]: item for item in target["fields"]}
    claims = {
        (item["source_concept"], item["target_attribute"]): item
        for item in evidence["mapping_claims"]
    }

    if not isinstance(spec["mappings"], list) or not spec["mappings"]:
        _fail("gate5_declaration_projection_missing_required_mapping")
    ids: set[str] = set()
    sources: set[str] = set()
    targets: set[str] = set()
    for mapping in spec["mappings"]:
        _keys(mapping, _MAPPING_KEYS, "gate5_declaration_projection_spec_invalid")
        if (
            not _clean(mapping["mapping_id"])
            or mapping["mapping_id"] in ids
            or mapping["source_concept"] in sources
            or mapping["target_attribute"] in targets
        ):
            _fail("gate5_declaration_projection_conflicting_mapping")
        if mapping["source_concept"] not in concept_kinds:
            _fail("gate5_declaration_projection_unknown_source_concept")
        field = fields.get(mapping["target_attribute"])
        if field is None:
            _fail("gate5_declaration_projection_invalid_target")
        if mapping["target_use"] != field["xsd_use"]:
            _fail("gate5_declaration_projection_target_contract_mismatch")
        _validate_transform(mapping["transform"])
        _validate_kind(
            concept_kinds[mapping["source_concept"]],
            field["datatype"],
            mapping["transform"],
        )
        claim = claims.get((mapping["source_concept"], mapping["target_attribute"]))
        if claim is None:
            _fail("gate5_declaration_projection_mapping_unsubstantiated")
        if mapping["transform"] != claim["transform"]:
            code = (
                "gate5_declaration_projection_unsupported_code"
                if mapping["transform"].get("kind") == "enum_code"
                else "gate5_declaration_projection_value_representation_invalid"
            )
            _fail(code)
        refs = mapping["evidence_refs"]
        if (
            not isinstance(refs, list)
            or len(refs) != len(set(refs))
            or set(refs) != set(claim["required_evidence_refs"])
        ):
            _fail("gate5_declaration_projection_evidence_incomplete")
        ids.add(mapping["mapping_id"])
        sources.add(mapping["source_concept"])
        targets.add(mapping["target_attribute"])

    required = {
        name for name, field in fields.items() if field["proof_required_mapping"]
    }
    if targets != required:
        _fail("gate5_declaration_projection_missing_required_mapping")


def _validate_transform(transform: Any) -> None:
    if not isinstance(transform, dict):
        _fail("gate5_declaration_projection_spec_invalid")
    if transform.get("kind") == "enum_code":
        if (
            set(transform) != {"kind", "values"}
            or not isinstance(transform["values"], dict)
            or not transform["values"]
            or any(
                not _clean(source) or not _clean(target)
                for source, target in transform["values"].items()
            )
        ):
            _fail("gate5_declaration_projection_spec_invalid")
        return
    if (
        set(transform) != {"kind", "currency", "scale"}
        or transform.get("kind") != "money_amount"
        or not _clean(transform["currency"])
        or transform["scale"] != 2
    ):
        _fail("gate5_declaration_projection_spec_invalid")


def _validate_kind(
    kind: str, datatype: dict[str, Any], transform: dict[str, Any]
) -> None:
    expected = (
        ("stable_enum", "string")
        if transform["kind"] == "enum_code"
        else ("money", "decimal")
    )
    if (kind, datatype["base"]) != expected:
        _fail("gate5_declaration_projection_value_representation_invalid")
    if transform["kind"] == "enum_code":
        values = transform["values"].values()
        if any(len(item) != datatype["length"] for item in values):
            _fail("gate5_declaration_projection_value_representation_invalid")
        if "enumeration" in datatype and any(
            item not in datatype["enumeration"] for item in values
        ):
            _fail("gate5_declaration_projection_unsupported_code")


def _validated_input(value: Any, spec: dict[str, Any]) -> dict[str, Any]:
    concepts = {
        item["concept"]: item["value_kind"]
        for item in spec["input_contract"]["concepts"]
    }
    if not isinstance(value, dict) or set(value) != set(concepts) | {"schema_version"}:
        _fail("gate5_declaration_projection_input_invalid")
    if value["schema_version"] != GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION:
        _fail("gate5_declaration_projection_input_invalid")
    for name, kind in concepts.items():
        supplied = value[name]
        if kind == "stable_enum":
            if not _clean(supplied):
                _fail("gate5_declaration_projection_input_invalid")
            continue
        _keys(
            supplied,
            {"amount", "currency"},
            "gate5_declaration_projection_input_invalid",
        )
        if not _clean(supplied["currency"]) or not isinstance(supplied["amount"], str):
            _fail("gate5_declaration_projection_input_invalid")
        if _MONEY.fullmatch(supplied["amount"]) is None:
            _fail("gate5_declaration_projection_input_invalid")
        try:
            amount = Decimal(supplied["amount"])
        except InvalidOperation:
            _fail("gate5_declaration_projection_input_invalid")
        if not amount.is_finite() or amount < 0:
            _fail("gate5_declaration_projection_input_invalid")
    return copy.deepcopy(value)


def _render(*, value: Any, transform: dict[str, Any]) -> str:
    if transform["kind"] == "enum_code":
        result = transform["values"].get(value)
        if result is None:
            _fail("gate5_declaration_projection_input_value_unsupported")
        return result
    if value["currency"] != transform["currency"]:
        _fail("gate5_declaration_projection_input_value_unsupported")
    return value["amount"]


def _validate_rendered(value: str, field: dict[str, Any]) -> None:
    datatype = field["datatype"]
    if datatype["base"] == "string":
        if len(value) != datatype["length"] or (
            "enumeration" in datatype and value not in datatype["enumeration"]
        ):
            _fail("gate5_declaration_projection_rendered_value_invalid")
        return
    digits = value.replace(".", "").lstrip("0") or "0"
    if _MONEY.fullmatch(value) is None or len(digits) > datatype["total_digits"]:
        _fail("gate5_declaration_projection_rendered_value_invalid")


def _keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(code)


def _clean(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fail(code: str) -> None:
    raise Gate5DeclarationProjectionError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE",
    "GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE_SHA256",
    "GATE5_DECLARATION_PROJECTION_EVIDENCE_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE",
    "GATE5_DECLARATION_PROJECTION_SPEC_SCHEMA_VERSION",
    "Gate5DeclarationProjectionError",
    "Gate5DeclarationProjectionRuntime",
    "Gate5DeclarationProjectionRuntimeFactory",
]
