"""Author, validate and publish one obligation-backed root Declaration Definition."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION,
)


GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION = (
    "broker_reports_gate5_full_declaration_definition_v1"
)
GATE5_FULL_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_gate5_full_declaration_definition_validation_v1"
)
GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION = (
    "broker_reports_gate5_full_declaration_definition_publication_v1"
)
GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE = (
    "gate5_full_declaration_obligations.ru_3ndfl_2025.v1.json"
)
GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256 = (
    "8065a2047b2d7bf5a1a3b87ed4dd49f65bd39e97b6a42c1acf24d2d62548b23c"
)
GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE = (
    "gate5_full_declaration_definition_authoring.primary.v1.payload.json"
)
GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE_SHA256 = (
    "5a51aa10b3aa5e880254722f79543fefe234c189969b25d2deae8291e30bc541"
)
GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE = (
    "gate5_full_declaration_definition_candidate.g528b.json"
)
GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256 = (
    "8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d"
)
GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE = (
    "gate5_full_declaration_definition_review.g528b.json"
)
GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE_SHA256 = (
    "731ae53ed77046cfd89b2aac8e53f5416c51cdb732709327a7702c2c28de1619"
)

FACTORY_REQUIRED = (
    "Gate5FullDeclarationDefinitionAuthoringFactory.create is the only G5.28B "
    "candidate-payload and deterministic-validation owner",
    "Gate5FullDeclarationDefinitionCandidateFactory.create loads only the exact "
    "hash-pinned untrusted G5.28B model evidence",
    "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create is the only "
    "G5.28B repository-published Definition authority",
)
FORBIDDEN = (
    "provider retry, candidate repair, best-of selection or semantic follow-up",
    "case-time scope resolution, questionnaire, tax calculation or projection",
    "XML/PDF layout, executable conditions, formulas, predicates or workflow",
    "unregistered component contracts, promoted bounded contracts or second authority",
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_VERSION = re.compile(r"^[0-9][a-zA-Z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_DOMAIN_TERMS = re.compile(
    r"\b(xml|xsd|xpath|pdf|namespace|encoding|tag|element|attribute|"
    r"section|appendix|page|line|field|coordinate|formula|predicate|"
    r"workflow|roadmap|python|javascript|sql|if|then|unless)\b",
    re.IGNORECASE,
)
_FORBIDDEN_CANDIDATE_KEYS = {
    "action",
    "code",
    "condition",
    "coordinate",
    "element_order",
    "expression",
    "fact_path",
    "formula",
    "namespace",
    "predicate",
    "query",
    "question",
    "rule",
    "step",
    "workflow",
    "xpath",
    "xml_tag",
}
_POLICY_AUTHORITY_CLASSES = {
    "definition_mandatory": ("trusted_declaration_definition",),
    "elective_claim": (
        "authenticated_declarant_attestation",
        "user_case_evidence",
    ),
    "exhaustive_coverage": ("domain_coverage_evidence",),
    "factual_occurrence": (
        "financial_case_evidence",
        "user_case_evidence",
        "validated_typed_component",
    ),
    "typed_legal_classification": (
        "published_typed_classification",
        "validated_typed_component",
    ),
}
_COMPONENT_AVAILABILITY = {"missing", "published_bounded", "published_exact"}
_ROOT_KEYS = {
    "schema_version",
    "definition_id",
    "definition_version",
    "declaration_identity",
    "obligation_package_binding",
    "domains",
}
_DOMAIN_KEYS = {
    "domain_id",
    "semantic_meaning",
    "obligation_refs",
    "expected_component",
}
_COMPONENT_KEYS = {"family", "availability", "contract_ids"}
_IDENTITY = {
    "jurisdiction": "RU",
    "form": "3-NDFL",
    "tax_period": "2025",
    "knd": "1151020",
    "order": "FNS_ED-7-11/913@_2025-10-20",
    "electronic_format_version": "5.20",
}


class Gate5FullDeclarationDefinitionError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


@dataclass(frozen=True)
class _Obligation:
    obligation_id: str
    policy_id: str
    official_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class _ComponentContract:
    contract_id: str
    root_coverage: str
    supported_obligation_refs: frozenset[str]


class Gate5FullDeclarationDefinitionAuthoringFactory:
    @staticmethod
    def create() -> "Gate5FullDeclarationDefinitionAuthoring":
        expected = (
            _canonical_json(build_unfrozen_full_declaration_definition_payload())
            + b"\n"
        )
        raw = _read_resource(
            GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE,
            GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE_SHA256,
            "gate5_full_declaration_definition_payload",
        )
        if raw != expected:
            _fail("gate5_full_declaration_definition_payload_drift")
        payload = _parse_json_object(raw, "gate5_full_declaration_definition_payload")
        package = payload["reviewed_obligation_package"]
        obligations, components = _validate_obligation_package(package)
        _validate_bias(payload)
        return Gate5FullDeclarationDefinitionAuthoring(
            payload=payload,
            package=package,
            obligations=obligations,
            components=components,
        )


class Gate5FullDeclarationDefinitionAuthoring:
    def __init__(
        self,
        *,
        payload: dict[str, Any],
        package: dict[str, Any],
        obligations: dict[str, _Obligation],
        components: dict[str, _ComponentContract],
    ) -> None:
        self._payload = copy.deepcopy(payload)
        self._package = copy.deepcopy(package)
        self._obligations = obligations
        self._components = components

    def model_payload(self) -> dict[str, Any]:
        return copy.deepcopy(self._payload)

    def model_payload_bytes(self) -> bytes:
        return _canonical_json(self._payload) + b"\n"

    def payload_sha256(self) -> str:
        return hashlib.sha256(self.model_payload_bytes()).hexdigest()

    def obligation_package(self) -> dict[str, Any]:
        return copy.deepcopy(self._package)

    def bias_audit(self) -> dict[str, Any]:
        return _validate_bias(self._payload)

    def parse_candidate_response(self, raw: bytes | str) -> dict[str, Any]:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        candidate = _parse_json_object(
            raw, "gate5_full_declaration_definition_candidate"
        )
        self.validate_candidate(candidate)
        return candidate

    def validate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return _validate_candidate(
            candidate=copy.deepcopy(candidate),
            package=self._package,
            obligations=self._obligations,
            components=self._components,
        )


class Gate5FullDeclarationDefinitionCandidateFactory:
    @staticmethod
    def create() -> "Gate5FullDeclarationDefinitionCandidateEvidence":
        raw = _read_resource(
            GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE,
            GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256,
            "gate5_full_declaration_definition_candidate",
        )
        authoring = Gate5FullDeclarationDefinitionAuthoringFactory.create()
        candidate = authoring.parse_candidate_response(raw)
        validation = authoring.validate_candidate(candidate)
        return Gate5FullDeclarationDefinitionCandidateEvidence(
            raw=raw,
            candidate=candidate,
            validation=validation,
        )


class Gate5TrustedFullDeclarationDefinitionAuthorityFactory:
    @staticmethod
    def create() -> "Gate5TrustedFullDeclarationDefinitionAuthority":
        review_raw = _read_resource(
            GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE,
            GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE_SHA256,
            "gate5_full_declaration_definition_review",
        )
        review = _parse_json_object(
            review_raw,
            "gate5_full_declaration_definition_review",
        )
        _validate_review(review)
        if review["status"] != "trusted_repository_published":
            _fail("gate5_full_declaration_definition_not_published")
        evidence = Gate5FullDeclarationDefinitionCandidateFactory.create()
        candidate = evidence.candidate()
        raw = evidence.candidate_bytes()
        validation = evidence.validation()
        if (
            review["candidate_sha256"] != hashlib.sha256(raw).hexdigest()
            or review["validation_sha256"]
            != hashlib.sha256(_canonical_json(validation)).hexdigest()
            or review["obligation_package_sha256"]
            != GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256
            or review["definition_id"] != candidate["definition_id"]
            or review["definition_version"] != candidate["definition_version"]
        ):
            _fail("gate5_full_declaration_definition_review_mismatch")
        return Gate5TrustedFullDeclarationDefinitionAuthority(
            raw=raw,
            definition=candidate,
            validation=validation,
        )


class Gate5FullDeclarationDefinitionCandidateEvidence:
    def __init__(
        self,
        *,
        raw: bytes,
        candidate: dict[str, Any],
        validation: dict[str, Any],
    ) -> None:
        self._raw = bytes(raw)
        self._candidate = copy.deepcopy(candidate)
        self._validation = copy.deepcopy(validation)

    def candidate(self) -> dict[str, Any]:
        return copy.deepcopy(self._candidate)

    def candidate_bytes(self) -> bytes:
        return bytes(self._raw)

    def validation(self) -> dict[str, Any]:
        return copy.deepcopy(self._validation)


class Gate5TrustedFullDeclarationDefinitionAuthority:
    def __init__(
        self,
        *,
        raw: bytes,
        definition: dict[str, Any],
        validation: dict[str, Any],
    ) -> None:
        self._raw = bytes(raw)
        self._definition = copy.deepcopy(definition)
        self._validation = copy.deepcopy(validation)

    def definition(self) -> dict[str, Any]:
        return copy.deepcopy(self._definition)

    def definition_bytes(self) -> bytes:
        return bytes(self._raw)

    def publication(self) -> dict[str, Any]:
        return {
            "schema_version": GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION,
            "status": "trusted_repository_published",
            "definition_id": self._definition["definition_id"],
            "definition_version": self._definition["definition_version"],
            "definition_sha256": hashlib.sha256(self._raw).hexdigest(),
            "validation_sha256": hashlib.sha256(
                _canonical_json(self._validation)
            ).hexdigest(),
            "obligation_package_sha256": (
                GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256
            ),
        }

    def resolve(
        self,
        definition_id: str,
        definition_version: str,
        definition_sha256: str,
    ) -> dict[str, Any]:
        if (
            definition_id != self._definition["definition_id"]
            or definition_version != self._definition["definition_version"]
            or definition_sha256 != hashlib.sha256(self._raw).hexdigest()
        ):
            _fail("gate5_full_declaration_definition_not_published")
        return self.definition()

    def resolve_for_scope(
        self,
        definition_id: str,
        definition_version: str,
        definition_sha256: str,
    ) -> dict[str, Any]:
        """Expose the reviewed Definition and its derived closed policies."""
        definition = self.resolve(
            definition_id,
            definition_version,
            definition_sha256,
        )
        return {
            "definition": definition,
            "publication": self.publication(),
            "applicability_audit": copy.deepcopy(
                self._validation["applicability_audit"]
            ),
        }


def build_unfrozen_full_declaration_definition_payload() -> dict[str, Any]:
    package = _load_obligation_package()
    return {
        "schema_version": (
            "broker_reports_gate5_full_declaration_definition_authoring_payload_v1"
        ),
        "task": (
            "Independently author the smallest complete target-independent root "
            "Declaration Definition for the supplied reviewed obligations."
        ),
        "output": "Return exactly one strict JSON object and no Markdown or commentary.",
        "local_boundary_contract": [
            "One domain has one honest applicability question for a case and period.",
            "One domain activates one coherent typed semantic component family, including value-level variants that belong to that family.",
            "Every obligation in one domain has one identical closed applicability policy.",
            "A domain remains meaningful if a target representation changes.",
        ],
        "non_goals": [
            "Do not design calculation, runtime resolution, questionnaires or case-time behavior.",
            "Do not emit target mapping, layout, executable logic, XML or PDF details.",
        ],
        "reviewed_obligation_package_binding": _package_binding(package),
        "reviewed_obligation_package": package,
        "candidate_contract": {
            "schema_version_const": GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION,
            "root_fields_exact": sorted(_ROOT_KEYS),
            "domain_fields_exact": sorted(_DOMAIN_KEYS),
            "expected_component_fields_exact": sorted(_COMPONENT_KEYS),
            "component_availability": sorted(_COMPONENT_AVAILABILITY),
            "domain_id_pattern": "^[a-z][a-z0-9_.-]{0,127}$",
            "definition_version_pattern": "^[0-9][a-zA-Z0-9_.-]{0,63}$",
            "semantic_meaning_utf8_bytes_max": 640,
            "domains_max": 32,
            "rules": [
                "Copy declaration_identity and reviewed_obligation_package_binding exactly into the candidate fields declaration_identity and obligation_package_binding.",
                "Reference every supplied obligation_id exactly once across all domains; emit no unknown refs and no empty domain.",
                "Do not group obligations having different applicability_policy_id values.",
                "Derive stable domain IDs, the partition and count yourself; none is expected or supplied.",
                "Use target-independent business meanings, not form sections, appendices, XML or PDF layout identities.",
                "Cite only supplied component contract IDs; use missing where none belongs to the family.",
                "Every listed contract is bounded_partial_only and may be cited only as published_bounded, never published_exact.",
                "Do not repeat policies, authority classes or official evidence refs in the candidate; validation derives them from obligation refs.",
                "Do not write formulas, executable conditions, predicates, workflows, questions, code, fact paths, target mapping or case-time behavior.",
            ],
        },
    }


def _load_obligation_package() -> dict[str, Any]:
    raw = _read_resource(
        GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE,
        GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256,
        "gate5_full_declaration_obligation_package",
    )
    package = _parse_json_object(raw, "gate5_full_declaration_obligation_package")
    _validate_obligation_package(package)
    return package


def _package_binding(package: dict[str, Any]) -> dict[str, str]:
    return {
        "package_id": package["package_id"],
        "package_version": package["package_version"],
        "package_sha256": GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256,
    }


def _validate_obligation_package(
    package: Any,
) -> tuple[dict[str, _Obligation], dict[str, _ComponentContract]]:
    if (
        not isinstance(package, dict)
        or set(package)
        != {
            "schema_version",
            "package_id",
            "package_version",
            "review_status",
            "source_bytes_verified_on",
            "declaration_identity",
            "official_evidence",
            "evidence_policy_definitions",
            "reviewed_semantic_obligations",
            "component_inventory",
            "coverage_rule",
        }
        or package.get("schema_version")
        != "broker_reports_gate5_declaration_obligation_package_v1"
        or package.get("package_id") != "fns-ru-3ndfl-2025-reviewed-obligations"
        or package.get("package_version") != "2026-08-10.1"
        or package.get("review_status") != "frozen_repository_reviewed"
        or package.get("source_bytes_verified_on") != "2026-08-10"
        or package.get("declaration_identity") != _IDENTITY
        or not _clean(package.get("coverage_rule"), 1024)
    ):
        _fail("gate5_full_declaration_obligation_package_invalid")
    evidence = package.get("official_evidence")
    if not isinstance(evidence, dict) or set(evidence) != {
        "sources",
        "surface_requirements",
    }:
        _fail("gate5_full_declaration_obligation_package_invalid")
    sources = evidence.get("sources")
    if not isinstance(sources, list) or len(sources) != 4:
        _fail("gate5_full_declaration_official_evidence_invalid")
    source_ids: set[str] = set()
    for source in sources:
        if (
            not isinstance(source, dict)
            or set(source) != {"source_ref", "url", "content_sha256"}
            or not _identifier(source.get("source_ref"))
            or source["source_ref"] in source_ids
            or not isinstance(source.get("url"), str)
            or not source["url"].startswith("https://www.nalog.gov.ru/")
            or _SHA256.fullmatch(source.get("content_sha256", "")) is None
        ):
            _fail("gate5_full_declaration_official_evidence_invalid")
        source_ids.add(source["source_ref"])
    surfaces = evidence.get("surface_requirements")
    if not isinstance(surfaces, list) or len(surfaces) != 14:
        _fail("gate5_full_declaration_official_evidence_invalid")
    surface_ids: set[str] = set()
    for surface in surfaces:
        if (
            not isinstance(surface, dict)
            or set(surface) != {"evidence_ref", "semantic_requirement"}
            or not _identifier(surface.get("evidence_ref"))
            or surface["evidence_ref"] in surface_ids
            or not _clean(surface.get("semantic_requirement"), 2048)
        ):
            _fail("gate5_full_declaration_official_evidence_invalid")
        surface_ids.add(surface["evidence_ref"])
    policies = package.get("evidence_policy_definitions")
    if not isinstance(policies, list) or len(policies) != len(
        _POLICY_AUTHORITY_CLASSES
    ):
        _fail("gate5_full_declaration_policy_package_invalid")
    policy_ids: set[str] = set()
    for policy in policies:
        if (
            not isinstance(policy, dict)
            or set(policy) != {"policy_id", "meaning"}
            or policy.get("policy_id") not in _POLICY_AUTHORITY_CLASSES
            or policy["policy_id"] in policy_ids
            or not _clean(policy.get("meaning"), 1024)
        ):
            _fail("gate5_full_declaration_policy_package_invalid")
        policy_ids.add(policy["policy_id"])
    if policy_ids != set(_POLICY_AUTHORITY_CLASSES):
        _fail("gate5_full_declaration_policy_package_invalid")
    obligations_raw = package.get("reviewed_semantic_obligations")
    if not isinstance(obligations_raw, list) or len(obligations_raw) != 25:
        _fail("gate5_full_declaration_obligation_package_invalid")
    obligations: dict[str, _Obligation] = {}
    covered_surfaces: set[str] = set()
    for item in obligations_raw:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "obligation_id",
                "semantic_requirement",
                "applicability_policy_id",
                "official_evidence_refs",
            }
            or not _identifier(item.get("obligation_id"))
            or item["obligation_id"] in obligations
            or not _clean(item.get("semantic_requirement"), 2048)
            or item.get("applicability_policy_id") not in policy_ids
            or not _string_list(item.get("official_evidence_refs"))
            or len(item["official_evidence_refs"])
            != len(set(item["official_evidence_refs"]))
            or not set(item["official_evidence_refs"]).issubset(surface_ids)
        ):
            _fail("gate5_full_declaration_obligation_package_invalid")
        obligation = _Obligation(
            obligation_id=item["obligation_id"],
            policy_id=item["applicability_policy_id"],
            official_evidence_refs=tuple(item["official_evidence_refs"]),
        )
        obligations[obligation.obligation_id] = obligation
        covered_surfaces.update(obligation.official_evidence_refs)
    if covered_surfaces != surface_ids:
        _fail("gate5_full_declaration_obligation_surface_coverage_invalid")
    components = _validate_component_inventory(
        package.get("component_inventory"), set(obligations)
    )
    return obligations, components


def _validate_component_inventory(
    value: Any,
    obligation_ids: set[str],
) -> dict[str, _ComponentContract]:
    if (
        not isinstance(value, dict)
        or set(value) != {"inventory_id", "inventory_version", "contracts", "rule"}
        or not _identifier(value.get("inventory_id"))
        or not _VERSION.fullmatch(value.get("inventory_version", ""))
        or not _clean(value.get("rule"), 1024)
        or not isinstance(value.get("contracts"), list)
    ):
        _fail("gate5_full_declaration_component_inventory_invalid")
    result: dict[str, _ComponentContract] = {}
    for item in value["contracts"]:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "contract_id",
                "semantic_scope",
                "root_coverage",
                "supported_obligation_refs",
            }
            or not _identifier(item.get("contract_id"))
            or item["contract_id"] in result
            or not _clean(item.get("semantic_scope"), 1024)
            or item.get("root_coverage")
            not in {"bounded_partial_only", "exact_root_domain"}
            or not _string_list(item.get("supported_obligation_refs"))
            or len(item["supported_obligation_refs"])
            != len(set(item["supported_obligation_refs"]))
            or not set(item["supported_obligation_refs"]).issubset(obligation_ids)
        ):
            _fail("gate5_full_declaration_component_inventory_invalid")
        result[item["contract_id"]] = _ComponentContract(
            contract_id=item["contract_id"],
            root_coverage=item["root_coverage"],
            supported_obligation_refs=frozenset(item["supported_obligation_refs"]),
        )
    if set(result) != {
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION,
        GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
        GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION,
        GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    }:
        _fail("gate5_full_declaration_component_inventory_drift")
    return result


def _validate_bias(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = {
        "g5.27",
        "g5.28",
        "mission context",
        "previous candidate",
        "previous failure",
        "expected domain",
        "expected partition",
        "expected count",
        "first downstream gap",
        "roadmap",
    }
    hits = sorted(term for term in forbidden if term in text)
    if hits:
        _fail("gate5_full_declaration_definition_prompt_bias_detected", hits[0])
    return {
        "schema_version": "broker_reports_gate5_full_declaration_definition_bias_audit_v1",
        "status": "passed",
        "forbidden_term_count": len(forbidden),
        "hits": [],
    }


def _validate_candidate(
    *,
    candidate: Any,
    package: dict[str, Any],
    obligations: dict[str, _Obligation],
    components: dict[str, _ComponentContract],
) -> dict[str, Any]:
    _reject_forbidden_keys(candidate)
    if not isinstance(candidate, dict) or set(candidate) != _ROOT_KEYS:
        _fail("gate5_full_declaration_definition_candidate_invalid")
    if (
        candidate.get("schema_version")
        != GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION
        or not _identifier(candidate.get("definition_id"))
        or not _VERSION.fullmatch(candidate.get("definition_version", ""))
        or candidate.get("declaration_identity") != _IDENTITY
        or candidate.get("obligation_package_binding") != _package_binding(package)
    ):
        _fail("gate5_full_declaration_definition_identity_invalid")
    domains = candidate.get("domains")
    if not isinstance(domains, list) or not 1 <= len(domains) <= 32:
        _fail("gate5_full_declaration_definition_domains_invalid")
    domain_ids: set[str] = set()
    component_families: set[str] = set()
    meaning_keys: set[str] = set()
    obligation_owners: dict[str, str] = {}
    obligation_rows: list[dict[str, str]] = []
    applicability_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    for position, domain in enumerate(domains):
        field = f"domains[{position}]"
        if not isinstance(domain, dict) or set(domain) != _DOMAIN_KEYS:
            _fail("gate5_full_declaration_definition_domain_invalid", field)
        domain_id = domain.get("domain_id")
        meaning = domain.get("semantic_meaning")
        if (
            not _identifier(domain_id)
            or domain_id in domain_ids
            or not _clean(meaning, 640)
            or _FORBIDDEN_DOMAIN_TERMS.search(domain_id) is not None
            or _FORBIDDEN_DOMAIN_TERMS.search(meaning) is not None
            or any(token in meaning for token in ("==", "=>", "->", "{", "}"))
        ):
            _fail("gate5_full_declaration_definition_domain_invalid", field)
        meaning_key = " ".join(meaning.lower().split())
        if meaning_key in meaning_keys:
            _fail("gate5_full_declaration_definition_domain_duplicate", field)
        domain_ids.add(domain_id)
        meaning_keys.add(meaning_key)
        refs = domain.get("obligation_refs")
        if not isinstance(refs, list) or not refs:
            _fail("gate5_full_declaration_definition_obligation_empty", field)
        if any(not _identifier(ref) or ref not in obligations for ref in refs):
            _fail("gate5_full_declaration_definition_obligation_unknown", field)
        if len(refs) != len(set(refs)):
            _fail("gate5_full_declaration_definition_obligation_duplicate", field)
        for ref in refs:
            if ref in obligation_owners:
                _fail("gate5_full_declaration_definition_obligation_duplicate", ref)
            obligation_owners[ref] = domain_id
            obligation_rows.append({"obligation_id": ref, "domain_id": domain_id})
        policies = {obligations[ref].policy_id for ref in refs}
        if len(policies) != 1:
            _fail("gate5_full_declaration_definition_policy_mixed", field)
        policy = next(iter(policies))
        evidence_refs = sorted(
            {
                evidence_ref
                for ref in refs
                for evidence_ref in obligations[ref].official_evidence_refs
            }
        )
        component_row = _validate_expected_component(
            domain["expected_component"],
            components,
            set(refs),
            field,
        )
        if component_row["family"] in component_families:
            _fail("gate5_full_declaration_definition_component_family_duplicate", field)
        component_families.add(component_row["family"])
        component_rows.append({"domain_id": domain_id, **component_row})
        applicability_rows.append(
            {
                "domain_id": domain_id,
                "mode": "always" if policy == "definition_mandatory" else "conditional",
                "policy": policy,
                "allowed_authority_classes": list(_POLICY_AUTHORITY_CLASSES[policy]),
                "official_evidence_refs": evidence_refs,
            }
        )
    missing = sorted(set(obligations) - set(obligation_owners))
    if missing:
        _fail("gate5_full_declaration_definition_obligation_missing", missing[0])
    obligation_rows.sort(key=lambda row: row["obligation_id"])
    return {
        "schema_version": GATE5_FULL_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION,
        "status": "eligible_for_review",
        "definition_id": candidate["definition_id"],
        "definition_version": candidate["definition_version"],
        "domain_count": len(domains),
        "obligation_accounting": {
            "status": "passed",
            "package_id": package["package_id"],
            "package_version": package["package_version"],
            "package_sha256": GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256,
            "obligation_count": len(obligation_rows),
            "missing_obligation_ids": [],
            "duplicate_obligation_ids": [],
            "unknown_obligation_ids": [],
            "rows": obligation_rows,
        },
        "applicability_audit": {"status": "passed", "rows": applicability_rows},
        "component_audit": {"status": "passed", "rows": component_rows},
        "target_independence_audit": {
            "status": "passed",
            "forbidden_schema_keys": sorted(_FORBIDDEN_CANDIDATE_KEYS),
            "forbidden_domain_term_pattern": _FORBIDDEN_DOMAIN_TERMS.pattern,
        },
    }


def _validate_expected_component(
    component: Any,
    components: dict[str, _ComponentContract],
    domain_obligation_refs: set[str],
    field: str,
) -> dict[str, Any]:
    if (
        not isinstance(component, dict)
        or set(component) != _COMPONENT_KEYS
        or not _identifier(component.get("family"))
        or component.get("availability") not in _COMPONENT_AVAILABILITY
        or not isinstance(component.get("contract_ids"), list)
        or len(component["contract_ids"]) != len(set(component["contract_ids"]))
        or any(not _identifier(item) for item in component["contract_ids"])
    ):
        _fail("gate5_full_declaration_definition_component_invalid", field)
    availability = component["availability"]
    contract_ids = component["contract_ids"]
    if availability == "missing":
        if contract_ids:
            _fail("gate5_full_declaration_definition_component_gap_invalid", field)
    else:
        if not contract_ids or any(item not in components for item in contract_ids):
            _fail("gate5_full_declaration_definition_component_ref_invalid", field)
        expected_coverage = (
            "bounded_partial_only"
            if availability == "published_bounded"
            else "exact_root_domain"
        )
        if any(
            components[item].root_coverage != expected_coverage for item in contract_ids
        ):
            _fail("gate5_full_declaration_definition_component_coverage_invalid", field)
        if any(
            not components[item].supported_obligation_refs.intersection(
                domain_obligation_refs
            )
            for item in contract_ids
        ):
            _fail("gate5_full_declaration_definition_component_scope_invalid", field)
    return {
        "family": component["family"],
        "availability": availability,
        "contract_ids": list(contract_ids),
    }


def _reject_forbidden_keys(value: Any, path: str = "$root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_CANDIDATE_KEYS:
                _fail(
                    "gate5_full_declaration_definition_executable_logic_forbidden",
                    f"{path}.{key}",
                )
            _reject_forbidden_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for position, item in enumerate(value):
            _reject_forbidden_keys(item, f"{path}[{position}]")


def _validate_review(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "status",
            "candidate_sha256",
            "validation_sha256",
            "obligation_package_sha256",
            "definition_id",
            "definition_version",
            "reviewed_at",
            "checks",
            "finding_ids",
        }
        or value.get("schema_version")
        != "broker_reports_gate5_full_declaration_definition_review_v1"
        or value.get("status")
        not in {"review_rejected", "trusted_repository_published"}
        or _SHA256.fullmatch(value.get("candidate_sha256", "")) is None
        or _SHA256.fullmatch(value.get("validation_sha256", "")) is None
        or _SHA256.fullmatch(value.get("obligation_package_sha256", "")) is None
        or not _identifier(value.get("definition_id"))
        or not _VERSION.fullmatch(value.get("definition_version", ""))
        or not _clean(value.get("reviewed_at"), 64)
        or not isinstance(value.get("finding_ids"), list)
        or len(value["finding_ids"]) != len(set(value["finding_ids"]))
        or any(not _identifier(item) for item in value["finding_ids"])
        or not isinstance(value.get("checks"), dict)
        or set(value["checks"])
        != {
            "honest_applicability_question",
            "coherent_component_boundary",
            "obligation_package_completeness",
            "aggregate_variant_retention",
        }
        or any(item not in {"passed", "failed"} for item in value["checks"].values())
    ):
        _fail("gate5_full_declaration_definition_review_invalid")
    passed = all(item == "passed" for item in value["checks"].values())
    if value["status"] == "trusted_repository_published":
        if not passed or value["finding_ids"]:
            _fail("gate5_full_declaration_definition_review_invalid")
    elif passed or not value["finding_ids"]:
        _fail("gate5_full_declaration_definition_review_invalid")


def _read_resource(name: str, digest: str, code: str) -> bytes:
    try:
        raw = resources.files(__package__).joinpath(name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5FullDeclarationDefinitionError(f"{code}_unavailable") from exc
    if _SHA256.fullmatch(digest) is None or hashlib.sha256(raw).hexdigest() != digest:
        _fail(f"{code}_hash_mismatch")
    return raw


def _parse_json_object(raw: bytes, code: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise Gate5FullDeclarationDefinitionError(f"{code}_json_invalid") from exc
    if not isinstance(value, dict):
        _fail(f"{code}_not_object")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _clean(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and len(value.encode("utf-8")) <= maximum
    )


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_identifier(item) for item in value)
    )


def _fail(code: str, field: str = "") -> None:
    raise Gate5FullDeclarationDefinitionError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE",
    "GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256",
    "GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE",
    "GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE_SHA256",
    "GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE",
    "GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256",
    "GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION",
    "GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE",
    "GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE_SHA256",
    "GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION",
    "GATE5_FULL_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION",
    "Gate5FullDeclarationDefinitionAuthoring",
    "Gate5FullDeclarationDefinitionAuthoringFactory",
    "Gate5FullDeclarationDefinitionCandidateEvidence",
    "Gate5FullDeclarationDefinitionCandidateFactory",
    "Gate5FullDeclarationDefinitionError",
    "Gate5TrustedFullDeclarationDefinitionAuthority",
    "Gate5TrustedFullDeclarationDefinitionAuthorityFactory",
    "build_unfrozen_full_declaration_definition_payload",
]
