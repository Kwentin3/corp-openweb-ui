"""Representation-only projection; no tax or evidence interpretation belongs here."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .declaration_semantics import (
    INCOME_GROUP_DECLARATION_SEMANTICS_INPUT_SCHEMA_VERSION,
    DeclarationSemanticsIncomeGroupError,
    DeclarationSemanticsIncomeGroupRuntimeFactory,
)

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
GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE_SHA256 = (
    "348e22da283bc8ff2a42c04f1fe45923b330840380466790f39670156a7970de"
)
GATE5_DECLARATION_PROJECTION_V1_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_evidence_v1"
)
GATE5_DECLARATION_PROJECTION_V1_SPEC_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_spec_v1"
)
GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_ref_v1"
)
GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_projection_fragment_v1"
)
GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_base_model_v0"
)
GATE5_DECLARATION_PROJECTION_SECTION2_ID = (
    "ru-3ndfl-2025-section2-securities-income-group-proof"
)
GATE5_DECLARATION_PROJECTION_SECTION2_VERSION = "2026.0-proof"
GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE = (
    "gate5_declaration_projection_spec.ru_3ndfl_2025_section2.v1.json"
)
GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256 = (
    "1dbe4124295ac2539f92349d28a8bcc2b4038133639c399f613eeb0bfe9a1705"
)
GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE = (
    "gate5_declaration_projection_evidence.ru_3ndfl_2025_section2.v1.json"
)
GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256 = (
    "ff67f17ea76758312e3f32b586c83904c86794ef4073f0b1543f68ffe6fdfc38"
)

FACTORY_REQUIRED = (
    "Gate5DeclarationProjectionRuntimeFactory.create is the only G5.12 "
    "candidate-validation and projector construction entrypoint",
    "Gate5DeclarationProjectionRuntimeV1Factory.create is the only versioned "
    "published-projection validation and construction entrypoint",
    "DeclarationSemanticsIncomeGroupRuntimeFactory.create owns validation "
    "of Section 2 source semantics before representation",
)
FORBIDDEN = (
    "LLM, official-source, XSD, Gate 4, Tax Methodology, Tax Model persistence "
    "or database reads during project",
    "declaration target paths, field names or codes embedded in projector control flow",
    "best-effort output after invalid candidate, input, target, code or "
    "evidence binding",
    "arbitrary XML trees, caller-defined paths or transforms, calculation, rate, "
    "tax, full-document assembly or serialization",
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
_V1_SPEC_KEYS = {
    "schema_version",
    "projection_id",
    "projection_version",
    "status",
    "declaration",
    "input_contract",
    "target",
    "mappings",
}
_V1_INPUT_CONTRACT_KEYS = {
    "schema_version",
    "model_kind",
    "income_group_semantic",
    "concepts",
}
_V1_TARGET_KEYS = {"path", "root_node_id", "nodes"}
_V1_NODE_KEYS = {
    "node_id",
    "parent_node_id",
    "path",
    "element",
    "min_occurs",
    "max_occurs",
}
_V1_MAPPING_KEYS = _MAPPING_KEYS | {"target_node_id"}
_V1_SOURCE_CONCEPTS = {
    "income_group_semantic": "stable_enum",
    "total_income": "money",
    "non_taxable_income": "money",
    "taxable_income": "money",
    "tax_deductions": "money",
    "accepted_expenses": "money",
    "tax_base": "money",
}
_V1_PROJECTION_BUNDLES = {
    ("ru-3ndfl-2025-appendix8-securities-proof", "2026.0-proof"): {
        "profile_kind": "legacy_v0",
        "spec_resource": GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE,
        "spec_resource_sha256": GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE_SHA256,
        "evidence_resource": GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE,
        "evidence_resource_sha256": (
            GATE5_DECLARATION_PROJECTION_EVIDENCE_RESOURCE_SHA256
        ),
    },
    (
        GATE5_DECLARATION_PROJECTION_SECTION2_ID,
        GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
    ): {
        "profile_kind": "v1",
        "spec_resource": GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE,
        "spec_resource_sha256": (
            GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256
        ),
        "evidence_resource": (
            GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE
        ),
        "evidence_resource_sha256": (
            GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256
        ),
    }
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


class Gate5DeclarationProjectionRuntimeV1Factory:
    @staticmethod
    def create() -> "Gate5DeclarationProjectionRuntimeV1":
        if (
            INCOME_GROUP_DECLARATION_SEMANTICS_INPUT_SCHEMA_VERSION
            != GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_declaration_projection_input_contract_incompatible")
        projections: dict[tuple[str, str], dict[str, Any]] = {}
        for identity, bundle in _V1_PROJECTION_BUNDLES.items():
            spec, spec_sha256 = _read_hash_bound_json_resource(
                bundle["spec_resource"],
                bundle["spec_resource_sha256"],
                "gate5_declaration_projection_spec_hash_mismatch",
            )
            evidence, evidence_sha256 = _read_hash_bound_json_resource(
                bundle["evidence_resource"],
                bundle["evidence_resource_sha256"],
                "gate5_declaration_projection_evidence_hash_mismatch",
            )
            if bundle["profile_kind"] == "legacy_v0":
                _validate_candidate(spec, evidence)
                if (spec["spec_id"], spec["spec_version"]) != identity:
                    _fail("gate5_declaration_projection_identity_mismatch")
            else:
                _validate_v1_projection(
                    spec=spec,
                    evidence=evidence,
                    expected_identity=identity,
                )
            projections[identity] = {
                "profile_kind": bundle["profile_kind"],
                "spec": copy.deepcopy(spec),
                "evidence": copy.deepcopy(evidence),
                "spec_sha256": spec_sha256,
                "evidence_sha256": evidence_sha256,
            }
        return Gate5DeclarationProjectionRuntimeV1(
            projections=projections,
            semantic_input_owner=(
                DeclarationSemanticsIncomeGroupRuntimeFactory.create()
            ),
        )


class Gate5DeclarationProjectionRuntimeV1:
    def __init__(
        self,
        *,
        projections: dict[tuple[str, str], dict[str, Any]],
        semantic_input_owner: Any,
    ) -> None:
        self._projections = copy.deepcopy(projections)
        self._semantic_input_owner = semantic_input_owner

    def project(
        self,
        *,
        projection_ref: dict[str, Any],
        declaration_semantics: dict[str, Any],
    ) -> dict[str, Any]:
        identity = _validated_v1_projection_ref(projection_ref)
        projection = self._projections.get(identity)
        if projection is None:
            _fail("gate5_declaration_projection_artifact_unavailable")
        if projection["profile_kind"] == "legacy_v0":
            return _project_legacy_as_v1(
                projection=projection,
                declaration_semantics=declaration_semantics,
            )
        spec = projection["spec"]
        try:
            semantic_input = self._semantic_input_owner.validate_projection_input(
                declaration_semantics=declaration_semantics,
                input_contract=spec["input_contract"],
            )
        except DeclarationSemanticsIncomeGroupError as exc:
            raise Gate5DeclarationProjectionError(exc.code) from exc
        values = semantic_input["values"]
        traces = semantic_input["traces"]
        validated_model = semantic_input["validated_model"]
        evidence = projection["evidence"]
        fields = {
            (node["node_id"], field["attribute"]): field
            for node in evidence["target_contract"]["nodes"]
            for field in node["fields"]
        }
        attributes_by_node = {
            node["node_id"]: {} for node in spec["target"]["nodes"]
        }
        provenance: list[dict[str, Any]] = []
        for mapping in spec["mappings"]:
            source_concept = mapping["source_concept"]
            target_key = (
                mapping["target_node_id"],
                mapping["target_attribute"],
            )
            rendered = _render(
                value=values[source_concept],
                transform=mapping["transform"],
            )
            _validate_rendered(rendered, fields[target_key])
            attributes_by_node[mapping["target_node_id"]][
                mapping["target_attribute"]
            ] = rendered
            provenance.append(
                {
                    "source": {
                        "contract": spec["input_contract"]["schema_version"],
                        "concept": source_concept,
                        "trace": copy.deepcopy(traces[source_concept]),
                    },
                    "rule": {
                        "projection_id": spec["projection_id"],
                        "projection_version": spec["projection_version"],
                        "mapping_id": mapping["mapping_id"],
                        "evidence_refs": copy.deepcopy(mapping["evidence_refs"]),
                    },
                    "target": {
                        "node_id": mapping["target_node_id"],
                        "attribute": mapping["target_attribute"],
                    },
                }
            )
        fragment = _build_v1_fragment(
            target=spec["target"],
            attributes_by_node=attributes_by_node,
        )
        return {
            "schema_version": GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION,
            "status": "projected",
            "declaration": copy.deepcopy(spec["declaration"]),
            "target": {
                "path": spec["target"]["path"],
                "occurrence": 1,
                "scope": "section2_lines_001_060_partial_fragment",
            },
            "fragment": fragment,
            "source_binding": {
                "input_contract": spec["input_contract"]["schema_version"],
                "model_id": validated_model["model_id"],
                "model_kind": validated_model["model_kind"],
                "model_sha256": _canonical_sha256(validated_model),
                "methodology_binding": copy.deepcopy(
                    validated_model["methodology_binding"]
                ),
            },
            "projection_binding": {
                "projection_id": spec["projection_id"],
                "projection_version": spec["projection_version"],
                "spec_resource_sha256": projection["spec_sha256"],
                "evidence_pack_id": evidence["evidence_pack_id"],
                "evidence_resource_sha256": projection["evidence_sha256"],
            },
            "provenance": provenance,
            "validation": {
                "projection_definition": "passed",
                "upstream_tax_model": "owner_revalidated",
                "required_mappings": "passed",
                "xsd_claim": "partial_section2_fragment_not_full_xml_validated",
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


def _read_hash_bound_json_resource(
    resource_name: str,
    expected_sha256: str,
    mismatch_code: str,
) -> tuple[dict[str, Any], str]:
    raw = _read_resource_bytes(resource_name)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        _fail(mismatch_code)
    return _decode_json(raw), digest


def _validate_v1_projection(
    *,
    spec: Any,
    evidence: Any,
    expected_identity: tuple[str, str],
) -> None:
    _keys(spec, _V1_SPEC_KEYS, "gate5_declaration_projection_spec_invalid")
    if (
        spec["schema_version"]
        != GATE5_DECLARATION_PROJECTION_V1_SPEC_SCHEMA_VERSION
        or (spec["projection_id"], spec["projection_version"])
        != expected_identity
        or spec["status"] != "inactive_evidence_bound_definition"
    ):
        _fail("gate5_declaration_projection_spec_invalid")
    _keys(
        spec["declaration"],
        _DECLARATION_KEYS,
        "gate5_declaration_projection_spec_invalid",
    )
    _validate_v1_evidence(evidence)
    if spec["declaration"] != evidence["declaration"]:
        _fail("gate5_declaration_projection_identity_mismatch")

    input_contract = spec["input_contract"]
    _keys(
        input_contract,
        _V1_INPUT_CONTRACT_KEYS,
        "gate5_declaration_projection_spec_invalid",
    )
    concepts = input_contract["concepts"]
    if (
        input_contract["schema_version"]
        != GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION
        or input_contract["model_kind"] != "stable_income_group_tax_base"
        or not _clean(input_contract["income_group_semantic"])
        or not isinstance(concepts, list)
    ):
        _fail("gate5_declaration_projection_input_contract_incompatible")
    concept_kinds: dict[str, str] = {}
    for concept in concepts:
        _keys(
            concept,
            {"concept", "value_kind"},
            "gate5_declaration_projection_spec_invalid",
        )
        name = concept["concept"]
        kind = concept["value_kind"]
        if name in concept_kinds or _V1_SOURCE_CONCEPTS.get(name) != kind:
            _fail("gate5_declaration_projection_input_contract_incompatible")
        concept_kinds[name] = kind
    if concept_kinds != _V1_SOURCE_CONCEPTS:
        _fail("gate5_declaration_projection_input_contract_incompatible")

    _validate_v1_target(spec["target"])
    evidence_target = evidence["target_contract"]
    spec_target = {
        "path": evidence_target["path"],
        "root_node_id": evidence_target["root_node_id"],
        "nodes": [
            {key: node[key] for key in _V1_NODE_KEYS}
            for node in evidence_target["nodes"]
        ],
    }
    if spec["target"] != spec_target:
        _fail("gate5_declaration_projection_invalid_target")
    fields = {
        (node["node_id"], field["attribute"]): field
        for node in evidence_target["nodes"]
        for field in node["fields"]
    }
    claims = {
        (
            claim["source_concept"],
            claim["target_node_id"],
            claim["target_attribute"],
        ): claim
        for claim in evidence["mapping_claims"]
    }
    mappings = spec["mappings"]
    if not isinstance(mappings, list) or not mappings:
        _fail("gate5_declaration_projection_missing_required_mapping")
    mapping_ids: set[str] = set()
    source_concepts: set[str] = set()
    targets: set[tuple[str, str]] = set()
    for mapping in mappings:
        _keys(
            mapping,
            _V1_MAPPING_KEYS,
            "gate5_declaration_projection_spec_invalid",
        )
        mapping_id = mapping["mapping_id"]
        source_concept = mapping["source_concept"]
        target_key = (
            mapping["target_node_id"],
            mapping["target_attribute"],
        )
        if (
            not _clean(mapping_id)
            or mapping_id in mapping_ids
            or source_concept in source_concepts
            or target_key in targets
        ):
            _fail("gate5_declaration_projection_conflicting_mapping")
        if source_concept not in concept_kinds:
            _fail("gate5_declaration_projection_unknown_source_concept")
        field = fields.get(target_key)
        if field is None:
            _fail("gate5_declaration_projection_invalid_target")
        if mapping["target_use"] != field["xsd_use"]:
            _fail("gate5_declaration_projection_target_contract_mismatch")
        _validate_transform(mapping["transform"])
        _validate_kind(
            concept_kinds[source_concept],
            field["datatype"],
            mapping["transform"],
        )
        claim = claims.get((source_concept, *target_key))
        if claim is None:
            _fail("gate5_declaration_projection_mapping_unsubstantiated")
        if mapping["transform"] != claim["transform"]:
            _fail("gate5_declaration_projection_mapping_unsubstantiated")
        refs = mapping["evidence_refs"]
        if (
            not isinstance(refs, list)
            or len(refs) != len(set(refs))
            or set(refs) != set(claim["required_evidence_refs"])
        ):
            _fail("gate5_declaration_projection_evidence_incomplete")
        mapping_ids.add(mapping_id)
        source_concepts.add(source_concept)
        targets.add(target_key)
    required_targets = {
        (node["node_id"], field["attribute"])
        for node in evidence_target["nodes"]
        for field in node["fields"]
        if field["proof_required_mapping"]
    }
    if targets != required_targets or source_concepts != set(_V1_SOURCE_CONCEPTS):
        _fail("gate5_declaration_projection_missing_required_mapping")

    classification = evidence["classification_binding"]
    group_mapping = next(
        mapping
        for mapping in mappings
        if mapping["source_concept"] == "income_group_semantic"
    )
    if (
        input_contract["income_group_semantic"]
        != classification["income_group_semantic"]
        or group_mapping["transform"]["values"].get(
            classification["income_group_semantic"]
        )
        != classification["income_group_code"]
        or classification["evidence_ref"] not in group_mapping["evidence_refs"]
    ):
        _fail("gate5_declaration_projection_classification_incompatible")


def _validate_v1_evidence(evidence: Any) -> None:
    _keys(
        evidence,
        {
            "schema_version",
            "evidence_pack_id",
            "captured_on",
            "declaration",
            "sources",
            "claims",
            "classification_binding",
            "target_contract",
            "mapping_claims",
        },
        "gate5_declaration_projection_evidence_invalid",
    )
    if (
        evidence["schema_version"]
        != GATE5_DECLARATION_PROJECTION_V1_EVIDENCE_SCHEMA_VERSION
        or not _clean(evidence["evidence_pack_id"])
        or not _clean(evidence["captured_on"])
    ):
        _fail("gate5_declaration_projection_evidence_invalid")
    _keys(
        evidence["declaration"],
        _DECLARATION_KEYS,
        "gate5_declaration_projection_evidence_invalid",
    )
    sources = evidence["sources"]
    if not isinstance(sources, list) or not sources:
        _fail("gate5_declaration_projection_evidence_invalid")
    source_refs: set[str] = set()
    for source in sources:
        _keys(
            source,
            {"source_ref", "authority_kind", "url", "sha256"},
            "gate5_declaration_projection_evidence_invalid",
        )
        if (
            not all(
                _clean(source[key])
                for key in ("source_ref", "authority_kind", "url", "sha256")
            )
            or source["source_ref"] in source_refs
            or re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) is None
        ):
            _fail("gate5_declaration_projection_evidence_invalid")
        source_refs.add(source["source_ref"])
    claims = evidence["claims"]
    if not isinstance(claims, list) or not claims:
        _fail("gate5_declaration_projection_evidence_invalid")
    evidence_refs: set[str] = set()
    for claim in claims:
        _keys(
            claim,
            {"evidence_ref", "source_refs", "locator", "supports"},
            "gate5_declaration_projection_evidence_invalid",
        )
        refs = claim["source_refs"]
        if (
            not _clean(claim["evidence_ref"])
            or claim["evidence_ref"] in evidence_refs
            or not isinstance(refs, list)
            or not refs
            or len(refs) != len(set(refs))
            or not set(refs) <= source_refs
            or not _clean(claim["locator"])
            or not _clean(claim["supports"])
        ):
            _fail("gate5_declaration_projection_evidence_invalid")
        evidence_refs.add(claim["evidence_ref"])
    classification = evidence["classification_binding"]
    _keys(
        classification,
        {
            "income_group_semantic",
            "income_group_code",
            "income_type_code",
            "income_type_projection_scope",
            "evidence_ref",
        },
        "gate5_declaration_projection_evidence_invalid",
    )
    if (
        not _clean(classification["income_group_semantic"])
        or re.fullmatch(r"[0-9]{2}", classification["income_group_code"]) is None
        or re.fullmatch(r"[0-9]{3}", classification["income_type_code"]) is None
        or classification["income_type_projection_scope"]
        != "evidence_only_not_section2_target"
        or classification["evidence_ref"] not in evidence_refs
    ):
        _fail("gate5_declaration_projection_evidence_invalid")
    target = evidence["target_contract"]
    _keys(
        target,
        _V1_TARGET_KEYS,
        "gate5_declaration_projection_evidence_invalid",
    )
    if not isinstance(target["nodes"], list) or not all(
        isinstance(node, dict) for node in target["nodes"]
    ):
        _fail("gate5_declaration_projection_evidence_invalid")
    _validate_v1_target(
        {
            "path": target["path"],
            "root_node_id": target["root_node_id"],
            "nodes": [
                {key: node.get(key) for key in _V1_NODE_KEYS}
                for node in target["nodes"]
            ],
        }
    )
    field_targets: set[tuple[str, str]] = set()
    for node in target["nodes"]:
        if set(node) != _V1_NODE_KEYS | {"fields"}:
            _fail("gate5_declaration_projection_evidence_invalid")
        fields = node["fields"]
        if not isinstance(fields, list) or not fields:
            _fail("gate5_declaration_projection_evidence_invalid")
        for field in fields:
            _keys(
                field,
                {"attribute", "xsd_use", "datatype", "proof_required_mapping"},
                "gate5_declaration_projection_evidence_invalid",
            )
            target_key = (node["node_id"], field["attribute"])
            if (
                not _clean(field["attribute"])
                or target_key in field_targets
                or field["xsd_use"] not in {"required", "optional"}
                or field["proof_required_mapping"] is not True
            ):
                _fail("gate5_declaration_projection_evidence_invalid")
            _validate_v1_datatype(field["datatype"])
            field_targets.add(target_key)
    mapping_claims = evidence["mapping_claims"]
    if not isinstance(mapping_claims, list) or not mapping_claims:
        _fail("gate5_declaration_projection_evidence_invalid")
    claim_targets: set[tuple[str, str, str]] = set()
    for claim in mapping_claims:
        _keys(
            claim,
            {
                "source_concept",
                "target_node_id",
                "target_attribute",
                "transform",
                "required_evidence_refs",
            },
            "gate5_declaration_projection_evidence_invalid",
        )
        target_key = (claim["target_node_id"], claim["target_attribute"])
        claim_key = (claim["source_concept"], *target_key)
        refs = claim["required_evidence_refs"]
        if (
            claim["source_concept"] not in _V1_SOURCE_CONCEPTS
            or target_key not in field_targets
            or claim_key in claim_targets
            or not isinstance(refs, list)
            or not refs
            or len(refs) != len(set(refs))
            or not set(refs) <= evidence_refs
        ):
            _fail("gate5_declaration_projection_evidence_invalid")
        _validate_transform(claim["transform"])
        claim_targets.add(claim_key)


def _validate_v1_target(target: Any) -> None:
    _keys(target, _V1_TARGET_KEYS, "gate5_declaration_projection_invalid_target")
    nodes = target["nodes"]
    if (
        not _clean(target["path"])
        or not _clean(target["root_node_id"])
        or not isinstance(nodes, list)
        or len(nodes) not in {1, 2}
    ):
        _fail("gate5_declaration_projection_invalid_target")
    node_ids: set[str] = set()
    roots = 0
    for node in nodes:
        _keys(node, _V1_NODE_KEYS, "gate5_declaration_projection_invalid_target")
        parent = node["parent_node_id"]
        if (
            not _clean(node["node_id"])
            or node["node_id"] in node_ids
            or not _clean(node["path"])
            or not _clean(node["element"])
            or node["min_occurs"] != 1
            or node["max_occurs"] != 1
            or (parent is not None and not _clean(parent))
        ):
            _fail("gate5_declaration_projection_invalid_target")
        if parent is None:
            roots += 1
            if node["node_id"] != target["root_node_id"] or node["path"] != target["path"]:
                _fail("gate5_declaration_projection_invalid_target")
        node_ids.add(node["node_id"])
    if roots != 1:
        _fail("gate5_declaration_projection_invalid_target")
    for node in nodes:
        parent = node["parent_node_id"]
        if parent is not None:
            if parent != target["root_node_id"] or parent not in node_ids:
                _fail("gate5_declaration_projection_invalid_target")
            if node["path"] != f'{target["path"]}/{node["element"]}':
                _fail("gate5_declaration_projection_invalid_target")


def _validate_v1_datatype(datatype: Any) -> None:
    if not isinstance(datatype, dict):
        _fail("gate5_declaration_projection_evidence_invalid")
    if datatype.get("base") == "string":
        if (
            set(datatype) not in ({"base", "length"}, {"base", "length", "pattern"})
            or not isinstance(datatype.get("length"), int)
            or datatype["length"] < 1
            or (
                "pattern" in datatype
                and (not _clean(datatype["pattern"]) or datatype["pattern"] != f'[0-9]{{{datatype["length"]}}}')
            )
        ):
            _fail("gate5_declaration_projection_evidence_invalid")
        return
    if (
        set(datatype) != {"base", "total_digits", "fraction_digits"}
        or datatype.get("base") != "decimal"
        or not isinstance(datatype.get("total_digits"), int)
        or datatype["total_digits"] < 1
        or datatype.get("fraction_digits") != 2
    ):
        _fail("gate5_declaration_projection_evidence_invalid")


def _validated_v1_projection_ref(value: Any) -> tuple[str, str]:
    _keys(
        value,
        {"schema_version", "projection_id", "projection_version"},
        "gate5_declaration_projection_ref_invalid",
    )
    if (
        value["schema_version"]
        != GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION
        or not _clean(value["projection_id"])
        or not _clean(value["projection_version"])
    ):
        _fail("gate5_declaration_projection_ref_invalid")
    return value["projection_id"], value["projection_version"]


def _build_v1_fragment(
    *,
    target: dict[str, Any],
    attributes_by_node: dict[str, dict[str, str]],
) -> dict[str, Any]:
    nodes = {node["node_id"]: node for node in target["nodes"]}
    root_node = nodes[target["root_node_id"]]
    fragment = {
        "element": root_node["element"],
        "attributes": copy.deepcopy(attributes_by_node[root_node["node_id"]]),
        "children": [],
    }
    for node in target["nodes"]:
        if node["parent_node_id"] is not None:
            fragment["children"].append(
                {
                    "element": node["element"],
                    "attributes": copy.deepcopy(attributes_by_node[node["node_id"]]),
                }
            )
    return fragment


def _project_legacy_as_v1(
    *,
    projection: dict[str, Any],
    declaration_semantics: dict[str, Any],
) -> dict[str, Any]:
    spec = projection["spec"]
    evidence = projection["evidence"]
    legacy = Gate5DeclarationProjectionRuntime(
        spec=copy.deepcopy(spec),
        evidence_pack=copy.deepcopy(evidence),
        spec_sha256=projection["spec_sha256"],
        evidence_pack_sha256=projection["evidence_sha256"],
    ).project(proof_input=declaration_semantics)
    return {
        "schema_version": GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION,
        "status": "projected",
        "declaration": copy.deepcopy(legacy["declaration"]),
        "target": {
            "path": legacy["target"]["path"],
            "occurrence": legacy["target"]["occurrence"],
            "scope": "single_declaration_fragment",
        },
        "fragment": {
            "element": legacy["target"]["element"],
            "attributes": copy.deepcopy(legacy["attributes"]),
            "children": [],
        },
        "source_binding": {
            "input_contract": spec["input_contract"]["schema_version"],
            "input_sha256": _canonical_sha256(declaration_semantics),
        },
        "projection_binding": {
            "projection_id": spec["spec_id"],
            "projection_version": spec["spec_version"],
            "spec_resource_sha256": projection["spec_sha256"],
            "evidence_pack_id": evidence["evidence_pack_id"],
            "evidence_resource_sha256": projection["evidence_sha256"],
        },
        "provenance": [
            {
                "source": {
                    "contract": spec["input_contract"]["schema_version"],
                    "concept": item["source_concept"],
                    "trace": {"source_kind": "supplied_stable_semantic"},
                },
                "rule": {
                    "projection_id": spec["spec_id"],
                    "projection_version": spec["spec_version"],
                    "mapping_id": item["mapping_id"],
                    "evidence_refs": copy.deepcopy(item["evidence_refs"]),
                },
                "target": {
                    "node_id": "root",
                    "attribute": item["target_attribute"],
                },
            }
            for item in legacy["provenance"]
        ],
        "validation": {
            "projection_definition": "passed",
            "upstream_tax_model": "not_applicable_registered_semantic_input",
            "required_mappings": "passed",
            "xsd_claim": "partial_declaration_fragment_not_full_xml_validated",
        },
    }


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
        if (
            len(value) != datatype["length"]
            or (
                "enumeration" in datatype
                and value not in datatype["enumeration"]
            )
            or (
                "pattern" in datatype
                and re.fullmatch(datatype["pattern"], value) is None
            )
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
    "GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE_SHA256",
    "GATE5_DECLARATION_PROJECTION_SPEC_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE",
    "GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256",
    "GATE5_DECLARATION_PROJECTION_SECTION2_ID",
    "GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE",
    "GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256",
    "GATE5_DECLARATION_PROJECTION_SECTION2_VERSION",
    "GATE5_DECLARATION_PROJECTION_V1_EVIDENCE_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_V1_REF_SCHEMA_VERSION",
    "GATE5_DECLARATION_PROJECTION_V1_SPEC_SCHEMA_VERSION",
    "Gate5DeclarationProjectionError",
    "Gate5DeclarationProjectionRuntime",
    "Gate5DeclarationProjectionRuntimeFactory",
    "Gate5DeclarationProjectionRuntimeV1",
    "Gate5DeclarationProjectionRuntimeV1Factory",
]
