"""Exact synthetic filing-context component for one declaration scope."""

from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
import re
from typing import Any


GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_filing_and_party_identity_input_v0"
)
GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_filing_and_party_identity_component_v0"
)
GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_OWNER = (
    "Gate5FilingAndPartyIdentityRuntimeFactory.create.validate_component"
)
GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID = "filing_and_party_identity"
GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY = "filing_and_party_identity"
GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS = (
    "obl_filing_instance_identity",
    "obl_taxpayer_identity_and_period_status",
    "obl_signer_and_representation_authority",
)

FACTORY_REQUIRED = (
    "Gate5FilingAndPartyIdentityRuntimeFactory.create owns exact component validation",
)
FORBIDDEN = (
    "real-user inference, Gate 4 identity inference or caller-owned scope replacement",
    "Tax Model, tax calculation, applicability decision, PROJECT, XML or PDF",
    "profile service, identity registry, questionnaire DB or case-time LLM authority",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_binding",
        "filing_instance",
        "taxpayer",
        "signer",
        "evidence",
    }
)
_COMPONENT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "component_id",
        "domain_id",
        "component_family",
        "root_coverage",
        "covered_obligation_refs",
        "scope_binding",
        "input_snapshot",
    }
)
_SCOPE_KEYS = frozenset(
    {
        "schema_version",
        "scope_ref",
        "taxpayer_scope_ref",
        "tax_period",
        "authenticated_user_ref",
        "case_id",
        "normalization_run_ref",
        "scope_binding_sha256",
    }
)
_FILING_KEYS = frozenset(
    {
        "declaration_instance_ref",
        "correction_kind",
        "correction_number",
        "declaration_date",
        "tax_period",
        "destination_tax_authority_ref",
        "tax_authority_code",
    }
)
_TAXPAYER_KEYS = frozenset(
    {
        "taxpayer_ref",
        "period_status",
        "declarant_category",
        "last_name",
        "first_name",
        "middle_name",
        "inn",
    }
)
_SIGNER_KEYS = frozenset({"signer_ref", "signer_capacity", "representation_authority"})
_REPRESENTATION_KEYS = frozenset({"authority_ref", "authority_kind", "evidence_ref"})
_EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "source_ref",
        "case_id",
        "tax_period",
        "input_channel",
        "real_user_fact",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PERSON_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,60}$")
