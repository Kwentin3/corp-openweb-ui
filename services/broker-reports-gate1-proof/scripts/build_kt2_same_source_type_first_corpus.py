from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_table_packages import (  # noqa: E402
    Gate2TablePackageFactory,
)


PRIVATE_ROOT = (
    REPO_ROOT.parent
    / "corp-openweb ui"
    / "local"
    / "goal18-private"
    / "BROKER_REPORTS_GATE2_RECONCILIATION_PRIVATE_EVIDENCE"
)
TRACE_PATH = PRIVATE_ROOT / "trace-a-visual-success.private.json"
WINDOW_PATH = PRIVATE_ROOT / "historical_artifact_window.private.json"
FIXTURE_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_corpus.safe.json"
)
BINDING_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_binding.safe.json"
)

CORPUS_SCHEMA_VERSION = "broker_reports_kt2_same_source_corpus_v1"
BINDING_SCHEMA_VERSION = "broker_reports_kt2_same_source_binding_v1"
SAFE_VALUES = (
    ("Aggregate resources", "USD", "100.00"),
    ("Aggregate obligations", "USD", "150.00"),
    ("Aggregate obligations and owner capital", "USD", "200.00"),
)


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    trace_bytes = TRACE_PATH.read_bytes()
    window_bytes = WINDOW_PATH.read_bytes()
    trace = json.loads(trace_bytes.decode("utf-8"))
    window = json.loads(window_bytes.decode("utf-8"))
    projection = trace["exact_visual_table_boundary"][
        "logical_table_projection"
    ]
    real_full_package = (
        Gate2TablePackageFactory()
        .create()
        .build(projection=projection, case_id=None)
    )
    real_units = _real_units(window)
    if len(real_units) != 3:
        raise ValueError("kt2_real_source_unit_selection_invalid")

    ref_map: dict[str, str] = {}
    safe_full = _sanitize_package(
        real_full_package,
        ref_map=ref_map,
        replacement_values=None,
    )
    safe_units = [
        _sanitize_package(
            package,
            ref_map=ref_map,
            replacement_values=SAFE_VALUES[index],
        )
        for index, package in enumerate(real_units)
    ]
    packages = [safe_full, *safe_units]
    structure = [
        _structure(package, evidence_class=evidence_class)
        for package, evidence_class in zip(
            packages,
            (
                "SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION",
                "SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION",
                "SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION",
                "PRIVACY_SAFE_STRUCTURAL_COPY",
            ),
            strict=True,
        )
    ]
    corpus_material = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "evidence_class": "PRIVACY_SAFE_STRUCTURAL_COPY",
        "primary_input": {
            "factory": "Gate2TablePackageFactory",
            "product_compatible_pipeline": True,
            "real_package_exact_bytes_in_git": False,
            "structural_copy_only": True,
        },
        "packages": packages,
        "full_real_package_structural_copy_index": 0,
        "proof_bounded_source_unit_package_indexes": [1, 2, 3],
        "structure": structure,
        "derived_cases": [
            {
                "case_id": "kt2_unique_typed",
                "evidence_class": "DETERMINISTIC_ADVERSARIAL_DERIVATION",
            },
            {
                "case_id": "kt2_plural_ambiguity",
                "evidence_class": "DETERMINISTIC_ADVERSARIAL_DERIVATION",
            },
            {
                "case_id": "kt2_no_exact_option",
                "evidence_class": "DETERMINISTIC_ADVERSARIAL_DERIVATION",
            },
            {
                "case_id": "kt2_false_singleton_trap",
                "evidence_class": "DETERMINISTIC_ADVERSARIAL_DERIVATION",
            },
        ],
        "privacy": {
            "customer_values": False,
            "raw_source_refs": False,
            "raw_provider_payloads": False,
            "private_paths": False,
            "safe_placeholders_only": True,
            "synthetic_semantic_labels": True,
        },
        "proof_bounded_normalization": {
            "field": "source_unit.document_ref",
            "authority": "package.document_ref",
            "reason": "restore_existing_required_contract_field",
            "canonical_shape_delta": 0,
            "product_route_changed": False,
        },
    }
    corpus = {
        **corpus_material,
        "integrity_hash": _sha256_json(corpus_material),
    }
    public_fixture_hash = _sha256_json(corpus)
    real_full_hash = _sha256_json(real_full_package)
    real_unit_hashes = tuple(_sha256_json(item) for item in real_units)
    binding_material = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "evidence_class": "REAL_SOURCE_TO_PRIVACY_SAFE_STRUCTURAL_COPY",
        "private_sources": {
            "trace_file_sha256": hashlib.sha256(trace_bytes).hexdigest(),
            "historical_window_file_sha256": hashlib.sha256(
                window_bytes
            ).hexdigest(),
            "real_gate2_package_sha256": real_full_hash,
            "real_source_unit_payload_sha256s": list(real_unit_hashes),
            "real_source_units_parent_identity_sha256": hashlib.sha256(
                str(real_units[0]["parent_package_id"]).encode("utf-8")
            ).hexdigest(),
        },
        "public_fixture": {
            "fixture_schema_version": CORPUS_SCHEMA_VERSION,
            "fixture_sha256": public_fixture_hash,
            "packages_total": len(packages),
            "real_gate2_packages_total": 1,
            "real_source_units_total": len(real_units),
            "row_graph_preserved": True,
            "unit_boundaries_preserved": True,
            "field_roles_preserved": True,
            "ref_topology_preserved": True,
            "literal_values_replaced": True,
            "semantic_row_roles_preserved": True,
        },
        "structure_comparison": [
            {
                "private_structure": _structure(
                    package,
                    evidence_class="REAL_SOURCE",
                ),
                "public_structure": _structure(
                    safe_package,
                    evidence_class="PRIVACY_SAFE_STRUCTURAL_COPY",
                ),
                "structure_equal": _topology(package)
                == _topology(safe_package),
            }
            for package, safe_package in zip(
                [real_full_package, *real_units],
                packages,
                strict=True,
            )
        ],
        "privacy": {
            "customer_values_in_receipt": False,
            "raw_source_refs_in_receipt": False,
            "raw_provider_payloads_in_receipt": False,
            "private_paths_in_receipt": False,
        },
    }
    if not all(
        item["structure_equal"]
        for item in binding_material["structure_comparison"]
    ):
        raise ValueError("kt2_safe_fixture_structure_drift")
    binding = {
        **binding_material,
        "integrity_sha256": _sha256_json(binding_material),
    }
    return corpus, binding


