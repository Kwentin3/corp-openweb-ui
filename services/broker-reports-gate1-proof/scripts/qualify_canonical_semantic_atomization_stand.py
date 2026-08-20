#!/usr/bin/env python3
"""Research-only qualification of semantic atom boundaries over one Canonical."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
)
from qualify_gate3_minimal_classifier_stand import (  # noqa: E402
    EXPECTED_CURRENT_TARGETS,
    FROZEN_CANONICAL_ROOT_SHA256,
    _atomic_write,
    _frozen_context,
    _is_within,
    _json_bytes,
    _live_client,
    _plain,
    _stable_sha256,
    _visible_text_index,
)


RUNS = 3
VARIANTS = ("refs_only", "ref_spans")
RESPONSE_SCHEMA_VERSION = "broker_reports_semantic_atomization_response_v1"
INSTRUCTION_ID = "broker-reports-canonical-semantic-atomization"
INSTRUCTION_VERSION = "0.1.0-research-only"
INSTRUCTION = (
    "Выполни только смысловую атомизацию данных в заранее объявленных source "
    "blocks. Атом — минимальное самостоятельное утверждение источника, которое "
    "можно отделить от соседнего без потери собственного смысла. Не назначай "
    "финансовые типы или роли, не классифицируй, не считай и не делай налоговых "
    "выводов. Заголовки и физическая структура сами по себе не атомы. Один block "
    "может дать ноль, один или несколько атомов. Не объединяй независимые "
    "утверждения и не режь одно утверждение на значения без собственного смысла. "
    "Используй только source refs и literals из входа. audit_description нужен "
    "только человеку и не является machine authority. assertion_id назначай "
    "последовательно a001, a002 и далее без пропусков. Верни только JSON по schema."
)


class SemanticAtomizationStandError(RuntimeError):
    pass


def response_schema(
    *, variant: str, block_ids: list[str], allowed_refs: list[str]
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise SemanticAtomizationStandError("atomization_variant_invalid")
    if not block_ids or block_ids != list(dict.fromkeys(block_ids)):
        raise SemanticAtomizationStandError("atomization_block_ids_invalid")
    if not allowed_refs or allowed_refs != list(dict.fromkeys(allowed_refs)):
        raise SemanticAtomizationStandError("atomization_source_refs_invalid")
    classification_properties: dict[str, Any] = {
        "assertion_id": {
            "type": "string",
            "pattern": "^a[0-9]{3}$",
            "description": "Sequential atom id: a001, a002, ...",
        },
        "block_id": {"type": "string", "enum": block_ids},
        "context_refs": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string", "enum": allowed_refs},
        },
        "audit_description": {"type": "string", "minLength": 1, "maxLength": 240},
    }
    if variant == "refs_only":
        classification_properties["claim_refs"] = {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "enum": allowed_refs},
        }
        required = [
            "assertion_id",
            "block_id",
            "claim_refs",
            "context_refs",
            "audit_description",
        ]
    else:
        classification_properties["claim_slices"] = {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_ref", "literal_fragment"],
                "properties": {
                    "source_ref": {"type": "string", "enum": allowed_refs},
                    "literal_fragment": {"type": "string", "minLength": 1},
                },
            },
        }
        required = [
            "assertion_id",
            "block_id",
            "claim_slices",
            "context_refs",
            "audit_description",
        ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "atoms"],
        "properties": {
            "schema_version": {"const": RESPONSE_SCHEMA_VERSION},
            "atoms": {
                "type": "array",
                "minItems": 0,
                "maxItems": 24,
                "items": {"$ref": "#/$defs/classification"},
            },
        },
        "$defs": {
            "classification": {
                "type": "object",
                "additionalProperties": False,
                "required": required,
                "properties": classification_properties,
            }
        },
    }


def model_request(
    *, variant: str, batch: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    if variant == "refs_only":
        rule = (
            "Machine boundary — exact claim_refs plus context_refs. claim_refs "
            "are the smallest complete source elements carrying this assertion. "
            "context_refs only qualify it and may be shared. If one element "
            "contains two assertions, two atoms may cite that same element; do "
            "not invent a smaller address."
        )
    elif variant == "ref_spans":
        rule = (
            "Machine boundary — exact claim_slices plus context_refs. Each "
            "literal_fragment must be copied verbatim as one non-empty substring "
            "of the literal at source_ref. Use the whole literal unless the same "
            "source element contains more than one independent assertion. "
            "context_refs only qualify the assertion and may be shared."
        )
    else:
        raise SemanticAtomizationStandError("atomization_variant_invalid")
    return {
        "messages": [
            {"role": "system", "content": INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "variant": variant,
                        "machine_boundary_rule": rule,
                        "forbidden": [
                            "financial types",
                            "financial roles",
                            "tax reasoning",
                            "calculations",
                            "new source refs",
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"batch": batch},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": RESPONSE_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(schema),
            },
        },
    }


def validate_response(
    raw: Any,
    *,
    variant: str,
    batch: dict[str, Any],
) -> dict[str, Any]:
    value = _decode_json(raw)
    if (
        set(value) != {"schema_version", "atoms"}
        or value.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("atoms"), list)
    ):
        raise SemanticAtomizationStandError("atomization_response_contract_invalid")
    block_by_id = {item["block_id"]: item for item in batch["blocks"]}
    expected_ids = [f"a{ordinal:03d}" for ordinal in range(1, len(value["atoms"]) + 1)]
    actual_ids: list[str] = []
    restored: list[dict[str, Any]] = []
    for item in value["atoms"]:
        required = {
            "assertion_id",
            "block_id",
            "context_refs",
            "audit_description",
            "claim_refs" if variant == "refs_only" else "claim_slices",
        }
        if not isinstance(item, dict) or set(item) != required:
            raise SemanticAtomizationStandError("atomization_response_contract_invalid")
        atom_id = item.get("assertion_id")
        block_id = item.get("block_id")
        description = item.get("audit_description")
        context_refs = item.get("context_refs")
        if (
            not isinstance(atom_id, str)
            or block_id not in block_by_id
            or not isinstance(description, str)
            or not description.strip()
            or not isinstance(context_refs, list)
            or any(not isinstance(ref, str) for ref in context_refs)
            or len(context_refs) != len(set(context_refs))
        ):
            raise SemanticAtomizationStandError("atomization_response_contract_invalid")
        block = block_by_id[block_id]
        element_text = {
            entry["source_ref"]: entry["literal"] for entry in block["elements"]
        }
        allowed_context = set(element_text) | {
            entry["source_ref"] for entry in block["header_context"]
        }
        if not set(context_refs) <= allowed_context:
            raise SemanticAtomizationStandError("atomization_context_ref_invalid")
        restored_atom: dict[str, Any] = {
            "atom_id": atom_id,
            "block_id": block_id,
            "context_refs": sorted(context_refs),
            "audit_description": description.strip(),
        }
        if variant == "refs_only":
            claim_refs = item.get("claim_refs")
            if (
                not isinstance(claim_refs, list)
                or not claim_refs
                or any(not isinstance(ref, str) for ref in claim_refs)
                or len(claim_refs) != len(set(claim_refs))
                or not set(claim_refs) <= set(element_text)
                or set(claim_refs) & set(context_refs)
            ):
                raise SemanticAtomizationStandError("atomization_claim_ref_invalid")
            restored_atom["claim_refs"] = sorted(claim_refs)
        else:
            slices = item.get("claim_slices")
            restored_slices: list[dict[str, str]] = []
            if not isinstance(slices, list) or not slices:
                raise SemanticAtomizationStandError("atomization_claim_slice_invalid")
            for source_slice in slices:
                if (
                    not isinstance(source_slice, dict)
                    or set(source_slice) != {"source_ref", "literal_fragment"}
                    or source_slice.get("source_ref") not in element_text
                    or not isinstance(source_slice.get("literal_fragment"), str)
                    or not source_slice["literal_fragment"]
                    or element_text[source_slice["source_ref"]].count(
                        source_slice["literal_fragment"]
                    )
                    != 1
                ):
                    raise SemanticAtomizationStandError(
                        "atomization_claim_slice_invalid"
                    )
                restored_slices.append(
                    {
                        "source_ref": source_slice["source_ref"],
                        "literal_fragment": source_slice["literal_fragment"],
                    }
                )
            slice_keys = [
                (entry["source_ref"], entry["literal_fragment"])
                for entry in restored_slices
            ]
            if len(slice_keys) != len(set(slice_keys)) or {
                ref for ref, _fragment in slice_keys
            } & set(context_refs):
                raise SemanticAtomizationStandError("atomization_claim_slice_invalid")
            restored_atom["claim_slices"] = sorted(
                restored_slices,
                key=lambda entry: (entry["source_ref"], entry["literal_fragment"]),
            )
        actual_ids.append(atom_id)
        restored.append(restored_atom)
    if actual_ids != expected_ids:
        raise SemanticAtomizationStandError("atomization_atom_id_sequence_invalid")
    boundaries = [_machine_boundary(item, variant=variant) for item in restored]
    if len(boundaries) != len({_stable_sha256(item) for item in boundaries}):
        raise SemanticAtomizationStandError("atomization_duplicate_boundary")
    return {
        "schema_version": "broker_reports_semantic_atomization_v1",
        "instruction_identity": {
            "instruction_id": INSTRUCTION_ID,
            "semantic_version": INSTRUCTION_VERSION,
        },
        "variant": variant,
        "atoms": restored,
        "validation_status": "validated",
    }


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise SemanticAtomizationStandError("atomization_response_contract_invalid")
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SemanticAtomizationStandError(
            "atomization_response_contract_invalid"
        ) from exc
    if not isinstance(result, dict):
        raise SemanticAtomizationStandError("atomization_response_contract_invalid")
    return result


def _machine_boundary(atom: dict[str, Any], *, variant: str) -> dict[str, Any]:
    boundary = {
        "block_id": atom["block_id"],
        "context_refs": sorted(atom["context_refs"]),
    }
    if variant == "refs_only":
        boundary["claim_refs"] = sorted(atom["claim_refs"])
    else:
        boundary["claim_slices"] = sorted(
            atom["claim_slices"],
            key=lambda item: (item["source_ref"], item["literal_fragment"]),
        )
    return boundary


def _canonical_boundaries(
    atoms: list[dict[str, Any]], *, variant: str
) -> list[dict[str, Any]]:
    return sorted(
        [_machine_boundary(item, variant=variant) for item in atoms],
        key=_stable_sha256,
    )


def _expected_atoms(
    source_truth: dict[str, Any], *, variant: str
) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for block in source_truth["blocks"]:
        for expected in block["expected_atoms"]:
            atom: dict[str, Any] = {
                "block_id": block["block_id"],
                "context_refs": sorted(expected["context_refs"]),
            }
            if variant == "refs_only":
                atom["claim_refs"] = sorted(
                    {item["source_ref"] for item in expected["claim_slices"]}
                )
            else:
                atom["claim_slices"] = copy.deepcopy(expected["claim_slices"])
            atoms.append(atom)
    return _canonical_boundaries(atoms, variant=variant)


def _build_batch(
    *, chunk: dict[str, Any], source_truth: dict[str, Any]
) -> dict[str, Any]:
    mapping_by_alias = {
        item["target_alias"]: item["canonical_target"]
        for item in chunk["target_mappings"]
    }
    text_by_alias, _row_lines = _visible_text_index(
        content=chunk["model_view"]["content"],
        mapping_by_alias=mapping_by_alias,
    )
    blocks: list[dict[str, Any]] = []
    for block in source_truth["blocks"]:
        elements = _source_elements(
            refs=block["element_refs"],
            text_by_alias=text_by_alias,
            mapping_by_alias=mapping_by_alias,
        )
        header = _source_elements(
            refs=block["header_refs"],
            text_by_alias=text_by_alias,
            mapping_by_alias=mapping_by_alias,
        )
        blocks.append(
            {
                "block_id": block["block_id"],
                "block_kind": block["block_kind"],
                "elements": elements,
                "header_context": header,
            }
        )
    return {
        "schema_version": "broker_reports_semantic_atomization_batch_v1",
        "blocks": blocks,
    }


def _source_elements(
    *,
    refs: list[str],
    text_by_alias: dict[str, str],
    mapping_by_alias: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    result = []
    for source_ref in refs:
        target = mapping_by_alias.get(source_ref)
        literal = text_by_alias.get(source_ref)
        if (
            not isinstance(target, dict)
            or target.get("kind") != "table_cell"
            or literal is None
        ):
            raise SemanticAtomizationStandError("atomization_source_ref_unavailable")
        result.append({"source_ref": source_ref, "literal": literal})
    return result


def _validated_source_truth(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != "broker_reports_semantic_atomization_source_truth_v1"
        or value.get("frozen_canonical_root_sha256") != FROZEN_CANONICAL_ROOT_SHA256
        or value.get("qualified_before_model_execution") is not True
        or value.get("model_output_used_as_truth_hint") is not False
        or not isinstance(value.get("blocks"), list)
        or not value["blocks"]
    ):
        raise SemanticAtomizationStandError("atomization_source_truth_invalid")
    block_ids: list[str] = []
    all_refs: set[str] = set()
    for block in value["blocks"]:
        if (
            not isinstance(block, dict)
            or set(block)
            != {
                "block_id",
                "block_kind",
                "element_refs",
                "header_refs",
                "expected_atoms",
            }
            or not re.fullmatch(r"b[0-9]{3}", str(block.get("block_id") or ""))
            or block.get("block_kind") not in {"header_control", "table_row"}
            or not isinstance(block.get("element_refs"), list)
            or not block["element_refs"]
            or not isinstance(block.get("header_refs"), list)
            or not isinstance(block.get("expected_atoms"), list)
        ):
            raise SemanticAtomizationStandError("atomization_source_truth_invalid")
        block_ids.append(block["block_id"])
        element_refs = block["element_refs"]
        header_refs = block["header_refs"]
        if (
            len(element_refs) != len(set(element_refs))
            or len(header_refs) != len(set(header_refs))
            or set(element_refs) & set(header_refs)
            or any(
                not re.fullmatch(r"t[0-9]+", ref)
                for ref in [*element_refs, *header_refs]
            )
        ):
            raise SemanticAtomizationStandError("atomization_source_truth_ref_invalid")
        all_refs.update(element_refs)
        all_refs.update(header_refs)
        for atom in block["expected_atoms"]:
            if (
                not isinstance(atom, dict)
                or set(atom) != {"audit_description", "claim_slices", "context_refs"}
                or not isinstance(atom.get("audit_description"), str)
                or not atom["audit_description"].strip()
                or not isinstance(atom.get("claim_slices"), list)
                or not atom["claim_slices"]
                or not isinstance(atom.get("context_refs"), list)
                or not set(atom["context_refs"]) <= set(element_refs) | set(header_refs)
            ):
                raise SemanticAtomizationStandError(
                    "atomization_source_truth_atom_invalid"
                )
            for source_slice in atom["claim_slices"]:
                if (
                    not isinstance(source_slice, dict)
                    or set(source_slice) != {"source_ref", "literal_fragment"}
                    or source_slice.get("source_ref") not in element_refs
                    or not isinstance(source_slice.get("literal_fragment"), str)
                    or not source_slice["literal_fragment"]
                ):
                    raise SemanticAtomizationStandError(
                        "atomization_source_truth_atom_invalid"
                    )
    if len(block_ids) != len(set(block_ids)):
        raise SemanticAtomizationStandError("atomization_source_truth_block_duplicate")
    return copy.deepcopy(value)


def _assert_truth_matches_batch(
    *, source_truth: dict[str, Any], batch: dict[str, Any]
) -> None:
    literal_by_ref = {
        element["source_ref"]: element["literal"]
        for block in batch["blocks"]
        for element in block["elements"]
    }
    for block in source_truth["blocks"]:
        for atom in block["expected_atoms"]:
            for source_slice in atom["claim_slices"]:
                literal = literal_by_ref[source_slice["source_ref"]]
                if literal.count(source_slice["literal_fragment"]) != 1:
                    raise SemanticAtomizationStandError(
                        "atomization_source_truth_fragment_not_exact"
                    )


def _score_run(
    *,
    ordinal: int,
    variant: str,
    validated: dict[str, Any],
    expected: list[dict[str, Any]],
    execution_metadata: Any,
    provider_submissions: int,
) -> dict[str, Any]:
    actual = _canonical_boundaries(validated["atoms"], variant=variant)
    expected_counter = Counter(_stable_sha256(item) for item in expected)
    actual_counter = Counter(_stable_sha256(item) for item in actual)
    exact_matches = sum((expected_counter & actual_counter).values())
    claim_key = "claim_refs" if variant == "refs_only" else "claim_slices"
    expected_claims = Counter(
        _stable_sha256({"block_id": item["block_id"], claim_key: item[claim_key]})
        for item in expected
    )
    actual_claims = Counter(
        _stable_sha256({"block_id": item["block_id"], claim_key: item[claim_key]})
        for item in actual
    )
    claim_matches = sum((expected_claims & actual_claims).values())
    expected_members = _claim_member_counter(expected, variant=variant)
    actual_members = _claim_member_counter(actual, variant=variant)
    metadata = _plain(execution_metadata)
    return {
        "ordinal": ordinal,
        "terminal_status": "validated",
        "atoms": len(actual),
        "boundary_sha256": _stable_sha256(actual),
        "exact_atoms_correct": exact_matches,
        "claim_boundaries_correct": claim_matches,
        "expected_atoms": len(expected),
        "missing_atoms": sum((expected_counter - actual_counter).values()),
        "extra_atoms": sum((actual_counter - expected_counter).values()),
        "claim_members_missing": sum((expected_members - actual_members).values()),
        "claim_members_extra": sum((actual_members - expected_members).values()),
        "repeated_claim_members": sum(
            max(0, count - 1) for count in actual_members.values()
        ),
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "duration_ms": metadata.get("duration_ms"),
        "provider_submissions": provider_submissions,
    }


def _claim_member_counter(
    boundaries: list[dict[str, Any]], *, variant: str
) -> Counter[str]:
    result: Counter[str] = Counter()
    for atom in boundaries:
        if variant == "refs_only":
            members = atom["claim_refs"]
        else:
            members = atom["claim_slices"]
        for member in members:
            result[
                _stable_sha256({"block_id": atom["block_id"], "member": member})
            ] += 1
    return result


def _safe_rejected_run(
    *, ordinal: int, provider_submissions: int, error: Exception
) -> dict[str, Any]:
    return {
        "ordinal": ordinal,
        "terminal_status": "rejected",
        "error_type": type(error).__name__,
        "atoms": None,
        "boundary_sha256": None,
        "provider_submissions": provider_submissions,
    }


def _variant_summary(
    *, variant: str, runs: list[dict[str, Any]], expected_atoms: int
) -> dict[str, Any]:
    validated = [item for item in runs if item["terminal_status"] == "validated"]
    hashes = [item["boundary_sha256"] for item in validated]
    repeatable = len(validated) == RUNS and len(set(hashes)) == 1
    faithful = len(validated) == RUNS and all(
        item["exact_atoms_correct"] == expected_atoms
        and item["missing_atoms"] == 0
        and item["extra_atoms"] == 0
        for item in validated
    )
    complete = len(validated) == RUNS and all(
        item["claim_members_missing"] == 0 and item["claim_members_extra"] == 0
        for item in validated
    )
    return {
        "variant": variant,
        "runs": runs,
        "validated_runs": len(validated),
        "unique_boundary_hashes": len(set(hashes)),
        "exact_boundary_repeatability": repeatable,
        "source_fidelity_exact": faithful,
        "source_claim_coverage_complete": complete,
    }


def verdict(*, variants: dict[str, dict[str, Any]]) -> str:
    spans = variants["ref_spans"]
    refs = variants["refs_only"]
    if (
        spans["exact_boundary_repeatability"]
        and spans["source_fidelity_exact"]
        and spans["source_claim_coverage_complete"]
    ):
        return "ATOMIZATION_PROMISING_BUT_CONTEXT_BOUND"
    if (
        not spans["exact_boundary_repeatability"]
        and not refs["exact_boundary_repeatability"]
    ):
        return "ATOM_BOUNDARIES_NOT_REPEATABLE"
    return "SEMANTIC_ATOMIZATION_DOES_NOT_ADD_USEFUL_BOUNDARY"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-frozen-runs", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--private-store-root", type=Path, required=True)
    parser.add_argument("--private-source-truth", type=Path, required=True)
    parser.add_argument("--private-results-dir", type=Path, required=True)
    parser.add_argument("--safe-receipt-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.execute_frozen_runs:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")
    store_root = args.private_store_root.resolve()
    truth_path = args.private_source_truth.resolve()
    results_dir = args.private_results_dir.resolve()
    safe_receipt = args.safe_receipt_path.resolve()
    for private_path in (store_root, truth_path, results_dir):
        if _is_within(private_path, REPO_ROOT.resolve()):
            raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_receipt, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if results_dir.exists() and any(results_dir.iterdir()):
        raise SystemExit("private_results_must_be_new_or_empty")
    results_dir.mkdir(parents=True, exist_ok=True)

    truth_raw = truth_path.read_bytes()
    source_truth = _validated_source_truth(json.loads(truth_raw))
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_id, context = _frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    if (
        len(chunk_set["chunks"]) != 1
        or chunk_set["coverage"]["eligible_targets"] != EXPECTED_CURRENT_TARGETS
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")
    batch = _build_batch(chunk=chunk_set["chunks"][0], source_truth=source_truth)
    _assert_truth_matches_batch(source_truth=source_truth, batch=batch)
    block_ids = [item["block_id"] for item in batch["blocks"]]
    allowed_refs = sorted(
        {
            element["source_ref"]
            for block in batch["blocks"]
            for element in [*block["elements"], *block["header_context"]]
        }
    )
    contracts: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        schema = response_schema(
            variant=variant,
            block_ids=block_ids,
            allowed_refs=allowed_refs,
        )
        request = model_request(variant=variant, batch=batch, schema=schema)
        contracts[variant] = {
            "schema": schema,
            "request": request,
            "request_sha256": _stable_sha256(request),
            "expected": _expected_atoms(source_truth, variant=variant),
        }
    plan = {
        "schema_version": "broker_reports_semantic_atomization_plan_v1",
        "goal": "Canonical Semantic Atomization Stand",
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(truth_raw).hexdigest(),
        "source_truth_qualified_before_model_execution": True,
        "batch": batch,
        "contracts": contracts,
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "model_id": NDFL_PROVIDER_MODEL_ID,
        "runs_per_variant": RUNS,
        "semantic_retry": False,
        "repair": False,
        "best_of_n": False,
        "classification": False,
        "production_activation": False,
    }
    _atomic_write(results_dir / "frozen-plan.private.json", _json_bytes(plan))

    client, submissions = _live_client(
        env_file=args.env_file,
        timeout_seconds=args.timeout_seconds,
    )
    variant_receipts: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        contract = contracts[variant]
        runs: list[dict[str, Any]] = []
        for ordinal in range(1, RUNS + 1):
            before = submissions["count"]
            private: dict[str, Any] = {"ordinal": ordinal, "variant": variant}
            try:
                model_result = asyncio.run(
                    client.label_gate3_once(
                        model_visible_request=contract["request"],
                        canonical_schema=contract["schema"],
                        model_id=NDFL_PROVIDER_MODEL_ID,
                    )
                )
                private.update(
                    {
                        "raw_model_output": copy.deepcopy(
                            model_result.adapter_extracted_output
                        ),
                        "raw_provider_response": copy.deepcopy(
                            model_result.raw_provider_response
                        ),
                        "execution_metadata": _plain(model_result.execution_metadata),
                    }
                )
                if _stable_sha256(contract["request"]) != contract["request_sha256"]:
                    raise SemanticAtomizationStandError("frozen_request_mutated")
                validated = validate_response(
                    model_result.adapter_extracted_output,
                    variant=variant,
                    batch=batch,
                )
                private.update(
                    {
                        "validated_output": validated,
                    }
                )
                runs.append(
                    _score_run(
                        ordinal=ordinal,
                        variant=variant,
                        validated=validated,
                        expected=contract["expected"],
                        execution_metadata=model_result.execution_metadata,
                        provider_submissions=submissions["count"] - before,
                    )
                )
            except Exception as exc:  # one frozen attempt; never repair or retry
                private.update(
                    {
                        "terminal_error_type": type(exc).__name__,
                        "terminal_error": str(exc),
                    }
                )
                runs.append(
                    _safe_rejected_run(
                        ordinal=ordinal,
                        provider_submissions=submissions["count"] - before,
                        error=exc,
                    )
                )
            _atomic_write(
                results_dir / f"{variant}-run-{ordinal}.private.json",
                _json_bytes(private),
            )
        variant_receipts[variant] = _variant_summary(
            variant=variant,
            runs=runs,
            expected_atoms=len(contract["expected"]),
        )
    final_terminal = verdict(variants=variant_receipts)
    receipt = {
        "schema_version": "broker_reports_semantic_atomization_receipt_v1",
        "status": final_terminal,
        "research_only": True,
        "production_changed": False,
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(truth_raw).hexdigest(),
        "source_truth_blocks": len(batch["blocks"]),
        "source_truth_atoms": len(contracts["ref_spans"]["expected"]),
        "input_source_elements": sum(
            len(block["elements"]) for block in batch["blocks"]
        ),
        "header_context_elements": sum(
            len(block["header_context"]) for block in batch["blocks"]
        ),
        "variants": variant_receipts,
        "request_sha256": {
            variant: contracts[variant]["request_sha256"] for variant in VARIANTS
        },
        "response_schema_sha256": {
            variant: _stable_sha256(contracts[variant]["schema"])
            for variant in VARIANTS
        },
        "provider_submissions": submissions["count"],
        "retry_count": 0,
        "repair_count": 0,
        "best_of_n": False,
        "manual_result_changes": 0,
        "classification_passes": 0,
        "role_passes": 0,
        "gate4_or_gate5_passes": 0,
        "whole_document_attempted": False,
        "context_scope": "six_prequalified_local_blocks_from_same_frozen_canonical",
        "audit_description_is_machine_authority": False,
    }
    _atomic_write(safe_receipt, _json_bytes(receipt))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
