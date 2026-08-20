#!/usr/bin/env python3
"""Qualify current Gate 3 on one frozen Canonical and fixed runtime settings."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate3ChunkBatchLabelingFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_LABELING_INSTRUCTION,
)
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
    ndfl_product_binding_snapshot,
)
from broker_reports_gate1.gate3_role_labeling import (  # noqa: E402
    GATE3_ROLE_LABELING_INSTRUCTION,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate5_real_source_fact_contract import (  # noqa: E402
    _atomic_write,
    _base_url,
    _json_bytes,
    _private_result,
    _read_env,
    _signin,
    _url,
)


FROZEN_CANONICAL_ROOT_SHA256 = (
    "bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d"
)
EXPECTED_CHUNKS = 1
EXPECTED_TARGETS = 2236
RUNS = 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-three-frozen-runs", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--private-store-root", required=True)
    parser.add_argument("--private-results-dir", required=True)
    parser.add_argument("--safe-receipt-path", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.execute_three_frozen_runs:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")

    store_root = Path(args.private_store_root).resolve()
    private_results = Path(args.private_results_dir).resolve()
    safe_path = Path(args.safe_receipt_path).resolve()
    if REPO_ROOT.resolve() in private_results.parents:
        raise SystemExit("private_results_must_be_outside_repository")
    if REPO_ROOT.resolve() not in safe_path.parents:
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("private_store_unavailable")
    if private_results.exists() and any(private_results.iterdir()):
        raise SystemExit("private_results_must_be_empty")
    private_results.mkdir(parents=True, exist_ok=True)

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_id, context, canonical_version_id = _frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    coverage = chunk_set["coverage"]
    if (
        chunk_set["canonical_binding"]["canonical_version_id"]
        != canonical_version_id
        or len(chunk_set["chunks"]) != EXPECTED_CHUNKS
        or coverage["eligible_targets"] != EXPECTED_TARGETS
        or coverage["lost_targets"] != 0
        or coverage["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if NDFL_PROVIDER_MODEL_ID not in _published_model_ids(session, base_url):
        raise SystemExit("current_model_not_published")
    if NDFL_PROVIDER_MODEL_ID not in gate2_provider_profile(
        NDFL_PROVIDER_PROFILE_ID
    ).approved_model_ids:
        raise SystemExit("current_model_not_approved")
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )
    submissions = 0

    def counted_completion(*, form_data, **kwargs):
        nonlocal submissions
        submissions += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=NDFL_PROVIDER_PROFILE_ID,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            counted_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()

    safe_runs: list[dict[str, Any]] = []
    for ordinal in range(1, RUNS + 1):
        before = submissions
        result = asyncio.run(
            Gate3ChunkBatchLabelingFactory(
                store=store,
                read_enabled=True,
                model_client=client,
                model_id=NDFL_PROVIDER_MODEL_ID,
            ).create(document_id=document_id, context=context)
        )
        private = _private_result(result)
        private_raw = _json_bytes(private)
        _atomic_write(
            private_results / f"run-{ordinal}.private.json",
            private_raw,
        )
        safe_runs.append(
            _safe_run(
                ordinal=ordinal,
                result=result,
                provider_submissions=submissions - before,
                private_sha256=_sha256(private_raw),
            )
        )

    semantic_hashes = [item["semantic_output_sha256"] for item in safe_runs]
    exact = len(set(semantic_hashes)) == 1
    receipt = {
        "schema_version": "broker_reports_current_gate3_repeatability_v1",
        "status": (
            "CURRENT_GATE3_EXACTLY_REPEATABLE_ON_FROZEN_CANONICAL"
            if exact
            else "CURRENT_GATE3_VARIANCE_OBSERVED_ON_FROZEN_CANONICAL"
        ),
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "frozen_canonical_version_sha256": _sha256(
            canonical_version_id.encode("utf-8")
        ),
        "chunks": EXPECTED_CHUNKS,
        "eligible_targets": EXPECTED_TARGETS,
        "product_binding": ndfl_product_binding_snapshot(),
        "pass1_instruction_sha256": _sha256(
            GATE3_LABELING_INSTRUCTION.encode("utf-8")
        ),
        "role_instruction_sha256": _sha256(
            GATE3_ROLE_LABELING_INSTRUCTION.encode("utf-8")
        ),
        "runs": safe_runs,
        "exact_semantic_repeatability": exact,
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "best_of_n_selection": False,
        "manual_fact_changes": 0,
        "provider_submissions": submissions,
    }
    _atomic_write(safe_path, _json_bytes(receipt))
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "annotations": [
                    item["annotations_validated"] for item in safe_runs
                ],
                "role_statuses": [
                    item["role_binding_status_counts"] for item in safe_runs
                ],
                "provider_submissions": submissions,
            },
            sort_keys=True,
        )
    )
    return 0 if exact else 2


def _frozen_context(
    store_root: Path,
) -> tuple[str, ArtifactAccessContext, str]:
    connection = sqlite3.connect(store_root / "artifacts.sqlite3")
    row = connection.execute(
        """
        SELECT user_id, case_id, chat_id, workspace_model_id,
               normalization_run_id, document_id, canonical_version_id
        FROM canonical_versions
        WHERE status = 'ACTIVE' AND canonical_root_sha256 = ?
        """,
        (FROZEN_CANONICAL_ROOT_SHA256,),
    ).fetchall()
    connection.close()
    if len(row) != 1:
        raise SystemExit("frozen_canonical_identity_not_unique")
    value = row[0]
    return (
        value[5],
        ArtifactAccessContext(
            user_id=value[0],
            case_id=value[1],
            chat_id=value[2],
            workspace_model_id=value[3],
            normalization_run_id=value[4],
            allow_private=True,
        ),
        value[6],
    )


def _safe_run(
    *, ordinal: int, result: Any, provider_submissions: int, private_sha256: str
) -> dict[str, Any]:
    labels: Counter[str] = Counter()
    role_statuses: Counter[str] = Counter()
    annotations: list[dict[str, Any]] = []
    for outcome in result.outcomes:
        output = (
            outcome.role_attempt.validated_output
            if outcome.role_attempt is not None
            else None
        )
        for annotation in (output or {}).get("annotations", []):
            labels[annotation["financial_label"]] += 1
            role_statuses.update(
                role["status"] for role in annotation.get("roles", [])
            )
            annotations.append(annotation)
    semantic_raw = json.dumps(
        annotations,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "ordinal": ordinal,
        "document_status": result.document_status,
        "chunks_validated": result.metrics["chunks_validated"],
        "chunks_rejected": result.metrics["chunks_rejected"],
        "chunks_provider_failed": result.metrics["chunks_provider_failed"],
        "annotations_validated": result.metrics["annotations_validated"],
        "financial_type_counts": dict(sorted(labels.items())),
        "role_binding_status_counts": dict(sorted(role_statuses.items())),
        "semantic_output_sha256": _sha256(semantic_raw),
        "private_result_sha256": private_sha256,
        "provider_submissions": provider_submissions,
    }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