def validate_checked_in() -> tuple[dict[str, Any], dict[str, Any]]:
    corpus = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    binding = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    corpus_material = copy.deepcopy(corpus)
    supplied_corpus_hash = corpus_material.pop("integrity_hash", None)
    binding_material = copy.deepcopy(binding)
    supplied_binding_hash = binding_material.pop("integrity_sha256", None)
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA_VERSION
        or supplied_corpus_hash != _sha256_json(corpus_material)
        or binding.get("schema_version") != BINDING_SCHEMA_VERSION
        or supplied_binding_hash != _sha256_json(binding_material)
        or binding["public_fixture"]["fixture_sha256"]
        != _sha256_json(corpus)
        or any(
            not item["structure_equal"]
            for item in binding["structure_comparison"]
        )
    ):
        raise ValueError("kt2_checked_in_corpus_integrity_invalid")
    serialized = json.dumps(
        {"corpus": corpus, "binding": binding},
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        "C:\\",
        "D:\\",
        "provider_response_id",
        "raw_provider_response",
        "openwebui_file_id",
    ):
        if forbidden in serialized:
            raise ValueError("kt2_checked_in_corpus_privacy_invalid")
    return corpus, binding


def _real_units(window: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for record in window.get("artifact_records") or []:
        if record.get("artifact_type") != "broker_reports_derived_source_unit_v0":
            continue
        payload = record.get("payload") or {}
        unit = payload.get("source_unit") or {}
        if (
            unit.get("source_input_mode") == "normalized_table_projection"
            and len(unit.get("source_value_refs") or []) == 3
            and len(unit.get("row_refs") or []) == 1
            and len(unit.get("cell_value_refs") or []) == 3
        ):
            result.append(copy.deepcopy(payload))
    return result


def _sanitize_package(
    package: dict[str, Any],
    *,
    ref_map: dict[str, str],
    replacement_values: tuple[str, ...] | None,
) -> dict[str, Any]:
    original_rows = (
        (package.get("source_unit") or {}).get("model_source_projection") or {}
    ).get("rows") or []
    safe = _sanitize_tree(copy.deepcopy(package), ref_map=ref_map)
    unit = safe.get("source_unit") or {}
    safe["source_unit"] = unit
    unit["document_ref"] = safe["document_ref"]
    rows = (unit.get("model_source_projection") or {}).get("rows") or []
    value_number = 0
    value_by_ref: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=1):
        for column_number, cell in enumerate(row.get("cells") or [], start=1):
            value_number += 1
            if replacement_values is not None:
                value = replacement_values[value_number - 1]
            else:
                value = f"opaque_{row_number:02d}_{column_number:02d}"
            cell["value"] = value
            original_header = str(
                original_rows[row_number - 1]["cells"][column_number - 1].get(
                    "header_label"
                )
                or ""
            )
            cell["header_label"] = (
                "unknown"
                if original_header.strip().casefold() in {"", "unknown"}
                else f"synthetic_column_role_{column_number:02d}"
            )
            refs = cell.get("source_value_refs") or [
                cell.get("source_value_ref")
            ]
            for ref in refs:
                if ref:
                    value_by_ref[str(ref)] = value
    normalized = unit.get("normalized_source_projection") or {}
    if rows:
        normalized["cells"] = [
            [cell["value"] for cell in row.get("cells") or []]
            for row in rows
        ]
        unit["normalized_source_projection"] = normalized
    for private_value in unit.get("private_values") or []:
        refs = private_value.get("source_value_refs") or []
        if refs and str(refs[0]) in value_by_ref:
            private_value["normalized_value"] = value_by_ref[str(refs[0])]
            private_value.pop("raw_value", None)
    unit["safe_section_labels"] = []
    return safe