_INN = re.compile(r"^[0-9]{12}$")
_TAX_AUTHORITY_CODE = re.compile(r"^[0-9]{4}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5FilingAndPartyIdentityError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5FilingAndPartyIdentityRuntimeFactory:
    @staticmethod
    def create() -> "Gate5FilingAndPartyIdentityRuntime":
        return Gate5FilingAndPartyIdentityRuntime()


class Gate5FilingAndPartyIdentityRuntime:
    def create_component(self, *, component_input: dict[str, Any]) -> dict[str, Any]:
        snapshot = _validated_input(component_input)
        base = {
            "schema_version": GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
            "status": "complete",
            "domain_id": GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID,
            "component_family": GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY,
            "root_coverage": "exact_root_domain",
            "covered_obligation_refs": list(
                GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS
            ),
            "scope_binding": copy.deepcopy(snapshot["scope_binding"]),
            "input_snapshot": snapshot,
        }
        return {
            **base,
            "component_id": f"filing-party:{_canonical_sha256(base)}",
        }

    def validate_component(
        self,
        *,
        component: dict[str, Any],
        scope_binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(component, dict) or set(component) != _COMPONENT_KEYS:
            _fail("gate5_filing_party_component_invalid")
        expected = self.create_component(
            component_input=component.get("input_snapshot")
        )
        if component != expected:
            _fail("gate5_filing_party_component_mismatch")
        scope = _validated_scope(scope_binding)
        if component["scope_binding"] != scope:
            _fail("gate5_filing_party_component_scope_mismatch")
        return copy.deepcopy(component)


def _validated_input(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _INPUT_KEYS
        or value.get("schema_version")
        != GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION
    ):
        _fail("gate5_filing_party_input_invalid")
    scope = _validated_scope(value.get("scope_binding"))
    filing = value.get("filing_instance")
    taxpayer = value.get("taxpayer")
    signer = value.get("signer")
    evidence = value.get("evidence")
    if not isinstance(filing, dict) or set(filing) != _FILING_KEYS:
        _fail("gate5_filing_party_filing_instance_invalid")
    if (
        not _identifier(filing.get("declaration_instance_ref"))
        or filing.get("correction_kind") not in {"initial", "correction"}
        or not isinstance(filing.get("correction_number"), int)
        or isinstance(filing.get("correction_number"), bool)
        or filing["correction_number"] < 0
        or (filing["correction_kind"] == "initial" and filing["correction_number"] != 0)
        or (
            filing["correction_kind"] == "correction"
            and filing["correction_number"] == 0
        )
        or not _iso_date(filing.get("declaration_date"))
        or filing.get("tax_period") != scope["tax_period"]
        or not _identifier(filing.get("destination_tax_authority_ref"))
        or _TAX_AUTHORITY_CODE.fullmatch(filing.get("tax_authority_code", ""))
        is None
    ):
        _fail("gate5_filing_party_filing_instance_invalid")
    if (
        not isinstance(taxpayer, dict)
        or set(taxpayer) != _TAXPAYER_KEYS
        or taxpayer.get("taxpayer_ref") != scope["taxpayer_scope_ref"]
        or taxpayer.get("period_status")
        not in {"resident_individual", "nonresident_individual"}
        or taxpayer.get("declarant_category")
        != "other_individual_declaring_article_228_income"
        or _PERSON_NAME.fullmatch(taxpayer.get("last_name", "")) is None
        or _PERSON_NAME.fullmatch(taxpayer.get("first_name", "")) is None
        or (
            taxpayer.get("middle_name") is not None
            and _PERSON_NAME.fullmatch(taxpayer.get("middle_name", "")) is None
        )
        or _INN.fullmatch(taxpayer.get("inn", "")) is None
    ):
        _fail("gate5_filing_party_taxpayer_invalid")
    if not isinstance(signer, dict) or set(signer) != _SIGNER_KEYS:
        _fail("gate5_filing_party_signer_invalid")
    capacity = signer.get("signer_capacity")
    representation = signer.get("representation_authority")
    if (
        not _identifier(signer.get("signer_ref"))
        or capacity not in {"taxpayer_self", "representative"}
        or (capacity == "taxpayer_self" and representation is not None)
        or (
            capacity == "taxpayer_self"
            and signer["signer_ref"] != scope["authenticated_user_ref"]
        )
        or (capacity == "representative" and not _representation(representation))
    ):
        _fail("gate5_filing_party_signer_invalid")
    if (
        not isinstance(evidence, dict)
        or set(evidence) != _EVIDENCE_KEYS
        or evidence.get("schema_version")
        != "broker_reports_gate5_synthetic_case_evidence_v0"
        or evidence.get("status") != "synthetic_proof_evidence"
        or not _identifier(evidence.get("source_ref"))
        or evidence.get("case_id") != scope["case_id"]
        or evidence.get("tax_period") != scope["tax_period"]
        or evidence.get("input_channel") != "filing_and_party_identity"
        or evidence.get("real_user_fact") is not False
    ):
        _fail("gate5_filing_party_evidence_invalid")
    return copy.deepcopy(value)


def _validated_scope(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _SCOPE_KEYS
        or not all(
            _identifier(value.get(key))
            for key in (
                "scope_ref",
                "taxpayer_scope_ref",
                "tax_period",
                "authenticated_user_ref",
                "case_id",
                "normalization_run_ref",
            )
        )
        or not isinstance(value.get("schema_version"), str)
        or _SHA256.fullmatch(value.get("scope_binding_sha256", "")) is None
    ):
        _fail("gate5_filing_party_scope_invalid")
    base = {
        key: copy.deepcopy(value[key]) for key in value if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _canonical_sha256(base):
        _fail("gate5_filing_party_scope_invalid")
    return copy.deepcopy(value)


def _representation(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _REPRESENTATION_KEYS
        and all(_identifier(value.get(key)) for key in _REPRESENTATION_KEYS)
    )


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5FilingAndPartyIdentityError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY",
    "GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_OWNER",
    "GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION",
    "GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID",
    "GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION",
    "GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS",
    "Gate5FilingAndPartyIdentityError",
    "Gate5FilingAndPartyIdentityRuntime",
    "Gate5FilingAndPartyIdentityRuntimeFactory",
]
