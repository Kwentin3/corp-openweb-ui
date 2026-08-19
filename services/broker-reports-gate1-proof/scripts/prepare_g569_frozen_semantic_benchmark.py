#!/usr/bin/env python3
"""Freeze the two G5.69 cases and comparison model before semantic calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
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
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.canonical_store import CanonicalReaderFactory  # noqa: E402
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_LLM_METADATA_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    build_metadata_context_package,
    compose_metadata_model_visible_request,
    metadata_proposal_response_schema,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
)
from live_gate2_economy_contract_qualification import _published_model_ids  # noqa: E402
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _base_url,
    _is_within,
    _read_env,
    _signin,
    _url,
)


CASE_SELECTION = (
    ("case_f", "holdout_a", "KNOWN_CLIENT_CODE_ACCOUNT_FAILURE"),
    ("case_c", "pdf_002", "CLEAN_G568_CONTROL"),
)
FLASH = ("google_gemini", "models/gemini-3.5-flash")
COMPARISON = ("anthropic_claude", "claude-opus-5")

FACTORY_REQUIRED = (
    "build_metadata_context_package, Gate2OpenWebUIRequestBuilder and "
    "Gate2ProviderAdapterFactory are the only freeze/preflight route"
)
FORBIDDEN = (
    "semantic provider calls, prompt/schema/context changes, model-result "
    "inspection, source mutation, product activation or comparison-model search"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-frozen", type=Path, required=True)
    parser.add_argument("--development-oracle", type=Path, required=True)
    parser.add_argument("--g568-replay", type=Path, required=True)
    parser.add_argument("--g568-qualification", type=Path, required=True)
    parser.add_argument("--g568-goal-freeze", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    args = parser.parse_args()
    outputs = (args.private_output.resolve(), args.safe_output.resolve())
    if any(_is_within(output, REPO_ROOT.resolve()) for output in outputs):
        raise SystemExit("g569_freeze_output_inside_repository")
    if any(output.exists() for output in outputs):
        raise SystemExit("g569_freeze_output_must_be_new")

    frozen = _read_json(args.development_frozen.resolve())
    oracle = _read_json(args.development_oracle.resolve())
    replay = _read_json(args.g568_replay.resolve())
    qualification = _read_json(args.g568_qualification.resolve())
    goal_freeze = _read_json(args.g568_goal_freeze.resolve())
    _validate_inputs(frozen, oracle, replay, qualification, goal_freeze)

    env = _read_env(args.env_file.resolve())
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if not str(_current_user(session, base_url).get("id") or ""):
        raise SystemExit("g569_authenticated_user_missing")
    published = sorted(_published_model_ids(session, base_url))
    for _profile_id, model_id in (FLASH, COMPARISON):
        if model_id not in published:
            raise SystemExit(f"g569_frozen_model_not_published:{model_id}")

    frozen_by_alias = {case["alias"]: case for case in frozen["cases"]}
    replay_by_alias = {case["alias"]: case for case in replay["cases"]}
    oracle_by_alias = {case["alias"]: case for case in oracle["cases"]}
    qualified_by_alias = {case["alias"]: case for case in qualification["cases"]}
    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    for case_id, alias, role in CASE_SELECTION:
        frozen_case = frozen_by_alias[alias]
        artifact = _read_canonical(frozen_case)
        package, registry = build_metadata_context_package(
            artifact=artifact,
            document_id=frozen_case["document_id"],
            canonical_version_id=artifact["artifact_id"],
        )
        request = compose_metadata_model_visible_request(
            context_package=package,
            response_schema=metadata_proposal_response_schema(),
        )
        request_hash = _sha256_json(request)
        historical_hash = _sha256_json(replay_by_alias[alias]["model_visible_request"])
        if request_hash != historical_hash:
            raise SystemExit(f"g569_g568_model_visible_request_changed:{alias}")
        model_preflights = [
            _model_preflight(
                profile_id=profile_id,
                model_id=model_id,
                model_visible_request=request,
            )
            for profile_id, model_id in (FLASH, COMPARISON)
        ]
        if len({item["canonical_schema_sha256"] for item in model_preflights}) != 1:
            raise SystemExit("g569_canonical_schema_not_comparable")
        if len({item["provider_visible_schema_sha256"] for item in model_preflights}) != 1:
            raise SystemExit("g569_provider_visible_schema_not_comparable")
        private_cases.append(
            {
                "case_id": case_id,
                "alias": alias,
                "benchmark_role": role,
                "source_store_root": frozen_case["source_store_root"],
                "context": frozen_case["context"],
                "document_id": frozen_case["document_id"],
                "canonical_version_id": frozen_case["canonical_version_id"],
                "canonical_root_sha256": frozen_case["canonical_root_sha256"],
                "source_sha256": frozen_case["source_sha256"],
                "oracle_facts": oracle_by_alias[alias]["facts"],
                "oracle_fact_count": len(oracle_by_alias[alias]["facts"]),
                "model_visible_request_sha256": request_hash,
                "historical_g568_request_sha256": historical_hash,
                "historical_request_exact": True,
                "context_package_sha256": _sha256_json(package),
                "binding_registry_sha256": _sha256_json(registry),
                "selected_targets": package["metrics"]["selected_targets"],
                "rendered_context_chars": package["metrics"]["rendered_context_chars"],
                "g568_semantic_exact": qualified_by_alias[alias]["semantic_exact"],
                "g568_role_value_structural_failures": qualified_by_alias[alias][
                    "role_value_structural_failures"
                ],
                "model_preflights": model_preflights,
            }
        )
        safe_cases.append(
            {
                "case_id": case_id,
                "alias": alias,
                "benchmark_role": role,
                "oracle_fact_count": len(oracle_by_alias[alias]["facts"]),
                "model_visible_request_sha256": request_hash,
                "historical_g568_request_sha256": historical_hash,
                "historical_request_exact": True,
                "selected_targets": package["metrics"]["selected_targets"],
                "rendered_context_chars": package["metrics"]["rendered_context_chars"],
                "g568_semantic_exact": qualified_by_alias[alias]["semantic_exact"],
                "g568_role_value_structural_failures": qualified_by_alias[alias][
                    "role_value_structural_failures"
                ],
            }
        )

    comparison_preflight = private_cases[0]["model_preflights"][1]
    private = {
        "schema_version": "broker_reports_g569_benchmark_freeze_private_v1",
        "goal": "G5.69",
        "frozen_before_semantic_calls": True,
        "semantic_provider_calls": 0,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "instruction_sha256": hashlib.sha256(
            GATE3_LLM_METADATA_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "proposal_schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
        "proposal_schema_sha256": _sha256_json(metadata_proposal_response_schema()),
        "runs_per_case_per_model": 5,
        "flash": {"provider_profile": FLASH[0], "model_id": FLASH[1]},
        "comparison": {
            "provider_profile": COMPARISON[0],
            "model_id": COMPARISON[1],
            "selection": "already_connected_stronger_general_model",
            "selected_before_first_comparison_result": True,
            "selected_before_any_g569_semantic_result": True,
            "canonical_schema_sha256": comparison_preflight[
                "canonical_schema_sha256"
            ],
            "provider_visible_schema_sha256": comparison_preflight[
                "provider_visible_schema_sha256"
            ],
        },
        "published_model_ids_sha256": _sha256_json(published),
        "published_model_ids": published,
        "cases": private_cases,
        "historical_g568_result_counted_in_five": False,
        "temperature_override": None,
        "seed_override": None,
        "best_of_models": False,
        "production_code_changes": 0,
        "source_inputs": {
            "development_frozen_sha256": _sha256_file(args.development_frozen),
            "development_oracle_sha256": _sha256_file(args.development_oracle),
            "g568_replay_sha256": _sha256_file(args.g568_replay),
            "g568_qualification_sha256": _sha256_file(args.g568_qualification),
            "g568_goal_freeze_sha256": _sha256_file(args.g568_goal_freeze),
        },
    }
    safe = {
        "schema_version": "broker_reports_g569_benchmark_freeze_safe_v1",
        "goal": "G5.69",
        "terminal": "FROZEN_BENCHMARK_READY",
        "frozen_before_semantic_calls": True,
        "semantic_provider_calls": 0,
        "contract_version": private["contract_version"],
        "instruction_version": private["instruction_version"],
        "instruction_sha256": private["instruction_sha256"],
        "context_policy_version": private["context_policy_version"],
        "proposal_schema_version": private["proposal_schema_version"],
        "proposal_schema_sha256": private["proposal_schema_sha256"],
        "runs_per_case_per_model": 5,
        "flash": private["flash"],
        "comparison": private["comparison"],
        "published_model_ids_sha256": private["published_model_ids_sha256"],
        "cases": safe_cases,
        "historical_g568_result_counted_in_five": False,
        "temperature_override": None,
        "seed_override": None,
        "best_of_models": False,
        "production_code_changes": 0,
        "private_values_committed": False,
    }
    for output, value in zip(outputs, (private, safe), strict=True):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _model_preflight(
    *,
    profile_id: str,
    model_id: str,
    model_visible_request: dict[str, Any],
) -> dict[str, Any]:
    response_format = model_visible_request["response_format"]
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE
    ).build_from_sealed_gate3_metadata(
        model_visible_request=model_visible_request,
        model_id=model_id,
    )
    prepared = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(profile_id)
    ).create().prepare_gate3_metadata_form_data(
        form_data=form_data,
        response_format=response_format,
    )
    return {
        "provider_profile": profile_id,
        "model_id": model_id,
        "canonical_schema_sha256": prepared.canonical_schema_hash,
        "provider_visible_schema_sha256": _sha256_json(
            prepared.provider_visible_schema
        ),
        "prepared_request_sha256": _sha256_json(prepared.form_data),
        "prepared_request_fields": sorted(prepared.form_data),
        "temperature_present": "temperature" in prepared.form_data,
        "seed_present": "seed" in prepared.form_data,
    }


def _read_canonical(frozen_case: dict[str, Any]) -> dict[str, Any]:
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
        raise SystemExit("g569_canonical_record_ambiguous")
    artifact = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read(records[0].artifact_id, context)
    )
    if (
        artifact.get("artifact_id") != frozen_case["canonical_version_id"]
        or artifact.get("canonical_root_hash")
        != frozen_case["canonical_root_sha256"]
    ):
        raise SystemExit("g569_frozen_canonical_changed")
    return artifact


def _validate_inputs(
    frozen: dict[str, Any],
    oracle: dict[str, Any],
    replay: dict[str, Any],
    qualification: dict[str, Any],
    goal_freeze: dict[str, Any],
) -> None:
    if (
        frozen.get("frozen_before_code") is not True
        or frozen.get("instruction_version") != "1.2.0"
        or oracle.get("source_truth_fact_count") != 24
        or replay.get("provider_submissions_total") != 4
        or qualification.get("goal") != "G5.68"
        or goal_freeze.get("goal") != "G5.68"
        or qualification.get("known_client_code_account_case", {}).get(
            "pure_llm_semantic_failure"
        )
        is not True
    ):
        raise SystemExit("g569_frozen_input_invalid")
    by_alias = {case["alias"]: case for case in qualification["cases"]}
    if (
        by_alias.get("pdf_002", {}).get("semantic_exact") is not True
        or by_alias.get("holdout_a", {}).get("wrong_roles") != 1
    ):
        raise SystemExit("g569_case_selection_basis_changed")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.resolve().read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("g569_json_object_required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