def _sanitize_tree(value: Any, *, ref_map: dict[str, str], key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            item_key: _sanitize_tree(
                item_value,
                ref_map=ref_map,
                key=item_key,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_tree(item, ref_map=ref_map, key=key) for item in value
        ]
    if isinstance(value, str) and _identity_key(key):
        if value not in ref_map:
            ref_map[value] = "safe_" + hashlib.sha256(
                value.encode("utf-8")
            ).hexdigest()[:24]
        return ref_map[value]
    if isinstance(value, str) and _sensitive_text_key(key):
        return "safe_text_" + hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()[:16]
    return value


def _identity_key(key: str) -> bool:
    return (
        key.endswith("_ref")
        or key.endswith("_refs")
        or key.endswith("_id")
        or key in {"case_id", "chat_id", "user_id"}
        or "checksum" in key
    )


def _sensitive_text_key(key: str) -> bool:
    return key in {
        "description",
        "filename",
        "header_label",
        "label",
        "normalized_label",
        "normalized_value",
        "raw_value",
        "section_label",
        "text",
        "title",
        "value",
    }


def _structure(
    package: dict[str, Any],
    *,
    evidence_class: str,
) -> dict[str, Any]:
    return {
        "evidence_class": evidence_class,
        **_topology(package),
        "package_sha256": _sha256_json(package),
    }


def _topology(package: dict[str, Any]) -> dict[str, Any]:
    unit = package.get("source_unit") or {}
    rows = (unit.get("model_source_projection") or {}).get("rows") or []
    return {
        "schema_version": package.get("schema_version"),
        "unit_kind": unit.get("unit_kind"),
        "source_input_mode": unit.get("source_input_mode"),
        "rows_total": len(rows),
        "cells_by_row": [len(row.get("cells") or []) for row in rows],
        "row_refs_total": len(unit.get("row_refs") or []),
        "cell_refs_total": len(unit.get("cell_refs") or []),
        "source_value_refs_total": len(unit.get("source_value_refs") or []),
        "source_value_index_total": len(unit.get("source_value_index") or []),
        "allowed_source_value_refs_total": len(
            package.get("allowed_source_value_refs") or []
        ),
        "selected_source_refs_total": len(
            (package.get("coverage_expectation") or {}).get(
                "selected_source_refs"
            )
            or []
        ),
    }


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        corpus, binding = validate_checked_in()
        if TRACE_PATH.exists() and WINDOW_PATH.exists():
            rebuilt = build()
            if rebuilt != (corpus, binding):
                raise SystemExit("kt2_same_source_corpus_drift")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "mode": "check",
                    "real_gate2_packages_total": 1,
                    "real_source_units_total": 3,
                    "customer_values_in_git_total": 0,
                },
                sort_keys=True,
            )
        )
        return
    corpus, binding = build()
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_bytes(_json_bytes(corpus))
    BINDING_PATH.write_bytes(_json_bytes(binding))
    print(
        json.dumps(
            {
                "status": "written",
                "fixture": FIXTURE_PATH.relative_to(REPO_ROOT).as_posix(),
                "binding": BINDING_PATH.relative_to(REPO_ROOT).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
