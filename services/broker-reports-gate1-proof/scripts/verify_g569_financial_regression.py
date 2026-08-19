#!/usr/bin/env python3
"""G5.69 reuse of the frozen Gate 4 39/129 exact-equality check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)
from verify_g568_financial_regression import (  # noqa: E402
    EXPECTED,
    _context_from_store,
    _json_hash,
    _tree_hash,
)


FACTORY_REQUIRED = "Gate4FinancialCaseRuntimeFactory.create().rebuild_case"
FORBIDDEN = "metadata reads, provider calls, tax changes or source-store mutation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise SystemExit("g569_financial_output_root_must_be_new")
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
        "schema_version": "broker_reports_g569_financial_regression_safe_v1",
        "goal": "G5.69",
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


if __name__ == "__main__":
    raise SystemExit(main())
