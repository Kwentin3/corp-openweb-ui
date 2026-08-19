#!/usr/bin/env python3
"""Rebuild the two frozen Gate 4 cases and prove exact fact equality."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)


EXPECTED = {"holdout_a": 39, "holdout_b": 129}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise SystemExit("g568_financial_output_root_must_be_new")
    output_root.mkdir(parents=True)
    source_before = _tree_hash(source_root)
    cases = []
    for alias, expected_count in EXPECTED.items():
        source_store = source_root / f"{alias}-store"
        working_store = output_root / f"{alias}-store"
        shutil.copytree(source_store, working_store)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=working_store / "artifacts.sqlite3",
                payload_root=working_store / "payloads",
            )
        ).create()
        context = _context_from_store(working_store / "artifacts.sqlite3")
        runtime = Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        ).create()
        before = runtime.read_case(context=context)
        after = runtime.rebuild_case(context=context)
        before_hash = _json_hash(list(before.facts))
        after_hash = _json_hash(list(after.facts))
        passed = (
            len(before.facts) == expected_count
            and len(after.facts) == expected_count
            and before.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
            and after.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
            and before_hash == after_hash
        )
        cases.append(
            {
                "alias": alias,
                "expected_facts": expected_count,
                "before_facts": len(before.facts),
                "after_facts": len(after.facts),
                "before_status": before.status,
                "after_status": after.status,
                "before_sha256": before_hash,
                "after_sha256": after_hash,
                "exact_frozen_equality": before_hash == after_hash,
                "passed": passed,
            }
        )
    source_unchanged = source_before == _tree_hash(source_root)
    passed = source_unchanged and all(case["passed"] for case in cases)
    safe = {
        "schema_version": "broker_reports_g568_financial_regression_safe_v1",
        "goal": "G5.68",
        "terminal": (
            "FINANCIAL_GENERALIZATION_PRESERVED"
            if passed
            else "ARCHITECTURE_REGRESSION"
        ),
        "factory_route": "Gate4FinancialCaseRuntimeFactory.create.rebuild_case",
        "source_stores_unchanged": source_unchanged,
        "cases": cases,
        "passed": passed,
        "private_values_committed": False,
    }
    (output_root / "result.safe.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if passed else 2


def _context_from_store(sqlite_path: Path) -> ArtifactAccessContext:
    with sqlite3.connect(sqlite_path) as connection:
        row = connection.execute(
            """
            SELECT user_id, normalization_run_id, case_id, chat_id,
                   workspace_model_id
            FROM artifact_records
            WHERE case_id IS NOT NULL
            ORDER BY created_at, artifact_id
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise SystemExit("g568_financial_context_missing")
    return ArtifactAccessContext(
        user_id=row[0],
        normalization_run_id=row[1],
        case_id=row[2],
        chat_id=row[3],
        workspace_model_id=row[4],
        allow_private=True,
    )


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
