#!/usr/bin/env python3
"""Replay frozen Gate 3 outputs through current factories without transport."""

from __future__ import annotations

import argparse
import asyncio
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3ChunkBatchLabelingFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    Gate4FinancialCaseRuntimeFactory,
)


DOCUMENT_ID = "brdoc_001_7cfd297786cc"
NORMALIZATION_RUN_ID = "normrun_1f4f2d9e30c1a076"
CANONICAL_VERSION_ID = "canver_lvs64r6lTXf56n30XPIfbV0FRxwVW1lE"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"
INCIDENT_ORDINALS = (10, 12, 42, 44, 76)


class FrozenReplayClient:
    """Return one exact frozen response after proving request parity."""

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self._attempts = attempts
        self.responses_consumed = 0

    async def label_gate3_once(
        self,
        *,
        model_visible_request: dict[str, Any],
        canonical_schema: dict[str, Any],
        model_id: str,
    ) -> Any:
        del canonical_schema
        if self.responses_consumed >= len(self._attempts):
            raise RuntimeError("frozen_response_inventory_exhausted")
        frozen = self._attempts[self.responses_consumed]
        self.responses_consumed += 1
        if (
            model_id != MODEL_ID
            or model_visible_request != frozen["model_visible_request"]
            or frozen["final_provider_request"].get("model") != MODEL_ID
        ):
            raise RuntimeError("frozen_model_request_parity_failed")
        return SimpleNamespace(
            prepared_request=SimpleNamespace(
                form_data=copy.deepcopy(frozen["final_provider_request"])
            ),
            adapter_extracted_output=copy.deepcopy(frozen["raw_model_output"]),
            raw_provider_response=copy.deepcopy(frozen["raw_provider_response"]),
            execution_metadata=SimpleNamespace(**frozen["execution_metadata"]),
        )

    def assert_complete(self) -> None:
        if self.responses_consumed != len(self._attempts):
            raise RuntimeError("frozen_response_inventory_not_consumed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-frozen-replay", action="store_true")
    parser.add_argument("--frozen-batch", type=Path, required=True)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute_frozen_replay:
        raise SystemExit("explicit_frozen_replay_flag_required")
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    frozen_path = args.frozen_batch.resolve()
    store_root = args.store_root.resolve()
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    outcomes = list(frozen.get("outcomes") or [])
    if (
        frozen.get("document_status") != "incomplete"
        or len(outcomes) != 140
        or [int(item["chunk"]["ordinal"]) for item in outcomes]
        != list(range(1, 141))
        or not (store_root / "artifacts.sqlite3").is_file()
    ):
        raise SystemExit("frozen_baseline_shape_invalid")

    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g540e-private-user",
        case_id="g540e-real-source-contract",
        chat_id=None,
        workspace_model_id="g540e-private-model",
        normalization_run_id=NORMALIZATION_RUN_ID,
        allow_private=True,
    )

    exact_five = _replay(
        store=store,
        context=context,
        frozen_outcomes=outcomes,
        ordinals=INCIDENT_ORDINALS,
    )
    full = _replay(
        store=store,
        context=context,
        frozen_outcomes=outcomes,
        ordinals=None,
    )
    if (
        exact_five["result"].metrics["role_bindings_rejected"] != 33
        or exact_five["result"].metrics[
            "facts_incomplete_due_to_role_rejection"
        ]
        != 18
        or exact_five["result"].metrics["chunks_with_local_failures"] != 5
        or full["result"].metrics["chunks_total"] != 140
        or full["result"].metrics["chunks_rejected"] != 0
        or full["result"].metrics["chunks_provider_failed"] != 0
        or full["result"].document_status != "complete"
        or full["result"].merged_output is None
    ):
        raise SystemExit("g583_expected_failure_localization_not_proven")

    document_result = _document_result(full["result"])
    sidecar = Gate3FinancialAnnotationsPersistenceFactory(
        store=store,
        read_enabled=True,
    ).create().save(
        document_id=DOCUMENT_ID,
        context=context,
        validated_document_result=document_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    gate4 = Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True).create()
    assembly = gate4.rebuild_case(context=context)
    facts = list(assembly.facts)
    fact_statuses = Counter(item["status"] for item in facts)
    fact_types = Counter(item["financial_type"] for item in facts)

    private = {
        "schema_version": "broker_reports_g583_deterministic_replay_private_v1",
        "goal": "G5.83",
        "frozen_batch_sha256": _sha256(frozen_path),
        "canonical_version_id": CANONICAL_VERSION_ID,
        "exact_five": _private_summary(exact_five["result"]),
        "full_batch": _private_summary(full["result"]),
        "sidecar_artifact_id": sidecar.artifact_id,
        "gate4": {
            "status": assembly.status,
            "gate3_case_status": assembly.gate3_case_status,
            "sources_total": len(assembly.sources),
            "facts_total": len(facts),
            "fact_status_counts": dict(sorted(fact_statuses.items())),
            "financial_type_counts": dict(sorted(fact_types.items())),
        },
        "provider_calls": 0,
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "manual_facts": 0,
        "production_visual_dependency": False,
    }
    _write_json(args.private_output.resolve(), private)
    safe = {
        "schema_version": "broker_reports_g583_deterministic_replay_safe_v1",
        "goal": "G5.83",
        "terminal": "MINIMAL_FAIL_CLOSED_UNIT_PROVEN",
        "canonical_version_id": CANONICAL_VERSION_ID,
        "frozen_batch_sha256": private["frozen_batch_sha256"],
        "exact_five": _safe_summary(exact_five),
        "full_batch": _safe_summary(full),
        "sidecar_persisted": True,
        "gate4_status": assembly.status,
        "gate4_gate3_case_status": assembly.gate3_case_status,
        "gate4_sources_total": len(assembly.sources),
        "gate4_facts_total": len(facts),
        "gate4_fact_status_counts": dict(sorted(fact_statuses.items())),
        "provider_calls": 0,
        "retry_count": 0,
        "repair_count": 0,
        "fallback_count": 0,
        "manual_facts": 0,
        "invented_relations": 0,
        "production_visual_dependency": False,
        "private_result_sha256": hashlib.sha256(
            json.dumps(
                private,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    _write_json(args.safe_output.resolve(), safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0


def _replay(
    *,
    store: Any,
    context: ArtifactAccessContext,
    frozen_outcomes: list[dict[str, Any]],
    ordinals: tuple[int, ...] | None,
) -> dict[str, Any]:
    wanted = set(ordinals or range(1, 141))
    attempts: list[dict[str, Any]] = []
    for outcome in frozen_outcomes:
        if int(outcome["chunk"]["ordinal"]) not in wanted:
            continue
        attempts.append(outcome["pass1_attempt"])
        role_attempt = outcome.get("role_attempt")
        if role_attempt and role_attempt.get("model_visible_request") is not None:
            attempts.append(role_attempt)
    client = FrozenReplayClient(attempts)
    result = asyncio.run(
        Gate3ChunkBatchLabelingFactory(
            store=store,
            read_enabled=True,
            model_client=client,
            model_id=MODEL_ID,
        ).create(
            document_id=DOCUMENT_ID,
            context=context,
            chunk_ordinals=ordinals,
        )
    )
    client.assert_complete()
    return {"result": result, "responses_consumed": client.responses_consumed}


def _private_summary(result: Any) -> dict[str, Any]:
    return {
        "document_status": result.document_status,
        "selection_mode": result.selection_mode,
        "metrics": copy.deepcopy(result.metrics),
        "local_rejections": [
            {
                "chunk_ordinal": int(outcome.chunk["ordinal"]),
                "rejected_role_bindings": copy.deepcopy(
                    list(outcome.role_attempt.rejected_role_bindings)
                ),
            }
            for outcome in result.outcomes
            if outcome.role_attempt is not None
            and outcome.role_attempt.rejected_role_bindings
        ],
    }


def _safe_summary(replay: dict[str, Any]) -> dict[str, Any]:
    result = replay["result"]
    metrics = result.metrics
    return {
        "document_status": result.document_status,
        "chunks_total": metrics["chunks_total"],
        "chunks_validated": metrics["chunks_validated"],
        "chunks_with_local_failures": metrics["chunks_with_local_failures"],
        "fully_unusable_chunks": metrics["fully_unusable_chunks"],
        "annotations_validated": metrics["annotations_validated"],
        "facts_role_complete": metrics["facts_role_complete"],
        "facts_role_incomplete": metrics["facts_role_incomplete"],
        "facts_incomplete_due_to_role_rejection": metrics[
            "facts_incomplete_due_to_role_rejection"
        ],
        "facts_rejected": metrics["facts_rejected"],
        "role_bindings_rejected": metrics["role_bindings_rejected"],
        "source_fact_completeness_status": metrics[
            "source_fact_completeness_status"
        ],
        "frozen_responses_consumed": replay["responses_consumed"],
        "provider_calls": 0,
    }


def _document_result(result: Any) -> dict[str, Any]:
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": copy.deepcopy(result.semantic_scope),
        "selected_chunk_ordinals": list(result.selected_chunk_ordinals),
        "selection_mode": result.selection_mode,
        "document_status": result.document_status,
        "metrics": copy.deepcopy(result.metrics),
        "merged_output": copy.deepcopy(result.merged_output),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
