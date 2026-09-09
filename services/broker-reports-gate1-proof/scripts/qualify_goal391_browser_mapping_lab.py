#!/usr/bin/env python3
"""Run the Goal #391 private lab through an existing ordinary-user browser session."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.gate2_model_clients import Gate2StructuredModelClientFactory
from broker_reports_gate1.gate2_model_contracts import Gate2SourceFactRuntimeError, Gate2StructuredModelClientConfig
from broker_reports_gate1.gate2_model_requests import Gate2OpenWebUIRequestBuilder, ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
from broker_reports_gate1.ordinary_trade_mapping_prompt import OrdinaryTradeMappingManagedPrompt, ordinary_trade_mapping_prompt_hash
from broker_reports_gate1.ordinary_trade_semantic_mapping import OrdinaryTradeSemanticMappingFactory
import qualify_goal391_current_mapping_lab as lab


class Bridge:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.last_error: str | None = None

    def call(self, payload: dict) -> dict:
        try:
            result = subprocess.run(
                ["node", str(self.path)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=125,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.last_error = "goal391_browser_bridge_timeout"
            raise BrowserBridgeError(self.last_error)
        if result.returncode != 0 or not result.stdout.strip():
            self.last_error = "goal391_browser_bridge_unavailable"
            raise RuntimeError("goal391_browser_bridge_unavailable")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.last_error = "goal391_browser_bridge_invalid_response"
            raise BrowserBridgeError(self.last_error) from exc
        if response.get("ok") is not True:
            self.last_error = response.get("code") or "goal391_browser_bridge_failed"
            raise BrowserBridgeError(self.last_error)
        return response["value"]

    def close(self) -> None:
        return None


class BrowserBridgeError(RuntimeError):
    @property
    def code(self) -> str:
        return str(self)


def _prompt(value: dict, *, command: str, version: str, prompt_hash: str) -> OrdinaryTradeMappingManagedPrompt:
    row, history = value["prompt"], value["history"]
    snapshot = history.get("snapshot") or {}
    if history.get("prompt_id") != row.get("id") or history.get("id") != row.get("version_id") or any(snapshot.get(key) != row.get(key) for key in ("command", "content", "meta", "tags")):
        raise RuntimeError("goal391_browser_prompt_history_drift")
    meta = row.get("meta") or {}
    content = row.get("content")
    actual_hash = ordinary_trade_mapping_prompt_hash(content)
    if row.get("command") != command or row.get("version_id") != version or actual_hash != prompt_hash:
        raise RuntimeError(f"goal391_browser_prompt_release_pin_mismatch:{actual_hash}")
    return OrdinaryTradeMappingManagedPrompt(prompt_ref=row["id"], command=row["command"], version=row["version_id"], content=content, hash=prompt_hash, source="openwebui_prompt_history", template_id=meta["template_id"], template_kind=meta["template_kind"], prompt_contract_id=meta["prompt_contract_id"], input_schema_version=meta["input_contract"], output_schema_id=meta["output_schema_id"], output_schema_version=meta["output_schema_version"], tags=tuple(row["tags"]), safe_metadata={"name": row.get("name") or row["command"], "mapping_domain": meta.get("mapping_domain") or "ordinary_trade"})


async def run(args, bridge: Bridge, prompt, cases, semantic):
    auth = bridge.call({"op": "preflight", "prompt_id": args.prompt_id})["auth"]
    user = SimpleNamespace(id=auth["id"])
    before = bridge.call({"op": "chat_count"})["chat_count"]
    submissions = {"count": 0}
    def complete(*, request, form_data, user, **_ignored):
        submissions["count"] += 1
        try:
            return bridge.call({"op": "complete", "form_data": form_data})["body"]
        except BrowserBridgeError as exc:
            raise Gate2SourceFactRuntimeError(exc.code, "Browser completion boundary failed") from exc
    client = Gate2StructuredModelClientFactory(config=Gate2StructuredModelClientConfig(request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE, provider_profile_id=lab.PROVIDER_PROFILE_ID, capability_probe=False, economy_budget_enforcement=False), user=user, request=SimpleNamespace(), completion_resolver=lambda _id: (complete, user)).create()
    records, error = await lab._run_all_cases(semantic=semantic, prompt=prompt, client=client, cases=cases, submissions=submissions, progress=lambda *_: None)
    error = bridge.last_error or error
    after = bridge.call({"op": "chat_count"})["chat_count"]
    lifecycle = client.qualification_lifecycle_snapshot()
    receipt = {"schema_version": lab.SAFE_RECEIPT_SCHEMA_VERSION, "status": "PASSED" if error is None and len(records) == len(cases) and all(r["outcome"] != "FAIL" for r in records) and before == after and submissions["count"] == len(cases) and lifecycle["provider_submissions_total"] == len(cases) and lifecycle["provider_responses_total"] == len(cases) else "FAILED", "candidate": lab._current_candidate(semantic=semantic, prompt=prompt, expected_git_head=args.expected_git_head), "corpus": {"cases_total": len(cases), "provider_calls_started_total": lifecycle["provider_submissions_total"], "provider_calls_returned_total": lifecycle["provider_responses_total"], "records": records}, "constraints": {"retries": 0, "best_of_n": False, "manual_output_repair": False, "chat_persistence": "forbidden", "chat_count_unchanged": before == after, "artifact_store_mutation": False, "canonical_mutation": False}, "terminal_error": error}
    lab._write_json(args.safe_receipt, receipt)
    print(json.dumps(lab._public_summary(receipt), sort_keys=True))
    return 0 if receipt["status"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("corpus_root", "expectations", "safe_receipt"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--expected-git-head", required=True); parser.add_argument("--prompt-id", required=True); parser.add_argument("--prompt-command", required=True); parser.add_argument("--prompt-version", required=True); parser.add_argument("--prompt-hash", required=True)
    args = parser.parse_args()
    bridge = Bridge(SCRIPT_DIR / "goal391_browser_session_bridge.mjs")
    try:
        preflight = bridge.call({"op": "preflight", "prompt_id": args.prompt_id})
        prompt = _prompt(preflight, command=args.prompt_command, version=args.prompt_version, prompt_hash=args.prompt_hash)
        semantic = OrdinaryTradeSemanticMappingFactory.create()
        cases = lab._preflight(corpus_root=args.corpus_root, expectation_path=args.expectations, candidate=lab._current_candidate(semantic=semantic, prompt=prompt, expected_git_head=args.expected_git_head))
        if args.preflight_only:
            package = semantic.build_mapping_package(canonical=cases[0]["canonical"], confirmed_understandings=cases[0]["confirmed_understandings"], target_table_node_ids=cases[0]["target_table_node_ids"])
            form_data = Gate2OpenWebUIRequestBuilder(request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE).build(prompt=prompt, package=package, model_id=lab.MODEL_ID, response_format=semantic.mapping_response_format())
            request_bytes = len(json.dumps(form_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            lab._write_json(args.safe_receipt, {"schema_version": lab.SAFE_RECEIPT_SCHEMA_VERSION, "status": "PREFLIGHT_PASSED", "cases_total": len(cases), "provider_calls": 0, "chat_persistence": "forbidden", "first_request_utf8_bytes": request_bytes})
            print(json.dumps({"status": "PREFLIGHT_PASSED", "cases_total": len(cases), "provider_calls": 0, "first_request_utf8_bytes": request_bytes}, sort_keys=True))
            return 0
        return asyncio.run(run(args, bridge, prompt, cases, semantic))
    finally: bridge.close()

if __name__ == "__main__": raise SystemExit(main())
