#!/usr/bin/env python3
"""Check the G5.80 admission seam against frozen 39/129 holdout sidecars."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import ArtifactStoreConfig, ArtifactStoreFactory  # noqa: E402
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.gate4_financial_case_materialization import (  # noqa: E402
    gate4_annotation_materialization_decision,
)
from verify_g568_financial_regression import (  # noqa: E402
    _context_from_store,
    _tree_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--frozen-safe", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise SystemExit("g580_financial_output_root_must_be_new")
    frozen = json.loads(args.frozen_safe.read_text(encoding="utf-8"))
    expected = {
        item["alias"]: {
            "facts": int(item["after_facts"]),
            "sha256": item["after_sha256"],
        }
        for item in frozen["cases"]
    }
    output_root.mkdir(parents=True)
    source_before = _tree_hash(source_root)
    cases = []
    for alias, baseline in expected.items():
        source_store = source_root / f"{alias}-store"
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=source_store / "artifacts.sqlite3",
                payload_root=source_store / "payloads",
            )
        ).create()
        context = _context_from_store(source_store / "artifacts.sqlite3")
        sidecars = [
            item
            for item in ArtifactResolver(store).catalog_case(context)
            if item.artifact_type == "broker_reports_financial_annotations_v2"
        ]
        if len(sidecars) != 1:
            raise SystemExit(f"{alias}:frozen_sidecar_count_invalid")
        # These qualification-only fixtures have expired lifecycle TTLs. Read the
        # retained immutable payload directly to test only the newly changed pure
        # admission seam; do not claim a current full-runtime replay.
        record = store.get_record_unchecked(sidecars[0].artifact_id)
        if record is None:
            raise SystemExit(f"{alias}:frozen_sidecar_missing")
        annotations = store.read_payload(record)["annotations"]
        decisions = [
            gate4_annotation_materialization_decision(item) for item in annotations
        ]
        admitted = sum(item["materializable"] for item in decisions)
        blocked = len(decisions) - admitted
        passed = (
            len(annotations) == baseline["facts"]
            and admitted == baseline["facts"]
            and blocked == 0
        )
        cases.append(
            {
                "alias": alias,
                "frozen_facts": baseline["facts"],
                "frozen_annotations": len(annotations),
                "admitted_annotations": admitted,
                "blocked_annotations": blocked,
                "frozen_sha256": baseline["sha256"],
                "full_rebuild": "not_run_expired_frozen_artifacts",
                "changed_seam_admission_compatibility": admitted == baseline["facts"],
                "passed": passed,
            }
        )
    source_unchanged = source_before == _tree_hash(source_root)
    passed = source_unchanged and all(item["passed"] for item in cases)
    safe = {
        "schema_version": "broker_reports_g580_financial_regression_safe_v1",
        "goal": "G5.80",
        "qualification_route": "gate4_annotation_materialization_decision",
        "qualification_limit": (
            "frozen sidecars expired; verifies the only changed admission seam, "
            "not a fresh full Gate4 rebuild"
        ),
        "source_stores_unchanged": source_unchanged,
        "cases": cases,
        "passed": passed,
        "terminal": (
            "FINANCIAL_GENERALIZATION_PRESERVED"
            if passed
            else "ARCHITECTURE_REGRESSION"
        ),
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
