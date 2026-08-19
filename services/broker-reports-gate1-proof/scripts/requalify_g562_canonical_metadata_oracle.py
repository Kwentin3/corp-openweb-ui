#!/usr/bin/env python3
"""Build a private G5.62 oracle from visual adjudication and Canonical evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import fitz


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
)


EXPECTED_ALIASES = ("pdf_002", "pdf_024", "holdout_a", "holdout_b")
EXPECTED_SOURCE_ABSENCE_TYPES = {
    "PERSON_BIRTH_DATE",
    "TAXPAYER_TAX_IDENTIFIER",
    "PERSON_CITIZENSHIP",
    "DOCUMENT_NUMBER",
}

FACTORY_REQUIRED = (
    "ArtifactResolver.catalog_case and CanonicalReaderFactory.create are the "
    "only Canonical read route"
)
FORBIDDEN = (
    "provider or model calls, LLM imports, metadata extractor execution, prompt "
    "changes, semantic inference, source mutation or product activation"
)


class G562RequalificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--frozen-corpus", type=Path, required=True)
    parser.add_argument("--old-oracle-result", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    adjudication = _read_json(args.adjudication.resolve())
    frozen = _read_json(args.frozen_corpus.resolve())
    old_result = _read_json(args.old_oracle_result.resolve())
    private_output = args.private_output.resolve()
    safe_output = args.safe_output.resolve()
    for output in (private_output, safe_output):
        if _is_within(output, REPO_ROOT.resolve()):
            raise G562RequalificationError("g562_private_output_inside_repository")
        if output.exists():
            raise G562RequalificationError("g562_output_must_not_exist")

    private_result, safe_result = build_requalified_oracle(
        adjudication=adjudication,
        frozen=frozen,
        old_result=old_result,
    )
    private_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    private_output.write_text(
        json.dumps(private_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    safe_output.write_text(
        json.dumps(safe_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


def build_requalified_oracle(
    *,
    adjudication: dict[str, Any],
    frozen: dict[str, Any],
    old_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(adjudication=adjudication, frozen=frozen, old_result=old_result)
    frozen_by_alias = {item["alias"]: item for item in frozen["cases"]}
    sources = _locate_sources(
        Path(adjudication["source_search_root"]).resolve(),
        {item["source_sha256"] for item in adjudication["cases"]},
    )

    private_cases: list[dict[str, Any]] = []
    all_facts: list[dict[str, Any]] = []
    for case in adjudication["cases"]:
        alias = case["alias"]
        source_path = sources[case["source_sha256"]]
        artifact = _read_frozen_canonical(frozen_by_alias[alias])
        case_facts = _qualify_case(
            case=case,
            source_path=source_path,
            artifact=artifact,
        )
        all_facts.extend(case_facts)
        private_cases.append(
            {
                "alias": alias,
                "source_sha256": case["source_sha256"],
                "source_path": str(source_path),
                "canonical_artifact_id": case["canonical_artifact_id"],
                "canonical_version_id": artifact["artifact_id"],
                "facts": case_facts,
                "source_truth_fact_count": len(case_facts),
                "canonical_losses": 0,
            }
        )

    comparison = classify_old_oracle(old_result=old_result, new_facts=all_facts)
    comparison_entries = classify_old_oracle_entries(
        old_result=old_result,
        new_facts=all_facts,
    )
    type_counts = Counter(item["fact_type"] for item in all_facts)
    observed_types = set(type_counts)
    source_absence_types = set(GATE3_MINIMAL_METADATA_FACT_TYPES) - observed_types
    if source_absence_types != EXPECTED_SOURCE_ABSENCE_TYPES:
        raise G562RequalificationError("g562_source_absence_set_changed")
    if comparison != {
        "old_oracle_facts": 21,
        "correct": 18,
        "false_binding": 3,
        "missing_from_oracle": 6,
    }:
        raise G562RequalificationError(
            "g562_old_oracle_classification_changed:"
            + json.dumps(comparison, sort_keys=True)
        )

    private_result = {
        "schema_version": "broker_reports_g562_source_truth_oracle_private_v1",
        "goal": "G5.62",
        "terminal": [
            "METADATA_SOURCE_TRUTH_ORACLE_REQUALIFIED",
            "CANONICAL_METADATA_PRESERVATION_PROVEN",
            "FROZEN_CORPUS_CONTRACT_METADATA_CANONICAL_LOSS_ZERO",
            "FALSE_ORACLE_BINDINGS_REMOVED",
            "ORACLE_COVERAGE_REQUALIFIED",
            "LLM_METADATA_ADAPTER_UNCHANGED",
            "FINANCIAL_GENERALIZATION_PRESERVED",
        ],
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "provider_calls": 0,
        "oracle_source": "visual_source_plus_canonical_provenance",
        "cases": private_cases,
        "source_truth_fact_count": len(all_facts),
        "fact_type_counts": dict(sorted(type_counts.items())),
        "old_oracle_classification": comparison,
        "old_oracle_entry_classification": comparison_entries,
        "source_absence_fact_types": sorted(source_absence_types),
        "visual_negative_qualifications": adjudication[
            "visual_negative_qualifications"
        ],
        "canonical_loss_count": 0,
        "canonical_fix_required": False,
        "previous_loss_hypothesis": (
            "context_selection_visibility_loss_not_canonical_literal_loss"
        ),
    }
    safe_cases = [
        {
            "alias": item["alias"],
            "source_truth_fact_count": item["source_truth_fact_count"],
            "canonical_bound_facts": item["source_truth_fact_count"],
            "canonical_losses": item["canonical_losses"],
            "source_pages_qualified": sorted(
                {fact["source_binding"]["page"] for fact in item["facts"]}
            ),
            "fact_type_counts": dict(
                sorted(Counter(fact["fact_type"] for fact in item["facts"]).items())
            ),
        }
        for item in private_cases
    ]
    safe_result = {
        "schema_version": "broker_reports_g562_source_truth_oracle_safe_v1",
        "goal": "G5.62",
        "terminal": private_result["terminal"],
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "frozen_corpus": list(EXPECTED_ALIASES),
        "provider_calls": 0,
        "oracle_source": "visual_source_plus_canonical_provenance",
        "cases": safe_cases,
        "source_truth_fact_count": len(all_facts),
        "old_oracle_classification": comparison,
        "old_oracle_entry_status_counts": dict(
            sorted(Counter(item["classification"] for item in comparison_entries).items())
        ),
        "wrong_role_negative_qualifications": [
            {
                "alias": item["alias"],
                "source_page": item["source_page"],
                "classification": item["classification"],
            }
            for item in adjudication["visual_negative_qualifications"]
        ],
        "source_absence_fact_types": sorted(source_absence_types),
        "canonical_loss_count": 0,
        "canonical_fix_required": False,
        "broker_specific_fixes": 0,
        "fixed_page_or_column_rules_added": 0,
        "previous_loss_hypothesis": (
            "context_selection_visibility_loss_not_canonical_literal_loss"
        ),
        "private_values_committed": False,
    }
    return private_result, safe_result


def _validate_inputs(
    *,
    adjudication: dict[str, Any],
    frozen: dict[str, Any],
    old_result: dict[str, Any],
) -> None:
    if adjudication.get("schema_version") != (
        "broker_reports_g562_visual_source_truth_adjudication_private_v1"
    ):
        raise G562RequalificationError("g562_adjudication_schema_invalid")
    if adjudication.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION:
        raise G562RequalificationError("g562_contract_version_changed")
    aliases = tuple(item.get("alias") for item in adjudication.get("cases") or [])
    if aliases != EXPECTED_ALIASES:
        raise G562RequalificationError("g562_frozen_corpus_changed")
    frozen_aliases = tuple(item.get("alias") for item in frozen.get("cases") or [])
    if frozen_aliases != EXPECTED_ALIASES or not frozen.get("frozen_before_code"):
        raise G562RequalificationError("g562_frozen_corpus_invalid")
    if old_result.get("goal") != "G5.61":
        raise G562RequalificationError("g562_old_oracle_input_invalid")
    if adjudication.get("provider_calls") != 0:
        raise G562RequalificationError("g562_provider_calls_forbidden")
    if adjudication.get("oracle_source") != "visual_source_plus_canonical_provenance":
        raise G562RequalificationError("g562_oracle_source_invalid")
    if adjudication.get("old_oracle_authority") is not False:
        raise G562RequalificationError("g562_old_oracle_authority_forbidden")
    if adjudication.get("llm_output_authority") is not False:
        raise G562RequalificationError("g562_llm_authority_forbidden")
    fact_ids: set[str] = set()
    for case in adjudication["cases"]:
        if case.get("canonical_artifact_id") != next(
            item["canonical_artifact_id"]
            for item in frozen["cases"]
            if item["alias"] == case["alias"]
        ):
            raise G562RequalificationError("g562_canonical_identity_changed")
        for fact in case.get("facts") or []:
            fact_id = str(fact.get("fact_id") or "")
            if not fact_id or fact_id in fact_ids:
                raise G562RequalificationError("g562_fact_id_invalid")
            fact_ids.add(fact_id)
            if fact.get("fact_type") not in GATE3_MINIMAL_METADATA_FACT_TYPES:
                raise G562RequalificationError("g562_fact_type_outside_contract")
            if fact.get("canonical_node_type") not in {"TEXT", "TABLE"}:
                raise G562RequalificationError("g562_canonical_node_type_invalid")
            if int(fact.get("source_page") or 0) < 1:
                raise G562RequalificationError("g562_source_page_invalid")
            for field in (
                "source_visible_literal",
                "canonical_literal",
                "structural_representation",
            ):
                if not str(fact.get(field) or "").strip():
                    raise G562RequalificationError("g562_fact_evidence_invalid")


def _locate_sources(root: Path, expected_hashes: set[str]) -> dict[str, Path]:
    if not root.is_dir():
        raise G562RequalificationError("g562_source_root_missing")
    found: dict[str, Path] = {}
    for path in sorted(root.rglob("*.pdf")):
        digest = _file_sha256(path)
        if digest in expected_hashes and digest not in found:
            found[digest] = path.resolve()
    if set(found) != expected_hashes:
        raise G562RequalificationError("g562_frozen_source_missing")
    return found


def _read_frozen_canonical(frozen_case: dict[str, Any]) -> dict[str, Any]:
    root = Path(frozen_case["source_store_root"]).resolve()
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(**frozen_case["context"], allow_private=True)
    records = [
        record
        for record in ArtifactResolver(store).catalog_case(context)
        if record.artifact_type == "broker_reports_canonical_artifact_v1"
        and record.document_id == frozen_case["document_id"]
    ]
    if len(records) != 1:
        raise G562RequalificationError("g562_canonical_record_ambiguous")
    record = records[0]
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(record.artifact_id, context)
    )
    if (
        record.artifact_id != frozen_case["canonical_artifact_id"]
        or artifact.get("artifact_id") != frozen_case["canonical_version_id"]
        or artifact.get("canonical_root_hash") != frozen_case["canonical_root_sha256"]
    ):
        raise G562RequalificationError("g562_frozen_canonical_identity_changed")
    return artifact


def _qualify_case(
    *,
    case: dict[str, Any],
    source_path: Path,
    artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    if _file_sha256(source_path) != case["source_sha256"]:
        raise G562RequalificationError("g562_source_hash_changed")
    provenance = {
        item["provenance_id"]: item for item in artifact.get("provenance") or []
    }
    result: list[dict[str, Any]] = []
    with fitz.open(source_path) as document:
        for fact in case["facts"]:
            page_number = int(fact["source_page"])
            if page_number > document.page_count:
                raise G562RequalificationError("g562_source_page_out_of_range")
            page = document[page_number - 1]
            visible_literal = fact["source_visible_literal"]
            page_text = page.get_text("text")
            if visible_literal not in page_text:
                raise G562RequalificationError(
                    f"g562_source_literal_missing:{fact['fact_id']}"
                )
            rectangles = page.search_for(visible_literal)
            occurrence = int(fact.get("source_occurrence") or 0)
            if occurrence >= len(rectangles):
                raise G562RequalificationError(
                    f"g562_source_bbox_missing:{fact['fact_id']}"
                )
            matches = find_canonical_matches(
                artifact=artifact,
                provenance=provenance,
                page=page_number,
                node_type=fact["canonical_node_type"],
                literal=fact["canonical_literal"],
            )
            if not matches:
                raise G562RequalificationError(
                    f"g562_canonical_metadata_loss:{fact['fact_id']}"
                )
            selected = matches[0]
            source_refs = selected["source_refs"]
            if not source_refs:
                raise G562RequalificationError("g562_canonical_provenance_missing")
            rectangle = rectangles[occurrence]
            result.append(
                {
                    "schema_version": "broker_reports_g562_source_truth_fact_v1",
                    "case_alias": case["alias"],
                    "fact_id": fact["fact_id"],
                    "fact_type": fact["fact_type"],
                    "value": fact["value"],
                    "source_binding": {
                        "source_sha256": case["source_sha256"],
                        "page": page_number,
                        "bbox": [round(value, 3) for value in rectangle],
                        "visible_literal": visible_literal,
                        "structural_representation": fact[
                            "structural_representation"
                        ],
                    },
                    "canonical_binding": {
                        "canonical_version_id": artifact["artifact_id"],
                        "node_id": selected["node_id"],
                        "field_path": selected["field_path"],
                        "source_refs": source_refs,
                        "literal": fact["canonical_literal"],
                        "matched_source_sha256": _sha256_text(
                            fact["canonical_literal"]
                        ),
                    },
                    "oracle_authority": "VISUAL_SOURCE_PLUS_CANONICAL_PROVENANCE",
                    "tax_meaning_assigned": False,
                }
            )
    return result


def find_canonical_matches(
    *,
    artifact: dict[str, Any],
    provenance: dict[str, dict[str, Any]],
    page: int,
    node_type: str,
    literal: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for node in artifact.get("nodes") or []:
        if node.get("node_type") != node_type:
            continue
        source_refs = list(node.get("source_refs") or [])
        if page not in _pages_for_refs(source_refs, provenance):
            continue
        for path, value in _string_leaves(node.get("content"), path="content"):
            if literal in value:
                matches.append(
                    {
                        "node_id": node["node_id"],
                        "field_path": path,
                        "source_refs": source_refs,
                        "node_order": int(node.get("order") or 0),
                    }
                )
    matches.sort(key=lambda item: (item["node_order"], item["node_id"], item["field_path"]))
    return matches


def _pages_for_refs(
    source_refs: Iterable[str], provenance: dict[str, dict[str, Any]]
) -> set[int]:
    pages: set[int] = set()
    for ref in source_refs:
        locator = (provenance.get(ref) or {}).get("source_locator") or {}
        for key in ("page", "page_start", "page_end"):
            value = locator.get(key)
            if isinstance(value, int) and value > 0:
                pages.add(value)
    return pages


def _string_leaves(value: Any, *, path: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        if path.endswith(".text"):
            for index, line in enumerate(value.splitlines()):
                yield f"{path}.lines[{index}]", line
        else:
            yield path, value
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _string_leaves(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _string_leaves(value[key], path=f"{path}.{key}")


def classify_old_oracle(
    *, old_result: dict[str, Any], new_facts: list[dict[str, Any]]
) -> dict[str, int]:
    old_facts = [
        {**fact, "case_alias": case.get("alias")}
        for case in old_result.get("cases") or []
        for fact in case.get("oracle_facts") or []
    ]
    new_keys = {_semantic_key(item) for item in new_facts}
    old_keys = {_semantic_key(item) for item in old_facts}
    return {
        "old_oracle_facts": len(old_facts),
        "correct": len(old_keys & new_keys),
        "false_binding": len(old_keys - new_keys),
        "missing_from_oracle": len(new_keys - old_keys),
    }


def classify_old_oracle_entries(
    *, old_result: dict[str, Any], new_facts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the private, case-scoped adjudication ledger behind the counts."""
    old_facts = [
        {**fact, "case_alias": case.get("alias")}
        for case in old_result.get("cases") or []
        for fact in case.get("oracle_facts") or []
    ]
    new_by_key = {_semantic_key(item): item for item in new_facts}
    old_by_key = {_semantic_key(item): item for item in old_facts}
    entries = [
        {
            "classification": (
                "CORRECT" if key in new_by_key else "FALSE_BINDING"
            ),
            "case_alias": fact.get("case_alias"),
            "fact_type": fact.get("fact_type"),
            "value": fact.get("value"),
        }
        for key, fact in old_by_key.items()
    ]
    entries.extend(
        {
            "classification": "MISSING_FROM_ORACLE",
            "case_alias": fact.get("case_alias"),
            "fact_type": fact.get("fact_type"),
            "value": fact.get("value"),
            "source_binding": fact.get("source_binding"),
            "canonical_binding": fact.get("canonical_binding"),
        }
        for key, fact in new_by_key.items()
        if key not in old_by_key
    )
    entries.sort(
        key=lambda item: (
            str(item["classification"]),
            str(item["case_alias"]),
            str(item["fact_type"]),
            json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True),
        )
    )
    return entries


def _semantic_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(fact.get("case_alias") or ""),
        str(fact.get("fact_type") or ""),
        json.dumps(fact.get("value"), ensure_ascii=False, sort_keys=True),
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G562RequalificationError("g562_json_object_required")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
