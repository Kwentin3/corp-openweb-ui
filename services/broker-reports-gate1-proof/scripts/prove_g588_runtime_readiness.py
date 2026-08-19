"""Prove the exact G5.88 persistence and Gate 4 readiness gaps offline."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate3_financial_annotations_persistence import (  # noqa: E402
    Gate3FinancialAnnotationsPersistence,
    Gate3FinancialAnnotationsPersistenceError,
)
from broker_reports_gate1.gate4_financial_case_materialization import (  # noqa: E402
    _normalize_role_value,
)
from g587_kiss_table_contract import (  # noqa: E402
    INSTRUCTION_ID,
    INSTRUCTION_VERSION,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--provider-profile-id", default="google_gemini")
    args = parser.parse_args()

    root = Path(args.evidence_dir).resolve()
    output_path = root / "runtime-readiness.private.json"
    if output_path.exists():
        raise SystemExit("runtime_readiness_output_already_exists")

    chunks = _read_json(root / "chunks.private.json")
    phases = [
        _read_json(root / "development.private.json"),
        _read_json(root / "holdout.private.json"),
    ]

    compatibility_payloads = []
    literal_findings = []
    bound_roles_total = 0
    exact_text_total = 0
    for phase in phases:
        for outcome in phase["outcomes"]:
            validated = outcome["validated"]
            payload = validated["mapped_financial_annotations_v2"]
            Gate3FinancialAnnotationsPersistence._validate_payload_contract(
                payload=payload,
                provider_profile_id=args.provider_profile_id,
            )
            honest = copy.deepcopy(payload)
            honest["instruction_identity"] = {
                "instruction_id": INSTRUCTION_ID,
                "semantic_version": INSTRUCTION_VERSION,
            }
            try:
                Gate3FinancialAnnotationsPersistence._validate_payload_contract(
                    payload=honest,
                    provider_profile_id=args.provider_profile_id,
                )
            except Gate3FinancialAnnotationsPersistenceError as exc:
                honest_identity_result = exc.code
            else:
                honest_identity_result = "accepted"
            compatibility_payloads.append(
                {
                    "phase": phase["phase"],
                    "ordinal": outcome["ordinal"],
                    "compatibility_projection_accepted": True,
                    "projected_instruction_identity": payload[
                        "instruction_identity"
                    ],
                    "projected_role_instruction_identity": payload[
                        "role_instruction_identity"
                    ],
                    "actual_kiss_instruction_identity": {
                        "instruction_id": INSTRUCTION_ID,
                        "semantic_version": INSTRUCTION_VERSION,
                    },
                    "honest_kiss_identity_result": honest_identity_result,
                }
            )

            chunk = chunks[str(outcome["ordinal"])]
            cell_text = _cell_text_by_target(chunk)
            for annotation in payload["annotations"]:
                for binding in annotation["roles"]:
                    if binding["status"] != "bound":
                        continue
                    bound_roles_total += 1
                    exact_text_total += int("exact_text" in binding)
                    role = binding["role"]
                    if role not in {"asset", "currency"}:
                        continue
                    source_literal = cell_text[_canonical_json(binding["target"])]
                    normalized = _normalize_role_value(role, source_literal)
                    if len(source_literal.split()) > 1:
                        literal_findings.append(
                            {
                                "phase": phase["phase"],
                                "ordinal": outcome["ordinal"],
                                "financial_label": annotation["financial_label"],
                                "role": role,
                                "target": binding["target"],
                                "source_literal": source_literal,
                                "gate4_normalized_value": normalized,
                                "whole_description_cell_used_as_role_value": (
                                    normalized == source_literal.strip()
                                ),
                            }
                        )

    payload = {
        "schema_version": "broker_reports_g588_runtime_readiness_v1",
        "goal": "G5.88",
        "mode": "offline_read_only_contract_proof",
        "provider_calls": 0,
        "store_writes": 0,
        "compatibility": {
            "payloads_checked": len(compatibility_payloads),
            "compatibility_projection_accepted": all(
                item["compatibility_projection_accepted"]
                for item in compatibility_payloads
            ),
            "honest_kiss_identity_accepted": all(
                item["honest_kiss_identity_result"] == "accepted"
                for item in compatibility_payloads
            ),
            "details": compatibility_payloads,
        },
        "role_literal_authority": {
            "bound_roles_total": bound_roles_total,
            "bindings_with_exact_text": exact_text_total,
            "asset_or_currency_whole_description_bindings": len(literal_findings),
            "findings": literal_findings,
        },
        "direct_runtime_materialization_proven": False,
        "exact_contract_gaps": [
            "existing persistence rejects the honest KISS instruction identity",
            "compatibility projection claims the legacy labeling and role-pass identities",
            "cell-only asset/currency bindings can resolve to an entire description cell, which Gate 4 preserves as the role value",
        ],
    }
    _atomic_write(output_path, _json_bytes(payload))
    print(
        json.dumps(
            {
                "status": "NOT_READY",
                "output": str(output_path),
                "payloads_checked": len(compatibility_payloads),
                "honest_kiss_identity_accepted": payload["compatibility"][
                    "honest_kiss_identity_accepted"
                ],
                "asset_or_currency_whole_description_bindings": len(
                    literal_findings
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _cell_text_by_target(chunk: dict[str, Any]) -> dict[str, str]:
    alias_text: dict[str, str] = {}
    for line in chunk["model_view"]["content"].splitlines():
        if not line.startswith("| [t"):
            continue
        for cell in line.strip().strip("|").split("|"):
            value = cell.strip()
            if not value.startswith("[t") or "]" not in value:
                continue
            alias, text = value[1:].split("]", 1)
            alias_text[alias] = text.strip()
    return {
        _canonical_json(item["canonical_target"]): alias_text[item["target_alias"]]
        for item in chunk["target_mappings"]
        if item["canonical_target"].get("kind") == "table_cell"
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"json_object_required:{path.name}")
    return value


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
